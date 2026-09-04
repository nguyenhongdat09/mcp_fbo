"""Main service implementation for clone_things tool."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from queryDatabase.connection import get_connection_config
from queryDatabase.executor import execute_query
from queryDatabase.service import query_database
from queryDatabase.bridges.summary_bridge import summary_object, resolve_object_ref
from sql_object_summary.options import DEFAULT_EXCLUDE_LIKE
from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml

from .file_manager import resolve_output_file, append_script_block, append_not_found_summary
from .open_editor import open_file_for_user

DEFAULT_EXTRA_EXCLUDES = [
    r"^sp_",
    r"^xp_",
    r"^sys\.",
    r"^sp_executesql$",
]


def normalize_fbo_db_table(raw: str) -> str:
    """d91$@@prime$partition$current -> d91$; c91$$$partition$current -> c91$"""
    s = (raw or "").strip()
    if not s:
        return s
    cleaned = re.sub(r"(\$)?(?:\$\$|@@).+$", r"\1", s).strip()
    return cleaned or s


def to_partition_structure_name(clean_name: str) -> str:
    """
    Map FBO partition names to the structure table (*$000000).

    - m41$        → m41$000000   (template từ XML/summary)
    - m41$202601  → m41$000000   (bảng kỳ — clone theo cấu trúc, không clone từng kỳ)
    - m41$000000  → m41$000000
    - dmkh        → dmkh         (không đụng)
    """
    name = (clean_name or "").strip()
    if not name or "$" not in name:
        return name

    # Đã là bảng cấu trúc
    if re.search(r"\$000000$", name, re.IGNORECASE):
        return name

    # m41$202601 / r00$000001 → giữ prefix tới $ rồi gắn 000000
    m = re.match(r"^(.+\$)\d+$", name)
    if m:
        return f"{m.group(1)}000000"

    # m41$ / r00$ (kết thúc bằng $) → nối 000000
    if name.endswith("$"):
        return f"{name}000000"

    return name


def normalize_object_name(name: str, default_schema: str = "dbo") -> tuple[str, str, str]:
    """
    Split name into (schema, clean_name, visited_key).
    visited_key is always '<schema_lower>.<clean_name_lower>'.
    Partition templates được map sang *$000000 trước khi tạo visited_key.
    """
    cleaned = str(name).strip().strip("'\"[]")
    if "." in cleaned:
        parts = cleaned.split(".", 1)
        schema = parts[0].strip().strip("'\"[]") or default_schema
        clean_name = parts[1].strip().strip("'\"[]")
    else:
        schema = default_schema
        clean_name = cleaned

    clean_name = to_partition_structure_name(clean_name)
    visited_key = f"{schema.lower()}.{clean_name.lower()}"
    return schema, clean_name, visited_key


def is_excluded(name: str, exclude_patterns: list[str]) -> bool:
    """Check if object name matches any exclude regex."""
    clean = name.split(".")[-1].strip()
    for pat in exclude_patterns:
        if re.search(pat, clean, re.IGNORECASE) or re.search(pat, name, re.IGNORECASE):
            return True
    return False


def check_object_exists_and_type(
    parsed_conn: dict[str, Any],
    clean_name: str,
    schema: str = "dbo",
) -> tuple[bool, str, str]:
    """
    Directly query sys.objects to check object existence and type.
    Avoids ObjectCatalogFetcher.fetch_one limitation for tables.
    Returns (exists, obj_type, type_desc).
    """
    sql = f"""
SELECT o.type, o.type_desc
FROM sys.objects o
WHERE o.name = N'{clean_name}'
  AND SCHEMA_NAME(o.schema_id) = N'{schema}'
