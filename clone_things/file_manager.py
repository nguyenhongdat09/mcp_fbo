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


def _check_ancestor_is_antigravity() -> bool:
    """Duyệt cây tiến trình cha để phát hiện Antigravity IDE trên Windows."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        th32cs_snapprocess = 0x00000002

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260),
            ]

        h_snapshot = kernel32.CreateToolhelp32Snapshot(th32cs_snapprocess, 0)
        if h_snapshot == -1 or not h_snapshot:
            return False

        pe32 = PROCESSENTRY32()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
        parents: dict[int, int] = {}
        names: dict[int, str] = {}

        try:
            if kernel32.Process32First(h_snapshot, ctypes.byref(pe32)):
                while True:
                    pid = pe32.th32ProcessID
                    ppid = pe32.th32ParentProcessID
                    name = pe32.szExeFile.decode("latin1", errors="replace").lower()
                    parents[pid] = ppid
                    names[pid] = name
                    if not kernel32.Process32Next(h_snapshot, ctypes.byref(pe32)):
                        break
        finally:
            kernel32.CloseHandle(h_snapshot)

        curr = os.getpid()
        while curr in parents and curr != 0:
            p = parents[curr]
            p_name = names.get(p, "")
            if "antigravity" in p_name or "language_server_windows_x64" in p_name:
                return True
            if "cursor" in p_name:
                return False
            curr = p
    except Exception:
        pass
    return False


def is_antigravity_ide() -> bool:
    """
    Kiểm tra xem môi trường IDE hiện tại có phải là Antigravity hay không.
    Tương đồng logic isAntigravityIde() của extension fbo-autocomplete.
    """
    # Khi chạy unit test và không cấu hình override, không kích hoạt Antigravity redirection
    if "PYTEST_CURRENT_TEST" in os.environ and "MCP_CLIENT" not in os.environ and "TEST_ANTIGRAVITY" not in os.environ:
        return False

    # 1. Biến môi trường chỉ định rõ
    mcp_client = os.environ.get("MCP_CLIENT", "").strip().lower()
    if mcp_client == "antigravity":
        return True
    if mcp_client == "cursor":
        return False

    # 2. Biến môi trường đặc trưng của Antigravity IDE
    antigravity_env_keys = [
        "ANTIGRAVITY_AGENT",
        "ANTIGRAVITY_TRAJECTORY_ID",
        "ANTIGRAVITY_CONVERSATION_ID",
        "ANTIGRAVITY_EDITOR_APP_ROOT",
        "ANTIGRAVITY_LS_VERSION",
        "ANTIGRAVITY_LS_ADDRESS",
        "ANTIGRAVITY_SAFECLIS_SOURCE",
    ]
    for k in antigravity_env_keys:
        if os.environ.get(k):
            return True

    for k in os.environ:
        if k.startswith("ANTIGRAVITY_"):
            return True

    cache_path = os.environ.get("VSCODE_CODE_CACHE_PATH", "")
    if "antigravity" in cache_path.lower():
        return True

    # 3. Duyệt cây tiến trình cha trên Windows
    if os.name == "nt":
        if _check_ancestor_is_antigravity():
            return True

    return False


def resolve_sql_temp_folder(
    folder_path: str,
    is_antigravity: bool | None = None,
    custom_skills_root: str | Path | None = None,
) -> str:
    """
    Xác định thư mục đích để lưu file .sql tạm.
    Nếu IDE là Antigravity:
      - Lấy tên thư mục cuối từ folder_path (ví dụ: 'E:\\SQL Temp' -> 'SQL Temp')
      - Tạo thư mục trong ~/.gemini/config/skills/<folder_name> nếu chưa có
      - Trả về đường dẫn thư mục đó để tạo tiếp các file .sql
      - Nếu folder đó đã tồn tại trong skills thì cứ dùng và tạo thêm .sql vô
    Nếu không phải Antigravity:
      - Trả về nguyên folder_path
    """
    if not folder_path or not str(folder_path).strip():
        return ""

    check_antigravity = is_antigravity if isinstance(is_antigravity, bool) else is_antigravity_ide()
    if not check_antigravity:
        return str(folder_path).strip()

    trimmed_path = str(folder_path).strip().rstrip("/\\")
    folder_name = Path(trimmed_path).name or "SQL Temp"

    if custom_skills_root:
        skills_root = Path(custom_skills_root)
    else:
        user_home = Path(os.environ.get("USERPROFILE") or Path.home())
        skills_root = user_home / ".gemini" / "config" / "skills"

    target_dir = skills_root / folder_name
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    return str(target_dir.resolve())


def _get_default_scripts_folder() -> Path:
    """Lấy thư mục Scripts trong folder chứa mcp và tự động tạo nếu chưa có."""
    import sys
    try:
        from fastbusiness_mcp.config_paths import get_mcp_base_dir
        base_dir = get_mcp_base_dir()
    except Exception:
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parent.parent
    scripts_dir = base_dir / "Scripts"
    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return scripts_dir


def resolve_output_file(
    path_to_pasted: str,
    seed_object: str,
    config: dict[str, Any],
    project_target: str = "",
    project_source: str = "",
    is_antigravity: bool | None = None,
    custom_skills_root: str | Path | None = None,
) -> tuple[str, str | None]:
    """
    Resolve output file path.
    Returns (abs_sql_file_path, error_code).

    Khi path_to_pasted rỗng: tên file theo project_target (parity NewSqlTemp group.label),
    không theo seed_object / XML stem.
    Nếu clone_things.sql_temp_folder để rỗng, tự động tạo thư mục Scripts trong folder chứa mcp.
    Nếu IDE là Antigravity: chuyển hướng tạo file vào ~/.gemini/config/skills/<folder_name>.
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
    env_sql_folder = os.environ.get("CLONE_THINGS_SQL_TEMP_FOLDER", "").strip()
    clone_cfg = config.get("clone_things") or {}
    sql_temp_folder = env_sql_folder or (clone_cfg.get("sql_temp_folder") or "")
    if not sql_temp_folder or not str(sql_temp_folder).strip():
        folder_p = _get_default_scripts_folder()
    else:
        # Hỗ trợ override từ config nếu có
        if is_antigravity is None and "is_antigravity" in clone_cfg:
            is_antigravity = bool(clone_cfg["is_antigravity"])

        resolved_folder = resolve_sql_temp_folder(
            str(sql_temp_folder),
            is_antigravity=is_antigravity,
            custom_skills_root=custom_skills_root,
        )
        folder_p = Path(resolved_folder)
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


