"""Orchestration bridge connecting queryDatabase connection/catalog with sql_object_summary."""

from __future__ import annotations

import collections
import re
import threading
import time
from datetime import datetime
from typing import Any, Literal, Optional

from queryDatabase.connection import get_connection_config
from queryDatabase.query_resolver import sanitize_sql_identifier
from queryDatabase.object_catalog.fetcher import ObjectCatalogFetcher
from queryDatabase.object_catalog.models import DbObjectMeta

from sql_object_summary import (
    analyze_definition,
    extract_snippet,
    build_call_graph,
    result_to_dict,
    AnalyzeOptions,
)
from sql_object_summary.classifier import classify_object
from sql_object_summary.models import SummaryResult, SnippetResult, Meta, CallGraph, CallGraphNode
from sql_object_summary.options import DEFAULT_EXCLUDE_LIKE


# -----------------------------------------------------------------------------
# Thread-safe LRU Cache
# -----------------------------------------------------------------------------

_CACHE_LOCK = threading.Lock()
_CACHE_MAX_ENTRIES = 200
_CACHE_TTL_SECONDS = 3600

# Key: tuple of parameters -> (timestamp, dict)
_SUMMARY_CACHE: collections.OrderedDict[tuple[Any, ...], tuple[float, dict[str, Any]]] = collections.OrderedDict()


def _make_cache_key(
    server: str,
    database: str,
    object_id: int,
    modify_date: Any,
    mode: str,
    max_depth: int,
    max_objects: int = 30,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    include_called_by: bool = False,
    max_snippet_lines: int = 120,
    max_full_chars: int = 50000,
) -> tuple[Any, ...]:
    mod_str = str(modify_date) if modify_date else ""
    return (
        server,
        database,
        object_id,
        mod_str,
        mode,
        max_depth,
        max_objects,
        tuple(sorted(keywords or [])),
        tuple(sorted(zones or [])),
        tuple(sorted(expand or [])),
        tuple(sorted(exclude_like or [])) if exclude_like is not None else None,
        include_called_by,
        max_snippet_lines,
        max_full_chars,
    )


def _get_from_cache(
    server: str,
    database: str,
    object_id: int,
    modify_date: Any,
    mode: str,
    max_depth: int,
    max_objects: int = 30,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    include_called_by: bool = False,
    max_snippet_lines: int = 120,
    max_full_chars: int = 50000,
) -> dict[str, Any] | None:
    key = _make_cache_key(
        server,
        database,
        object_id,
        modify_date,
        mode,
        max_depth,
        max_objects=max_objects,
        keywords=keywords,
        zones=zones,
        expand=expand,
        exclude_like=exclude_like,
        include_called_by=include_called_by,
        max_snippet_lines=max_snippet_lines,
        max_full_chars=max_full_chars,
    )
    now = time.time()

    with _CACHE_LOCK:
        if key in _SUMMARY_CACHE:
            ts, data = _SUMMARY_CACHE[key]
            if now - ts <= _CACHE_TTL_SECONDS:
                _SUMMARY_CACHE.move_to_end(key)
                cached = dict(data)
                if "meta" in cached:
                    cached["meta"] = dict(cached["meta"])
                    cached["meta"]["cache_hit"] = True
                return cached
            else:
                del _SUMMARY_CACHE[key]
    return None


