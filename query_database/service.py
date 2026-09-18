"""API chính: file path + query → kết quả SQL."""

from __future__ import annotations

from .connection import get_connection_config
from .executor import (
    DEFAULT_MAX_ROWS,
    check_sql_batches,
    execute_query,
    execute_sql_batches,
)
from .query_resolver import (
    is_user_table,
    normalize_query_type,
    parse_object_lookup_result,
    resolve_object_sql,
    resolve_query,
)
from .bridges.summary_bridge import resolve_object_ref

_SEARCH_OBJECT_TYPES = {"P", "FN", "IF", "TF", "V", "TR"}
_SEARCH_DEFAULT_TYPES = "P,FN,IF,TF,V,TR"


def query_database(
    file_path: str,
    query: str,
    db_type: str = "app",
    max_rows: int = DEFAULT_MAX_ROWS,
    query_type: int = 1,
    mode: str = "summary",
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
    fetcher_override: object = None,
    object_name: str = "",
    references: str = "",
    object_types: str = _SEARCH_DEFAULT_TYPES,
    include_snippet: bool = True,
    max_results: int = 50,
    max_lines_per_object: int = 10,
    **extra_kwargs: object,
) -> dict:
    """
    Resolve connection từ file path, chạy query, trả kết quả cho agent.

    Args:
        file_path: Path file trong project FBO (XML, SQL, ...)
        query: Tên object (type=0), câu SQL inline (type=1), hoặc path file .sql (type=2/3)
        db_type: app hoặc sys (default: app)
        max_rows: Giới hạn số dòng trả về (default: 20000)
        query_type: 0=object, 1=SQL inline (default), 2=đọc file .sql,
            3=check file .sql qua SET PARSEONLY (chỉ parse, không execute)
        mode: summary | snippet | full (khi query_type=0 với proc/view/func)
        schema: Schema mặc định (default: dbo)
        max_depth: Độ sâu call graph (default: 1)
        max_objects: Giới hạn số object đệ quy (default: 30)
        expand: Danh sách infra object cần bung thêm 1 cấp
        exclude_like: Pattern loại trừ khỏi call graph
        include_called_by: Có lấy inbound references không
        keywords: Từ khóa trích xuất snippet
        zones: Vùng cấu trúc cần lấy snippet
        max_snippet_lines: Giới hạn dòng snippet
        max_full_chars: Giới hạn ký tự mode full
        use_cache: Dùng cache in-memory thread-safe
        fetcher_override: Override fetcher cho unit test
    """
    if not file_path or not str(file_path).strip():
        return {"success": False, "error": "file_path is required"}

    if (mode or "").strip().lower() == "search":
        conn_result = get_connection_config(file_path, db_type)
        if not conn_result.get("success"):
            return conn_result
        return _search_objects(
            file_path=file_path,
            conn_result=conn_result,
            db_type=db_type,
            object_name=object_name,
            references=references,
            object_types=object_types,
            include_snippet=include_snippet,
            max_results=max_results,
            max_lines_per_object=max_lines_per_object,
        )

    if not query or not str(query).strip():
        return {"success": False, "error": "query is required"}

    try:
        qt = normalize_query_type(query_type)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    conn_result = get_connection_config(file_path, db_type)
    if not conn_result.get("success"):
        return conn_result

    parsed = conn_result["parsed"]

    if qt == 0:
        return _query_object(
            file_path=file_path,
            query=query,
            parsed=parsed,
            conn_result=conn_result,
            db_type=db_type,
            max_rows=max_rows,
            query_type=qt,
            mode=mode,
            schema=schema,
            max_depth=max_depth,
            max_objects=max_objects,
            expand=expand,
            exclude_like=exclude_like,
            include_called_by=include_called_by,
            keywords=keywords,
            zones=zones,
            max_snippet_lines=max_snippet_lines,
            max_full_chars=max_full_chars,
            use_cache=use_cache,
            fetcher_override=fetcher_override,
            **extra_kwargs,
        )

    try:
        sql, label = resolve_query(qt, query)
    except (ValueError, FileNotFoundError) as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    extra: dict = {}
    if qt in (2, 3):
        extra["sql_file_path"] = str(query).strip()

    # type=3: check parse-only per batch (SET PARSEONLY) — KHÔNG execute
    # type=2 (file .sql) có thể chứa nhiều batch GO — split + exec tuần tự
    if qt == 3:
        query_result = check_sql_batches(parsed, sql)
    elif qt == 2:
        query_result = execute_sql_batches(parsed, sql, max_rows=max_rows)
    else:
        query_result = execute_query(parsed, sql, max_rows=max_rows)
    return _attach_metadata(
        query_result,
        file_path=file_path,
        conn_result=conn_result,
        db_type=db_type,
        query_type=qt,
        query_label=label,
        original_query=query,
        **extra,
    )