def _read_sql_file(file_path: str | Path) -> str:
    """
    Đọc file .sql với utf-8-sig để tự động loại bỏ UTF-8 BOM ở đầu file,
    đồng thời loại bỏ triệt để mọi ký tự \\ufeff nếu có ở giữa file.
    """
    p = Path(file_path)
    if not p.exists():
        return ""
    content = p.read_text(encoding="utf-8-sig")
    return content.replace("\ufeff", "")


def _sql_file_body(content: str) -> str:
    """
    Lấy nội dung body thực của file SQL: loại bỏ hoàn toàn UTF-8 BOM và khoảng trắng.
    Giúp tránh trường hợp file chỉ có BOM hoặc BOM + whitespace khiến content.strip() bị truthy.
    """
    return (content or "").replace("\ufeff", "").strip()


def ensure_use_db_sections(
    file_path: str,
    app_db_name: str = "",
    sys_db_name: str = "",
) -> None:
    """
    Ensure output SQL file has USE [app_db] at top and USE [sys_db] section.
    Idempotent: matches case-insensitively with or without brackets.
    Missing app connection -> skips app section.
    Missing sys connection -> skips sys section.
    """
    p = Path(file_path)
    raw_has_bom = False
    if p.exists():
        try:
            with open(file_path, "rb") as bf:
                raw_has_bom = bf.read().startswith(b"\xef\xbb\xbf")
        except Exception:
            pass

    content = _read_sql_file(p)
    changed = False

    # 1. Ensure USE app_db at top
    clean_app = (app_db_name or "").strip()
    if clean_app:
        app_pat = rf"^\s*USE\s+\[?{re.escape(clean_app)}\]?\s*;?\s*$"
        if not re.search(app_pat, content, flags=re.IGNORECASE | re.MULTILINE):
            app_header = f"USE [{clean_app}]\nGO"
            if _sql_file_body(content):
                content = app_header + "\n\n" + content.lstrip("\n")
            else:
                content = app_header + "\n"
            changed = True

    # 2. Ensure USE sys_db
    clean_sys = (sys_db_name or "").strip()
    if clean_sys:
        sys_pat = rf"^\s*USE\s+\[?{re.escape(clean_sys)}\]?\s*;?\s*$"
        if not re.search(sys_pat, content, flags=re.IGNORECASE | re.MULTILINE):
            sys_header = f"USE [{clean_sys}]\nGO"
            # If not_found_both summary line is present at the end, insert before it
            nf_match = re.search(r"^\s*--\s*not found in 2 project:.*$", content, flags=re.IGNORECASE | re.MULTILINE)
            if nf_match:
                before = content[:nf_match.start()].rstrip()
                after = content[nf_match.start():].lstrip("\n")
                prefix = "\n\n" if _sql_file_body(before) else ""
                content = before + prefix + sys_header + "\n\n" + after
            else:
                prefix = "\n\n" if _sql_file_body(content) else ""
                content = content.rstrip() + prefix + sys_header + "\n"
            changed = True

    if changed or raw_has_bom or not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)