def _set_to_cache(
    server: str,
    database: str,
    object_id: int,
    modify_date: Any,
    mode: str,
    max_depth: int,
    result: dict[str, Any],
    max_objects: int = 30,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    include_called_by: bool = False,
    max_snippet_lines: int = 120,
    max_full_chars: int = 50000,
) -> None:
    key = _make_cache_key(
        server,
        database,
        object_id,
        modify_date,
        mode,
        max_depth,
        max_objects=max_objects,
        keywords=keywords,
        zones=zones,
        expand=expand,
        exclude_like=exclude_like,
        include_called_by=include_called_by,
        max_snippet_lines=max_snippet_lines,
        max_full_chars=max_full_chars,
    )
    now = time.time()

    with _CACHE_LOCK:
        if key in _SUMMARY_CACHE:
            _SUMMARY_CACHE.move_to_end(key)
        _SUMMARY_CACHE[key] = (now, result)
        if len(_SUMMARY_CACHE) > _CACHE_MAX_ENTRIES:
            _SUMMARY_CACHE.popitem(last=False)


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _format_modify_date(val: Any) -> str | None:
    """Format modify_date which may be datetime object, ISO str, or None."""
    if not val:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def resolve_object_ref(object_name: str, schema: str = "dbo") -> tuple[str, str]:
    """Resolve schema and object name, supporting 'dbo.zc_bcthlv', '[dbo].[zc_bcthlv]', etc."""
    cleaned = object_name.strip()
    if "." in cleaned:
        parts = [p.strip().strip("[]\"") for p in cleaned.split(".")]
        if len(parts) == 2:
            return sanitize_sql_identifier(parts[0]), sanitize_sql_identifier(parts[1])
        elif len(parts) > 2:
            return sanitize_sql_identifier(parts[0]), sanitize_sql_identifier(".".join(parts[1:]))
        cleaned = parts[0]
    else:
        cleaned = cleaned.strip("[]\"")
    return sanitize_sql_identifier(schema.strip().strip("[]\"")), sanitize_sql_identifier(cleaned)


def map_object_type(sys_type: str) -> str:
    """Map SQL Server sys.objects.type to standard enum string."""
    t = sys_type.strip().upper()
    if t == "P":
        return "PROCEDURE"
    if t in ("FN", "IF", "TF"):
        return "FUNCTION"
    if t == "V":
        return "VIEW"
    return "UNSUPPORTED"


def _extract_shallow_calls(sql_text: str) -> list[str]:
    """Fast regex extraction of EXEC calls for call graph recursion."""
    calls: list[str] = []
    exec_matches = re.findall(r"\bEXEC(?:UTE)?\s+(?:dbo\.)?([a-zA-Z0-9_$#]+)", sql_text, re.IGNORECASE)
    for m in exec_matches:
        if not m.startswith("@") and not m.startswith("#"):
            full_call = f"dbo.{m}" if "." not in m else m
            if full_call not in calls:
                calls.append(full_call)
    return calls


# -----------------------------------------------------------------------------
# Main summary_object function
# -----------------------------------------------------------------------------

