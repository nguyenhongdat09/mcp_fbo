"""Table semantic schema comparison orchestration for kind=table."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple


from .db_access import resolve_project_dbs
from .table_schema import compute_table_fingerprint, fetch_table_schema


def _split_table_name(raw_name: str, default_schema: str = "dbo") -> Tuple[str, str, str]:
    clean = raw_name.strip().strip("'\"[]")
    if "." in clean:
        parts = clean.split(".", 1)
        schema = parts[0].strip().strip("'\"[]") or default_schema
        name = parts[1].strip().strip("'\"[]")
    else:
        schema = default_schema
        name = clean
    return schema, name, f"{schema}.{name}"


def _build_schema_diff(
    sch_src: Dict[str, Any],
    sch_tgt: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate detailed differences between source and target table schemas."""
    cols_src = sch_src.get("columns", {})
    cols_tgt = sch_tgt.get("columns", {})

    cols_src_keys = set(cols_src.keys())
    cols_tgt_keys = set(cols_tgt.keys())

    only_src = sorted([cols_src[k]["name"] for k in (cols_src_keys - cols_tgt_keys)])
    only_tgt = sorted([cols_tgt[k]["name"] for k in (cols_tgt_keys - cols_src_keys)])

    type_mismatches: List[Dict[str, Any]] = []
    for k in sorted(list(cols_src_keys & cols_tgt_keys)):
        c_src = cols_src[k]
        c_tgt = cols_tgt[k]
        if c_src["type"] != c_tgt["type"]:
            type_mismatches.append({
                "column": c_src["name"],
                "source": c_src["type"],
                "target": c_tgt["type"],
            })

    pk_src = sch_src.get("pk", [])
    pk_tgt = sch_tgt.get("pk", [])
    pk_diff = set(pk_src) != set(pk_tgt)
    pk_column_order_diff = (not pk_diff) and (pk_src != pk_tgt)

    # Indexes
    idx_src = sch_src.get("indexes", {})
    idx_tgt = sch_tgt.get("indexes", {})
    idx_src_keys = set(idx_src.keys())
    idx_tgt_keys = set(idx_tgt.keys())

    idx_only_src = sorted([idx_src[k]["name"] for k in (idx_src_keys - idx_tgt_keys)])
    idx_only_tgt = sorted([idx_tgt[k]["name"] for k in (idx_tgt_keys - idx_src_keys)])
    idx_mismatches: List[Dict[str, Any]] = []
    for k in sorted(list(idx_src_keys & idx_tgt_keys)):
        i_src = idx_src[k]
        i_tgt = idx_tgt[k]
        if (
            i_src["is_unique"] != i_tgt["is_unique"]
            or i_src["type_desc"] != i_tgt["type_desc"]
            or i_src["columns"] != i_tgt["columns"]
            or i_src["included_columns"] != i_tgt["included_columns"]
        ):
            idx_mismatches.append({
                "index": i_src["name"],
                "source": i_src,
                "target": i_tgt,
            })

    # Triggers
    trig_src = sch_src.get("triggers", {})
    trig_tgt = sch_tgt.get("triggers", {})
    trig_src_keys = set(trig_src.keys())
    trig_tgt_keys = set(trig_tgt.keys())

    trig_only_src = sorted([trig_src[k]["name"] for k in (trig_src_keys - trig_tgt_keys)])
    trig_only_tgt = sorted([trig_tgt[k]["name"] for k in (trig_tgt_keys - trig_src_keys)])
    trig_mismatches: List[Dict[str, Any]] = []
    for k in sorted(list(trig_src_keys & trig_tgt_keys)):
        t_src = trig_src[k]
        t_tgt = trig_tgt[k]
        if t_src["is_disabled"] != t_tgt["is_disabled"]:
            trig_mismatches.append({
                "trigger": t_src["name"],
                "source": t_src,
                "target": t_tgt,
            })

    return {
        "columns_only_source": only_src,
        "columns_only_target": only_tgt,
        "columns_type_mismatch": type_mismatches,
        "pk_diff": pk_diff,
        "pk_column_order_diff": pk_column_order_diff,
        "pk_source": pk_src,
        "pk_target": pk_tgt,
        "indexes_only_source": idx_only_src,
        "indexes_only_target": idx_only_tgt,
        "indexes_mismatch": idx_mismatches,
        "triggers_only_source": trig_only_src,
        "triggers_only_target": trig_only_tgt,
        "triggers_mismatch": trig_mismatches,
    }