def object_already_in_sql_file(
    file_path: str,
    object_name: str,
    schema: str = "dbo",
) -> tuple[bool, int | None, int | None]:
    """
    Check if an object (PROC/FUNCTION/VIEW/TABLE) already exists in the .sql file (CREATE or ALTER).
    Returns (already_exists, line_start, line_end).
    """
    p = Path(file_path)
    if not p.exists():
        return False, None, None

    content = _read_sql_file(p)
    if not _sql_file_body(content):
        return False, None, None

    cleaned = str(object_name).strip().strip("'\"[]")
    if "." in cleaned:
        parts = cleaned.split(".", 1)
        obj_schema = parts[0].strip().strip("'\"[]") or schema
        clean_name = parts[1].strip().strip("'\"[]")
    else:
        obj_schema = schema
        clean_name = cleaned

    escaped_schema = re.escape(obj_schema)
    escaped_name = re.escape(clean_name)

    # Match CREATE/ALTER [OR ALTER] PROC/FUNCTION/VIEW/TABLE [schema.][name]
    pat = (
        rf"(?im)^\s*(?:/\*.*?\*/\s*)*"
        rf"(CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(PROC(?:EDURE)?|FUNCTION|VIEW|TABLE)\s+"
        rf"(?:\[?{escaped_schema}\]?\s*\.\s*)?\[?{escaped_name}\]?(?=[^a-zA-Z0-9_$]|$)"
    )

    match = re.search(pat, content)
    if not match:
        return False, None, None

    stmt_line = content[: match.start()].count("\n") + 1
    file_lines = content.splitlines()

    # Check if preceding line is a clone_things comment header
    line_start = stmt_line
    if stmt_line >= 2:
        prev_line = file_lines[stmt_line - 2].strip()
        if prev_line.startswith("--") and ("clone_things" in prev_line or clean_name.lower() in prev_line.lower()):
            line_start = stmt_line - 1

    # Find next GO statement for line_end
    after_match = content[match.end() :]
    go_match = re.search(r"^\s*GO\b", after_match, flags=re.IGNORECASE | re.MULTILINE)
    if go_match:
        end_idx = match.end() + go_match.end()
        line_end = content[:end_idx].count("\n") + 1
    else:
        line_end = len(file_lines)

    return True, line_start, line_end