"""
    res = execute_query(parsed_conn, sql, max_rows=5)
    rows = res.get("result_sets", [{}])[0].get("rows", [])
    if rows:
        obj_type = str(rows[0][0] or "").strip()
        type_desc = str(rows[0][1] or "").strip()
        return True, obj_type, type_desc

    # Fallback without schema check in case schema mismatch
    sql_any_schema = f"SELECT o.type, o.type_desc FROM sys.objects o WHERE o.name = N'{clean_name}'"
    res_any = execute_query(parsed_conn, sql_any_schema, max_rows=5)
    rows_any = res_any.get("result_sets", [{}])[0].get("rows", [])
    if rows_any:
        obj_type = str(rows_any[0][0] or "").strip()
        type_desc = str(rows_any[0][1] or "").strip()
        return True, obj_type, type_desc

    return False, "", ""


def fetch_object_script(
    file_path: str,
    clean_name: str,
    schema: str,
    obj_type: str,
    type_desc: str,
    db_type: str = "app",
) -> str:
    """Fetch full script for either Table DDL or Routine Definition."""
    # Table DDL
    if obj_type == "U" or type_desc.upper() == "USER_TABLE":
        res = query_database(
            file_path=file_path,
            query=clean_name,
            query_type=0,
            db_type=db_type,
            schema=schema,
        )
        if not res.get("success"):
            return ""
        result_sets = res.get("result_sets") or []
        if not result_sets:
            return ""
        rows = result_sets[0].get("rows") or []
        return "".join(str(r[0]) for r in rows if r and r[0])

    # Routine (Proc, Func, View)
    summary_res = summary_object(
        file_path=file_path,
        object_name=clean_name,
        mode="full",
        schema=schema,
        db_type=db_type,
    )
    if summary_res.get("success"):
        return summary_res.get("definition") or ""

    return ""


def extract_object_dependencies(
    file_path: str,
    clean_name: str,
    schema: str,
    obj_type: str,
    type_desc: str,
    db_type: str = "app",
) -> list[str]:
    """Extract direct dependencies for routines using summary mode."""
    if obj_type == "U" or type_desc.upper() == "USER_TABLE":
        return []

    summary_res = summary_object(
        file_path=file_path,
        object_name=clean_name,
        mode="summary",
        schema=schema,
        db_type=db_type,
        max_depth=0,
    )
    if not summary_res.get("success"):
        return []

    summary_data = summary_res.get("summary") or {}
    deps: list[str] = []

    # Routine calls
    for call_item in summary_data.get("calls_direct", []):
        c_name = call_item.get("name")
        if c_name:
            deps.append(c_name)

    # Tables read/write
    for t in summary_data.get("tables_read", []):
        if t:
            deps.append(t)
    for t in summary_data.get("tables_write", []):
        if t:
            deps.append(t)

    return deps


def deploy_script_to_target(parsed_target_conn: dict[str, Any], script: str) -> tuple[bool, str | None]:
    """Deploy script batches to target database using execute_query."""
    batches = [b.strip() for b in re.split(r"^\s*GO\s*$", script, flags=re.IGNORECASE | re.MULTILINE) if b.strip()]
    if not batches:
        return True, None
    for batch in batches:
        res = execute_query(parsed_target_conn, batch)
        if not res.get("success"):
            return False, res.get("error", "Unknown deployment error")
    return True, None


def clone_things(
    object: str,
    project_source: str,
    project_target: str,
    type: int = 0,
    path_to_pasted: str = "",
    schema: str = "dbo",
    db_type: str = "app",
    max_objects: int = 50,
    open_file: bool = True,
    exclude_like: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    BƯỚC 1 BẮT BUỘC khi cần clone object SQL (table/proc/func/view) giữa 2 dự án FBO:
    Tool tự kiểm tra Target-first, đệ quy dependency và xuất toàn bộ script vào file .sql temp.
    Agent BẮT BUỘC gọi tool này trước, sau đó đọc file .sql tại 'path_to_pasted' để chỉnh sửa tiếp (tiết kiệm token).

    Args:
        object: Tên object SQL (vd: 'zc_report', 'dmkh') hoặc path .xml controller để seed
        project_source: Absolute path tới project FBO nguồn (chứa Web.config / App_Data)
        project_target: Absolute path tới project FBO đích
        type: 0 = SQL clone (v1)
        path_to_pasted: File .sql để append; để trống = tự tạo temp và mở editor
        schema: Schema mặc định (default: "dbo")
        db_type: "app" hoặc "sys" (default: "app")
        max_objects: Giới hạn số object xử lý (default: 50)
        open_file: Mở file trên editor sau khi ghi (default: True)
        exclude_like: Regex bổ sung loại trừ khỏi dependency con
        config: Cấu hình hệ thống từ config.yaml
    """
    start_time = time.perf_counter()
    warnings: list[str] = []

    if config is None:
        try:
            from fastbusiness_mcp.mcp_app import get_config
            config = get_config()
        except Exception:
            config = {}

    # Override max_objects / open_file / execute_clone from config if not passed
    clone_cfg = config.get("clone_things") or {}
    if max_objects == 50 and "max_objects" in clone_cfg:
        max_objects = int(clone_cfg["max_objects"])
    if open_file is True and "open_file" in clone_cfg:
        open_file = bool(clone_cfg["open_file"])
    execute_clone = bool(clone_cfg.get("execute_clone", clone_cfg.get("Execute_clone", False)))
    open_editor_cmd = clone_cfg.get("open_editor_cmd", "auto")

    # 1. Validation
    if not object or not str(object).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "invalid_object",
            "message": "object is required",
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    if not project_source or not str(project_source).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "invalid_project_source",
            "message": "project_source is required",
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    if not project_target or not str(project_target).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "invalid_project_target",
            "message": "project_target is required",
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    if type != 0:
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "unsupported_type",
            "message": f"type={type} not implemented; only type=0 (SQL clone) is supported",
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    if not Path(project_source).is_absolute():
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "invalid_project_source",
            "message": f"project_source must be an absolute path: {project_source}",
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    if not Path(project_target).is_absolute():
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "invalid_project_target",
            "message": f"project_target must be an absolute path: {project_target}",
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    # 2. Resolve Output File (Fail fast on path_to_pasted or sql_temp_folder)
    # Tên sql temp parity NewSqlTemp: group/project label từ project_target (vd. vlotus_sp228), không dùng stem XML
    output_file, file_err = resolve_output_file(
        path_to_pasted, object, config, project_target=project_target, project_source=project_source
    )
    if file_err:
        msg = "Chưa cấu hình clone_things.sql_temp_folder hoặc thư mục không tồn tại."
        if file_err == "invalid_path_to_pasted":
            msg = "path_to_pasted không hợp lệ (phải là file .sql và thư mục cha phải tồn tại)."
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": file_err,
            "message": msg,
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    # 3. Resolve Connections
    source_conn_res = get_connection_config(project_source, db_type)
    if not source_conn_res.get("success"):
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "invalid_project_source",
            "message": f"Cannot resolve connection from project_source: {source_conn_res.get('error')}",
            "path_to_pasted": output_file,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    target_conn_res = get_connection_config(project_target, db_type)
    if not target_conn_res.get("success"):
        return {
            "success": False,
            "spec_version": "1.0",
            "error_code": "invalid_project_target",
            "message": f"Cannot resolve connection from project_target: {target_conn_res.get('error')}",
            "path_to_pasted": output_file,
            "cloned": [],
            "skipped_exists": [],
            "not_found_both": [],
            "warnings": [],
        }

    parsed_source_conn = source_conn_res["parsed"]
    parsed_target_conn = target_conn_res["parsed"]

    # 4. Seed Queue
    clean_object_input = str(object).strip()
    is_xml_seed = clean_object_input.lower().endswith(".xml") or (
        Path(clean_object_input).exists() and Path(clean_object_input).suffix.lower() == ".xml"
    )

    queue: list[str] = []
    mode_seed = "xml" if is_xml_seed else "sql_name"

    if is_xml_seed:
        xml_path = Path(clean_object_input)
        if not xml_path.exists():
            return {
                "success": False,
                "spec_version": "1.0",
                "error_code": "xml_not_found",
                "message": f"XML seed file not found: {clean_object_input}",
                "path_to_pasted": output_file,
                "cloned": [],
                "skipped_exists": [],
                "not_found_both": [],
                "warnings": [],
            }
        try:
            summary_dict = summary_xml(str(xml_path))
            if not summary_dict.get("success"):
                return {
                    "success": False,
                    "spec_version": "1.0",
                    "error_code": "xml_summary_failed",
                    "message": f"Summary XML failed: {summary_dict.get('meta', {}).get('warnings')}",
                    "path_to_pasted": output_file,
                    "cloned": [],
                    "skipped_exists": [],
                    "not_found_both": [],
                    "warnings": [],
                }

            sql_sec = summary_dict.get("sql") or {}
            for p_name in sql_sec.get("procs", []):
                if p_name:
                    queue.append(p_name)
            for t_name in sql_sec.get("tables", []):
                if t_name:
                    queue.append(t_name)
            for v_name in sql_sec.get("views", []):
                if v_name:
                    queue.append(v_name)

            ctrl_sec = summary_dict.get("controller") or {}
            raw_db_table = ctrl_sec.get("db_table")
            if raw_db_table:
                norm_table = normalize_fbo_db_table(raw_db_table)
                if norm_table:
                    queue.append(norm_table)
        except Exception as e:
            return {
                "success": False,
                "spec_version": "1.0",
                "error_code": "xml_summary_failed",
                "message": f"Failed to parse XML summary: {e}",
                "path_to_pasted": output_file,
                "cloned": [],
                "skipped_exists": [],
                "not_found_both": [],
                "warnings": [],
            }
    else:
        queue.append(clean_object_input)

    # Track direct seeds so they are not filtered by exclude patterns
    seed_objects = set(queue)

    # Prepare excludes
    exclude_patterns = list(DEFAULT_EXCLUDE_LIKE) + DEFAULT_EXTRA_EXCLUDES
    if exclude_like:
        exclude_patterns.extend(exclude_like)

    # 5. Queue Processing Loop
    visited: set[str] = set()
    cloned: list[dict[str, Any]] = []
    skipped_exists: list[dict[str, Any]] = []
    not_found_both: list[str] = []

    processed_count = 0
    is_root_step = True
    truncated_max_objects = False

    while queue and processed_count < max_objects:
        raw_name = queue.pop(0).strip()
        if not raw_name:
            continue

        # Filter out temp tables / variable tables
        if raw_name.startswith("#") or raw_name.startswith("@"):
            continue

        item_schema, item_clean_name, visited_key = normalize_object_name(raw_name, schema)

        if visited_key in visited:
            continue
        visited.add(visited_key)

        # Exclude check: root seed items (either direct sql_name or extracted directly from XML) are always processed
        is_seed = (mode_seed == "sql_name" and is_root_step) or (raw_name in seed_objects)
        if not is_seed:
            if is_excluded(item_clean_name, exclude_patterns):
                continue

        is_root_step = False
        processed_count += 1

        # Target-First check: directly via sys.objects
        target_exists, t_type, t_desc = check_object_exists_and_type(
            parsed_target_conn, item_clean_name, item_schema
        )
        if target_exists:
            skipped_exists.append({
                "name": f"{item_schema}.{item_clean_name}",
                "object_type": t_desc or t_type or "OBJECT",
                "where": "target",
            })
            continue  # v1: do not expand dependencies if already on target

        # Source check
        src_exists, s_type, s_desc = check_object_exists_and_type(
            parsed_source_conn, item_clean_name, item_schema
        )
        if not src_exists:
            not_found_both.append(f"{item_schema}.{item_clean_name}")
            continue

        # Fetch script from source
        script = fetch_object_script(
            file_path=project_source,
            clean_name=item_clean_name,
            schema=item_schema,
            obj_type=s_type,
            type_desc=s_desc,
            db_type=db_type,
        )
        if script:
            append_script_block(
                output_file,
                script,
                f"{item_schema}.{item_clean_name}",
                s_desc or s_type or "OBJECT",
            )
            deployed_ok = False
            deploy_error = None
            if execute_clone:
                deployed_ok, deploy_error = deploy_script_to_target(parsed_target_conn, script)
                if not deployed_ok:
                    warnings.append(f"deploy_failed on {item_schema}.{item_clean_name}: {deploy_error}")

            cloned_item = {
                "name": f"{item_schema}.{item_clean_name}",
                "object_type": s_desc or s_type or "OBJECT",
                "from": "source",
                "chars": len(script),
                "line_count": len(script.splitlines()),
                "deployed": deployed_ok if execute_clone else False,
            }
            if deploy_error:
                cloned_item["deploy_error"] = deploy_error
            cloned.append(cloned_item)

        # Enqueue dependencies
        child_deps = extract_object_dependencies(
            file_path=project_source,
            clean_name=item_clean_name,
            schema=item_schema,
            obj_type=s_type,
            type_desc=s_desc,
            db_type=db_type,
        )
        for dep in child_deps:
            if not dep or dep.startswith("#") or dep.startswith("@"):
                continue
            _, _, dep_key = normalize_object_name(dep, schema)
            if dep_key not in visited:
                queue.append(dep)

    if queue and processed_count >= max_objects:
        truncated_max_objects = True
        warnings.append(f"truncated_max_objects: reached limit {max_objects}, {len(queue)} objects remaining in queue")

    # 6. Append single not_found_both summary line
    if not_found_both:
        append_not_found_summary(output_file, not_found_both)

    # 7. Open file for user visibility
    open_attempted = open_file and open_editor_cmd.lower() != "none"
    open_ok = False
    if open_attempted:
        open_ok, open_warn = open_file_for_user(output_file, open_editor_cmd, open_file)
        if open_warn:
            warnings.append(open_warn)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # 8. Return standard JSON schema
    return {
        "success": True,
        "spec_version": "1.0",
        "type": 0,
        "object": object,
        "mode_seed": mode_seed,
        "project_source": str(Path(project_source).resolve()),
        "project_target": str(Path(project_target).resolve()),
        "path_to_pasted": output_file,
        "deployed": bool(execute_clone),
        "execute_clone": bool(execute_clone),
        "cloned": cloned,
        "skipped_exists": skipped_exists,
        "not_found_both": not_found_both,
        "warnings": warnings,
        "meta": {
            "processed_count": processed_count,
            "queue_remaining": len(queue),
            "truncated_max_objects": truncated_max_objects,
            "open_file_attempted": open_attempted,
            "open_file_ok": open_ok,
            "elapsed_ms": elapsed_ms,
        },
    }
