"""Main service implementation and facade dispatcher for clone_things tool."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from query_database.connection import get_connection_config
from query_database.executor import execute_query, execute_sql_batches
from query_database.service import query_database
from query_database.bridges.summary_bridge import summary_object, resolve_object_ref
from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml

from .file_manager import (
    resolve_output_file,
    append_script_block,
    append_not_found_summary,
    ensure_use_db_sections,
    object_already_in_sql_file,
)
from .open_editor import open_file_for_user

from .helpers import (
    DEFAULT_EXTRA_EXCLUDES,
    SYSTEM_NOISE_NAMES,
    is_system_noise_name,
    normalize_fbo_db_table,
    to_partition_structure_name,
    normalize_object_name,
    is_excluded,
    parse_object_list,
    MODE_GET_TOKEN_MAP,
    parse_mode_get,
    parse_mode_recursion,
    parse_mode_read,
)
from .script_transform import (
    wrap_check_exists,
    transform_create_to_alter,
)
from .db_ops import (
    DB_LOOKUP_ORDER,
    load_project_db_connections,
    find_object_on_side,
    classify_dependency,
    check_object_exists_and_type,
    is_object_encrypted,
    fetch_object_script,
    extract_object_dependencies,
    deploy_script_to_target,
)
from .type0_flow import execute_type0_flow
from .type1_flow import execute_type1_flow
from .type2_data_clone import execute_type2_data_clone
from .type3_file_clone import run_type3_file_clone
from .type4_template import run_type4_template

logger = logging.getLogger("clone_things")


def clone_things(
    object: str = "",
    project_source: str = "",
    project_target: str = "",
    type: int = 0,
    path_to_pasted: str = "",
    schema: str = "dbo",
    db_type: str = "app",
    max_objects: int = 50,
    open_file: bool = True,
    exclude_like: list[str] | None = None,
    mode_get: str = "proc",
    mode_recursion: str | int = "0",
    mode_read: str | int = 1,
    execute: bool | str = False,
    execute_clone: bool | str | None = None,
    overwrite: bool | str = False,
    confirm_overwrite: bool | str = False,
    expand_dirs: bool | str = False,
    max_files: int = 100,
    copy_filter: str = "",
    list_presets: bool | str = False,
    planned_sample_size: int = 10,
    table: str = "",
    where: str = "",
    new_name: str = "",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    BƯỚC 1 BẮT BUỘC khi cần clone object SQL (table/proc/func/view) giữa 2 dự án FBO hoặc lấy ra sửa:
    - type=0: Clone thiếu từ source sang target, target-first, đệ quy dependency.
    - type=1: Paste-for-edit trên project_source ra file .sql dạng ALTER (proc/func/view) hoặc CREATE (table).
    - type=2: Clone DATA — DELETE FROM <table> WHERE <where> + INSERT INTO từng dòng ra file .sql.
    - type=3: Copy file bất kỳ (relative, list, glob, preset) từ project_source sang project_target.
    - type=4: Paste template suite đóng gói sẵn (template/<name>/) vào project_target — đổi tên file + rewrite token nội dung theo manifest. object='?' để list template.

    Args:
        object: Tên object SQL hoặc path .xml controller (hoặc file/glob/preset cho type=3)
        project_source: Absolute path tới project FBO nguồn
        project_target: Absolute path tới project FBO đích (bắt buộc với type=0; type=3 được để trống khi clone trong cùng project_source; bỏ qua khi type=1)
        type: 0 = SQL clone giữa 2 project (mặc định), 1 = paste-for-edit, 3 = file clone, 4 = paste template bundled vào project_target
        path_to_pasted: File .sql để append; để trống = tự tạo temp và mở editor
        schema: Schema mặc định (default: "dbo")
        db_type: Ưu tiên lookup — "app" (app→sys) hoặc "sys" (sys→app). Mặc định luôn quét cả hai DB.
        max_objects: Giới hạn số object xử lý (default: 50)
        open_file: Mở file trên editor sau khi ghi (default: True)
        exclude_like: Regex bổ sung loại trừ khỏi dependency con
        mode_get: Lọc loại object khi seed từ XML trong type=1 (default: "proc")
        mode_recursion: Đệ quy dependency trong type=1 ("0" hoặc "1", default: "0")
        mode_read: Chế độ đọc trong type=1 (0: ghi file .sql, 1: metadata summary, 3: full SQL body)
        execute: Thực hiện copy file thật trong type=3 (default: False = dry-run)
        execute_clone: Alias của execute (nếu khác None thì dùng)
        overwrite: Cho phép ghi đè file đã tồn tại trên target trong type=3 (default: False)
        table: Tên bảng cần clone data (type=2). Khi truyền table+where → chạy data clone bất kể type
        where: Điều kiện lọc dòng cho data clone (bắt buộc khi table được truyền)
        new_name: Tên controller mới cho type=4 (vd 'zccnsldkbctdo') — dùng thay token {new} trong tên file và nội dung
        config: Cấu hình hệ thống từ config.yaml
    """
    start_time = time.perf_counter()
    warnings: list[str] = []

    logger.info("clone_things invoked with type=%s, object=%s, project_source=%s", type, object, project_source)

    if config is None:
        try:
            from fastbusiness_mcp.mcp_app import get_config
            config = get_config()
        except Exception:
            config = {}

    # Override max_objects / open_file / execute_clone from config if not passed
    clone_cfg = config.get("clone_things") or {}
    if max_objects == 50 and "max_objects" in clone_cfg:
        max_objects = int(clone_cfg["max_objects"])
    if open_file is True and "open_file" in clone_cfg:
        open_file = bool(clone_cfg["open_file"])
    cfg_execute_clone = bool(clone_cfg.get("execute_clone", clone_cfg.get("Execute_clone", False)))
    execute_clone_effective = execute_clone if execute_clone is not None else cfg_execute_clone
    open_editor_cmd = clone_cfg.get("open_editor_cmd", "auto")

    # Early check for list_presets in type=3
    from .type3_file_clone import coerce_bool
    if type == 3 and (coerce_bool(list_presets) or (isinstance(object, str) and object.strip().lower() == "preset:?")):
        return run_type3_file_clone(
            object=object,
            list_presets=True,
            start_time=start_time,
        )

    # type=4: paste template — object='?'/'list' để xem template có sẵn
    if type == 4:
        return run_type4_template(
            object=object,
            new_name=new_name,
            project_target=project_target,
            execute=execute if execute_clone is None else execute_clone,
            overwrite=overwrite,
            confirm_overwrite=confirm_overwrite,
            warnings=warnings,
            start_time=start_time,
        )

    # 1. Validation
    if type not in (0, 1, 2, 3):
        logger.warning("Unsupported type requested: %s", type)
        return {
            "success": False,
            "spec_version": "1.0",
            "type": type,
            "error_code": "unsupported_type",
            "message": f"type={type} not implemented; only type=0 (SQL clone), type=1 (paste-for-edit), type=2 (data clone), type=3 (file clone), and type=4 (template paste) are supported",
            "path_to_pasted": None,
            "cloned": [],
            "skipped_exists": [],
            "skipped_noise": [],
            "not_found_both": [],
            "warnings": [],
        }

    # Data clone mode: type=2 hoặc agent truyền table (ưu tiên hơn type/object)
    data_mode = (type == 2) or bool(str(table or "").strip())
    if data_mode:
        if not str(table or "").strip():
            logger.warning("type=2 requested without table parameter")
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 2,
                "mode": "data_clone",
                "error_code": "missing_table",
                "message": "table is required when type=2 (data clone)",
                "path_to_pasted": None,
                "warnings": warnings,
            }
        if not str(where or "").strip():
            logger.warning("Data clone requested without where parameter")
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 2,
                "mode": "data_clone",
                "error_code": "missing_where",
                "message": "where is required for data clone (điều kiện lọc dòng, vd: ma_ct = 'DDV')",
                "path_to_pasted": None,
                "warnings": warnings,
            }

    if not data_mode and (not object or not str(object).strip()):
        logger.warning("Empty object parameter provided")
        err_res: dict[str, Any] = {
            "success": False,
            "spec_version": "1.0",
            "type": type,
            "error_code": "invalid_object",
            "message": "object is required",
            "path_to_pasted": None,
            "warnings": [],
        }
        if type == 1:
            err_res["pasted"] = []
            err_res["skipped_already_in_file"] = []
            err_res["not_found_source"] = []
        else:
            err_res["cloned"] = []
            err_res["skipped_exists"] = []
            err_res["skipped_noise"] = []
            err_res["not_found_both"] = []
        return err_res

    if type == 1 and not data_mode:
        parsed_mode_read, mode_read_err = parse_mode_read(mode_read)
        if mode_read_err:
            logger.warning("Invalid mode_read: %s", mode_read_err)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "invalid_mode_read",
                "message": mode_read_err,
                "mode_read": mode_read,
                "path_to_pasted": None,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "warnings": warnings,
            }

        parsed_kinds, mode_get_warns = parse_mode_get(mode_get)
        warnings.extend(mode_get_warns)
        if not parsed_kinds:
            logger.warning("Invalid mode_get: %s", mode_get)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "invalid_mode_get",
                "message": f"Invalid mode_get '{mode_get}': no recognized object kinds",
                "mode_read": parsed_mode_read,
                "path_to_pasted": None,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "warnings": warnings,
            }

        parsed_rec, rec_err = parse_mode_recursion(mode_recursion)
        if rec_err:
            logger.warning("Invalid mode_recursion: %s", rec_err)
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "invalid_mode_recursion",
                "message": rec_err,
                "mode_read": parsed_mode_read,
                "path_to_pasted": None,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "warnings": warnings,
            }

        if parsed_mode_read == 3 and parsed_rec == 1:
            logger.warning("mode_read=3 combined with mode_recursion=1 is not allowed")
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 1,
                "error_code": "invalid_mode_read_combo",
                "message": "mode_read=3 requires mode_recursion=0; recursion with full body is not allowed",
                "mode_read": 3,
                "path_to_pasted": None,
                "pasted": [],
                "analyzed": [],
                "skipped_already_in_file": [],
                "not_found_source": [],
                "warnings": warnings,
            }

    if not project_source or not str(project_source).strip():
        logger.warning("Missing project_source parameter")
        err_res = {
            "success": False,
            "spec_version": "1.0",
            "type": type,
            "error_code": "invalid_project_source",
            "message": "project_source is required",
            "path_to_pasted": None,
            "warnings": [],
        }
        if type == 1:
            err_res["pasted"] = []
            err_res["skipped_already_in_file"] = []
            err_res["not_found_source"] = []
        else:
            err_res["cloned"] = []
            err_res["skipped_exists"] = []
            err_res["skipped_noise"] = []
            err_res["not_found_both"] = []
        return err_res

    if not Path(project_source).is_absolute():
        logger.warning("project_source is not an absolute path: %s", project_source)
        err_res = {
            "success": False,
            "spec_version": "1.0",
            "type": type,
            "error_code": "invalid_project_source",
            "message": f"project_source must be an absolute path: {project_source}",
            "path_to_pasted": None,
            "warnings": [],
        }
        if type == 1:
            err_res["pasted"] = []
            err_res["skipped_already_in_file"] = []
            err_res["not_found_source"] = []
        else:
            err_res["cloned"] = []
            err_res["skipped_exists"] = []
            err_res["skipped_noise"] = []
            err_res["not_found_both"] = []
        return err_res

    if type == 0 and not data_mode:
        if not project_target or not str(project_target).strip():
            logger.warning("Missing project_target parameter for type=0")
            err_res = {
                "success": False,
                "spec_version": "1.0",
                "type": 0,
                "error_code": "invalid_project_target",
                "message": "project_target is required when type=0",
                "path_to_pasted": None,
                "warnings": [],
                "cloned": [],
                "skipped_exists": [],
                "skipped_noise": [],
                "not_found_both": [],
            }
            return err_res

        if not Path(project_target).is_absolute():
            logger.warning("project_target is not an absolute path: %s", project_target)
            err_res = {
                "success": False,
                "spec_version": "1.0",
                "type": 0,
                "error_code": "invalid_project_target",
                "message": f"project_target must be an absolute path: {project_target}",
                "path_to_pasted": None,
                "warnings": [],
                "cloned": [],
                "skipped_exists": [],
                "skipped_noise": [],
                "not_found_both": [],
            }
            return err_res
    elif type == 3 and not data_mode:
        if project_target and str(project_target).strip():
            if not Path(project_target).is_absolute():
                logger.warning("project_target is not an absolute path: %s", project_target)
                return {
                    "success": False,
                    "spec_version": "1.0",
                    "type": 3,
                    "error_code": "invalid_project_target",
                    "message": f"project_target must be an absolute path: {project_target}",
                    "path_to_pasted": None,
                    "warnings": [],
                }

    # Sticky context visibility — nuôi context theo project đang thao tác
    # (target thắng vì feed sau) + cảnh báo khi sticky vừa đổi project.
    from xml_fbograph.utils.any_path import project_switch_message, resolve_any_path

    ctx_root: str | None = None
    ctx_switched_from: str | None = None
    for _ctx_path in (project_source, project_target):
        if not _ctx_path or not str(_ctx_path).strip():
            continue
        _ctx_res = resolve_any_path(str(_ctx_path))
        if _ctx_res.ok and _ctx_res.project_root:
            if _ctx_res.switched_from and ctx_switched_from is None:
                ctx_switched_from = _ctx_res.switched_from
            ctx_root = _ctx_res.project_root
    _switch_msg = project_switch_message(ctx_switched_from, ctx_root)
    if _switch_msg:
        warnings.append(_switch_msg)

    # Dispatch based on type
    if data_mode:
        result = execute_type2_data_clone(
            table=table,
            where=where,
            project_source=project_source,
            path_to_pasted=path_to_pasted,
            schema=schema,
            db_type=db_type,
            open_file=open_file,
            open_editor_cmd=open_editor_cmd,
            clone_cfg=clone_cfg,
            config=config,
            warnings=warnings,
            start_time=start_time,
        )
    elif type == 3:
        resolved_exec = execute_clone if execute_clone is not None else execute
        result = run_type3_file_clone(
            object=object,
            project_source=project_source,
            project_target=project_target,
            execute=resolved_exec,
            overwrite=overwrite,
            confirm_overwrite=confirm_overwrite,
            expand_dirs=expand_dirs,
            max_files=max_files,
            copy_filter=copy_filter,
            list_presets=list_presets,
            planned_sample_size=planned_sample_size,
            warnings=warnings,
            start_time=start_time,
        )
    elif type == 1:
        result = execute_type1_flow(
            object=object,
            project_source=project_source,
            project_target=project_target,
            path_to_pasted=path_to_pasted,
            schema=schema,
            db_type=db_type,
            max_objects=max_objects,
            open_file=open_file,
            open_editor_cmd=open_editor_cmd,
            clone_cfg=clone_cfg,
            config=config,
            parsed_mode_read=parsed_mode_read,
            parsed_kinds=parsed_kinds,
            parsed_rec=parsed_rec,
            mode_get=mode_get,
            warnings=warnings,
            start_time=start_time,
        )
    else:
        result = execute_type0_flow(
            object=object,
            project_source=project_source,
            project_target=project_target,
            path_to_pasted=path_to_pasted,
            schema=schema,
            db_type=db_type,
            max_objects=max_objects,
            open_file=open_file,
            open_editor_cmd=open_editor_cmd,
            execute_clone=execute_clone_effective,
            exclude_like=exclude_like,
            config=config,
            warnings=warnings,
            start_time=start_time,
        )

    if isinstance(result, dict):
        result.setdefault("project_root", ctx_root)
        if ctx_root:
            result.setdefault("resolved_via", "absolute")
    return result
