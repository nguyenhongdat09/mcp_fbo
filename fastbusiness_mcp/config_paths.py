"""Resolve paths for dev vs PyInstaller frozen executable."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_mcp_base_dir() -> Path:
    """Trả về thư mục gốc chứa MCP (thư mục chứa file config.yaml hoặc file exe/repo)."""
    cfg = resolve_config_path("config.yaml")
    if cfg is not None:
        return cfg.parent.resolve()
    return get_exe_dir()


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


def resolve_config_path_local(filename: str = "config_path.yaml") -> Path | None:
    """
    Xác định đường dẫn file config_path.yaml theo thứ tự ưu tiên:
    1. Biến môi trường FASTBUSINESS_CONFIG_PATH_FILE
    2. Cùng thư mục với file config.yaml đã resolve
    3. Cạnh file exe hoặc bundle (frozen)
    """
    env_path = os.environ.get("FASTBUSINESS_CONFIG_PATH_FILE")
    if env_path:
        p = Path(env_path)
        return p if p.is_file() else None

    direct = Path(filename)
    if direct.is_file():
        return direct

    cfg_file = resolve_config_path("config.yaml")
    if cfg_file is not None:
        candidate = cfg_file.parent / filename
        if candidate.is_file():
            return candidate

    exe_dir = get_exe_dir()
    bundle_dir = get_bundle_dir()
    for candidate in (
        exe_dir / filename,
        exe_dir / "_internal" / filename,
        bundle_dir / filename,
    ):
        if candidate.is_file():
            return candidate

    return None


# Alias for backwards compatibility
resolve_config_path_xml = resolve_config_path_local


def load_machine_paths(path: Path | None = None) -> dict:
    """
    Đọc cấu hình đường dẫn máy từ file YAML (mặc định config_path.yaml).
    Trả về dict lồng, ví dụ:
    {
        "fbograph": {"kuzu_db_base": "C:/KuzuDB"},
        "clone_things": {"sql_temp_folder": "E:/SQL Temp"}
    }
    Nếu YAML lỗi cú pháp hoặc thiếu file -> log warning, trả về dict rỗng không crash.
    """
    import logging
    import yaml

    logger = logging.getLogger(__name__)

    if path is None:
        resolved = resolve_config_path_local("config_path.yaml")
    else:
        resolved = Path(path) if Path(path).is_file() else None

    if resolved is None:
        return {}

    try:
        with open(resolved, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            logger.warning(f"File {resolved} không chứa YAML mapping hợp lệ, bỏ qua.")
            return {}

        result: dict = {}

        # fbograph.kuzu_db_base
        kuzu_val = data.get("fbograph", {}).get("kuzu_db_base") if isinstance(data.get("fbograph"), dict) else None
        if kuzu_val and str(kuzu_val).strip():
            result.setdefault("fbograph", {})["kuzu_db_base"] = str(kuzu_val).strip()

        # clone_things.sql_temp_folder
        sql_val = data.get("clone_things", {}).get("sql_temp_folder") if isinstance(data.get("clone_things"), dict) else None
        if sql_val and str(sql_val).strip():
            result.setdefault("clone_things", {})["sql_temp_folder"] = str(sql_val).strip()

        return result
    except Exception as e:
        logger.warning(f"Không thể đọc hoặc parse {resolved}: {e}, dùng cấu hình mặc định.")
        return {}


def merge_config_with_machine_paths(cfg: dict, machine: dict | None = None) -> dict:
    """
    Deep-merge các key path từ machine vào bản sao của cfg.
    config_path.yaml thắng config.yaml đối với các path key khi non-empty.
    Không ghi đè các options non-path từ YAML.
    """
    import copy

    merged = copy.deepcopy(cfg) if cfg else {}
    if not machine:
        return merged

    for section, keys in machine.items():
        if isinstance(keys, dict):
            sec_dict = merged.setdefault(section, {})
            for k, v in keys.items():
                if v is not None and str(v).strip():
                    sec_dict[k] = v

    return merged


def get_effective_kuzu_db_base(cfg: dict | None = None) -> str:
    """
    Trả về đường dẫn kuzu_db_base hiệu lực (trước khi mkdir):
    Env FBOGRAPH_KUZU_BASE > cfg kuzu_db_base > {MCP_BASE}/KuzuDB
    """
    env_base = os.environ.get("FBOGRAPH_KUZU_BASE", "").strip()
    if env_base:
        return env_base

    if cfg is None:
        try:
            from fastbusiness_mcp.mcp_app import get_config
            cfg = get_config()
        except Exception:
            cfg = {}

    val = cfg.get("fbograph", {}).get("kuzu_db_base", "") if cfg else ""
    if str(val).strip():
        return str(val).strip()

    return str(get_mcp_base_dir() / "KuzuDB")


def get_effective_sql_temp_folder(cfg: dict | None = None) -> str:
    """
    Trả về đường dẫn sql_temp_folder hiệu lực:
    Env CLONE_THINGS_SQL_TEMP_FOLDER > cfg sql_temp_folder > {MCP_BASE}/Scripts
    """
    env_folder = os.environ.get("CLONE_THINGS_SQL_TEMP_FOLDER", "").strip()
    if env_folder:
        return env_folder

    if cfg is None:
        try:
            from fastbusiness_mcp.mcp_app import get_config
            cfg = get_config()
        except Exception:
            cfg = {}

    val = cfg.get("clone_things", {}).get("sql_temp_folder", "") if cfg else ""
    if str(val).strip():
        return str(val).strip()

    return str(get_mcp_base_dir() / "Scripts")