def append_script_block(
    file_path: str,
    script: str,
    object_name: str,
    object_type: str,
    db: str = "app",
    app_db_name: str = "",
    sys_db_name: str = "",
    header_tag: str = "clone_things",
) -> tuple[int, int]:
    """
    Append a script block to file with blank line separator and GO batch terminator.
    Places block in App section (before USE sys_db) or Sys section (after USE sys_db).
    Returns (line_start, line_end) of the inserted block (1-based, inclusive).
    """
    if app_db_name or sys_db_name:
        ensure_use_db_sections(file_path, app_db_name=app_db_name, sys_db_name=sys_db_name)

    p = Path(file_path)
    content = _read_sql_file(p)

    # Normalize newlines: convert \r\n and \r to \n to avoid \r\r\n (double spacing on Windows)
    clean_script = script.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = clean_script.splitlines()
    if lines and re.match(r"^\s*GO\s*$", lines[-1], re.IGNORECASE):
        body = clean_script
    else:
        body = f"{clean_script}\nGO"

    if header_tag in ("paste_edit", "type1", "type=1"):
        header_line = f"-- clone_things type=1: {object_name} | {object_type} | paste-for-edit | from source"
    elif header_tag == "clone_things":
        header_line = f"-- clone_things: {object_name} | {object_type} | from source"
    else:
        header_line = f"-- {header_tag}: {object_name} | {object_type} | from source"

    block = f"{header_line}\n{body}"

    clean_sys = (sys_db_name or "").strip()
    sys_pat = rf"^\s*USE\s+\[?{re.escape(clean_sys)}\]?\s*;?\s*$" if clean_sys else None
    nf_pat = r"^\s*--\s*not found in 2 project:.*$"

    sys_match = re.search(sys_pat, content, flags=re.IGNORECASE | re.MULTILINE) if sys_pat else None

    clean_obj = object_name.strip()
    old_pat = rf"^[ \t]*--[ \t]*clone_things(?:\s+type=1)?:[ \t]*{re.escape(clean_obj)}[ \t]*\|[^\n]*\n.*?(?:^[ \t]*GO[ \t]*(?:;)?(?:\r?\n|$))"
    if re.search(old_pat, content, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE):
        content = re.sub(old_pat, "", content, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
        content = re.sub(r"\n{3,}", "\n\n", content)
        if sys_pat:
            sys_match = re.search(sys_pat, content, flags=re.IGNORECASE | re.MULTILINE)

    is_sys = (str(db).lower() == "sys")

    if is_sys:
        if sys_match:
            # sys_body_start = position after USE sys_db line (and subsequent GO if present)
            after_use = content[sys_match.end():]
            go_match = re.match(r"(\s*\n)?\s*GO\s*(;)?\s*(\n|$)", after_use, flags=re.IGNORECASE)
            sys_body_start = sys_match.end() + (go_match.end() if go_match else 0)

            # Search for not_found summary ONLY in sys section (after sys_body_start)
            nf_match = re.search(nf_pat, content[sys_body_start:], flags=re.IGNORECASE | re.MULTILINE)
            if nf_match:
                insert_pos = sys_body_start + nf_match.start()
                before = content[:insert_pos].rstrip()
                after = content[insert_pos:].lstrip("\n")
                prefix = "\n\n" if _sql_file_body(before) else ""
                new_content = before + prefix + block + "\n\n" + after
            else:
                before = content.rstrip()
                prefix = "\n\n" if _sql_file_body(before) else ""
                new_content = before + prefix + block + "\n"
        else:
            # Fallback if no USE sys_db marker: append at EOF (or before not_found if present)
            nf_match = re.search(nf_pat, content, flags=re.IGNORECASE | re.MULTILINE)
            if nf_match:
                insert_pos = nf_match.start()
                before = content[:insert_pos].rstrip()
                after = content[insert_pos:].lstrip("\n")
                prefix = "\n\n" if _sql_file_body(before) else ""
                new_content = before + prefix + block + "\n\n" + after
            else:
                before = content.rstrip()
                prefix = "\n\n" if _sql_file_body(before) else ""
                new_content = before + prefix + block + "\n"
    else:
        # Insert in APP section:
        # If USE sys_db exists in content, insert strictly BEFORE USE sys_db
        if sys_match:
            insert_pos = sys_match.start()
            before = content[:insert_pos].rstrip()
            after = content[insert_pos:].lstrip("\n")
            prefix = "\n\n" if _sql_file_body(before) else ""
            new_content = before + prefix + block + "\n\n" + after
        else:
            # No USE sys_db found: insert before not_found if present, or at EOF
            nf_match = re.search(nf_pat, content, flags=re.IGNORECASE | re.MULTILINE)
            if nf_match:
                insert_pos = nf_match.start()
                before = content[:insert_pos].rstrip()
                after = content[insert_pos:].lstrip("\n")
                prefix = "\n\n" if _sql_file_body(before) else ""
                new_content = before + prefix + block + "\n\n" + after
            else:
                before = content.rstrip()
                prefix = "\n\n" if _sql_file_body(before) else ""
                new_content = before + prefix + block + "\n"

    # Calculate 1-based line_start and line_end
    leading_text = before + prefix
    line_start = leading_text.count("\n") + 1
    block_line_count = len(block.splitlines())
    line_end = line_start + block_line_count - 1

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)

    return line_start, line_end


def append_not_found_summary(file_path: str, not_found_list: list[str]) -> None:
    """Append a single summary line for objects not found in both projects at EOF."""
    if not not_found_list:
        return
    p = Path(file_path)
    content = _read_sql_file(p)
    summary_line = f"-- not found in 2 project: {', '.join(not_found_list)}"
    if summary_line in content:
        return

    content_clean = content.rstrip()
    prefix = "\n\n" if _sql_file_body(content_clean) else ""
    new_content = content_clean + prefix + summary_line + "\n"

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
