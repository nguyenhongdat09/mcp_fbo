"""Type 1 workflow: paste-for-edit / analyze flow for clone_things."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from .file_manager import (
    resolve_output_file,
    append_script_block,
    ensure_use_db_sections,
    object_already_in_sql_file,
)
from .helpers import (
    normalize_object_name,
    is_system_noise_name,
    normalize_fbo_db_table,
    parse_object_list,
)
from .child_deps import collect_and_classify_child_deps
from .script_transform import transform_create_to_alter

logger = logging.getLogger("clone_things.type1")


def execute_type1_flow(
    object: str,
    project_source: str,
    project_target: str,
    path_to_pasted: str,
    schema: str,
    db_type: str,
    max_objects: int,
    open_file: bool,
    open_editor_cmd: str,
    clone_cfg: dict[str, Any],
    config: dict[str, Any],
    parsed_mode_read: int,
    parsed_kinds: list[str],
    parsed_rec: int,
    mode_get: str,
    warnings: list[str],
    start_time: float,
) -> dict[str, Any]:
    """Execute type=1 paste-for-edit / analyze flow."""
    import clone_things.service as svc

    logger.debug("Starting type=1 flow for object=%s, mode_read=%s, recursion=%s", object, parsed_mode_read, parsed_rec)

    output_file = None
    if parsed_mode_read == 0:
        output_file, file_err = resolve_output_file(
            path_to_pasted, object, config, project_target="", project_source=project_source
        )
        if file_err:
            msg = "Chưa cấu hình clone_things.sql_temp_folder hoặc thư mục không tồn tại."
            if file_err == "invalid_path_to_pasted":
                msg = "path_to_pasted không hợp lệ (phải là file .sql và thư mục cha phải tồn tại)."
            logger.warning("Output file resolution failed: %s", file_err)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": file_err,
                "message": msg,
                "mode_read": 0,
                "path_to_pasted": None,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "warnings": warnings,
            }

    source_dbs = svc.load_project_db_connections(project_source, warnings)
    if not source_dbs:
        logger.error("Cannot resolve connections from project_source: %s", project_source)
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 1,
            "error_code": "invalid_project_source",
            "message": "Cannot resolve app/sys connection from project_source",
            "mode_read": parsed_mode_read,
            "path_to_pasted": output_file,
            "pasted": [],
            "analyzed": [],
            "skipped_already_in_file": [],
            "not_found_source": [],
            "warnings": warnings,
        }

    source_app_db = (source_dbs.get("app") or {}).get("database") or ""
    source_sys_db = (source_dbs.get("sys") or {}).get("database") or ""
    if parsed_mode_read == 0 and output_file:
        ensure_use_db_sections(output_file, app_db_name=source_app_db, sys_db_name=source_sys_db)

    lookup_order: tuple[str, ...] = (
        ("sys", "app") if str(db_type).lower() == "sys" else svc.DB_LOOKUP_ORDER
    )

    clean_obj_str = str(object).strip()
    is_xml_seed = clean_obj_str.lower().endswith(".xml") or (
        Path(clean_obj_str).exists() and Path(clean_obj_str).suffix.lower() == ".xml"
    )
    mode_seed = "xml" if is_xml_seed else "sql_name"
    seed: list[str] = []

    if is_xml_seed:
        xml_path = Path(clean_obj_str)
        if not xml_path.is_absolute() or not xml_path.exists():
            candidate_source = Path(project_source) / clean_obj_str
            candidate_target = Path(project_target) / clean_obj_str if project_target else None
            if candidate_source.exists():
                xml_path = candidate_source
            elif candidate_target and candidate_target.exists():
                xml_path = candidate_target

        if not xml_path.exists():
            logger.warning("XML seed file not found: %s", clean_obj_str)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "xml_not_found",
                "message": f"XML seed file not found: {clean_obj_str}",
                "mode_read": parsed_mode_read,
                "path_to_pasted": output_file,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "warnings": warnings,
            }
        try:
            summary_dict = svc.summary_xml(str(xml_path))
            if not summary_dict.get("success"):
                logger.warning("summary_xml returned failure for %s", xml_path)
                return {
                    "success": False,
                    "spec_version": "1.0",
                    "type": 1,
                    "error_code": "xml_summary_failed",
                    "message": f"Summary XML failed: {summary_dict.get('meta', {}).get('warnings')}",
                    "mode_read": parsed_mode_read,
                    "path_to_pasted": output_file,
                    "pasted": [],
                    "analyzed": [],
                    "skipped_already_in_file": [],
                    "not_found_source": [],
                    "warnings": warnings,
                }

            sql_sec = summary_dict.get("sql") or {}
            ctrl_sec = summary_dict.get("controller") or {}
            seen_seed: set[str] = set()

            def _add_seed(raw_nm: str):
                if not raw_nm or not str(raw_nm).strip():
                    return
                item_s, item_c, item_k = normalize_object_name(raw_nm, schema)
                if item_k not in seen_seed:
                    seen_seed.add(item_k)
                    seed.append(f"{item_s}.{item_c}")

            if "proc" in parsed_kinds:
                for p_name in sql_sec.get("procs", []):
                    _add_seed(p_name)

            if "table" in parsed_kinds:
                for t_name in sql_sec.get("tables", []):
                    _add_seed(t_name)
                raw_db_table = ctrl_sec.get("db_table")
                if raw_db_table:
                    norm_table = normalize_fbo_db_table(raw_db_table)
                    _add_seed(norm_table)

            if "view" in parsed_kinds:
                for v_name in sql_sec.get("views", []):
                    _add_seed(v_name)

            if "func" in parsed_kinds:
                funcs = sql_sec.get("functions") or sql_sec.get("funcs") or []
                if funcs:
                    for fn_name in funcs:
                        _add_seed(fn_name)
                else:
                    warnings.append("xml_functions_not_in_summary")

        except Exception as e:
            logger.exception("Failed to parse XML summary: %s", e)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "xml_summary_failed",
                "message": f"Failed to parse XML summary: {e}",
                "mode_read": parsed_mode_read,
                "path_to_pasted": output_file,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "encrypt_proc": [],
                "warnings": warnings,
            }
    else:
        seed = parse_object_list(object, schema)
        if not seed:
            logger.warning("No valid SQL object names found in: %s", object)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "invalid_object",
                "message": "No valid SQL object names found in object parameter",
                "mode_read": parsed_mode_read,
                "path_to_pasted": output_file,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "encrypt_proc": [],
                "warnings": warnings,
            }

    # Rule R2 & R3: mode_read=3 allows at most mode_read_full_max_objects (default 3) objects
    if parsed_mode_read == 3:
        max_full_objects = int(clone_cfg.get("mode_read_full_max_objects", 3))
        if len(seed) > max_full_objects:
            logger.warning("mode_read=3 seed count %s exceeds limit %s", len(seed), max_full_objects)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "invalid_mode_read",
                "message": (
                    f"mode_read=3 allows at most {max_full_objects} seed objects (got {len(seed)}). "
                    f"Please use mode_read=1 or specify 1–{max_full_objects} SQL objects."
                ),
                "mode_read": 3,
                "path_to_pasted": None,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "encrypt_proc": [],
                "warnings": warnings,
            }

    pasted: list[dict[str, Any]] = []
    analyzed: list[dict[str, Any]] = []
    skipped_already_in_file: list[dict[str, Any]] = []
    not_found_source: list[str] = []
    encrypt_proc: list[str] = []

    seed_objects = set(seed)
    queue: list[str] = list(seed)
    visited: set[str] = set()
    parent_map: dict[str, tuple[str, str]] = {}  # dep_visited_key -> (parent_full_name, "proc" | "func")
    processed_count = 0

    while queue and processed_count < max_objects:
        raw_name = queue.pop(0).strip()
        if not raw_name:
            continue

        if raw_name.startswith("#") or raw_name.startswith("@"):
            continue

        item_schema, item_clean_name, visited_key = normalize_object_name(raw_name, schema)
        full_item_name = f"{item_schema}.{item_clean_name}"

        if visited_key in visited:
            continue
        visited.add(visited_key)

        is_seed = raw_name in seed_objects
        if not is_seed and is_system_noise_name(item_clean_name):
            continue

        if parsed_mode_read == 0:
            already_in, ex_start, ex_end = object_already_in_sql_file(output_file, full_item_name, item_schema)
            if already_in:
                skip_item: dict[str, Any] = {"name": full_item_name}
                if ex_start is not None and ex_end is not None:
                    skip_item["line_start"] = ex_start
                    skip_item["line_end"] = ex_end
                skipped_already_in_file.append(skip_item)

                if parsed_rec == 1:
                    src_exists, s_type, s_desc, s_db = svc.find_object_on_side(
                        source_dbs, item_clean_name, item_schema, order=lookup_order
                    )
                    if src_exists:
                        type_desc_upper = (s_desc or s_type or "").upper()
                        is_proc_or_func = any(
                            k in type_desc_upper for k in ("PROCEDURE", "PROC", "FUNCTION")
                        ) or s_type.upper() in ("P", "FN", "IF", "TF")
                        if is_proc_or_func:
                            collect_and_classify_child_deps(
                                project_source=project_source,
                                item_clean_name=item_clean_name,
                                item_schema=item_schema,
                                s_type=s_type,
                                s_desc=s_desc,
                                fetch_db=s_db or "app",
                                source_dbs=source_dbs,
                                lookup_order=lookup_order,
                                full_item_name=full_item_name,
                                parent_map=parent_map,
                                visited=visited,
                                queue=queue,
                                recursion=1,
                            )
                continue

        processed_count += 1

        src_exists, s_type, s_desc, s_db = svc.find_object_on_side(
            source_dbs, item_clean_name, item_schema, order=lookup_order
        )
        if not src_exists:
            not_found_source.append(full_item_name)
            continue

        fetch_db = s_db or "app"
        source_conn = source_dbs.get(fetch_db)
        type_desc_upper = (s_desc or s_type or "OBJECT").upper()
        is_table = "TABLE" in type_desc_upper or s_type.upper() == "U"
        is_proc_or_func = any(
            k in type_desc_upper for k in ("PROCEDURE", "PROC", "FUNCTION")
        ) or s_type.upper() in ("P", "FN", "IF", "TF")
        is_view = "VIEW" in type_desc_upper or s_type.upper() == "V"
        is_proc_func_view = is_proc_or_func or is_view

        if parsed_mode_read == 1:
            is_enc = False
            if source_conn:
                is_enc = svc.is_object_encrypted(source_conn, item_clean_name, item_schema)
            if is_enc:
                encrypt_proc.append(full_item_name)
                continue

            analyzed_item: dict[str, Any] = {
                "name": full_item_name,
                "object_type": s_desc or s_type or "OBJECT",
                "db": fetch_db,
            }

            parent_info = parent_map.get(visited_key)
            if parent_info:
                p_name, p_kind = parent_info
                if p_kind == "func":
                    analyzed_item["parent_func"] = p_name
                else:
                    analyzed_item["parent_proc"] = p_name

            if is_proc_or_func:
                child_info = collect_and_classify_child_deps(
                    project_source=project_source,
                    item_clean_name=item_clean_name,
                    item_schema=item_schema,
                    s_type=s_type,
                    s_desc=s_desc,
                    fetch_db=fetch_db,
                    source_dbs=source_dbs,
                    lookup_order=lookup_order,
                    full_item_name=full_item_name,
                    parent_map=parent_map,
                    visited=visited,
                    queue=queue,
                    recursion=parsed_rec,
                )
                analyzed_item.update(child_info)

            analyzed.append(analyzed_item)

        elif parsed_mode_read == 3:
            is_enc = False
            if source_conn:
                is_enc = svc.is_object_encrypted(source_conn, item_clean_name, item_schema)
            if is_enc:
                encrypt_proc.append(full_item_name)
                continue

            script = svc.fetch_object_script(
                file_path=project_source,
                clean_name=item_clean_name,
                schema=item_schema,
                obj_type=s_type,
                type_desc=s_desc,
                db_type=fetch_db,
                wrap_exists=False,
            )
            if not script:
                if source_conn and svc.is_object_encrypted(source_conn, item_clean_name, item_schema):
                    encrypt_proc.append(full_item_name)
                else:
                    warnings.append(f"fetch_failed: {full_item_name}")
                continue

            if is_table:
                out_script = script
                warnings.append(
                    f"table_kept_create: {full_item_name} (type=1 không đổi ALTER TABLE toàn khối)"
                )
                script_style = "create"
            elif is_proc_func_view:
                out_script = transform_create_to_alter(script)
                script_style = "alter"
            else:
                out_script = script
                warnings.append(
                    f"unsupported_object_kind: {full_item_name} ({s_desc or s_type})"
                )
                script_style = "raw"

            max_full_chars = int(clone_cfg.get("mode_read_full_max_chars", 0))
            is_truncated = False
            if max_full_chars > 0 and len(out_script) > max_full_chars:
                out_script = out_script[:max_full_chars]
                is_truncated = True
                warnings.append(f"definition_truncated: {full_item_name} exceeded {max_full_chars} chars")

            analyzed_item = {
                "name": full_item_name,
                "object_type": s_desc or s_type or "OBJECT",
                "db": fetch_db,
                "script_style": script_style,
                "definition": out_script,
                "chars": len(out_script),
            }
            if is_truncated:
                analyzed_item["definition_truncated"] = True

            parent_info = parent_map.get(visited_key)
            if parent_info:
                p_name, p_kind = parent_info
                if p_kind == "func":
                    analyzed_item["parent_func"] = p_name
                else:
                    analyzed_item["parent_proc"] = p_name

            if is_proc_or_func:
                child_info = collect_and_classify_child_deps(
                    project_source=project_source,
                    item_clean_name=item_clean_name,
                    item_schema=item_schema,
                    s_type=s_type,
                    s_desc=s_desc,
                    fetch_db=fetch_db,
                    source_dbs=source_dbs,
                    lookup_order=lookup_order,
                    full_item_name=full_item_name,
                    parent_map=parent_map,
                    visited=visited,
                    queue=queue,
                    recursion=parsed_rec,
                )
                analyzed_item.update(child_info)

            analyzed.append(analyzed_item)

        else:  # parsed_mode_read == 0
            script = svc.fetch_object_script(
                file_path=project_source,
                clean_name=item_clean_name,
                schema=item_schema,
                obj_type=s_type,
                type_desc=s_desc,
                db_type=fetch_db,
                wrap_exists=False,
            )
            if not script:
                is_enc = False
                if source_conn:
                    is_enc = svc.is_object_encrypted(source_conn, item_clean_name, item_schema)
                if is_enc:
                    encrypt_proc.append(full_item_name)
                else:
                    warnings.append(f"fetch_failed: {full_item_name}")
                continue

            if is_table:
                out_script = script
                warnings.append(
                    f"table_kept_create: {full_item_name} (type=1 không đổi ALTER TABLE toàn khối)"
                )
                script_style = "create"
            elif is_proc_func_view:
                out_script = transform_create_to_alter(script)
                script_style = "alter"
            else:
                out_script = script
                warnings.append(
                    f"unsupported_object_kind: {full_item_name} ({s_desc or s_type})"
                )
                script_style = "raw"

            line_start, line_end = append_script_block(
                output_file,
                out_script,
                full_item_name,
                s_desc or s_type or "OBJECT",
                db=fetch_db,
                app_db_name=source_app_db,
                sys_db_name=source_sys_db,
                header_tag="paste_edit",
            )

            pasted_item: dict[str, Any] = {
                "name": full_item_name,
                "object_type": s_desc or s_type or "OBJECT",
                "db": fetch_db,
                "line_start": line_start,
                "line_end": line_end,
                "chars": len(out_script),
                "script_style": script_style,
            }

            parent_info = parent_map.get(visited_key)
            if parent_info:
                p_name, p_kind = parent_info
                if p_kind == "func":
                    pasted_item["parent_func"] = p_name
                else:
                    pasted_item["parent_proc"] = p_name

            if is_proc_or_func:
                child_info = collect_and_classify_child_deps(
                    project_source=project_source,
                    item_clean_name=item_clean_name,
                    item_schema=item_schema,
                    s_type=s_type,
                    s_desc=s_desc,
                    fetch_db=fetch_db,
                    source_dbs=source_dbs,
                    lookup_order=lookup_order,
                    full_item_name=full_item_name,
                    parent_map=parent_map,
                    visited=visited,
                    queue=queue,
                    recursion=parsed_rec,
                )
                pasted_item.update(child_info)

            pasted.append(pasted_item)

    if queue and processed_count >= max_objects:
        warnings.append(
            f"truncated_max_objects: reached limit {max_objects}, {len(queue)} objects remaining in queue"
        )

    open_attempted = (parsed_mode_read == 0) and open_file and open_editor_cmd.lower() != "none"
    open_ok = False
    if open_attempted and output_file:
        open_ok, open_warn = svc.open_file_for_user(output_file, open_editor_cmd, open_file)
        if open_warn:
            warnings.append(open_warn)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    if parsed_mode_read == 1:
        agent_msg = (
            f"Đã analyze {len(analyzed)} object (mode_read=1, không ghi .sql). "
            f"Xem analyzed[].child_* / encrypt_proc. Cần sửa file → gọi lại mode_read=0; cần full body → mode_read=3 (≤3 object)."
        )
        if encrypt_proc:
            agent_msg += (
                f" Lưu ý có {len(encrypt_proc)} object mã hóa (encrypted) không thể đọc definition / không có trong file: "
                f"{', '.join(encrypt_proc)}."
            )
    elif parsed_mode_read == 3:
        agent_msg = (
            f"Đã trả full body trong analyzed[].definition (mode_read=3, không ghi .sql). "
            f"Không dump lại ra chat nếu đã có trong JSON."
        )
        if encrypt_proc:
            agent_msg += (
                f" Lưu ý có {len(encrypt_proc)} object mã hóa (encrypted) không thể đọc definition / không có trong file: "
                f"{', '.join(encrypt_proc)}."
            )
    else:
        if pasted:
            has_child = any(
                any(k in p for k in ("child_proc", "child_func", "child_table", "child_view"))
                for p in pasted
            )
            if parsed_rec == 0 and has_child:
                agent_msg = (
                    f"Đã paste {len(pasted)} object vào {output_file}. "
                    f"Xem child_proc/child_func/child_table để biết deps; recursion=0 chưa paste deps. User tự F5."
                )
            else:
                agent_msg = (
                    f"Đã paste {len(pasted)} object vào {output_file}. "
                    f"Sửa trong file theo pasted[].line_start–line_end. User tự F5."
                )
        else:
            agent_msg = (
                f"Không paste object mới. Xem skipped_already_in_file / not_found_source. "
                f"Nếu object đã có trong file, sửa trực tiếp tại line range (nếu có) hoặc tìm ALTER/CREATE trong {output_file}."
            )

        if encrypt_proc:
            agent_msg += (
                f" Lưu ý có {len(encrypt_proc)} object mã hóa (encrypted) không thể đọc definition / không có trong file: "
                f"{', '.join(encrypt_proc)}."
            )

    meta_dict: dict[str, Any] = {
        "mode_read": parsed_mode_read,
        "mode_get": mode_get,
        "mode_get_kinds": parsed_kinds,
        "mode_recursion": parsed_rec,
        "execute_clone": False,
        "db_lookup_order": list(lookup_order),
        "elapsed_ms": elapsed_ms,
    }
    if parsed_mode_read == 0:
        meta_dict["open_file_attempted"] = open_attempted
        meta_dict["open_file_ok"] = open_ok

    res_dict: dict[str, Any] = {
        "success": True,
        "spec_version": "1.0",
        "type": 1,
        "object": object,
        "mode": "paste_for_edit",
        "mode_seed": mode_seed,
        "mode_read": parsed_mode_read,
        "project_source": str(Path(project_source).resolve()),
        "project_target": str(Path(project_target).resolve()) if project_target else "",
        "path_to_pasted": output_file if parsed_mode_read == 0 else None,
        "pasted": pasted if parsed_mode_read == 0 else [],
        "skipped_already_in_file": skipped_already_in_file if parsed_mode_read == 0 else [],
        "not_found_source": not_found_source,
        "encrypt_proc": encrypt_proc,
        "warnings": warnings,
        "agent_message": agent_msg,
        "meta": meta_dict,
    }
    if parsed_mode_read in (1, 3):
        res_dict["analyzed"] = analyzed

    return res_dict
