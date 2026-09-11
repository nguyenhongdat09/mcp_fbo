"""Database operations and queries for clone_things."""

from __future__ import annotations

import re
from typing import Any

from queryDatabase.connection import get_connection_config
from queryDatabase.executor import execute_query
from queryDatabase.service import query_database
from queryDatabase.bridges.summary_bridge import summary_object

from .script_transform import wrap_check_exists

DB_LOOKUP_ORDER = ("app", "sys")


def load_project_db_connections(
    project_path: str,
    warnings: list[str],
) -> dict[str, dict[str, Any]]:
    """
    Resolve cả app + sys từ Web.config (cùng logic query_database / find_connect_by_path).
    Trả {"app": parsed, "sys": parsed} — thiếu bucket nào thì bỏ, kèm warning.
    """
    import clone_things.service as svc
    out: dict[str, dict[str, Any]] = {}
    for dt in DB_LOOKUP_ORDER:
        res = svc.get_connection_config(project_path, dt)
        if res.get("success") and res.get("parsed"):
            out[dt] = res["parsed"]
        else:
            warnings.append(
                f"connection_{dt}_unavailable: {res.get('error', 'unknown')}"
            )
    return out


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
    import clone_things.service as svc
    safe_clean = str(clean_name).replace("'", "''")
    safe_schema = str(schema).replace("'", "''") if schema else "dbo"
    sql = f"""
SELECT o.type, o.type_desc
FROM sys.objects o
WHERE o.name = N'{safe_clean}'
  AND SCHEMA_NAME(o.schema_id) = N'{safe_schema}'
"""
    res = svc.execute_query(parsed_conn, sql, max_rows=5)
    rows = res.get("result_sets", [{}])[0].get("rows", [])
    if rows:
        obj_type = str(rows[0][0] or "").strip()
        type_desc = str(rows[0][1] or "").strip()
        return True, obj_type, type_desc

    # Fallback without schema check in case schema mismatch
    sql_any_schema = f"SELECT o.type, o.type_desc FROM sys.objects o WHERE o.name = N'{safe_clean}'"
    res_any = svc.execute_query(parsed_conn, sql_any_schema, max_rows=5)
    rows_any = res_any.get("result_sets", [{}])[0].get("rows", [])
    if rows_any:
        obj_type = str(rows_any[0][0] or "").strip()
        type_desc = str(rows_any[0][1] or "").strip()
        return True, obj_type, type_desc

    return False, "", ""


def is_object_encrypted(
    parsed_conn: dict[str, Any],
    clean_name: str,
    schema: str = "dbo",
) -> bool:
    """
    Kiểm tra xem đối tượng SQL (proc/func/view) có bị mã hóa (IsEncrypted = 1) trên DB hay không.
    """
    if not parsed_conn:
        return False

    import clone_things.service as svc
    safe_name = str(clean_name).strip().strip("'\"[]").replace("'", "''")
    safe_schema = (str(schema).strip().strip("'\"[]") or "dbo").replace("'", "''")

    # 1. Thử OBJECTPROPERTY với OBJECT_ID(QUOTENAME(schema) + '.' + QUOTENAME(name))
    sql1 = f"""
SELECT CASE 
    WHEN OBJECTPROPERTY(OBJECT_ID(QUOTENAME(N'{safe_schema}') + N'.' + QUOTENAME(N'{safe_name}')), 'IsEncrypted') = 1 
    THEN 1 ELSE 0 END
"""
    try:
        res1 = svc.execute_query(parsed_conn, sql1, max_rows=5)
        rows1 = res1.get("result_sets", [{}])[0].get("rows", [])
        if rows1 and str(rows1[0][0]) in ("1", "True"):
            return True
    except Exception:
        pass

    # 2. Thử sys.objects + OBJECTPROPERTY(o.object_id, 'IsEncrypted')
    sql2 = f"""
SELECT 1
FROM sys.objects o
WHERE o.name = N'{safe_name}'
  AND (SCHEMA_NAME(o.schema_id) = N'{safe_schema}' OR N'{safe_schema}' = N'')
  AND OBJECTPROPERTY(o.object_id, 'IsEncrypted') = 1
"""
    try:
        res2 = svc.execute_query(parsed_conn, sql2, max_rows=5)
        rows2 = res2.get("result_sets", [{}])[0].get("rows", [])
        if rows2:
            return True
    except Exception:
        pass

    return False