def compare_table(
    project_source: str,
    project_target: str,
    object: str,
    db_type: str = "app",
    schema: str = "dbo",
    max_objects: int = 50,
    config: Optional[Dict[str, Any]] = None,
    on_progress: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Compare table schema (columns, types, PK, indexes, triggers) between source and target.
    Ignores physical column order.
    """
    warnings: List[str] = []
    source_dbs = resolve_project_dbs(project_source, warnings)
    target_dbs = resolve_project_dbs(project_target, warnings)

    actual_db = "app" if db_type not in ("app", "sys") else db_type
    conn_src = source_dbs.get(actual_db)
    conn_tgt = target_dbs.get(actual_db)

    if not conn_src:
        return {
            "success": False,
            "kind": "table",
            "error_code": "invalid_project_source",
            "error": f"Cannot connect to database '{actual_db}' from project_source: {project_source}",
            "summary": None,
            "compared": [],
            "message": "Không kết nối được database từ project_source.",
            "next_actions": ["fix_paths"],
            "warnings": warnings,
        }
    if not conn_tgt:
        return {
            "success": False,
            "kind": "table",
            "error_code": "invalid_project_target",
            "error": f"Cannot connect to database '{actual_db}' from project_target: {project_target}",
            "summary": None,
            "compared": [],
            "message": "Không kết nối được database từ project_target.",
            "next_actions": ["fix_paths"],
            "warnings": warnings,
        }

    raw_objects = [o.strip() for o in re.split(r"[,;\s]+", object) if o.strip()]
    if not raw_objects:
        return {
            "success": False,
            "kind": "table",
            "error_code": "invalid_object",
            "error": "object parameter is empty",
            "summary": None,
            "compared": [],
            "message": "Thiếu tham số object (tên bảng) cho kind=table.",
            "next_actions": ["fix_paths"],
            "warnings": warnings,
        }

    compared_items: List[Dict[str, Any]] = []
    missing_on_target: List[str] = []
    missing_on_source: List[str] = []
    missing_both: List[str] = []
    identical_list: List[str] = []
    different_list: List[str] = []
    errors_list: List[str] = []

    targets = raw_objects[:max_objects]
    total_tbl = len(targets)
    for idx, raw_t in enumerate(targets, 1):
        if on_progress:
            pct = int(100 * (idx - 1) / max(1, total_tbl))
            on_progress(pct, 100, f"Đang so sánh bảng ({idx}/{total_tbl}): {raw_t}")

        sch, clean_name, full_name = _split_table_name(raw_t, default_schema=schema)

        if "$" in clean_name:
            warnings.append(f"partition_table_warning: {full_name} contains '$' partition suffix")

        sch_src = fetch_table_schema(conn_src, clean_name, schema=sch)
        sch_tgt = fetch_table_schema(conn_tgt, clean_name, schema=sch)

        if sch_src is None and sch_tgt is None:
            missing_both.append(full_name)
            compared_items.append({
                "name": full_name,
                "status": "missing_both",
                "error": "Table not found on source nor target",
                "next_actions": ["investigate_object_name", "fix_paths"],
            })
            continue

        if sch_src is not None and sch_tgt is None:
            missing_on_target.append(full_name)
            compared_items.append({
                "name": full_name,
                "status": "missing_on_target",
                "next_actions": ["clone_things_type0"],
            })
            continue

        if sch_src is None and sch_tgt is not None:
            missing_on_source.append(full_name)
            compared_items.append({
                "name": full_name,
                "status": "missing_on_source",
                "next_actions": ["investigate_source"],
            })
            continue

        # Both exist: compute fingerprints
        fp_src = compute_table_fingerprint(sch_src)
        fp_tgt = compute_table_fingerprint(sch_tgt)

        if fp_src == fp_tgt:
            diff_detail = _build_schema_diff(sch_src, sch_tgt)
            item_ident: Dict[str, Any] = {
                "name": full_name,
                "status": "identical",
                "next_actions": ["noop"],
            }
            if diff_detail.get("pk_column_order_diff"):
                item_ident["pk_column_order_diff"] = True
            identical_list.append(full_name)
            compared_items.append(item_ident)
        else:
            different_list.append(full_name)
            diff_detail = _build_schema_diff(sch_src, sch_tgt)

            next_acts: List[str] = []
            if diff_detail["columns_only_source"]:
                next_acts.append("alter_add_column")
            if diff_detail["columns_type_mismatch"]:
                next_acts.append("review_column_type")
            if diff_detail["pk_diff"]:
                next_acts.append("review_pk")
            if diff_detail["indexes_only_source"] or diff_detail["indexes_mismatch"]:
                next_acts.append("review_index")
            if diff_detail["triggers_only_source"] or diff_detail["triggers_mismatch"]:
                next_acts.append("review_trigger")
            if not next_acts:
                next_acts = ["alter_table"]

            compared_items.append({
                "name": full_name,
                "status": "different",
                "schema_diff": diff_detail,
                "next_actions": next_acts,
            })

    top_actions: List[str] = []
    if missing_on_target:
        top_actions.append("clone_things_type0")
    if any(item.get("schema_diff", {}).get("columns_only_source") for item in compared_items if item["status"] == "different"):
        top_actions.append("alter_add_column")
    if any(item.get("schema_diff", {}).get("columns_type_mismatch") for item in compared_items if item["status"] == "different"):
        top_actions.append("review_column_type")
    if any(item.get("schema_diff", {}).get("pk_diff") for item in compared_items if item["status"] == "different"):
        top_actions.append("review_pk")
    if any(item.get("schema_diff", {}).get("indexes_only_source") or item.get("schema_diff", {}).get("indexes_mismatch") for item in compared_items if item["status"] == "different"):
        top_actions.append("review_index")
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
        msg_parts.append(f"{tgt_name} thiếu {len(missing_on_target)} bảng (ứng viên clone_things_type0),")
    if different_list:
        msg_parts.append(f"{len(different_list)} bảng khác schema (xem schema_diff, không dán DDL),")
    if identical_list:
        msg_parts.append(f"{len(identical_list)} giống nhau,")
    if missing_on_source:
        msg_parts.append(f"{len(missing_on_source)} thiếu trên nguồn ({src_name}),")
    if missing_both:
        msg_parts.append(f"{len(missing_both)} không tìm thấy trên cả hai bên.")
    message = " ".join(msg_parts).rstrip(",")

    return {
        "success": True,
        "kind": "table",
        "role_source": "reference_clone_from",
        "role_target": "editing",
        "project_source": project_source,
        "project_target": project_target,
        "mode": "summary",
        "summary": {
            "missing_on_target": missing_on_target,
            "missing_on_source": missing_on_source,
            "missing_both": missing_both,
            "identical": identical_list,
            "different": different_list,
            "errors": errors_list,
            "truncated": len(raw_objects) > max_objects,
            "counts": {
                "missing_on_target": len(missing_on_target),
                "missing_on_source": len(missing_on_source),
                "missing_both": len(missing_both),
                "identical": len(identical_list),
                "different": len(different_list),
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

