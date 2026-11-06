"""Bridge to load, expand flat XML, and summarize via xml_controller_summary."""

from __future__ import annotations

import copy
import os
import threading
from typing import Any
from find_entity_by_xml.facade import flat_xml_with_trace
from xml_controller_summary import analyze_flat_xml, result_to_dict
from xml_controller_summary.origins import build_function_origins
from xml_controller_summary.models import (
    SPEC_VERSION,
    SummaryXmlResult,
    ControllerMeta,
    JsSummary,
    SqlSummary,
    Meta,
)
from xml_controller_summary.analyze import infer_folder_type, normalize_display_file_path

_CACHE_LOCK = threading.Lock()
# Giá trị cache: {"data": summary dict, "deps": {đường dẫn file include: mtime_ns}}
_SUMMARY_CACHE: dict[tuple[str, int, int, str], dict[str, Any]] = {}
_MAX_CACHE_ENTRIES = 256


def _deps_unchanged(deps: dict[str, int]) -> bool:
    """True nếu mọi file include/entity phụ thuộc vẫn giữ nguyên mtime."""
    for dep_path, old_mtime_ns in deps.items():
        try:
            if os.stat(dep_path).st_mtime_ns != old_mtime_ns:
                return False
        except OSError:
            return False
    return True


def _collect_deps(file_mtimes: dict[str, float]) -> dict[str, int]:
    """Đổi danh sách file tham gia flat thành {path: mtime_ns} đọc lại từ đĩa."""
    deps: dict[str, int] = {}
    for dep_path in file_mtimes:
        try:
            deps[dep_path] = os.stat(dep_path).st_mtime_ns
        except OSError:
            continue
    return deps


def summary_xml(file_path: str, *, use_cache: bool = True) -> dict[str, Any]:
    """Execute flat expansion on file_path and return structured summary dictionary."""
    display_file = normalize_display_file_path(file_path)

    # Check cache if enabled
    cache_key = None
    if use_cache:
        try:
            st = os.stat(file_path)
            cache_key = (
                os.path.abspath(file_path).lower(),
                st.st_mtime_ns,
                st.st_size,
                f"summary_xml:{SPEC_VERSION}",
            )
            with _CACHE_LOCK:
                cached = _SUMMARY_CACHE.get(cache_key)
                if cached is not None and _deps_unchanged(cached["deps"]):
                    return copy.deepcopy(cached["data"])
        except Exception:
            cache_key = None

    try:
        flat, entity_trace, file_mtimes = flat_xml_with_trace(file_path)
    except Exception as exc:
        return result_to_dict(
            SummaryXmlResult(
                success=False,
                file=display_file,
                controller=ControllerMeta(folder_type=infer_folder_type(file_path)),
                js=JsSummary(parse_status="empty"),
                sql=SqlSummary(parse_status="empty"),
                fields=[],
                meta=Meta(warnings=["flat_failed", str(exc)]),
            )
        )

    # Check for fully encrypted .f files that cannot be resolved into valid XML
    if file_path.lower().endswith(".f") and (not flat or "<" not in flat or "\x00" in flat[:500] or not flat.strip()):
        return result_to_dict(
            SummaryXmlResult(
                success=False,
                file=display_file,
                controller=ControllerMeta(folder_type=infer_folder_type(file_path)),
                js=JsSummary(parse_status="empty"),
                sql=SqlSummary(parse_status="empty"),
                fields=[],
                meta=Meta(warnings=["encrypted_file_not_supported"]),
            )
        )

    res = analyze_flat_xml(flat, source_path=file_path)
    if res.js.functions:
        res.js.function_origins = build_function_origins(res.js.functions, entity_trace)
    res_dict = result_to_dict(res)

    if use_cache and cache_key is not None:
        with _CACHE_LOCK:
            if len(_SUMMARY_CACHE) >= _MAX_CACHE_ENTRIES:
                _SUMMARY_CACHE.clear()
            _SUMMARY_CACHE[cache_key] = {
                "data": copy.deepcopy(res_dict),
                "deps": _collect_deps(file_mtimes),
            }

    return res_dict
