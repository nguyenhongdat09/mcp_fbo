"""File management for clone_things: temp file creation and script appending."""

import os
import re
from pathlib import Path
from typing import Any


def sanitize_filename_base(raw_name: str) -> str:
    """
    Port from VS Code extension sqlTempFile.js:
    Normalize base name: strip .sql, lowercase, replace spaces/hyphens with _, strip _.
    """
    name = str(raw_name).strip().strip("'\"[]")
    if name.lower().endswith(".sql"):
        name = name[:-4]
    if name.lower().endswith(".xml"):
        name = Path(name).stem

    # Remove schema prefix if present (e.g. dbo.zc_foo -> zc_foo)
    if "." in name:
        name = name.split(".")[-1]

    name = name.strip("'\"[]").lower()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_$]", "", name)
    name = name.strip("_")
    return name if name else "temp"


def sql_temp_base_name_from_project(project_path: str) -> str:
    """
    Parity fboFile.NewSqlTemp: tên file theo group.label dự án (vd. vlotus_sp228),
    KHÔNG theo tên object SQL / stem XML.

    Lấy 2 segment cuối của project root (cắt App_Data nếu path là file controller):
    .../VLOTUS/SP228 → vlotus_sp228
    .../SHOWA/FBISP242 → showa_fbisp242
    """
    from find_connect_by_path.path_resolver import get_project_root_from_path

    root = get_project_root_from_path(project_path) or str(project_path).strip()
    p = Path(root)
    # Nếu vẫn là file (root resolve fail), dùng parent
    if p.is_file():
        p = p.parent
    parts = [x for x in p.parts if x not in ("\\", "/", "") and not (len(x) == 2 and x.endswith(":"))]
    # UNC: ('\\\\172.168.5.14', 'CustomerPro', 'FBO', 'VLOTUS', 'SP228')
    if len(parts) >= 2:
        raw = f"{parts[-2]}_{parts[-1]}"
    elif parts:
        raw = parts[-1]
    else:
        raw = "temp"
    return sanitize_filename_base(raw)


def create_sql_temp_file(base_name: str, folder_path: str) -> str:
    """
    Create a new .sql temp file with incremental suffix (2), (3)... if already exists.
    Returns absolute path of the created file.
    """
    target_dir = Path(folder_path)
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError(f"Thư mục sql_temp_folder không tồn tại: {folder_path}")

    stem = sanitize_filename_base(base_name)
    file_path = target_dir / f"{stem}.sql"
    counter = 2
    while file_path.exists():
        file_path = target_dir / f"{stem} ({counter}).sql"
        counter += 1

    file_path.write_text("", encoding="utf-8")
    return str(file_path.resolve())


def resolve_output_file(
    path_to_pasted: str,
    seed_object: str,
    config: dict[str, Any],
    project_target: str = "",
    project_source: str = "",
) -> tuple[str, str | None]:
    """
    Resolve output file path.
    Returns (abs_sql_file_path, error_code).

    Khi path_to_pasted rỗng: tên file theo project_target (parity NewSqlTemp group.label),
    không theo seed_object / XML stem.
    """
    raw_path = (path_to_pasted or "").strip()
    if raw_path:
        p = Path(raw_path)
        if p.suffix.lower() != ".sql":
            return "", "invalid_path_to_pasted"
        if not p.parent.exists():
            return "", "invalid_path_to_pasted"
        if not p.exists():
            p.write_text("", encoding="utf-8")
        return str(p.resolve()), None

    # Parity NewSqlTemp: read config
    clone_cfg = config.get("clone_things") or {}
    sql_temp_folder = clone_cfg.get("sql_temp_folder") or ""
    if not sql_temp_folder or not str(sql_temp_folder).strip():
        return "", "sql_temp_folder_not_configured"

    folder_p = Path(sql_temp_folder.strip())
    if not folder_p.exists() or not folder_p.is_dir():
        return "", "sql_temp_folder_not_configured"

    target_project = (project_target or "").strip() or (project_source or "").strip()
    naming_base = (
        sql_temp_base_name_from_project(target_project)
        if target_project
        else sanitize_filename_base(seed_object)
    )

    try:
        new_file = create_sql_temp_file(naming_base, str(folder_p))
        return new_file, None
    except Exception:
        return "", "sql_temp_folder_not_configured"


def append_script_block(
    file_path: str,
    script: str,
    object_name: str,
    object_type: str,
) -> None:
    """
    Append a script block to file with blank line separator and GO batch terminator.
    """
    p = Path(file_path)
    content = p.read_text(encoding="utf-8") if p.exists() else ""

    prefix = ""
    if content.strip():
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        last_meaningful = lines[-1] if lines else ""

        if last_meaningful.upper() != "GO" and not last_meaningful.startswith("--"):
            # Previous content needs GO
            if not content.endswith("\n"):
                prefix += "\n"
            prefix += "GO\n\n"
        else:
            # Previous content already had GO or comments
            if not content.endswith("\n"):
                prefix += "\n\n"
            elif not content.endswith("\n\n"):
                prefix += "\n"

    # Header comment
    block = prefix
    block += f"-- clone_things: {object_name} | {object_type} | from source\n"
    
    # Normalize newlines: convert \r\n and \r to \n to avoid \r\r\n (double spacing on Windows)
    clean_script = script.replace("\r\n", "\n").replace("\r", "\n").strip()
    block += clean_script
    if not block.endswith("\n"):
        block += "\n"
    block += "GO\n"

    with open(file_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(block)


def append_not_found_summary(file_path: str, not_found_list: list[str]) -> None:
    """Append a single summary line for objects not found in both projects."""
    if not not_found_list:
        return
    p = Path(file_path)
    content = p.read_text(encoding="utf-8") if p.exists() else ""
    prefix = "\n" if (content and not content.endswith("\n")) else ""
    summary_line = f"{prefix}-- not found in 2 project: {', '.join(not_found_list)}\n"

    with open(file_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(summary_line)