def summary_object(
    *,
    file_path: str,
    object_name: str,
    mode: str = "summary",
    db_type: str = "app",
    schema: str = "dbo",
    max_depth: int = 1,
    max_objects: int = 30,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    include_called_by: bool = False,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    max_snippet_lines: int = 120,
    max_full_chars: int = 50000,
    use_cache: bool = True,
    fetcher_override: ObjectCatalogFetcher | None = None,
) -> dict[str, Any]:
    """
    Phân tích cú pháp và tóm tắt cấu trúc Stored Procedure / Function / View trên SQL Server.

    Args:
        -- BẮT BUỘC (2 tham số) --
        file_path: Đường dẫn tới file XML/SQL trong project FBO để tìm Web.config kết nối DB.
        object_name: Tên đối tượng SQL cần phân tích (vd: 'zc_bcthlv' hoặc 'dbo.zc_bcthlv').

        -- TÙY CHỌN CHUNG (Chế độ & Kết nối) --
        mode: 'summary' (tóm tắt cấu trúc AST), 'snippet' (lấy đoạn code theo từ khóa), 'full' (lấy toàn bộ source code).
        db_type: 'app' (database dữ liệu nghiệp vụ chính) hoặc 'sys' (database hệ thống).
        schema: Schema mặc định nếu object_name không có prefix (mặc định: 'dbo').

        -- TÙY CHỌN CALL GRAPH (Đồ thị quan hệ hàm gọi) --
        max_depth: Độ sâu đệ quy gọi các Stored Procedure con (0-3, mặc định: 1).
        max_objects: Giới hạn tổng số lượng Stored Procedure được fetch tối đa (mặc định: 30).
        expand: Danh sách Stored Procedure hạ tầng cần ép bung thêm 1 cấp (vd: ['FastBusiness$Balance$BContract']).
        exclude_like: Danh sách mẫu LIKE loại trừ khỏi đệ quy (mặc định loại trừ các hàm hạ tầng FastBusiness$%, ff_%, fsd_%).
        include_called_by: True nếu muốn truy vấn ngược các đối tượng nào đang gọi tới Procedure này.

        -- TÙY CHỌN CHẾ ĐỘ SNIPPET (mode='snippet') --
        keywords: Danh sách từ khóa để trích xuất đoạn code chứa nó (vd: ['tl_th', '@Status']).
        zones: Danh sách vùng cấu trúc cần trích xuất ('header', 'params', 'cursor', 'pivot', ...).
        max_snippet_lines: Giới hạn số dòng tối đa trả về cho snippet (mặc định: 120 dòng).

        -- TÙY CHỌN CHẾ ĐỘ FULL (mode='full') --
        max_full_chars: Giới hạn ký tự tối đa khi lấy toàn bộ code (mặc định: 50,000 ký tự).

        -- TÙY CHỌN HỆ THỐNG / TESTING --
        use_cache: Bật/tắt LRU cache trong bộ nhớ RAM theo modify_date (mặc định: True).
        fetcher_override: Mock catalog fetcher dùng riêng cho Unit Test (không dùng khi chạy thật).

    Returns:
        dict: Kết quả chuẩn hóa JSON chứa thông tin phân tích hoặc lỗi.
    """
    t_start = time.perf_counter()

    # 1. Resolve & Sanitize object name and schema
    safe_schema, safe_name = resolve_object_ref(object_name, schema)
    full_object_name = f"{safe_schema}.{safe_name}"

    # 2. Validate snippet mode early
    if mode == "snippet" and not (keywords or zones):
        return {
            "success": False,
            "error": "snippet_params_required",
            "message": "mode=snippet cần keywords hoặc zones",
        }

    # 3. Connection config
    parsed_conn = None
    server_name = "localhost"
    db_name = "database"
    project_root = ""

    if fetcher_override is None:
        conn_res = get_connection_config(file_path, db_type)
        if not conn_res.get("success"):
            return conn_res

        parsed_conn = conn_res.get("parsed")
        server_name = parsed_conn.get("server", "localhost") if parsed_conn else "localhost"
        db_name = parsed_conn.get("database", "database") if parsed_conn else "database"
        project_root = conn_res.get("project_root", "")
        fetcher = ObjectCatalogFetcher(parsed_conn, query_timeout=10)
    else:
        fetcher = fetcher_override

    t_conn_done = time.perf_counter()
    conn_ms = int((t_conn_done - t_start) * 1000)

    # 4. Fetch root object from SQL catalog
    meta = fetcher.fetch_one(safe_name, safe_schema)
    t_fetch_root_done = time.perf_counter()
    fetch_root_ms = int((t_fetch_root_done - t_conn_done) * 1000)

    if not meta:
        return {
            "success": False,
            "error": "object_not_found",
            "message": f"Không tìm thấy {full_object_name} trong sys.objects",
        }

    # 5. Check object type
    obj_type = map_object_type(meta.sys_type)
    if obj_type == "UNSUPPORTED":
        return {
            "success": False,
            "error": "unsupported_type",
            "message": f"Object type '{meta.sys_type}' ({meta.type_desc}) không được hỗ trợ bởi summary_object (chỉ hỗ trợ P, FN, IF, TF, V)",
        }

    # 6. Check Cache
    if use_cache and meta.object_id:
        cached = _get_from_cache(
            server_name,
            db_name,
            meta.object_id,
            meta.modify_date,
            mode,
            max_depth,
            max_objects=max_objects,
            keywords=keywords,
            zones=zones,
            expand=expand,
            exclude_like=exclude_like,
            include_called_by=include_called_by,
            max_snippet_lines=max_snippet_lines,
            max_full_chars=max_full_chars,
        )
        if cached:
            return cached

    # Check for empty definition (encrypted or missing body)
    if not meta.definition or not meta.definition.strip():
        return {
            "success": True,
            "spec_version": "1.0",
            "object": full_object_name,
            "object_type": obj_type,
            "mode": mode,
            "parse_status": "failed",
            "line_count": 0,
            "char_count": 0,
            "database": db_name,
            "modify_date": _format_modify_date(meta.modify_date),
            "meta": {
                "file_path": file_path,
                "project_root": project_root,
                "cache_hit": False,
                "warnings": ["encrypted_or_empty_definition"],
            },
        }

    # 7. Execute according to mode
    if mode == "full":
        truncated = len(meta.definition) > max_full_chars
        def_text = meta.definition[:max_full_chars] if truncated else meta.definition
        lines = def_text.splitlines()
        res_dict = {
            "success": True,
            "spec_version": "1.0",
            "object": full_object_name,
            "object_type": obj_type,
            "mode": "full",
            "definition": def_text,
            "line_count": len(lines),
            "char_count": len(def_text),
            "truncated": truncated,
            "truncated_at_char": max_full_chars if truncated else None,
            "modify_date": _format_modify_date(meta.modify_date),
            "database": db_name,
            "meta": {
                "file_path": file_path,
                "project_root": project_root,
                "cache_hit": False,
                "estimated_full_chars": len(meta.definition),
                "estimated_tokens_saved": 0,
                "warnings": [],
            },
        }
        if use_cache:
            _set_to_cache(
                server_name,
                db_name,
                meta.object_id,
                meta.modify_date,
                mode,
                max_depth,
                res_dict,
                max_objects=max_objects,
                keywords=keywords,
                zones=zones,
                expand=expand,
                exclude_like=exclude_like,
                include_called_by=include_called_by,
                max_snippet_lines=max_snippet_lines,
                max_full_chars=max_full_chars,
            )
        return res_dict

    if mode == "snippet":
        snippet_res = extract_snippet(
            meta.definition,
            object_name=full_object_name,
            keywords=keywords,
            zones=zones,
            max_lines=max_snippet_lines,
        )
        res_dict = result_to_dict(snippet_res)
        res_dict["database"] = db_name
        res_dict["meta"]["file_path"] = file_path
        res_dict["meta"]["project_root"] = project_root
        if use_cache:
            _set_to_cache(
                server_name,
                db_name,
                meta.object_id,
                meta.modify_date,
                mode,
                max_depth,
                res_dict,
                max_objects=max_objects,
                keywords=keywords,
                zones=zones,
                expand=expand,
                exclude_like=exclude_like,
                include_called_by=include_called_by,
                max_snippet_lines=max_snippet_lines,
                max_full_chars=max_full_chars,
            )
        return res_dict

    # 8. Mode: summary
    t_before_ast = time.perf_counter()
    exclude_patterns = exclude_like if exclude_like is not None else list(DEFAULT_EXCLUDE_LIKE)
    summary_opts = AnalyzeOptions(
        max_depth=max_depth,
        max_objects=max_objects,
        expand=expand or [],
        exclude_like=exclude_patterns,
        include_called_by=include_called_by,
    )

    pure_summary = analyze_definition(
        meta.definition,
        object_name=full_object_name,
        object_type=obj_type,
        catalog_meta=meta,
        options=summary_opts,
    )
    t_after_ast = time.perf_counter()
    antlr_parse_ms = pure_summary.meta.parse_time_ms

    # 9. Call Graph recursion with cycle detection and depth traversal
    t_before_cg = time.perf_counter()
    definitions_dict: dict[str, str] = {full_object_name: meta.definition}
    truncated_list: list[str] = []

    if obj_type != "VIEW" and max_depth > 0 and pure_summary.summary.calls_direct:
        # Prepare expansion matchers (bare names and qualified names)
        expand_normalized: set[str] = {x.split(".")[-1] for x in (expand or [])} | set(expand or [])
        visited: set[str] = {full_object_name, safe_name}
        deadline = time.perf_counter() + 30.0

        # Queue contains items to expand: (schema, name, current_depth)
        current_level_calls: list[str] = [c.name for c in pure_summary.summary.calls_direct]

        for current_depth in range(1, max_depth + 1):
            if not current_level_calls or time.perf_counter() > deadline:
                break

            to_fetch_keys: list[tuple[str, str]] = []
            next_level_calls: list[str] = []

            for call_item in current_level_calls:
                call_schema, call_name = resolve_object_ref(call_item)
                full_call_key = f"{call_schema}.{call_name}"

                if full_call_key in visited or call_name in visited:
                    continue

                call_kind = classify_object(full_call_key)
                is_expandable = (
                    call_kind == "business"
                    or call_name in expand_normalized
                    or full_call_key in expand_normalized
                )

                if is_expandable:
                    if len(definitions_dict) + len(to_fetch_keys) >= max_objects:
                        truncated_list.append(full_call_key)
                        continue
                    to_fetch_keys.append((call_schema, call_name))
                    visited.add(full_call_key)
                    visited.add(call_name)

            if to_fetch_keys:
                try:
                    batch_defs = fetcher.fetch_many(to_fetch_keys)
                    for k, v in batch_defs.items():
                        definitions_dict[k] = v.definition
                        # Extract calls for next depth level if depth < max_depth
                        if current_depth < max_depth and v.definition:
                            child_calls = _extract_shallow_calls(v.definition)
                            next_level_calls.extend(child_calls)
                except Exception as e:
                    pure_summary.meta.warnings.append(f"Lỗi batch fetch call graph (level {current_depth}): {str(e)}")

            current_level_calls = next_level_calls

        # Mark expanded=True on direct calls if definition exists
        for c in pure_summary.summary.calls_direct:
            c_schema, c_name = resolve_object_ref(c.name)
            if f"{c_schema}.{c_name}" in definitions_dict or c.name in definitions_dict:
                c.expanded = True

        pure_summary.call_graph = build_call_graph(
            full_object_name,
            definitions_dict,
            max_depth=max_depth,
            expand=expand,
            exclude_like=exclude_patterns,
            truncated_objects=truncated_list,
        )

    t_after_cg = time.perf_counter()
    call_graph_ms = int((t_after_cg - t_before_cg) * 1000)

    # 10. Inbound called_by
    t_before_cb = time.perf_counter()
    if include_called_by and meta.object_id:
        try:
            callers = fetcher.fetch_callers(meta.object_id, safe_schema, safe_name)
            if pure_summary.call_graph is None:
                pure_summary.call_graph = CallGraph(
                    root=full_object_name,
                    max_depth_applied=max_depth,
                    total_objects_count=1,
                    nodes={
                        full_object_name: CallGraphNode(
                            kind=classify_object(full_object_name),
                            depth=0,
                            expanded=True,
                        )
                    },
                )
            pure_summary.call_graph.called_by = callers
        except Exception as e:
            pure_summary.meta.warnings.append(f"Không thể truy vấn called_by: {str(e)}")

    t_after_cb = time.perf_counter()
    called_by_ms = int((t_after_cb - t_before_cb) * 1000)
    total_time_ms = int((time.perf_counter() - t_start) * 1000)

    # 11. Finalize metadata
    pure_summary.database = db_name
    pure_summary.modify_date = _format_modify_date(meta.modify_date)
    pure_summary.meta.file_path = file_path
    pure_summary.meta.project_root = project_root
    pure_summary.meta.objects_fetched = len(definitions_dict)
    pure_summary.meta.timing = {
        "resolve_connection_ms": conn_ms,
        "fetch_root_catalog_ms": fetch_root_ms,
        "antlr_ast_parse_ms": antlr_parse_ms,
        "call_graph_expand_ms": call_graph_ms,
        "inbound_called_by_ms": called_by_ms,
        "total_time_ms": total_time_ms,
    }

    final_dict = result_to_dict(pure_summary)
    if use_cache:
        _set_to_cache(
            server_name,
            db_name,
            meta.object_id,
            meta.modify_date,
            mode,
            max_depth,
            final_dict,
            max_objects=max_objects,
            keywords=keywords,
            zones=zones,
            expand=expand,
            exclude_like=exclude_like,
            include_called_by=include_called_by,
            max_snippet_lines=max_snippet_lines,
            max_full_chars=max_full_chars,
        )

    return final_dict
