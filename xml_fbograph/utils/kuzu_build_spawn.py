"""
Gate MCP: validate reference_file + sync-build Kuzu in-process khi thiếu DB. Không spawn detached, không trả build_cmd cho Agent.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from xml_fbograph.utils.path_helper import (
    ProjectPathHelper,
    get_customerpro_project_path,
)

BUILDING_MARKER_NAME = ".building"
BUILDING_MARKER_MAX_AGE_SEC = 45 * 60  # 45 phut


class InvalidReferenceFileError(Exception):
    """Loi khi reference_file truyen vao la path tuong doi hoac khong hop le."""

    def __init__(self, reference_file: str, reason: str, message: str, known_projects: Optional[list[str]] = None):
        self.payload = {
            "error": "invalid_reference_file",
            "reason": reason,
            "message": message,
            "reference_file": reference_file,
            "hint": "Luôn truyền absolute path, ví dụ: E:\\FBO\\SP2263\\App_Data\\Controllers\\Filter\\SVInvoiceFilter.xml"
        }
        if known_projects is not None:
            self.payload["known_projects"] = known_projects
        super().__init__(self.payload["message"])


class NotFastBusinessProjectError(Exception):
    """reference_file khong hop le de index Kuzu (Other / thieu Controllers)."""

    def __init__(
        self,
        reference_file: str,
        group: str = "Other",  # giữ param tương thích caller cũ; không đưa vào JSON
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
            "reason": reason,
        }
        project_path = get_customerpro_project_path(reference_file)
        if project_path:
            self.payload["project_root"] = project_path
            self.payload["controllers_path"] = str(
                Path(project_path) / "App_Data" / "Controllers"
            )
        super().__init__(self.payload["message"])


class KuzuBuildFailedError(Exception):
    """Loi xay ra khi build Kuzu in-process."""

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        super().__init__(payload.get("message", "Kuzu build failed"))


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


def _write_building_marker(graph_dir: Path, pid: int) -> None:
    graph_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": pid,
        "started_at": time.time(),
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
    if pid > 0 and _pid_alive(pid):
        return data
    clear_building_marker(graph_dir)
    return None





def kuzu_db_ready(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    if db_path.is_file():
        return db_path.stat().st_size > 0
    try:
        return any(db_path.iterdir())
    except Exception:
        return False


def _validate_and_resolve_reference_file(reference_file: str) -> str:
    if not reference_file:
        raise InvalidReferenceFileError(
            reference_file=str(reference_file),
            reason="missing",
            message="reference_file bi trong. Ban phai truyen duong dan absolute."
        )

    ref_str = str(reference_file).strip()
    
    is_absolute = False
    if len(ref_str) >= 2 and ref_str[0].isalpha() and ref_str[1] == ':':
        is_absolute = True
    elif ref_str.startswith("\\\\") or ref_str.startswith("//"):
        is_absolute = True
    elif ref_str.startswith("/") and not ref_str.startswith("//"):
        is_absolute = False
        
    if not is_absolute:
        from xml_fbograph.utils.path_helper import discover_registered_projects
        known = discover_registered_projects()
        
        rel = ref_str.replace("\\", "/")
        if rel.lower().startswith("app_data/controllers/"):
            rel = rel[len("app_data/controllers/"):]
        elif rel.lower().startswith("controllers/"):
            rel = rel[len("controllers/"):]
            
        matches = []
        known_str_list = []
        for proj in known:
            known_str_list.append(str(proj))
            candidate = proj / "App_Data" / "Controllers" / rel
            if candidate.is_file():
                matches.append(candidate)
                
        if len(matches) == 1:
            return str(matches[0])
            
        raise InvalidReferenceFileError(
            reference_file=ref_str,
            reason="ambiguous_or_unresolved_relative",
            message="reference_file la duong dan tuong doi. Agent CẤM dùng path tương đối.",
            known_projects=known_str_list
        )
        
    from xml_fbograph.utils.path_helper import has_app_data_controllers
    if not has_app_data_controllers(ref_str):
        raise InvalidReferenceFileError(
            reference_file=ref_str,
            reason="missing_controllers",
            message="reference_file absolute nhung khong tim thay thu muc App_Data\\Controllers."
        )
        
    return ref_str


def _sync_build_kuzu_in_mcp(reference_file: str, graph_dir: Path) -> None:
    helper = ProjectPathHelper(reference_file)
    project_root = str(helper.get_project_root())
    
    # 1. Log stderr
    sys.stderr.write(f"[FboFBOGraph MCP] Kuzu missing. Sync-building in-process for {project_root} ...\n")
    sys.stderr.flush()
    
    # 2. Marker
    pid = os.getpid()
    _write_building_marker(graph_dir, pid)
    
    try:
        # 3. Invalidate cache
        db_path = graph_dir / "kuzu"
        db_key = str(db_path)
        graph_dir_key = str(graph_dir)
        
        try:
            from xml_fbograph.query import engine as qe
            qe._store_cache.pop(graph_dir_key, None)
            qe._graph_cache.pop(graph_dir_key, None)
        except Exception:
            pass
            
        try:
            from xml_fbograph.storage.kuzu_index import _db_instances
            _db_instances.pop(db_key.replace("\\", "/").lower(), None)
        except Exception:
            pass
            
        try:
            if 'xml_fbograph.mcp_tools' in sys.modules:
                sys.modules['xml_fbograph.mcp_tools']._kuzu_stores.pop(db_key, None)
        except Exception:
            pass

        # 4. Build
        import contextlib
        from xml_fbograph.builder.graph_builder import build_and_save_graph
        with contextlib.redirect_stdout(sys.stderr): # tránh phá JSON-RPC MCP
            build_and_save_graph(
                helper.get_controllers_path(),
                graph_dir,
                project_label=project_root
            )
        sys.stderr.write("[FboFBOGraph MCP] Sync-build finished.\n")
        sys.stderr.flush()
    finally:
        # 6. Clear marker
        clear_building_marker(graph_dir)

import threading
_sync_build_locks: dict[str, threading.Lock] = {}
_sync_build_locks_guard = threading.Lock()

def _graph_build_lock(graph_dir: Path) -> threading.Lock:
    key = str(graph_dir)
    with _sync_build_locks_guard:
        lock = _sync_build_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _sync_build_locks[key] = lock
        return lock

def ensure_mcp_kuzu_ready(reference_file: str) -> Path:
    """
    Gate MCP: validate reference_file + dam bao Kuzu ready.
    - invalid path -> InvalidReferenceFileError (KHONG build)
    - kuzu ready -> return db_path
    - thieu kuzu -> sync-build in-process (build_and_save_graph), roi return db_path
    - build fail -> exception ro, KHONG tra build_cmd
    """
    reference_file = _validate_and_resolve_reference_file(reference_file)

    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    db_path = graph_dir / "kuzu"

    if kuzu_db_ready(db_path):
        clear_building_marker(graph_dir)
        return db_path

    # Wait if another process is building
    existing_marker = is_building_in_progress(graph_dir)
    if existing_marker and existing_marker.get("pid") != os.getpid():
        sys.stderr.write(f"[FboFBOGraph MCP] Waiting for in-process Kuzu build pid={existing_marker.get('pid')} ...\n")
        sys.stderr.flush()
        start_wait = time.time()
        while is_building_in_progress(graph_dir):
            time.sleep(2)
            if kuzu_db_ready(db_path):
                clear_building_marker(graph_dir)
                return db_path
            if time.time() - start_wait > BUILDING_MARKER_MAX_AGE_SEC:
                break
        
        if kuzu_db_ready(db_path):
            clear_building_marker(graph_dir)
            return db_path

    lock = _graph_build_lock(graph_dir)
    with lock:
        if kuzu_db_ready(db_path):
            clear_building_marker(graph_dir)
            return db_path

        try:
            _sync_build_kuzu_in_mcp(reference_file, graph_dir)
        except Exception as e:
            clear_building_marker(graph_dir)
            raise KuzuBuildFailedError({
                "error": "kuzu_build_failed",
                "message": f"Kuzu build in-process failed: {str(e)}",
                "project_root": str(helper.get_project_root()),
                "graph_dir": str(graph_dir)
            })

        if not kuzu_db_ready(db_path):
            raise KuzuBuildFailedError({
                "error": "kuzu_build_failed",
                "message": "Kuzu build completed but DB is still not ready.",
                "project_root": str(helper.get_project_root()),
                "graph_dir": str(graph_dir)
            })
            
        clear_building_marker(graph_dir)
        return db_path