def find_object_on_side(
    parsed_by_db: dict[str, dict[str, Any]],
    clean_name: str,
    schema: str = "dbo",
    order: tuple[str, ...] = DB_LOOKUP_ORDER,
) -> tuple[bool, str, str, str | None]:
    """
    Tìm object lần lượt app → sys (hoặc order chỉ định).
    Returns (exists, obj_type, type_desc, db_type|None).
    """
    import clone_things.service as svc
    for dt in order:
        parsed = parsed_by_db.get(dt)
        if not parsed:
            continue
        exists, obj_type, type_desc = svc.check_object_exists_and_type(
            parsed, clean_name, schema
        )
        if exists:
            # If object name indicates a system object (sys* or v20*) and was found on app,
            # but sys DB is also configured, check if it also exists on sys.
            # If present on sys, sys is the canonical database for system objects!
            if dt == "app" and (clean_name.lower().startswith("sys") or clean_name.lower().startswith("v20")):
                sys_parsed = parsed_by_db.get("sys")
                if sys_parsed:
                    sys_exists, s_type, s_desc = svc.check_object_exists_and_type(
                        sys_parsed, clean_name, schema
                    )
                    if sys_exists:
                        return True, s_type, s_desc, "sys"
            return True, obj_type, type_desc, dt
    return False, "", "", None


def classify_dependency(
    source_dbs: dict[str, Any],
    clean_name: str,
    schema: str = "dbo",
    order: tuple[str, ...] = DB_LOOKUP_ORDER,
) -> str:
    """
    Classify dependency into 'proc', 'func', 'table', or 'view'.
    Uses source DB catalog if available, falling back to naming patterns.
    """
    import clone_things.service as svc
    src_exists, s_type, s_desc, _ = svc.find_object_on_side(
        source_dbs, clean_name, schema, order=order
    )
    if src_exists:
        type_desc_upper = (s_desc or s_type or "").upper()
        if "TABLE" in type_desc_upper or s_type.upper() == "U":
            return "table"
        if "FUNCTION" in type_desc_upper or s_type.upper() in ("FN", "IF", "TF"):
            return "func"
        if "VIEW" in type_desc_upper or s_type.upper() == "V":
            return "view"
        if "PROCEDURE" in type_desc_upper or "PROC" in type_desc_upper or s_type.upper() == "P":
            return "proc"

    # Fallback heuristic based on name conventions
    low = clean_name.lower()
    if low.startswith("fn_") or "func" in low:
        return "func"
    if low.startswith("v_") or low.startswith("v20") or "view" in low:
        return "view"
    if low.startswith(("dm", "m", "c", "d", "tbl")) or "$" in low or "table" in low:
        return "table"
    return "proc"


def fetch_object_script(
    file_path: str,
    clean_name: str,
    schema: str,
    obj_type: str,
    type_desc: str,
    db_type: str = "app",
    wrap_exists: bool = True,
) -> str:
    """Fetch full script for either Table DDL or Routine Definition with optional check exists wrapping."""
    import clone_things.service as svc

    # Table DDL
    if obj_type == "U" or type_desc.upper() == "USER_TABLE":
        res = svc.query_database(
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
        raw_ddl = "".join(str(r[0]) for r in rows if r and r[0])
        if wrap_exists:
            return svc.wrap_check_exists(raw_ddl, clean_name=clean_name, schema=schema, obj_type=obj_type, type_desc=type_desc)
        return raw_ddl

    # Routine (Proc, Func, View)
    summary_res = svc.summary_object(
        file_path=file_path,
        object_name=clean_name,
        mode="full",
        schema=schema,
        db_type=db_type,
    )
    if summary_res.get("success"):
        raw_def = summary_res.get("definition") or ""
        if wrap_exists:
            return svc.wrap_check_exists(raw_def, clean_name=clean_name, schema=schema, obj_type=obj_type, type_desc=type_desc)
        return raw_def

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

    import clone_things.service as svc
    summary_res = svc.summary_object(
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
    import clone_things.service as svc
    batches = [b.strip() for b in re.split(r"^\s*GO\s*$", script, flags=re.IGNORECASE | re.MULTILINE) if b.strip()]
    if not batches:
        return True, None
    for batch in batches:
        res = svc.execute_query(parsed_target_conn, batch)
        if not res.get("success"):
            return False, res.get("error", "Unknown deployment error")
    return True, None
