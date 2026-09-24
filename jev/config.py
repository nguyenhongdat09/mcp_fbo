"""Resolve + parse config Jev (entitlement gate).

Hỗ trợ 2 dạng file, tìm theo thứ tự giống resolve_config_path_local():
  1. env FASTBUSINESS_JEV_CONFIG (trỏ thẳng file)
  2. Cạnh config.yaml đã resolve
  3. cwd -> exe_dir -> exe_dir/_internal -> bundle

File chấp nhận:
  - config_jev.xml : <jev enabled="true"><apiKey/><baseUrl/><model/>
                     <timeoutSeconds/><confidenceAct/><confidenceReview/></jev>
  - config_jev.yaml: api_key: {jev: <key>} + optional jev: {base_url, model,
                     timeout_seconds, confidence_act, confidence_review,
                     enabled}

Trả dict config chuẩn hoặc None (file thiếu / disabled / XML lỗi /
thiếu apiKey) -> feature locked.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "base_url": "https://api.typesafe.ai",
    "model": "jev-latest",
    "timeout_seconds": 15,
    "confidence_act": 0.7,
    "confidence_review": 0.4,
}

_CANDIDATE_NAMES = ("config_jev.xml", "config_jev.yaml")


def _iter_candidate_paths() -> list[Path]:
    from fastbusiness_mcp.config_paths import (
        get_bundle_dir,
        get_exe_dir,
        resolve_config_path,
    )

    env_path = os.environ.get("FASTBUSINESS_JEV_CONFIG", "").strip()
    if env_path:
        p = Path(env_path)
        return [p] if p.is_file() else []

    dirs: list[Path] = []
    cfg_file = resolve_config_path("config.yaml")
    if cfg_file is not None:
        dirs.append(cfg_file.parent)
    dirs.append(Path.cwd())
    exe_dir = get_exe_dir()
    dirs += [exe_dir, exe_dir / "_internal", get_bundle_dir()]

    seen: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        for name in _CANDIDATE_NAMES:
            p = d / name
            key = str(p).lower()
            if key not in seen and p.is_file():
                seen.add(key)
                out.append(p)
    return out


def _to_bool(v, default=True) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _to_float(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _parse_xml(path: Path) -> dict | None:
    import xml.etree.ElementTree as ET

    root = ET.parse(path).getroot()
    if root.tag.lower() != "jev":
        return None
    cfg = dict(_DEFAULTS)
    cfg["enabled"] = _to_bool(root.get("enabled"), True)
    child = {c.tag.lower(): (c.text or "").strip() for c in root}
    cfg["api_key"] = child.get("apikey", "")
    for k, dk in (("baseurl", "base_url"), ("model", "model")):
        if child.get(k):
            cfg[dk] = child[k]
    cfg["timeout_seconds"] = _to_int(
        child.get("timeoutseconds"), _DEFAULTS["timeout_seconds"])
    cfg["confidence_act"] = _to_float(
        child.get("confidenceact"), _DEFAULTS["confidence_act"])
    cfg["confidence_review"] = _to_float(
        child.get("confidencereview"), _DEFAULTS["confidence_review"])
    return cfg


def _parse_yaml(path: Path) -> dict | None:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    cfg = dict(_DEFAULTS)
    jev_sec = data.get("jev") if isinstance(data.get("jev"), dict) else {}
    cfg["enabled"] = _to_bool(jev_sec.get("enabled"), True)
    api = data.get("api_key")
    cfg["api_key"] = (api or {}).get("jev", "") if isinstance(api, dict) else ""
    for k in ("base_url", "model"):
        if jev_sec.get(k):
            cfg[k] = str(jev_sec[k]).strip()
    cfg["timeout_seconds"] = _to_int(
        jev_sec.get("timeout_seconds"), _DEFAULTS["timeout_seconds"])
    cfg["confidence_act"] = _to_float(
        jev_sec.get("confidence_act"), _DEFAULTS["confidence_act"])
    cfg["confidence_review"] = _to_float(
        jev_sec.get("confidence_review"), _DEFAULTS["confidence_review"])
    return cfg


def load_jev_config() -> dict | None:
    """Trả config dict nếu feature được bật và có api_key, ngược lại None."""
    for path in _iter_candidate_paths():
        try:
            cfg = (_parse_xml(path) if path.suffix.lower() == ".xml"
                   else _parse_yaml(path))
        except Exception as e:
            logger.warning(f"Parse {path} lỗi: {e} — bỏ qua, Jev locked.")
            continue
        if cfg is None:
            continue
        if not cfg.get("enabled"):
            logger.info(f"{path.name}: enabled=false — Jev locked.")
            return None
        if not str(cfg.get("api_key") or "").strip():
            logger.warning(f"{path.name}: thiếu api_key — Jev locked.")
            return None
        cfg["source"] = str(path)
        logger.info(f"Jev config loaded từ {path.name} "
                    f"(model={cfg['model']})")
        return cfg
    return None


def jev_available() -> bool:
    return load_jev_config() is not None
