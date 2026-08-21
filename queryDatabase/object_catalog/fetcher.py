"""Object catalog fetcher for SQL Server metadata (sys.objects, sys.sql_modules, sys.parameters)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from queryDatabase.executor import execute_query
from queryDatabase.query_resolver import sanitize_sql_identifier
from queryDatabase.object_catalog.models import DbObjectMeta, ParameterMeta


def _rows_from_result(res: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert execute_query result_sets into a list of column-name mapped dictionaries."""
    if not res.get("success"):
        return []
    result_sets = res.get("result_sets") or []
    if not result_sets:
        return []
    rs = result_sets[0]
    columns = [str(c).lower() for c in rs.get("columns", [])]
    raw_rows = rs.get("rows") or []
    out: list[dict[str, Any]] = []
    for row in raw_rows:
        row_dict = {}
        for i in range(min(len(columns), len(row))):
            row_dict[columns[i]] = row[i]
        out.append(row_dict)
    return out


class ObjectCatalogFetcher:
    """Fetches SQL Server object definitions and parameter metadata."""

    def __init__(self, parsed_conn: dict[str, Any], query_timeout: int = 10):
        self._parsed = parsed_conn
        self._query_timeout = query_timeout

    def fetch_one(self, name: str, schema: str = "dbo") -> DbObjectMeta | None:
        """Fetch definition and metadata for a single object by schema and name."""
        safe_schema = sanitize_sql_identifier(schema)
        safe_name = sanitize_sql_identifier(name)

        sql = f"""
SELECT
    o.object_id,
    SCHEMA_NAME(o.schema_id) AS schema_name,
    o.name,
    o.type,
    o.type_desc,
    m.definition,
    o.modify_date
FROM sys.objects o
JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name = N'{safe_name}'
  AND SCHEMA_NAME(o.schema_id) = N'{safe_schema}'
"""
        start = time.perf_counter()
        res = execute_query(self._parsed, sql)
        elapsed = time.perf_counter() - start

        rows = _rows_from_result(res)
        if not rows:
            return None

        row = rows[0]
        obj_id = row.get("object_id")
        sys_type = (row.get("type") or "").strip()
        type_desc = (row.get("type_desc") or "").strip()
        definition = row.get("definition") or ""
        modify_date = row.get("modify_date")

        params = []
        if obj_id:
            try:
                params = self.fetch_parameters(obj_id)
            except Exception:
                pass

        return DbObjectMeta(
            schema_name=row.get("schema_name") or safe_schema,
            name=row.get("name") or safe_name,
            object_id=obj_id,
            type_desc=type_desc,
            sys_type=sys_type,
            definition=definition,
            modify_date=modify_date,
            parameters=params,
        )

    def fetch_parameters(self, object_id: int) -> list[ParameterMeta]:
        """Fetch parameter metadata from sys.parameters."""
        sql = f"""
SELECT
    p.name,
    TYPE_NAME(p.user_type_id) AS type_name,
    p.max_length,
    p.is_output,
    p.has_default_value,
    p.default_value
FROM sys.parameters p
WHERE p.object_id = {int(object_id)}
ORDER BY p.parameter_id
"""
        res = execute_query(self._parsed, sql)
        rows = _rows_from_result(res)
        params = []
        for r in rows:
            p_name = r.get("name") or ""
            if p_name:
                params.append(
                    ParameterMeta(
                        name=p_name,
                        type_name=(r.get("type_name") or "").upper(),
                        max_length=r.get("max_length", 0),
                        is_output=bool(r.get("is_output", False)),
                        has_default_value=bool(r.get("has_default_value", False)),
                        default_value=str(r.get("default_value")) if r.get("default_value") is not None else None,
                    )
                )
        return params

    def fetch_callers(self, object_id: int, schema: str, name: str) -> list[str]:
        """Fetch inbound callers using sys.sql_expression_dependencies."""
        # Primary: by referenced_id
        sql_primary = f"""
SELECT DISTINCT
    OBJECT_SCHEMA_NAME(d.referencing_id) + '.' + OBJECT_NAME(d.referencing_id) AS caller
FROM sys.sql_expression_dependencies AS d
WHERE d.referenced_id = {int(object_id)}
  AND d.referencing_id <> d.referenced_id
ORDER BY caller
"""
        res = execute_query(self._parsed, sql_primary)
        rows = _rows_from_result(res)
        if rows:
            return [r["caller"] for r in rows if r.get("caller")]

        # Fallback: by safe_name
        safe_schema = sanitize_sql_identifier(schema)
        safe_name = sanitize_sql_identifier(name)
        sql_fallback = f"""
SELECT DISTINCT
    OBJECT_SCHEMA_NAME(d.referencing_id) + '.' + OBJECT_NAME(d.referencing_id) AS caller
FROM sys.sql_expression_dependencies AS d
INNER JOIN sys.objects AS ro ON ro.object_id = d.referenced_id
WHERE ro.name = N'{safe_name}'
  AND (OBJECT_SCHEMA_NAME(ro.object_id) = N'{safe_schema}' OR N'{safe_schema}' = 'dbo')
ORDER BY caller
"""
        res2 = execute_query(self._parsed, sql_fallback)
        rows2 = _rows_from_result(res2)
        if rows2:
            return [r["caller"] for r in rows2 if r.get("caller")]

        return []

    def fetch_many(self, keys: list[tuple[str, str]]) -> dict[str, DbObjectMeta]:
        """Batch fetch multiple object definitions in 1 query."""
        if not keys:
            return {}

        where_clauses = []
        for s, n in keys:
            safe_s = sanitize_sql_identifier(s)
            safe_n = sanitize_sql_identifier(n)
            where_clauses.append(f"(SCHEMA_NAME(o.schema_id) = N'{safe_s}' AND o.name = N'{safe_n}')")

        where_str = " OR ".join(where_clauses)
        sql = f"""
SELECT
    o.object_id,
    SCHEMA_NAME(o.schema_id) AS schema_name,
    o.name,
    o.type,
    o.type_desc,
    m.definition,
    o.modify_date
FROM sys.objects o
JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE {where_str}
"""
        res = execute_query(self._parsed, sql)
        out: dict[str, DbObjectMeta] = {}
        rows = _rows_from_result(res)

        for row in rows:
            schema_name = row.get("schema_name") or "dbo"
            obj_name = row.get("name") or ""
            full_key = f"{schema_name}.{obj_name}"
            out[full_key] = DbObjectMeta(
                schema_name=schema_name,
                name=obj_name,
                object_id=row.get("object_id", 0),
                type_desc=(row.get("type_desc") or "").strip(),
                sys_type=(row.get("type") or "").strip(),
                definition=row.get("definition") or "",
                modify_date=row.get("modify_date"),
                parameters=[],
            )
        return out
