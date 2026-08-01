import os
from typing import Optional
from xml_fbograph.utils.path_helper import _find_config_file

_access_log_retention_days_cache: Optional[int] = None

def get_access_log_retention_days() -> int:
    """
    Get the retention days for Kuzu DB access log.
    Default is 30 days. Can be overridden by config.yaml (fbograph.access_log_retention_days)
    or env var FBOGRAPH_ACCESS_LOG_RETENTION_DAYS.
    """
    global _access_log_retention_days_cache
    if _access_log_retention_days_cache is not None:
        return _access_log_retention_days_cache

    env_val = os.environ.get("FBOGRAPH_ACCESS_LOG_RETENTION_DAYS", "").strip()
    if env_val.isdigit():
        _access_log_retention_days_cache = int(env_val)
        return _access_log_retention_days_cache

    retention_days = 30
    try:
        import yaml
        config_file = _find_config_file()
        if config_file:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            fbograph_cfg = cfg.get("fbograph", {})
            if "access_log_retention_days" in fbograph_cfg:
                retention_days = int(fbograph_cfg["access_log_retention_days"])
    except Exception:
        pass

    _access_log_retention_days_cache = retention_days
    return _access_log_retention_days_cache

def reset_retention_config_cache():
    """For testing."""
    global _access_log_retention_days_cache
    _access_log_retention_days_cache = None
