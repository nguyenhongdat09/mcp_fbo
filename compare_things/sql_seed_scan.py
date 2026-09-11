"""SQL seed keyword scanner to discover candidate routines."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from .db_access import run_sql_query


def scan_seed_candidates(
    source_dbs: Dict[str, Dict[str, Any]],
    keywords_str: str,
    db_type: str = "app",
    max_objects: int = 50,
) -> List[str]:
    """
    Scan source database(s) for proc/func/view containing seed keywords.
    Prioritizes object name matches over definition matches to eliminate noise (e.g. cs_CFExtractData).
    Returns list of formatted names 'schema.name'.
    """
    raw_keywords = [k.strip() for k in re.split(r"[,;\s]+", keywords_str) if k.strip()]
    if not raw_keywords:
        return []

    # Choose databases to scan
    dbs_to_scan: List[Tuple[str, Dict[str, Any]]] = []
    if db_type in ("app", "both") and "app" in source_dbs:
        dbs_to_scan.append(("app", source_dbs["app"]))
    if db_type in ("sys", "both") and "sys" in source_dbs:
        dbs_to_scan.append(("sys", source_dbs["sys"]))

    if not dbs_to_scan:
        return []

    per_kw_cap = max(10, max_objects // max(1, len(raw_keywords)))
    seen: Set[str] = set()
    name_hits: List[str] = []
    definition_hits: List[str] = []

    # 1. Tier 1: Match by object name first (higher precision)
    for dt, conn in dbs_to_scan:
        for kw in raw_keywords:
            safe_kw = kw.replace("'", "''")
            name_query = f"""
SELECT TOP ({per_kw_cap})
    OBJECT_SCHEMA_NAME(o.object_id) AS [schema_name],
    o.name AS [object_name],
    o.type AS [object_type]
FROM sys.objects AS o
WHERE o.name LIKE '%{safe_kw}%'
  AND o.type IN ('P', 'FN', 'IF', 'TF', 'V')
ORDER BY 
    CASE WHEN o.name LIKE '{safe_kw}%' THEN 0
         WHEN o.name LIKE '%[_$]' + '{safe_kw}%' THEN 1
         ELSE 2 END,
    o.name;
"""
            res = run_sql_query(conn, name_query, max_rows=per_kw_cap)
            rows = res.get("result_sets", [{}])[0].get("rows", [])
            for r in rows:
                if not r or len(r) < 2:
                    continue
                s_name = str(r[0] or "dbo").strip()
                o_name = str(r[1] or "").strip()
                full_name = f"{s_name}.{o_name}"
                full_key = full_name.lower()
                if full_key not in seen:
                    seen.add(full_key)
                    name_hits.append(full_name)
                    if len(name_hits) >= max_objects:
                        return name_hits

    # 2. Tier 2: Match by definition if we still need more candidates
    remaining_quota = max_objects - len(name_hits)
    if remaining_quota > 0:
        for dt, conn in dbs_to_scan:
            for kw in raw_keywords:
                safe_kw = kw.replace("'", "''")
                def_query = f"""
SELECT TOP ({remaining_quota})
    OBJECT_SCHEMA_NAME(m.object_id) AS [schema_name],
    o.name AS [object_name],
    o.type AS [object_type]
FROM sys.sql_modules AS m
INNER JOIN sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%{safe_kw}%'
  AND o.type IN ('P', 'FN', 'IF', 'TF', 'V')
ORDER BY 
    CASE WHEN m.definition LIKE '%[^a-zA-Z0-9_]' + '{safe_kw}' + '[^a-zA-Z0-9_]%' THEN 0 ELSE 1 END,
    o.name;
"""
                res = run_sql_query(conn, def_query, max_rows=remaining_quota)
                rows = res.get("result_sets", [{}])[0].get("rows", [])
                for r in rows:
                    if not r or len(r) < 2:
                        continue
                    s_name = str(r[0] or "dbo").strip()
                    o_name = str(r[1] or "").strip()
                    full_name = f"{s_name}.{o_name}"
                    full_key = full_name.lower()
                    if full_key not in seen:
                        seen.add(full_key)
                        definition_hits.append(full_name)
                        if len(name_hits) + len(definition_hits) >= max_objects:
                            return name_hits + definition_hits

    return name_hits + definition_hits
