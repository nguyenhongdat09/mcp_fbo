"""Client goi daemon qua named pipe (AF_PIPE) + auto-spawn daemon khi can.

Y nghia kien truc: khi daemon song, no la SINGLE ACCESSOR duy nhat cua file
Kuzu — moi query/write cua cac process khac deu di qua pipe, client khong mo
file DB -> het tinh trang RO connection cross-process block writer (Kuzu chi
cho 1 writer, va RO reader o process khac cung giu lock file).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from multiprocessing.connection import Client
from typing import Optional

_DEFAULT_TIMEOUT_SEC = 300.0
_SPAWN_WAIT_SEC = 15.0


def _daemon_disabled() -> bool:
    """True trong chinh process daemon, hoac khi user tat qua env."""
    if os.environ.get("FBOGRAPH_DAEMON", "").strip() == "1":
        return True
    return os.environ.get("FBOGRAPH_NO_DAEMON", "").strip().lower() in ("1", "true", "yes")


def _get_timeout() -> float:
    env = os.environ.get("FBOGRAPH_DAEMON_TIMEOUT", "").strip()
    if env:
        try:
            return max(5.0, float(env))
        except ValueError:
            pass
    return _DEFAULT_TIMEOUT_SEC


def _pipe_name_for(path_hint) -> str:
    from xml_fbograph.service.daemon import get_pipe_name
    return get_pipe_name(Path(path_hint))


def _try_connect(pipe_name: str) -> bool:
    try:
        conn = Client(pipe_name, 'AF_PIPE')
        conn.close()
        return True
    except Exception:
        return False


def _spawn_daemon(ref_file) -> None:
    if getattr(sys, 'frozen', False):
        return  # PyInstaller exe khong spawn duoc script .py
    daemon_script = Path(__file__).resolve().parent / "daemon.py"
    try:
        subprocess.Popen(
            [sys.executable, str(daemon_script), "--ref", str(ref_file)],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception:
        pass


def ensure_daemon_running(ref_file, wait_sec: float = _SPAWN_WAIT_SEC) -> bool:
    """Dam bao daemon song cho project chua path_hint. True = connect duoc pipe."""
    if _daemon_disabled():
        return False
    try:
        pipe_name = _pipe_name_for(ref_file)
    except Exception:
        return False
    if _try_connect(pipe_name):
        return True
    _spawn_daemon(ref_file)
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if _try_connect(pipe_name):
            return True
        time.sleep(0.5)
    return _try_connect(pipe_name)


def daemon_rpc(ref_file, payload: dict, timeout: Optional[float] = None,
               autostart: bool = False) -> Optional[dict]:
    """Gui payload toi daemon, tra ve dict response; None neu daemon khong
    chay / timeout / loi. autostart=True spawn daemon roi retry 1 lan."""
    if _daemon_disabled():
        return None
    to = timeout if timeout and timeout > 0 else _get_timeout()
    for attempt in range(2 if autostart else 1):
        try:
            conn = Client(_pipe_name_for(ref_file), 'AF_PIPE')
            try:
                conn.send(json.dumps(payload, ensure_ascii=False))
                if not conn.poll(to):
                    return None
                res = json.loads(conn.recv())
                return res if isinstance(res, dict) else {"output": res}
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            if attempt == 0 and autostart and ensure_daemon_running(ref_file):
                continue
            return None
    return None
