"""Database access layer wrapping clone_things.db_ops for compare_things."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import clone_things.db_ops as c_db
from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.executor import execute_query


def resolve_project_dbs(
    project_path: str,
    warnings: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    Resolve both app and sys database connections from Web.config.
    Returns {"app": parsed_conn, "sys": parsed_conn}.
    """
    return c_db.load_project_db_connections(project_path, warnings)


def check_object_exists(
    parsed_conn: Dict[str, Any],
    clean_name: str,
    schema: str = "dbo",
) -> Tuple[bool, str, str]:
    """
    Check if object exists and get its type code and type description.
    Returns (exists, obj_type, type_desc).
    """
    return c_db.check_object_exists_and_type(parsed_conn, clean_name, schema)


def check_is_encrypted(
    parsed_conn: Dict[str, Any],
    clean_name: str,
    schema: str = "dbo",
) -> bool:
    """Check if SQL routine/view is encrypted."""
    return c_db.is_object_encrypted(parsed_conn, clean_name, schema)


def fetch_routine_definition(
    project_path: str,
    clean_name: str,
    schema: str = "dbo",
    db_type: str = "app",
) -> str:
    """
    Fetch the raw definition of proc, function, or view using summary_object (mode='full').
    Does not dump into chat or execution logs.
    """
    res = summary_object(
        file_path=project_path,
        object_name=clean_name,
        mode="full",
        schema=schema,
        db_type=db_type,
    )
    if res.get("success"):
        return res.get("definition") or ""
    return ""


def run_sql_query(
    parsed_conn: Dict[str, Any],
    sql: str,
    max_rows: int = 100,
) -> Dict[str, Any]:
    """Execute SQL query safely with max_rows limit."""
    return execute_query(parsed_conn, sql, max_rows=max_rows)


def resolve_objects_types_from_db(
    dbs: Optional[Dict[str, Any] | List[Dict[str, Any]]],
    object_names: List[str],
) -> Dict[str, Dict[str, str]]:
    """
    Query sys.objects on provided DB connection(s) to get exact object types.
    Returns mapping: {object_name_lower: {"name": str, "schema": str, "type": str, "type_desc": str, "category": str}}.
    Categories: 'view', 'table', 'func', 'proc', 'other'.
    """
    if not dbs or not object_names:
        return {}

    conn_list: List[Dict[str, Any]] = []
    if isinstance(dbs, dict):
        if "server" in dbs and "database" in dbs:
            conn_list.append(dbs)
        else:
            if "app" in dbs and isinstance(dbs["app"], dict) and "server" in dbs["app"]:
                conn_list.append(dbs["app"])
            if "sys" in dbs and isinstance(dbs["sys"], dict) and "server" in dbs["sys"]:
                conn_list.append(dbs["sys"])
            for k, v in dbs.items():
                if k not in ("app", "sys") and isinstance(v, dict) and "server" in v:
                    conn_list.append(v)
    elif isinstance(dbs, list):
        conn_list = [c for c in dbs if isinstance(c, dict) and "server" in c]

    if not conn_list:
        return {}

    clean_names = set()
    for n in object_names:
        clean = str(n).split(".")[-1].strip().strip("[]\"'")
        if clean and not clean.startswith("#") and not clean.startswith("@"):
            clean_names.add(clean)

    if not clean_names:
        return {}

    remaining = set(clean_names)
    results: Dict[str, Dict[str, str]] = {}

    for conn in conn_list:
        if not remaining:
            break
        name_list = list(remaining)
        batch_size = 100
        for i in range(0, len(name_list), batch_size):
            batch = name_list[i : i + batch_size]
            escaped = ["N'" + b.replace("'", "''") + "'" for b in batch]
            in_clause = ", ".join(escaped)
            sql = f"""
SELECT RTRIM(o.name) AS name, SCHEMA_NAME(o.schema_id) AS schema_name, RTRIM(o.type) AS [type], RTRIM(o.type_desc) AS type_desc
FROM sys.objects o
WHERE o.name IN ({in_clause})
"""
            try:
                res = execute_query(conn, sql, max_rows=len(batch) + 20)
                if not res.get("success"):
                    continue
                rows = res.get("result_sets", [{}])[0].get("rows", [])
                for row in rows:
                    name_val = str(row[0] or "").strip()
                    schema_val = str(row[1] or "dbo").strip()
                    type_val = str(row[2] or "").strip().upper()
                    type_desc_val = str(row[3] or "").strip().upper()

                    cat = "other"
                    if type_val == "V" or "VIEW" in type_desc_val:
                        cat = "view"
                    elif type_val in ("U", "S") or "TABLE" in type_desc_val:
                        cat = "table"
                    elif type_val in ("FN", "IF", "TF", "FS", "FT") or "FUNC" in type_desc_val:
                        cat = "func"
                    elif type_val in ("P", "PC") or "PROC" in type_desc_val:
                        cat = "proc"

                    key = name_val.lower()
                    results[key] = {
                        "name": name_val,
                        "schema": schema_val,
                        "type": type_val,
                        "type_desc": type_desc_val,
                        "category": cat,
                    }
                    remaining.discard(name_val)
                    remaining.discard(key)
            except Exception:
                continue

    return results
