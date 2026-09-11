"""Database catalog queries and semantic schema extraction for kind=table."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from .db_access import run_sql_query


def fetch_table_schema(
    conn: Dict[str, Any],
    clean_name: str,
    schema: str = "dbo",
) -> Optional[Dict[str, Any]]:
    """
    Query SQL Server catalog to extract semantic table structure:
    - columns (sorted alphabetically by name)
    - primary key (sorted by key_ordinal)
    - indexes (sorted by index name)
    - triggers (sorted by trigger name)
    """
    safe_name = clean_name.replace("'", "''")
    safe_schema = schema.replace("'", "''")

    # 1. Fetch columns
    col_sql = f"""
SELECT 
    c.name AS column_name,
    t.name AS type_name,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable
FROM sys.columns c
INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
WHERE c.object_id = OBJECT_ID(QUOTENAME('{safe_schema}') + '.' + QUOTENAME('{safe_name}'))
ORDER BY c.name;
"""
    col_res = run_sql_query(conn, col_sql, max_rows=500)
    col_rows = col_res.get("result_sets", [{}])[0].get("rows", [])
    if not col_rows:
        return None

    columns: Dict[str, Dict[str, Any]] = {}
    for r in col_rows:
        col_name = str(r[0] or "").strip()
        type_name = str(r[1] or "").strip().lower()
        max_len = int(r[2]) if r[2] is not None else 0
        prec = int(r[3]) if r[3] is not None else 0
        scale = int(r[4]) if r[4] is not None else 0
        is_null = bool(r[5])

        # Pretty type string e.g. "varchar(50) null"
        if type_name in ("varchar", "nvarchar", "char", "nchar", "varbinary", "binary"):
            len_str = "max" if max_len == -1 else str(max_len // 2 if "n" in type_name and max_len > 0 else max_len)
            formatted_type = f"{type_name}({len_str})"
        elif type_name in ("decimal", "numeric"):
            formatted_type = f"{type_name}({prec},{scale})"
        else:
            formatted_type = type_name

        null_str = "null" if is_null else "not null"
        full_type_desc = f"{formatted_type} {null_str}"

        columns[col_name.lower()] = {
            "name": col_name,
            "type": full_type_desc,
            "type_name": type_name,
            "is_nullable": is_null,
            "max_length": max_len,
            "precision": prec,
            "scale": scale,
        }

    # 2. Fetch PK
    pk_sql = f"""
SELECT 
    c.name AS column_name,
    ic.key_ordinal
FROM sys.indexes i
INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
WHERE i.object_id = OBJECT_ID(QUOTENAME('{safe_schema}') + '.' + QUOTENAME('{safe_name}'))
  AND i.is_primary_key = 1
ORDER BY ic.key_ordinal;
"""
    pk_res = run_sql_query(conn, pk_sql, max_rows=50)
    pk_rows = pk_res.get("result_sets", [{}])[0].get("rows", [])
    pk_columns = [str(r[0]).strip().lower() for r in pk_rows if r and r[0]]

    # 3. Fetch Indexes
    idx_sql = f"""
SELECT 
    i.name AS index_name,
    i.is_unique,
    i.type_desc,
    c.name AS column_name,
    ic.key_ordinal,
    ic.is_included_column
FROM sys.indexes i
INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
WHERE i.object_id = OBJECT_ID(QUOTENAME('{safe_schema}') + '.' + QUOTENAME('{safe_name}'))
  AND i.is_primary_key = 0
  AND i.type > 0
ORDER BY i.name, ic.key_ordinal;
"""
    idx_res = run_sql_query(conn, idx_sql, max_rows=200)
    idx_rows = idx_res.get("result_sets", [{}])[0].get("rows", [])
    indexes: Dict[str, Dict[str, Any]] = {}
    for r in idx_rows:
        i_name = str(r[0] or "").strip()
        is_uniq = bool(r[1])
        t_desc = str(r[2] or "").strip()
        c_name = str(r[3] or "").strip().lower()
        is_inc = bool(r[5])

        i_key = i_name.lower()
        if i_key not in indexes:
            indexes[i_key] = {
                "name": i_name,
                "is_unique": is_uniq,
                "type_desc": t_desc,
                "columns": [],
                "included_columns": [],
            }
        if is_inc:
            indexes[i_key]["included_columns"].append(c_name)
        else:
            indexes[i_key]["columns"].append(c_name)

    # 4. Fetch Triggers
    trig_sql = f"""
SELECT 
    tr.name AS trigger_name,
    OBJECTPROPERTY(tr.object_id, 'ExecIsTriggerDisabled') AS is_disabled
FROM sys.triggers tr
WHERE tr.parent_id = OBJECT_ID(QUOTENAME('{safe_schema}') + '.' + QUOTENAME('{safe_name}'))
ORDER BY tr.name;
"""
    trig_res = run_sql_query(conn, trig_sql, max_rows=100)
    trig_rows = trig_res.get("result_sets", [{}])[0].get("rows", [])
    triggers: Dict[str, Dict[str, Any]] = {}
    for r in trig_rows:
        tr_name = str(r[0] or "").strip()
        is_dis = bool(r[1])
        triggers[tr_name.lower()] = {
            "name": tr_name,
            "is_disabled": is_dis,
        }

    return {
        "columns": columns,
        "pk": pk_columns,
        "indexes": indexes,
        "triggers": triggers,
    }


def compute_table_fingerprint(schema_dict: Dict[str, Any]) -> str:
    """
    Compute deterministic SHA256 fingerprint sorted by column names (ignores physical column order).
    """
    # Columns sorted by name
    sorted_cols = [
        {"name": k, "type": v["type"]}
        for k, v in sorted(schema_dict.get("columns", {}).items())
    ]
    # PK list (sorted for order-independence)
    pk = sorted(schema_dict.get("pk", []))
    # Indexes sorted by name
    sorted_indexes = [
        {
            "name": k,
            "is_unique": v["is_unique"],
            "type_desc": v["type_desc"],
            "columns": v["columns"],
            "included_columns": v["included_columns"],
        }
        for k, v in sorted(schema_dict.get("indexes", {}).items())
    ]
    # Triggers sorted by name
    sorted_triggers = [
        {"name": k, "is_disabled": v["is_disabled"]}
        for k, v in sorted(schema_dict.get("triggers", {}).items())
    ]

    canonical = {
        "columns": sorted_cols,
        "pk": pk,
        "indexes": sorted_indexes,
        "triggers": sorted_triggers,
    }
    dumped = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(dumped.encode("utf-8")).hexdigest()
