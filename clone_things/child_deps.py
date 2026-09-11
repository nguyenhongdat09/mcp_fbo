"""Dependency collection and classification for clone_things."""

from __future__ import annotations

from typing import Any, Callable

from .helpers import normalize_object_name, is_system_noise_name


def collect_and_classify_child_deps(
    project_source: str,
    item_clean_name: str,
    item_schema: str,
    s_type: str,
    s_desc: str,
    fetch_db: str,
    source_dbs: dict[str, Any],
    lookup_order: tuple[str, ...],
    full_item_name: str,
    parent_map: dict[str, tuple[str, str]],
    visited: set[str],
    queue: list[str],
    recursion: int = 0,
    extract_deps_fn: Callable[..., list[str]] | None = None,
    classify_dep_fn: Callable[..., str] | None = None,
) -> dict[str, str]:
    """
    Extract direct dependencies for a routine (proc/func), classify into
    child_proc, child_func, child_table, child_view, update parent_map,
    and enqueue new dependencies if recursion == 1.

    Returns dict mapping:
      'child_proc': 'dbo.p1,dbo.p2',
      'child_func': 'dbo.f1',
      ...
    (only non-empty keys included).
    """
    if extract_deps_fn is None:
        import clone_things.service as svc
        extract_deps_fn = svc.extract_object_dependencies
    if classify_dep_fn is None:
        import clone_things.service as svc
        classify_dep_fn = svc.classify_dependency

    child_deps = extract_deps_fn(
        file_path=project_source,
        clean_name=item_clean_name,
        schema=item_schema,
        obj_type=s_type,
        type_desc=s_desc,
        db_type=fetch_db,
    )

    child_procs: list[str] = []
    child_funcs: list[str] = []
    child_tables: list[str] = []
    child_views: list[str] = []

    type_desc_upper = (s_desc or s_type or "").upper()
    parent_kind = "func" if ("FUNCTION" in type_desc_upper or s_type.upper() in ("FN", "IF", "TF")) else "proc"

    for dep in child_deps:
        if not dep or dep.startswith("#") or dep.startswith("@"):
            continue
        d_schema, d_clean, dep_key = normalize_object_name(dep, item_schema)
        if is_system_noise_name(d_clean):
            continue

        d_full = f"{d_schema}.{d_clean}"
        dep_kind = classify_dep_fn(source_dbs, d_clean, d_schema, order=lookup_order)

        if dep_kind == "proc":
            if d_full not in child_procs:
                child_procs.append(d_full)
        elif dep_kind == "func":
            if d_full not in child_funcs:
                child_funcs.append(d_full)
        elif dep_kind == "view":
            if d_full not in child_views:
                child_views.append(d_full)
        else:
            if d_full not in child_tables:
                child_tables.append(d_full)

        if recursion == 1:
            if dep_key not in parent_map:
                parent_map[dep_key] = (full_item_name, parent_kind)
            if dep_key not in visited:
                queue.append(dep)

    result: dict[str, str] = {}
    if child_procs:
        result["child_proc"] = ",".join(child_procs)
    if child_funcs:
        result["child_func"] = ",".join(child_funcs)
    if child_tables:
        result["child_table"] = ",".join(child_tables)
    if child_views:
        result["child_view"] = ",".join(child_views)
    return result