def _query_object(
    *,
    file_path: str,
    query: str,
    parsed: dict,
    conn_result: dict,
    db_type: str,
    max_rows: int,
    query_type: int,
    mode: str = "summary",
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
    fetcher_override: object = None,
    **extra_kwargs: object,
) -> dict:
    try:
        resolved_schema, clean_object_name = resolve_object_ref(query, schema=schema)
        lookup_sql = f"SELECT type, type_desc FROM sys.objects WHERE name = N'{clean_object_name}'"
    except (ValueError, FileNotFoundError) as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    lookup_result = execute_query(parsed, lookup_sql, max_rows=10)
    if not lookup_result.get("success"):
        lookup_result["file_path"] = file_path
        lookup_result["query_type"] = query_type
        lookup_result["query_label"] = f"object_lookup:{clean_object_name}"
        lookup_result["original_query"] = query
        return lookup_result

    parsed_object = parse_object_lookup_result(lookup_result)
    if not parsed_object:
        return {
            "success": False,
            "error": f"Không tìm thấy object trong sys.objects: {clean_object_name}",
            "file_path": file_path,
            "project_root": conn_result.get("project_root"),
            "web_config_path": conn_result.get("web_config_path"),
            "db_type": db_type,
            "query_type": query_type,
            "original_query": query,
        }

    obj_type, type_desc = parsed_object

    # Nếu là Bảng (Table) -> Thực thi script schema bảng (CREATE TABLE + Index + Constraint)
    if is_user_table(obj_type, type_desc):
        try:
            sql, label, resolved_as = resolve_object_sql(clean_object_name, obj_type, type_desc)
        except (ValueError, FileNotFoundError) as exc:
            return {
                "success": False,
                "error": str(exc),
                "file_path": file_path,
                "object_name": clean_object_name,
                "object_type": obj_type,
                "object_type_desc": type_desc,
                "query_type": query_type,
                "original_query": query,
            }

        query_result = execute_query(parsed, sql, max_rows=max_rows)
        query_result["object_name"] = clean_object_name
        query_result["object_type"] = obj_type
        query_result["object_type_desc"] = type_desc
        query_result["resolved_as"] = resolved_as
        return _attach_metadata(
            query_result,
            file_path=file_path,
            conn_result=conn_result,
            db_type=db_type,
            query_type=query_type,
            query_label=label,
            original_query=query,
        )

    # Nếu là Stored Procedure, Function, View, Trigger... -> Nhúng gọi summary_object
    from .bridges.summary_bridge import summary_object

    summary_result = summary_object(
        file_path=file_path,
        object_name=query,
        mode=mode,
        db_type=db_type,
        schema=resolved_schema,
        max_depth=max_depth,
        max_objects=max_objects,
        expand=expand,
        exclude_like=exclude_like,
        include_called_by=include_called_by,
        keywords=keywords,
        zones=zones,
        max_snippet_lines=max_snippet_lines,
        max_full_chars=max_full_chars,
        use_cache=use_cache,
        fetcher_override=fetcher_override,
        **extra_kwargs,
    )
    summary_result["file_path"] = file_path
    summary_result["project_root"] = conn_result.get("project_root")
    summary_result["web_config_path"] = conn_result.get("web_config_path")
    summary_result["db_type"] = db_type
    summary_result["query_type"] = query_type
    summary_result["query_label"] = f"object_summary:{clean_object_name}"
    summary_result["original_query"] = query
    summary_result["resolved_as"] = "object_summary"
    if "object_name" not in summary_result:
        summary_result["object_name"] = clean_object_name
    if "object_type" not in summary_result:
        summary_result["object_type"] = obj_type
    summary_result["object_type_desc"] = type_desc
    return summary_result


