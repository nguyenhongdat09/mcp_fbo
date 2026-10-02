"""type=5 — Tạo file .sql temp rỗng (UTF-8 BOM) trong sql_temp_folder.

Dùng khi agent cần một file .sql để viết script tay (proc/script mới cho
user F5) thay vì tự tạo .sql trong workspace. Tái dùng resolve_output_file:
path_to_pasted rỗng → auto-temp tên theo project trong sql_temp_folder;
path_to_pasted truyền vào → tạo/dùng đúng file đó (file mới có BOM).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from .file_manager import resolve_output_file
from .open_editor import open_file_for_user

logger = logging.getLogger("clone_things.type5")


def run_type5_new_sql_file(
    object: str = "",
    project_source: str = "",
    path_to_pasted: str = "",
    open_file: bool = True,
    open_editor_cmd: str = "auto",
    config: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    start_time: float = 0.0,
) -> dict[str, Any]:
    warnings = warnings if warnings is not None else []
    elapsed = lambda: round((time.perf_counter() - start_time) * 1000, 1)

    out_file, err = resolve_output_file(
        path_to_pasted,
        object or "temp",
        config or {},
        project_source=project_source,
    )
    if err:
        logger.warning("type=5 resolve_output_file failed: %s", err)
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 5,
            "mode": "new_sql_file",
            "error_code": err,
            "message": (
                "Không tạo được file .sql temp — kiểm tra "
                "clone_things.sql_temp_folder trong config_path.yaml "
                f"(lỗi: {err})"
            ),
            "path_to_pasted": None,
            "warnings": warnings,
            "elapsed_ms": elapsed(),
        }

    opened, warn = open_file_for_user(out_file, open_editor_cmd, open_file)
    if warn:
        warnings.append(warn)

    logger.info("type=5 created sql temp file: %s", out_file)
    return {
        "success": True,
        "spec_version": "1.0",
        "type": 5,
        "mode": "new_sql_file",
        "path_to_pasted": out_file,
        "encoding": "utf-8-bom",
        "opened": bool(opened),
        "hint": (
            "File .sql temp rỗng trong sql_temp_folder — viết SQL vào bằng "
            "Edit/Write (KHÔNG tạo .sql trong workspace); xong check syntax "
            "bằng query_database query_type=3 (PARSEONLY) trước khi báo "
            "user F5"
        ),
        "warnings": warnings,
        "elapsed_ms": elapsed(),
    }
