"""
Spawn detached build Kuzu cho MCP — không sync-build trong process MCP.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from xml_fbograph.utils.path_helper import (
    ProjectPathHelper,
    get_customerpro_project_path,
    get_fbo_group_name,
    has_app_data_controllers,
)

BUILDING_MARKER_NAME = ".building"
BUILDING_MARKER_MAX_AGE_SEC = 45 * 60  # 45 phut


class NotFastBusinessProjectError(Exception):
    """reference_file khong hop le de index Kuzu (Other / thieu Controllers)."""

    def __init__(
        self,
        reference_file: str,
        group: str = "Other",
        reason: str = "other",
    ):
        if reason == "missing_controllers":
            message = (
                "reference_file thuoc group CustomerPro nhung thieu App_Data\\Controllers "
                "(can Dir/Grid/Filter...). Khong tao Kuzu."
            )
        elif reason == "not_xml":
            message = (
                "reference_file khong phai la file XML. "
                "Chi index file XML."
            )
        else:
            message = (
                "reference_file khong thuoc group CustomerPro FastBusiness (Other). "
                "Chi index du an dang \\\\server\\CustomerPro\\...\\<Cty>\\<SP> "
                "va phai co App_Data\\Controllers."
            )
        self.payload: Dict[str, Any] = {
            "error": "not_fastbusiness_project",
            "message": message,
            "reference_file": reference_file,
            "group": group or "Other",
            "reason": reason,
        }
        project_path = get_customerpro_project_path(reference_file)
        if project_path:
            self.payload["project_root"] = project_path
            self.payload["controllers_path"] = str(
                Path(project_path) / "App_Data" / "Controllers"
            )
        super().__init__(self.payload["message"])


class KuzuBuildingError(Exception):
    """Kuzu chua san sang; da spawn (hoac dang) build detached."""

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        super().__init__(payload.get("message", "Kuzu building"))


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _read_building_marker(graph_dir: Path) -> Optional[Dict[str, Any]]:
    marker = graph_dir / BUILDING_MARKER_NAME
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        try:
            # Legacy: pid tren dong dau
            pid = int(marker.read_text(encoding="utf-8").strip().splitlines()[0])
            return {"pid": pid, "started_at": marker.stat().st_mtime}
        except Exception:
            return {"pid": 0, "started_at": marker.stat().st_mtime}


def _write_building_marker(graph_dir: Path, pid: int, build_cmd: str) -> None:
    graph_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": pid,
        "started_at": time.time(),
        "build_cmd": build_cmd,
    }
    (graph_dir / BUILDING_MARKER_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_building_marker(graph_dir: Path) -> None:
    marker = graph_dir / BUILDING_MARKER_NAME
    try:
        if marker.is_file():
            marker.unlink()
    except Exception:
        pass


def is_building_in_progress(graph_dir: Path) -> Optional[Dict[str, Any]]:
    """Tra ve marker dict neu build dang chay / marker con song; else None."""
    data = _read_building_marker(graph_dir)
    if not data:
        return None
    pid = int(data.get("pid") or 0)
    started_at = float(data.get("started_at") or 0.0)
    age = time.time() - started_at if started_at else BUILDING_MARKER_MAX_AGE_SEC + 1
    if _pid_alive(pid) or age < BUILDING_MARKER_MAX_AGE_SEC:
        return data
    clear_building_marker(graph_dir)
    return None


def _mcp_json_candidates() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".cursor" / "mcp.json",
        home / ".cursor" / "mcp" / "mcp.json",
    ]
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        candidates.append(Path(appdata) / "Cursor" / "User" / "globalStorage" / "mcp.json")
        candidates.append(Path(appdata) / "Cursor" / "mcp.json")
    return candidates


def resolve_fastbusiness_mcp_command() -> Tuple[Optional[Path], Optional[Path]]:
    """
    Tim (exe, cwd) cua fastbusiness-mcp.
    Uu tien: mcp.json -> FASTBUSINESS_MCP_EXE -> sys.frozen executable.
    """
    env_exe = os.environ.get("FASTBUSINESS_MCP_EXE", "").strip()
    if env_exe:
        exe = Path(env_exe)
        return exe, exe.parent if exe.parent.is_dir() else None

    for cfg_path in _mcp_json_candidates():
        if not cfg_path.is_file():
            continue
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        servers = cfg.get("mcpServers") or {}
        if not isinstance(servers, dict):
            continue
        entry = None
        for key, val in servers.items():
            if "fastbusiness" in str(key).lower() and isinstance(val, dict):
                entry = val
                break
        if not entry:
            continue
        command = (entry.get("command") or "").strip()
        if not command:
            continue
        exe = Path(command)
        cwd_raw = (entry.get("cwd") or "").strip()
        cwd = Path(cwd_raw) if cwd_raw else exe.parent
        return exe, cwd

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return exe, exe.parent

    return None, None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def build_detached_command(reference_file: str) -> Tuple[list, Path]:
    """
    Tra ve (argv, cwd) de spawn build.
    Exe: fastbusiness_mcp.exe build <path>
    Dev: py xml_fbograph/build_kuzu_projects.py <path>
    """
    helper = ProjectPathHelper(reference_file)
    target = str(helper.get_project_root())
    exe, cwd = resolve_fastbusiness_mcp_command()
    if exe and exe.is_file():
        work_dir = cwd if cwd and cwd.is_dir() else exe.parent
        return [str(exe), "build", target], work_dir

    repo = _repo_root()
    script = repo / "xml_fbograph" / "build_kuzu_projects.py"
    py = sys.executable or "py"
    return [py, str(script), target], repo


def spawn_detached_kuzu_build(reference_file: str, graph_dir: Path) -> Dict[str, Any]:
    """
    Spawn CMD/process detached. Tra ve payload status=building.
    Neu marker dang song -> khong spawn lai.
    """
    group = get_fbo_group_name(reference_file)
    helper = ProjectPathHelper(reference_file)
    project_root = str(helper.get_project_root())

    existing = is_building_in_progress(graph_dir)
    if existing:
        return {
            "status": "building",
            "message": (
                "Kuzu chua co. Build detached dang chay. "
                "Hay goi lai tool sau khi build xong (15-30 phut)."
            ),
            "group": group,
            "project_root": project_root,
            "graph_dir": str(graph_dir),
            "build_cmd": existing.get("build_cmd", ""),
            "pid": existing.get("pid"),
            "spawned": False,
        }

    argv, work_dir = build_detached_command(reference_file)
    build_cmd = " ".join(f'"{a}"' if " " in a else a for a in argv)

    creationflags = 0
    if os.name == "nt":
        # Mo console moi — user thay tien do; khong block MCP stdio
        creationflags = (
            subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
            | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )

    popen_kwargs: Dict[str, Any] = {
        "cwd": str(work_dir),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if creationflags:
        popen_kwargs["creationflags"] = creationflags

    proc = subprocess.Popen(argv, **popen_kwargs)
    _write_building_marker(graph_dir, proc.pid, build_cmd)
    sys.stderr.write(
        f"[FboFBOGraph MCP] spawn build pid={proc.pid} cmd={build_cmd}\n"
    )
    return {
        "status": "building",
        "message": (
            "Kuzu chua co. Da mo CMD build detached. "
            "Hay goi lai tool sau khi build xong (15-30 phut)."
        ),
        "group": group,
        "project_root": project_root,
        "graph_dir": str(graph_dir),
        "build_cmd": build_cmd,
        "pid": proc.pid,
        "spawned": True,
    }


def kuzu_db_ready(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    if db_path.is_file():
        return db_path.stat().st_size > 0
    try:
        return any(db_path.iterdir())
    except Exception:
        return False


def _raise_if_not_fbo_project(reference_file: str) -> None:
    pass


def ensure_mcp_kuzu_ready(reference_file: str) -> Path:
    """
    Gate MCP: CustomerPro + App_Data/Controllers + Kuzu ready.
    - Other / thieu Controllers -> NotFastBusinessProjectError
    - Thieu Kuzu -> spawn detached + KuzuBuildingError (khong sync-build)
    - Ready -> tra ve db_path
    """
    _raise_if_not_fbo_project(reference_file)

    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    db_path = graph_dir / "kuzu"

    if kuzu_db_ready(db_path):
        clear_building_marker(graph_dir)
        return db_path

    payload = spawn_detached_kuzu_build(reference_file, graph_dir)
    raise KuzuBuildingError(payload)
