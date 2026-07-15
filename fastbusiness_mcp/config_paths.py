"""Resolve paths for dev vs PyInstaller frozen executable."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return get_exe_dir() / "_internal"


def ensure_frozen_working_directory() -> None:
    """Khi chạy từ .exe, đặt cwd = thư mục chứa exe để path tương đối ổn định."""
    if getattr(sys, "frozen", False):
        os.chdir(get_exe_dir())


def resolve_config_path(config_path: str = "config.yaml") -> Path | None:
    env_path = os.environ.get("FASTBUSINESS_CONFIG_PATH")
    if env_path:
        p = Path(env_path)
        return p if p.is_file() else None

    direct = Path(config_path)
    if direct.is_file():
        return direct

    exe_dir = get_exe_dir()
    bundle_dir = get_bundle_dir()
    for candidate in (
        exe_dir / config_path,
        exe_dir / "_internal" / config_path,
        bundle_dir / config_path,
    ):
        if candidate.is_file():
            return candidate
    return None


def resolve_log_file(default: str = "logs/server.log") -> str | None:
    env_path = os.environ.get("FASTBUSINESS_LOG_FILE")
    if env_path:
        return env_path
    if getattr(sys, "frozen", False):
        return str(get_exe_dir() / "logs" / "server.log")
    return default
