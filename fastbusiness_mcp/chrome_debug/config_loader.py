"""Cấu hình cho Chrome CDP Debug package — load YAML + biến môi trường."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
import yaml

from .constants import (
    DEFAULT_CDP_URL,
    MAX_SNAPSHOT_NODES_DEFAULT,
    MAX_LABEL_CHARS_DEFAULT,
    MAX_RESPONSE_CHARS_DEFAULT,
    MAX_CONSOLE_LINES_DEFAULT,
    MAX_RESULT_CHARS_DEFAULT,
)
from ..config_paths import get_exe_dir, get_bundle_dir


def resolve_chrome_debug_config_path(config_path: str = "chrome_debug.yaml") -> Path | None:
    """Tìm đường dẫn file chrome_debug.yaml."""
    env_path = os.environ.get("CHROME_DEBUG_CONFIG_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p

    direct = Path(config_path)
    if direct.is_file():
        return direct

    # Kiểm tra trong package fastbusiness_mcp
    pkg_dir = Path(__file__).resolve().parent.parent
    if (pkg_dir / config_path).is_file():
        return pkg_dir / config_path

    exe_dir = get_exe_dir()
    bundle_dir = get_bundle_dir()
    for candidate in (
        exe_dir / config_path,
        exe_dir / "fastbusiness_mcp" / config_path,
        exe_dir / "_internal" / config_path,
        exe_dir / "_internal" / "fastbusiness_mcp" / config_path,
        bundle_dir / config_path,
    ):
        if candidate.is_file():
            return candidate

    return None


def load_chrome_debug_config(parent_cfg: dict | None = None) -> dict:
    """Tải và merge cấu hình chrome_debug.yaml kèm override từ biến môi trường."""
    cfg: Dict[str, Any] = {
        "enabled": True,
        "cdp_url": DEFAULT_CDP_URL,
        "chrome_path": "",
        "user_data_dir": "",
        "snapshot": {
            "max_nodes": MAX_SNAPSHOT_NODES_DEFAULT,
            "max_label_chars": MAX_LABEL_CHARS_DEFAULT,
            "mode": "interactive",
        },
        "network": {
            "max_response_chars": MAX_RESPONSE_CHARS_DEFAULT,
            "capture_status_from": 400,
        },
        "console": {
            "max_lines": MAX_CONSOLE_LINES_DEFAULT,
        },
        "execute_js": {
            "max_result_chars": MAX_RESULT_CHARS_DEFAULT,
        },
        "launch": {
            "auto_launch": False,
            "port": 9222,
            "headless": False,
        },
    }

    # Nếu parent config (từ config.yaml) có pointer chrome_debug_config
    config_file_name = "chrome_debug.yaml"
    if parent_cfg and isinstance(parent_cfg, dict):
        if "chrome_debug_config" in parent_cfg:
            config_file_name = str(parent_cfg["chrome_debug_config"])

    resolved = resolve_chrome_debug_config_path(config_file_name)
    if resolved and resolved.is_file():
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict):
                    # Recursive update
                    for k, v in loaded.items():
                        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                            cfg[k].update(v)
                        else:
                            cfg[k] = v
        except Exception:
            pass

    # Overrides từ ENV
    if "CHROME_DEBUG_ENABLED" in os.environ:
        cfg["enabled"] = os.environ["CHROME_DEBUG_ENABLED"].lower() in ("true", "1", "yes")

    if "CHROME_DEBUG_CDP_URL" in os.environ:
        cfg["cdp_url"] = os.environ["CHROME_DEBUG_CDP_URL"]

    return cfg