def _search_objects(
    *,
    file_path: str,
    conn_result: dict,
    db_type: str,
    object_name: str = "",
    references: str = "",
    object_types: str = _SEARCH_DEFAULT_TYPES,
    include_snippet: bool = True,
    max_results: int = 50,
    max_lines_per_object: int = 10,
) -> dict:
    """mode='search': tìm DB object theo tên (LIKE) hoặc theo nội dung definition.

    ``references`` là chuỗi literal cần có trong sys.sql_modules.definition —
    luôn parameterized (LIKE '%'+?+'%'), không nối chuỗi vào SQL.
    """
    object_name = (object_name or "").strip()
    references = references or ""
    if not object_name and not references:
        return {
            "success": False,
            "error_code": "search_criteria_required",
            "error": "Cần ít nhất 1 trong object_name / references",
            "mode": "search",
            "file_path": file_path,
        }

    types = [t.strip().upper() for t in (object_types or "").split(",") if t.strip()]
    dropped = [t for t in types if t not in _SEARCH_OBJECT_TYPES]
    types = [t for t in types if t in _SEARCH_OBJECT_TYPES]
    if not types:
        types = sorted(_SEARCH_OBJECT_TYPES)
    type_list = ", ".join(f"'{t}'" for t in types)  # whitelist enum — an toàn

    sql = (
        "SELECT o.object_id, o.name, s.name AS schema_name, o.type, o.type_desc, "
        "o.create_date, o.modify_date, "
        "CASE WHEN m.object_id IS NULL THEN 0 ELSE 1 END AS has_definition "
        "FROM sys.objects o "
        "JOIN sys.schemas s ON s.schema_id = o.schema_id "
        "LEFT JOIN sys.sql_modules m ON m.object_id = o.object_id "
        "WHERE o.is_ms_shipped = 0 "
        f"AND o.type IN ({type_list}) "
        "AND (? = N'' OR o.name LIKE ?) "
        "AND (? = N'' OR m.definition LIKE N'%' + ? + N'%') "
        "ORDER BY o.modify_date DESC"
    )
    max_results = max(1, int(max_results or 50))
    params = (object_name, object_name, references, references)
    res = execute_query(parsed=conn_result["parsed"], query=sql,
                        max_rows=max_results + 1, params=params)
    if not res.get("success"):
        res["mode"] = "search"
        res["file_path"] = file_path
        return res

    rows = (res.get("result_sets") or [{}])[0].get("rows", [])
    truncated = len(rows) > max_results
    rows = rows[:max_results]

    objects: list[dict] = []
    obj_ids: list[int] = []
    for row in rows:
        obj = {
            "object_id": row[0],
            "name": row[1],
            "schema": row[2],
            "type": row[3],
            "type_desc": row[4],
            "create_date": row[5],
            "modify_date": row[6],
            "has_definition": row[7],
            "matched_lines": [],
        }
        objects.append(obj)
        if obj["has_definition"]:
            obj_ids.append(obj["object_id"])

    if include_snippet and references and obj_ids:
        placeholders = ", ".join("?" for _ in obj_ids)
        def_sql = (
            "SELECT m.object_id, m.definition FROM sys.sql_modules m "
            f"WHERE m.object_id IN ({placeholders})"
        )
        def_res = execute_query(parsed=conn_result["parsed"], query=def_sql,
                                max_rows=len(obj_ids), params=tuple(obj_ids))
        if def_res.get("success"):
            defs = {
                r[0]: (r[1] or "")
                for r in (def_res.get("result_sets") or [{}])[0].get("rows", [])
            }
            cap = max(1, int(max_lines_per_object or 10))
            ref_low = references.lower()
            by_id = {o["object_id"]: o for o in objects}
            for oid, definition in defs.items():
                obj = by_id.get(oid)
                if obj is None:
                    continue
                for ln, line in enumerate(definition.split("\n"), 1):
                    if ref_low in line.lower():
                        obj["matched_lines"].append(
                            {"line": ln, "text": line.strip()[:300]}
                        )
                        if len(obj["matched_lines"]) >= cap:
                            break

    result = {
        "success": True,
        "mode": "search",
        "criteria": {
            "object_name": object_name,
            "references": references,
            "object_types": ",".join(types),
        },
        "objects": objects,
        "object_count": len(objects),
        "truncated": truncated,
    }
    if dropped:
        result["warnings"] = [
            f"object_types bỏ qua giá trị ngoài whitelist {_SEARCH_OBJECT_TYPES}: {dropped}"
        ]
    return _attach_metadata(
        result,
        file_path=file_path,
        conn_result=conn_result,
        db_type=db_type,
        query_type=0,
        query_label="object_search",
        original_query=object_name or references,
    )


def _attach_metadata(
    query_result: dict,
    *,
    file_path: str,
    conn_result: dict,
    db_type: str,
    query_type: int,
    query_label: str,
    original_query: str,
    **extra: object,
) -> dict:
    query_result["file_path"] = file_path
    query_result["project_root"] = conn_result.get("project_root")
    query_result["web_config_path"] = conn_result.get("web_config_path")
    query_result["db_type"] = db_type
    query_result["query_type"] = query_type
    query_result["query_label"] = query_label
    query_result["original_query"] = original_query
    query_result.update(extra)
    return query_result
