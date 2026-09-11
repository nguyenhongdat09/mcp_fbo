"""SQL routine (proc/func/view) comparison orchestration for compare_things."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple


from .db_access import (
    check_is_encrypted,
    check_object_exists,
    fetch_routine_definition,
    resolve_project_dbs,
)
from .line_diff import build_line_diff
from .sql_fingerprint import (
    compute_sql_fingerprint,
    extract_hunk_signals,
    extract_sql_refs,
    extract_sql_signals,
    normalize_sql_definition,
)
from .sql_seed_scan import scan_seed_candidates


def _split_schema_name(raw_name: str, default_schema: str = "dbo") -> Tuple[str, str, str]:
    """
    Split name into (schema, clean_name, full_name).
    E.g. 'dbo.ProcA' -> ('dbo', 'ProcA', 'dbo.ProcA')
    """
    clean = raw_name.strip().strip("'\"[]")
    if "." in clean:
        parts = clean.split(".", 1)
        schema = parts[0].strip().strip("'\"[]") or default_schema
        name = parts[1].strip().strip("'\"[]")
    else:
        schema = default_schema
        name = clean
    return schema, name, f"{schema}.{name}"


def _find_routine_on_dbs(
    parsed_dbs: Dict[str, Dict[str, Any]],
    clean_name: str,
    schema: str,
    db_type: str,
    side_label: str,
    warnings: List[str],
) -> Tuple[bool, str, str, Optional[str], Optional[Dict[str, Any]]]:
    """
    Find routine on app / sys databases according to db_type.
    Handles conflict if routine exists on both app and sys when db_type='both'.
    Returns (exists, obj_type, type_desc, found_db_type, conn).
    """
    if db_type in ("app", "sys"):
        conn = parsed_dbs.get(db_type)
        if not conn:
            return False, "", "", None, None
        exists, o_type, o_desc = check_object_exists(conn, clean_name, schema)
        return exists, o_type, o_desc, db_type if exists else None, conn if exists else None

    # db_type == "both": check app and sys
    app_conn = parsed_dbs.get("app")
    sys_conn = parsed_dbs.get("sys")

    app_exists = False
    app_type = ""
    app_desc = ""
    if app_conn:
        app_exists, app_type, app_desc = check_object_exists(app_conn, clean_name, schema)

    sys_exists = False
    sys_type = ""
    sys_desc = ""
    if sys_conn:
        sys_exists, sys_type, sys_desc = check_object_exists(sys_conn, clean_name, schema)

    if app_exists and sys_exists:
        warnings.append(
            f"db_conflict_{side_label}: {schema}.{clean_name} exists on app and sys; using app"
        )
        return True, app_type, app_desc, "app", app_conn

    if app_exists:
        return True, app_type, app_desc, "app", app_conn

    if sys_exists:
        return True, sys_type, sys_desc, "sys", sys_conn

    return False, "", "", None, None


def _map_object_type(type_code: str, type_desc: str) -> str:
    """Map SQL Server object type code to 'proc' | 'func' | 'view'."""
    tc = (type_code or "").strip().upper()
    td = (type_desc or "").strip().upper()
    if tc == "P" or "PROC" in td:
        return "proc"
    if tc in ("FN", "IF", "TF") or "FUNC" in td:
        return "func"
    if tc == "V" or "VIEW" in td:
        return "view"
    return "proc"


def compare_sql(
    project_source: str,
    project_target: str,
    object: str = "",
    seed: str = "",
    db_type: str = "app",
    schema: str = "dbo",
    mode: str = "summary",
    max_objects: int = 50,
    max_diff_lines: int = 200,
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
    context_lines: int = 3,
    include_unified_diff: bool = False,
    include_text_snippets: bool = False,
    max_hunks_summary: int = 5,
    max_hunks_detail: int = 30,
    config: Optional[Dict[str, Any]] = None,
    on_progress: Optional[Any] = None,
) -> Dict[str, Any]:

    """
    Compare SQL stored procedures, functions, and views between source and target projects.
    """
    warnings: List[str] = []
    source_dbs = resolve_project_dbs(project_source, warnings)
    target_dbs = resolve_project_dbs(project_target, warnings)

    if not source_dbs:
        return {
            "success": False,
            "kind": "sql",
            "error_code": "invalid_project_source",
            "error": f"Cannot connect to source databases from: {project_source}",
            "summary": None,
            "compared": [],
            "message": "Không kết nối được database từ project_source.",
            "next_actions": ["fix_paths"],
            "warnings": warnings,
        }
    if not target_dbs:
        return {
            "success": False,
            "kind": "sql",
            "error_code": "invalid_project_target",
            "error": f"Cannot connect to target databases from: {project_target}",
            "summary": None,
            "compared": [],
            "message": "Không kết nối được database từ project_target.",
            "next_actions": ["fix_paths"],
            "warnings": warnings,
        }

    # Determine object list
    object_names: List[str] = []
    if object:
        raw_names = [n.strip() for n in re.split(r"[,;\s]+", object) if n.strip()]
        for r in raw_names:
            _, _, full = _split_schema_name(r, default_schema=schema)
            if full not in object_names:
                object_names.append(full)
    elif seed:
        object_names = scan_seed_candidates(
            source_dbs=source_dbs,
            keywords_str=seed,
            db_type=db_type,
            max_objects=max_objects,
        )

    # Deduplicate
    seen_keys: Set[str] = set()
    deduped_names: List[str] = []
    for name in object_names:
        k = name.lower()
        if k not in seen_keys:
            seen_keys.add(k)
            deduped_names.append(name)

    truncated = len(deduped_names) > max_objects
    target_names = deduped_names[:max_objects]

    seed_keywords = [k.strip() for k in re.split(r"[,;\s]+", seed) if k.strip()] if seed else []

    compared_items: List[Dict[str, Any]] = []
    missing_on_target: List[str] = []
    missing_on_source: List[str] = []
    missing_both: List[str] = []
    identical_list: List[str] = []
    different_list: List[str] = []
    encrypted_skip_list: List[str] = []
    errors_list: List[str] = []

    total_sql = len(target_names)
    type_cache_src: Dict[str, Dict[str, str]] = {}
    type_cache_tgt: Dict[str, Dict[str, str]] = {}

    for idx, full_name in enumerate(target_names, 1):
        if on_progress:
            pct = int(100 * (idx - 1) / max(1, total_sql))
            on_progress(pct, 100, f"Đang so sánh SQL ({idx}/{total_sql}): {full_name}")

        sch, clean_name, obj_fullname = _split_schema_name(full_name, default_schema=schema)

        src_exists, src_t, src_desc, src_dt, src_conn = _find_routine_on_dbs(
            source_dbs, clean_name, sch, db_type, "source", warnings
        )
        tgt_exists, tgt_t, tgt_desc, tgt_dt, tgt_conn = _find_routine_on_dbs(
            target_dbs, clean_name, sch, db_type, "target", warnings
        )

        obj_type_str = _map_object_type(src_t or tgt_t, src_desc or tgt_desc)

        if not src_exists and not tgt_exists:
            missing_both.append(obj_fullname)
            compared_items.append({
                "name": obj_fullname,
                "object_type": obj_type_str,
                "status": "missing_both",
                "error": "Object not found on source nor target",
                "next_actions": ["investigate_object_name", "fix_paths"],
            })
            continue

        if src_exists and not tgt_exists:
            missing_on_target.append(obj_fullname)
            compared_items.append({
                "name": obj_fullname,
                "object_type": obj_type_str,
                "status": "missing_on_target",
                "db_type_found": src_dt,
                "next_actions": ["clone_things_type0"],
            })
            continue

        if not src_exists and tgt_exists:
            missing_on_source.append(obj_fullname)
            compared_items.append({
                "name": obj_fullname,
                "object_type": obj_type_str,
                "status": "missing_on_source",
                "db_type_found": tgt_dt,
                "next_actions": ["investigate_source"],
            })
            continue

        # Both exist: check encryption
        enc_src = check_is_encrypted(src_conn, clean_name, sch)
        enc_tgt = check_is_encrypted(tgt_conn, clean_name, sch)

        if enc_src or enc_tgt:
            encrypted_skip_list.append(obj_fullname)
            compared_items.append({
                "name": obj_fullname,
                "object_type": obj_type_str,
                "status": "encrypted_skip",
                "db_type_found_source": src_dt,
                "db_type_found_target": tgt_dt,
                "encrypted_source": enc_src,
                "encrypted_target": enc_tgt,
                "next_actions": ["skip_encrypted"],
            })
            continue

        # Both readable: fetch definitions
        def_src = fetch_routine_definition(project_source, clean_name, sch, db_type=src_dt or "app")
        def_tgt = fetch_routine_definition(project_target, clean_name, sch, db_type=tgt_dt or "app")

        canon_src, lines_src = normalize_sql_definition(
            def_src,
            ignore_line_endings=ignore_line_endings,
            ignore_whitespace=ignore_whitespace,
        )
        canon_tgt, lines_tgt = normalize_sql_definition(
            def_tgt,
            ignore_line_endings=ignore_line_endings,
            ignore_whitespace=ignore_whitespace,
        )

        fp_src = compute_sql_fingerprint(canon_src)
        fp_tgt = compute_sql_fingerprint(canon_tgt)
        refs_src = extract_sql_refs(canon_src, dbs=source_dbs, type_cache=type_cache_src)
        refs_tgt = extract_sql_refs(canon_tgt, dbs=target_dbs, type_cache=type_cache_tgt)
        refs_structured = {
            "source": refs_src,
            "target": refs_tgt,
        }
        fp_structured = {
            "source": {
                "sha_norm": fp_src,
                "refs_view": refs_src.get("views", []),
                "refs_table": refs_src.get("tables", []),
                "refs_func": refs_src.get("funcs", []),
                "refs_proc": refs_src.get("procs", []),
            },
            "target": {
                "sha_norm": fp_tgt,
                "refs_view": refs_tgt.get("views", []),
                "refs_table": refs_tgt.get("tables", []),
                "refs_func": refs_tgt.get("funcs", []),
                "refs_proc": refs_tgt.get("procs", []),
            },
        }

        if fp_src == fp_tgt:
            identical_list.append(obj_fullname)
            compared_items.append({
                "name": obj_fullname,
                "object_type": obj_type_str,
                "status": "identical",
                "db_type_found_source": src_dt,
                "db_type_found_target": tgt_dt,
                "fingerprint_source": fp_src,
                "fingerprint_target": fp_tgt,
                "fingerprint": fp_structured,
                "refs": refs_structured,
                "next_actions": ["noop"],
            })
        else:
            different_list.append(obj_fullname)
            signals = extract_sql_signals(
                canon_src,
                canon_tgt,
                seed_keywords=seed_keywords,
                refs_source=refs_src,
                refs_target=refs_tgt,
            )

            content_diff = build_line_diff(
                lines_a=lines_src,
                lines_b=lines_tgt,
                context_lines=context_lines,
                max_preview_lines_per_hunk=8,
                max_diff_lines=max_diff_lines,
                max_hunks=max_hunks_detail,
                mode=mode,
                is_sql=True,
                file_label_a=f"{project_source}:{obj_fullname}",
                file_label_b=f"{project_target}:{obj_fullname}",
                extract_signals_fn=extract_hunk_signals,
                include_unified_diff=include_unified_diff,
                include_text_snippets=include_text_snippets,
            )

            cap_hunks = max_hunks_summary if mode == "summary" else max_hunks_detail
            content_dict = content_diff.to_dict(
                is_sql=True,
                mode=mode,
                max_hunks=cap_hunks,
                include_text_snippets=include_text_snippets,
                include_unified_diff=include_unified_diff,
            )

            compared_items.append({
                "name": obj_fullname,
                "object_type": obj_type_str,
                "status": "different",
                "db_type_found_source": src_dt,
                "db_type_found_target": tgt_dt,
                "fingerprint_source": fp_src,
                "fingerprint_target": fp_tgt,
                "fingerprint": fp_structured,
                "refs": refs_structured,
                "signals": signals,
                "content": content_dict,
                "next_actions": ["review_hunks_before_alter", "clone_things_type1_mode_read_0"],
            })

    # Summary next_actions
    top_actions: List[str] = []
    if missing_on_target:
        top_actions.append("clone_things_type0")
    if different_list:
        top_actions.append("review_hunks_before_alter")
        top_actions.append("clone_things_type1_mode_read_0")
    if encrypted_skip_list:
        top_actions.append("skip_encrypted")
    if missing_on_source:
        top_actions.append("investigate_source")
    if missing_both:
        top_actions.append("investigate_object_name")
    if not top_actions:
        top_actions = ["noop"]

    src_name = Path(project_source).name or project_source
    tgt_name = Path(project_target).name or project_target
    msg_parts = [f"So {tgt_name} (đang sửa) với {src_name} (nguồn clone):"]
    if missing_on_target:
        msg_parts.append(f"{tgt_name} thiếu {len(missing_on_target)} đối tượng SQL (ứng viên clone_things_type0),")
    if different_list:
        msg_parts.append(f"{len(different_list)} khác definition (xem hunks ranges + signals, không dán SQL),")
    if identical_list:
        msg_parts.append(f"{len(identical_list)} giống nhau,")
    if missing_on_source:
        msg_parts.append(f"{len(missing_on_source)} thiếu trên nguồn ({src_name}),")
    if missing_both:
        msg_parts.append(f"{len(missing_both)} không tìm thấy trên cả hai bên,")
    if encrypted_skip_list:
        msg_parts.append(f"{len(encrypted_skip_list)} mã hóa (bỏ qua).")
    message = " ".join(msg_parts).rstrip(",")

    return {
        "success": True,
        "kind": "sql",
        "role_source": "reference_clone_from",
        "role_target": "editing",
        "project_source": project_source,
        "project_target": project_target,
        "mode": mode,
        "summary": {
            "missing_on_target": missing_on_target,
            "missing_on_source": missing_on_source,
            "missing_both": missing_both,
            "identical": identical_list,
            "different": different_list,
            "encrypted_skip": encrypted_skip_list,
            "errors": errors_list,
            "truncated": truncated,
            "counts": {
                "missing_on_target": len(missing_on_target),
                "missing_on_source": len(missing_on_source),
                "missing_both": len(missing_both),
                "identical": len(identical_list),
                "different": len(different_list),
                "encrypted_skip": len(encrypted_skip_list),
                "errors": len(errors_list),
            },
        },
        "compared": compared_items,
        "message": message,
        "next_actions": top_actions,
        "warnings": warnings,
        "error_code": None,
        "error": None,
    }

