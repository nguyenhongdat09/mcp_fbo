"""Type 0 workflow: cross-project SQL clone flow for clone_things."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from .file_manager import (
    resolve_output_file,
    append_script_block,
    append_not_found_summary,
    ensure_use_db_sections,
)
from .helpers import (
    DEFAULT_EXTRA_EXCLUDES,
    normalize_object_name,
    is_system_noise_name,
    normalize_fbo_db_table,
    is_excluded,
    parse_object_list,
)

logger = logging.getLogger("clone_things.type0")

def execute_type0_flow(
    object: str,
    project_source: str,
    project_target: str,
    path_to_pasted: str,
    schema: str,
    db_type: str,
    max_objects: int,
    open_file: bool,
    open_editor_cmd: str,
    execute_clone: bool,
    exclude_like: list[str] | None,
    config: dict[str, Any],
    warnings: list[str],
    start_time: float,
) -> dict[str, Any]:
    """Execute type=0 SQL clone between two FBO projects."""
    import clone_things.service as svc

    logger.debug("Starting type=0 flow for object=%s, source=%s, target=%s", object, project_source, project_target)

    # 1. Resolve Output File (Fail fast on path_to_pasted or sql_temp_folder)
    output_file, file_err = resolve_output_file(
        path_to_pasted, object, config, project_target=project_target, project_source=project_source
    )
    if file_err:
        msg = "Chưa cấu hình clone_things.sql_temp_folder hoặc thư mục không tồn tại."
        if file_err == "invalid_path_to_pasted":
            msg = "path_to_pasted không hợp lệ (phải là file .sql và thư mục cha phải tồn tại)."
        logger.warning("Output file resolution failed: %s", file_err)
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 0,
            "error_code": file_err,
            "message": msg,
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "skipped_noise": [],
            "not_found_both": [],
            "warnings": [],
        }

    # 2. Resolve Connections (app + sys — cùng Web.config như query_database)
    lookup_order: tuple[str, ...] = (
        ("sys", "app") if str(db_type).lower() == "sys" else svc.DB_LOOKUP_ORDER
    )
    source_dbs = svc.load_project_db_connections(project_source, warnings)
    if not source_dbs:
        logger.error("Cannot resolve connections from project_source: %s", project_source)
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 0,
            "error_code": "invalid_project_source",
            "message": "Cannot resolve app/sys connection from project_source",
            "path_to_pasted": output_file,
            "cloned": [],
            "skipped_exists": [],
            "skipped_noise": [],
            "not_found_both": [],
            "warnings": warnings,
        }

    target_dbs = svc.load_project_db_connections(project_target, warnings)
    if not target_dbs:
        logger.error("Cannot resolve connections from project_target: %s", project_target)
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 0,
            "error_code": "invalid_project_target",
            "message": "Cannot resolve app/sys connection from project_target",
            "path_to_pasted": output_file,
            "cloned": [],
            "skipped_exists": [],
            "skipped_noise": [],
            "not_found_both": [],
            "warnings": warnings,
        }

    target_app_db = (target_dbs.get("app") or {}).get("database") or ""
    target_sys_db = (target_dbs.get("sys") or {}).get("database") or ""
    ensure_use_db_sections(output_file, app_db_name=target_app_db, sys_db_name=target_sys_db)

    # 3. Seed Queue
    clean_object_input = str(object).strip()
    is_xml_seed = clean_object_input.lower().endswith(".xml") or (
        Path(clean_object_input).exists() and Path(clean_object_input).suffix.lower() == ".xml"
    )

    queue: list[str] = []
    mode_seed = "xml" if is_xml_seed else "sql_name"

    if is_xml_seed:
        xml_path = Path(clean_object_input)
        if not xml_path.is_absolute() or not xml_path.exists():
            candidate_target = Path(project_target) / clean_object_input
            candidate_source = Path(project_source) / clean_object_input
            if candidate_target.exists():
                xml_path = candidate_target
            elif candidate_source.exists():
                xml_path = candidate_source

        if not xml_path.exists():
            logger.warning("XML seed file not found: %s", clean_object_input)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 0,
                "error_code": "xml_not_found",
                "message": f"XML seed file not found: {clean_object_input}",
                "path_to_pasted": output_file,
                "cloned": [],
                "skipped_exists": [],
                "skipped_noise": [],
                "not_found_both": [],
                "warnings": warnings,
            }
        try:
            summary_dict = svc.summary_xml(str(xml_path))
            if not summary_dict.get("success"):
                logger.warning("summary_xml returned failure for %s", xml_path)
                return {
                    "success": False,
                    "spec_version": "1.0",
                    "type": 0,
                    "error_code": "xml_summary_failed",
                    "message": f"Summary XML failed: {summary_dict.get('meta', {}).get('warnings')}",
                    "path_to_pasted": output_file,
                    "cloned": [],
                    "skipped_exists": [],
                    "skipped_noise": [],
                    "not_found_both": [],
                    "warnings": warnings,
                }

            sql_sec = summary_dict.get("sql") or {}
            for p_name in sql_sec.get("procs", []):
                if p_name:
                    queue.append(p_name)
            for t_name in sql_sec.get("tables", []):
                if t_name:
                    queue.append(t_name)
            for v_name in sql_sec.get("views", []):
                if v_name:
                    queue.append(v_name)

            ctrl_sec = summary_dict.get("controller") or {}
            raw_db_table = ctrl_sec.get("db_table")
            if raw_db_table:
                norm_table = normalize_fbo_db_table(raw_db_table)
                if norm_table:
                    queue.append(norm_table)
        except Exception as e:
            logger.exception("Failed to parse XML summary: %s", e)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 0,
                "error_code": "xml_summary_failed",
                "message": f"Failed to parse XML summary: {e}",
                "path_to_pasted": output_file,
                "cloned": [],
                "skipped_exists": [],
                "skipped_noise": [],
                "not_found_both": [],
                "warnings": warnings,
            }
    else:
        # object="A,B;C\nD" → split như type=1 (dedupe + normalize schema)
        queue.extend(parse_object_list(clean_object_input, schema))
        if not queue:
            queue.append(clean_object_input)

    # Track direct seeds so they are not filtered by exclude patterns
    seed_objects = set(queue)
    parsed_objects = list(queue)

    # Prepare excludes: chỉ loại trừ routine hệ thống của SQL Server (sp_, xp_, sys., sp_executesql).
    exclude_patterns = list(DEFAULT_EXTRA_EXCLUDES)
    if exclude_like:
        exclude_patterns.extend(exclude_like)

    # 4. Queue Processing Loop
    visited: set[str] = set()
    cloned: list[dict[str, Any]] = []
    skipped_exists: list[dict[str, Any]] = []
    skipped_noise: list[str] = []
    not_found_both: list[str] = []

    processed_count = 0
    is_root_step = True
    truncated_max_objects = False

    while queue and processed_count < max_objects:
        raw_name = queue.pop(0).strip()
        if not raw_name:
            continue

        # Filter out temp tables / variable tables
        if raw_name.startswith("#") or raw_name.startswith("@"):
            continue

        item_schema, item_clean_name, visited_key = normalize_object_name(raw_name, schema)

        if visited_key in visited:
            continue
        visited.add(visited_key)

        # Noise: tempdb / systypes / master… — không đưa vào not_found_both
        if is_system_noise_name(item_clean_name):
            skipped_noise.append(f"{item_schema}.{item_clean_name}")
            continue

        # Exclude check: root seed items are always processed
        is_seed = (mode_seed == "sql_name" and is_root_step) or (raw_name in seed_objects)
        if not is_seed:
            if is_excluded(item_clean_name, exclude_patterns):
                continue

        is_root_step = False
        processed_count += 1

        # Target-first: app rồi sys (hoặc sys→app nếu db_type=sys)
        target_exists, t_type, t_desc, t_db = svc.find_object_on_side(
            target_dbs, item_clean_name, item_schema, order=lookup_order
        )
        if target_exists:
            skipped_exists.append({
                "name": f"{item_schema}.{item_clean_name}",
                "object_type": t_desc or t_type or "OBJECT",
                "where": "target",
                "db": t_db,
            })
            continue  # v1: do not expand dependencies if already on target

        # Source: app rồi sys (hoặc sys→app nếu db_type=sys)
        src_exists, s_type, s_desc, s_db = svc.find_object_on_side(
            source_dbs, item_clean_name, item_schema, order=lookup_order
        )
        if not src_exists:
            not_found_both.append(f"{item_schema}.{item_clean_name}")
            continue

        # Fetch script từ đúng DB (app/sys) nơi tìm thấy trên source
        fetch_db = s_db or "app"
        script = svc.fetch_object_script(
            file_path=project_source,
            clean_name=item_clean_name,
            schema=item_schema,
            obj_type=s_type,
            type_desc=s_desc,
            db_type=fetch_db,
        )
        if script:
            script = svc.wrap_check_exists(
                script=script,
                clean_name=item_clean_name,
                schema=item_schema,
                obj_type=s_type,
                type_desc=s_desc,
            )
            if fetch_db == "sys" and not target_sys_db:
                warnings.append(
                    f"sys_db_name_missing_for_append: {item_schema}.{item_clean_name}"
                )
            append_script_block(
                output_file,
                script,
                f"{item_schema}.{item_clean_name}",
                s_desc or s_type or "OBJECT",
                db=fetch_db,
                app_db_name=target_app_db,
                sys_db_name=target_sys_db,
            )
            deployed_ok = False
            deploy_error = None
            if execute_clone:
                deploy_conn = target_dbs.get(fetch_db) or target_dbs.get("app") or next(
                    iter(target_dbs.values())
                )
                deployed_ok, deploy_error = svc.deploy_script_to_target(deploy_conn, script)
                if not deployed_ok:
                    warnings.append(
                        f"deploy_failed on {item_schema}.{item_clean_name} ({fetch_db}): {deploy_error}"
                    )

            cloned_item = {
                "name": f"{item_schema}.{item_clean_name}",
                "object_type": s_desc or s_type or "OBJECT",
                "from": "source",
                "db": fetch_db,
                "target_db": target_sys_db if fetch_db == "sys" else target_app_db,
                "chars": len(script),
                "line_count": len(script.splitlines()),
                "deployed": deployed_ok if execute_clone else False,
            }
            if deploy_error:
                cloned_item["deploy_error"] = deploy_error
            cloned.append(cloned_item)
        else:
            source_conn = source_dbs.get(fetch_db)
            if source_conn and svc.is_object_encrypted(source_conn, item_clean_name, item_schema):
                warnings.append(
                    f"encrypted_object: {item_schema}.{item_clean_name} (không thể clone definition)"
                )
            else:
                warnings.append(f"fetch_failed: {item_schema}.{item_clean_name}")

        # Enqueue dependencies (cùng db_type nơi tìm thấy object)
        child_deps = svc.extract_object_dependencies(
            file_path=project_source,
            clean_name=item_clean_name,
            schema=item_schema,
            obj_type=s_type,
            type_desc=s_desc,
            db_type=fetch_db,
        )
        for dep in child_deps:
            if not dep or dep.startswith("#") or dep.startswith("@"):
                continue
            _, _, dep_key = normalize_object_name(dep, schema)
            if dep_key not in visited:
                queue.append(dep)

    if queue and processed_count >= max_objects:
        truncated_max_objects = True
        warnings.append(f"truncated_max_objects: reached limit {max_objects}, {len(queue)} objects remaining in queue")

    # 5. Append single not_found_both summary line
    if not_found_both:
        append_not_found_summary(output_file, not_found_both)

    # 6. Open file for user visibility
    open_attempted = open_file and open_editor_cmd.lower() != "none"
    open_ok = False
    if open_attempted:
        open_ok, open_warn = svc.open_file_for_user(output_file, open_editor_cmd, open_file)
        if open_warn:
            warnings.append(open_warn)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # 7. Return standard JSON schema
    return {
        "success": True,
        "spec_version": "1.0",
        "type": 0,
        "object": object,
        "mode_seed": mode_seed,
        "parsed_objects": parsed_objects,
        "project_source": str(Path(project_source).resolve()),
        "project_target": str(Path(project_target).resolve()),
        "path_to_pasted": output_file,
        "deployed": bool(execute_clone),
        "execute_clone": bool(execute_clone),
        "cloned": cloned,
        "skipped_exists": skipped_exists,
        "skipped_noise": skipped_noise,
        "not_found_both": not_found_both,
        "warnings": warnings,
        "meta": {
            "processed_count": processed_count,
            "queue_remaining": len(queue),
            "truncated_max_objects": truncated_max_objects,
            "open_file_attempted": open_attempted,
            "open_file_ok": open_ok,
            "db_lookup_order": list(lookup_order),
            "elapsed_ms": elapsed_ms,
        },
    }
