"""Construct call graph from dictionary of definitions."""

from __future__ import annotations

import re
from typing import Any
from sql_object_summary.models import CallGraph, CallGraphNode
from sql_object_summary.classifier import classify_object
from sql_object_summary.options import DEFAULT_EXCLUDE_LIKE


def _matches_exclude(name: str, patterns: list[str]) -> bool:
    """Check if name matches any SQL LIKE pattern in exclude list."""
    bare = name.split(".")[-1]
    for pat in patterns:
        regex_pat = "^" + pat.replace("%", ".*").replace("_", ".") + "$"
        if re.match(regex_pat, bare, re.IGNORECASE) or re.match(regex_pat, name, re.IGNORECASE):
            return True
    return False


def _normalize_name(name: str) -> str:
    """Normalize object name to schema.name format."""
    cleaned = name.strip().strip("[]\"")
    if "." in cleaned:
        return cleaned
    return f"dbo.{cleaned}"


from sql_object_summary.visitors.summary_visitor import SQL_TABLE_NOISE_TOKENS


def _normalize_table_token(raw: str, cte_names: set[str] | None = None) -> str | None:
    t_clean = raw.strip().strip("[]\"").lower()
    if not t_clean or t_clean.startswith("@") or t_clean.startswith("#") or t_clean.isdigit():
        return None
    if "." in t_clean:
        schema, tbl = t_clean.split(".", 1)
        t_clean = tbl if schema == "dbo" else f"{schema}.{tbl}"

    # Dynamic CTE aliases
    if cte_names and t_clean in cte_names:
        return None

    # Collapse partition table: r00$, d91$, a89$, m89$, c00$
    part_match = re.match(r"^([ardcm]\d\d\$)\d+$", t_clean)
    if part_match:
        t_clean = part_match.group(1)

    if t_clean.isdigit() or t_clean in SQL_TABLE_NOISE_TOKENS:
        return None
    return t_clean


def build_call_graph(
    root_name: str,
    definitions: dict[str, str],
    *,
    max_depth: int = 1,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    truncated_objects: list[str] | None = None,
) -> CallGraph:
    """Build call graph from pure definitions dictionary."""
    normalized_root = _normalize_name(root_name)
    normalized_definitions = {_normalize_name(k): v for k, v in definitions.items()}

    expand_set = {_normalize_name(x) for x in (expand or [])}
    exclude_patterns = exclude_like if exclude_like is not None else list(DEFAULT_EXCLUDE_LIKE)
    trunc_list = truncated_objects or []

    nodes: dict[str, CallGraphNode] = {}
    execution_tree: dict[str, list[str]] = {}
    impacted_tables: set[str] = set()

    def _extract_shallow_calls_and_tables(sql_text: str) -> tuple[list[str], list[str]]:
        calls: list[str] = []
        tables: list[str] = []

        # Strip SQL comments
        clean_sql = re.sub(r"/\*.*?\*/", "", sql_text, flags=re.DOTALL)
        clean_sql = re.sub(r"--[^\r\n]*", "", clean_sql)

        cte_matches = re.findall(r"(?i)(?:;?\s*WITH|,)\s*([a-zA-Z_][\w]*)\s+AS\s*\(", clean_sql)
        cte_names = {c.lower() for c in cte_matches}

        # Find EXEC proc
        exec_matches = re.findall(r"\bEXEC(?:UTE)?\s+(?:dbo\.)?([a-zA-Z0-9_$#]+)", clean_sql, re.IGNORECASE)
        for m in exec_matches:
            if not m.startswith("@") and not m.startswith("#"):
                full_call = _normalize_name(m)
                if full_call not in calls:
                    calls.append(full_call)

        # Find FROM / JOIN tables
        from_matches = re.findall(r"\b(?:FROM|JOIN)\s+(?:dbo\.)?([a-zA-Z0-9_$]+)", clean_sql, re.IGNORECASE)
        for t in from_matches:
            tbl = _normalize_table_token(t, cte_names)
            if tbl and tbl not in tables:
                tables.append(tbl)

        return calls, sorted(tables)

    # Process root first
    root_sql = normalized_definitions.get(normalized_root, "")
    root_calls, root_tables = _extract_shallow_calls_and_tables(root_sql)
    for t in root_tables:
        impacted_tables.add(t)

    root_kind = classify_object(normalized_root)
    nodes[normalized_root] = CallGraphNode(
        kind=root_kind,
        depth=0,
        expanded=True,
        calls=root_calls,
        tables_read=root_tables,
    )
    execution_tree[normalized_root] = root_calls

    # Compute depths using BFS from root
    depth_map: dict[str, int] = {normalized_root: 0}
    queue: list[tuple[str, int]] = [(normalized_root, 0)]
    visited_queue: set[str] = {normalized_root}

    while queue:
        curr, d = queue.pop(0)
        if d >= max_depth:
            continue
        curr_sql = normalized_definitions.get(curr, "")
        curr_calls, _ = _extract_shallow_calls_and_tables(curr_sql) if curr_sql else ([], [])
        for c in curr_calls:
            if c not in depth_map:
                depth_map[c] = d + 1
            if c not in visited_queue and c in normalized_definitions:
                visited_queue.add(c)
                queue.append((c, d + 1))

    # Process child definitions
    unresolved_calls: list[tuple[str, int]] = []

    for name, sql_text in normalized_definitions.items():
        if name == normalized_root:
            continue

        kind = classify_object(name)
        child_calls, child_tables = _extract_shallow_calls_and_tables(sql_text)
        for t in child_tables:
            impacted_tables.add(t)

        node_depth = depth_map.get(name, 1)
        is_excluded = _matches_exclude(name, exclude_patterns)
        is_expanded = (name in expand_set or (kind == "business" and not is_excluded)) and (node_depth < max_depth)

        nodes[name] = CallGraphNode(
            kind=kind,
            depth=node_depth,
            expanded=is_expanded,
            calls=child_calls if is_expanded else [],
            tables_read=child_tables,
        )
        if child_calls and is_expanded:
            execution_tree[name] = child_calls
            for gc in child_calls:
                if gc not in normalized_definitions and gc not in nodes:
                    unresolved_calls.append((gc, node_depth + 1))

    # Add unresolved grandchildren as leaf nodes
    for gc_name, gc_depth in unresolved_calls:
        if gc_name not in nodes:
            nodes[gc_name] = CallGraphNode(
                kind=classify_object(gc_name),
                depth=gc_depth,
                expanded=False,
                calls=[],
                tables_read=[],
            )

    return CallGraph(
        root=normalized_root,
        max_depth_applied=max_depth,
        total_objects_count=len(nodes) + len(trunc_list),
        truncated=bool(trunc_list),
        truncated_objects=trunc_list,
        nodes=nodes,
        execution_tree_shallow=execution_tree,
        impacted_tables=sorted(list(impacted_tables)),
        called_by=[],
    )
