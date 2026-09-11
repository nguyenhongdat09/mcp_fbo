"""Open editor helper for clone_things on Windows/Linux."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _resolve_editor_path(cmd_name: str) -> str | None:
    """Resolve executable path from PATH, env var overrides, or default install locations."""
    env_var_map = {
        "cursor": "FBO_CURSOR_PATH",
        "code": "FBO_VSCODE_PATH",
        "antigravity": "FBO_ANTIGRAVITY_PATH",
        "antigravity-ide": "FBO_ANTIGRAVITY_PATH",
    }
    env_var = env_var_map.get(cmd_name.lower())
    if env_var:
        env_path = os.environ.get(env_var)
        if env_path and Path(env_path).exists():
            return str(Path(env_path))

    found = shutil.which(cmd_name)
    if found:
        return found

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates = {
            "cursor": [
                Path(local_app_data) / "Programs" / "cursor" / "resources" / "app" / "bin" / "cursor.cmd",
                Path(local_app_data) / "Programs" / "cursor" / "Cursor.exe",
            ],
            "code": [
                Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
                Path(local_app_data) / "Programs" / "Microsoft VS Code" / "Code.exe",
            ],
            "antigravity": [
                Path(r"E:\Antigravity IDE\bin\antigravity-ide.cmd"),
                Path(r"E:\Antigravity IDE\Antigravity IDE.exe"),
            ],
            "antigravity-ide": [
                Path(r"E:\Antigravity IDE\bin\antigravity-ide.cmd"),
                Path(r"E:\Antigravity IDE\Antigravity IDE.exe"),
            ],
        }
        for path_obj in candidates.get(cmd_name.lower(), []):
            if path_obj.exists():
                return str(path_obj)

    # Extra common portable / custom installs (this machine)
    extra = {
        "cursor": [
            Path(r"E:\cursor\resources\app\bin\cursor.CMD"),
            Path(r"E:\cursor\resources\app\bin\cursor.cmd"),
            Path(r"E:\cursor\Cursor.exe"),
        ],
        "code": [
            Path(r"E:\Microsoft VS Code\bin\code.CMD"),
            Path(r"E:\Microsoft VS Code\bin\code.cmd"),
            Path(r"E:\Microsoft VS Code\Code.exe"),
        ],
        "antigravity": [
            Path(r"E:\Antigravity IDE\bin\antigravity-ide.cmd"),
            Path(r"E:\Antigravity IDE\bin\antigravity-ide.CMD"),
            Path(r"E:\Antigravity IDE\Antigravity IDE.exe"),
        ],
        "antigravity-ide": [
            Path(r"E:\Antigravity IDE\bin\antigravity-ide.cmd"),
            Path(r"E:\Antigravity IDE\bin\antigravity-ide.CMD"),
            Path(r"E:\Antigravity IDE\Antigravity IDE.exe"),
        ],
    }
    for path_obj in extra.get(cmd_name.lower(), []):
        if path_obj.exists():
            return str(path_obj)

    return None


def _spawn_editor(exe: str, file_path: str) -> bool:
    """
    Non-blocking spawn. Critical on Windows:
    - path may contain spaces / parentheses (e.g. E:\\SQL Temp\\vlotus_sp228 (4).sql)
    - .cmd/.bat must go through cmd.exe /c
    - do NOT use shell=True with unquoted paths (silent no-open)
    """
    abs_path = str(Path(file_path).resolve())
    exe_lower = exe.lower()

    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(
            subprocess, "DETACHED_PROCESS", 0x00000008
        )
        if exe_lower.endswith((".cmd", ".bat")):
            args = ["cmd.exe", "/c", exe, abs_path]
        else:
            args = [exe, abs_path]
        try:
            subprocess.Popen(
                args,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                close_fds=True,
            )
            return True
        except Exception:
            return False

    try:
        subprocess.Popen(
            [exe, abs_path],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def open_file_for_user(
    file_path: str,
    open_editor_cmd: str = "auto",
    open_file: bool = True,
) -> tuple[bool, str | None]:
    """
    Open file in editor for user visibility.
    Returns (ok, warning_message).
    """
    if not open_file or open_editor_cmd.lower() == "none":
        return True, None

    cmd_mode = open_editor_cmd.lower().strip()
    abs_path = str(Path(file_path).resolve())
    if not Path(abs_path).exists():
        return False, f"open_file_failed: file does not exist: {abs_path}"

    tried: list[str] = []

    def _try(name: str) -> bool:
        exe = _resolve_editor_path(name)
        if not exe:
            tried.append(f"{name}=not_found")
            return False
        ok = _spawn_editor(exe, abs_path)
        tried.append(f"{name}={'ok' if ok else 'spawn_failed'}:{exe}")
        return ok

    spawned = False
    if cmd_mode == "cursor":
        spawned = _try("cursor")
    elif cmd_mode == "code":
        spawned = _try("code")
    elif cmd_mode in ("antigravity", "antigravity-ide"):
        spawned = _try("antigravity-ide") or _try("antigravity")
    elif cmd_mode == "os":
        spawned = False
    elif cmd_mode == "auto":
        from .file_manager import is_antigravity_ide
        if is_antigravity_ide():
            spawned = _try("antigravity-ide") or _try("antigravity") or _try("cursor") or _try("code")
        else:
            spawned = _try("cursor") or _try("code") or _try("antigravity-ide")
    else:
        spawned = _try(cmd_mode)

    if spawned:
        return True, None

    if hasattr(os, "startfile"):
        try:
            os.startfile(abs_path)  # type: ignore[attr-defined]
            return True, None
        except Exception as e:
            detail = "; ".join(tried) if tried else "no editor tried"
            return False, f"open_file_failed: startfile={e}; tried={detail}"

    detail = "; ".join(tried) if tried else f"cmd={open_editor_cmd}"
    return False, f"open_file_failed: could not open editor; tried={detail}"
