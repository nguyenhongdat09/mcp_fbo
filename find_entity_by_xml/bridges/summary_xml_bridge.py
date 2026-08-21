"""Bridge to load, expand flat XML, and summarize via xml_controller_summary."""

from __future__ import annotations

import copy
import os
import threading
from typing import Any
from find_entity_by_xml.facade import flat_xml
from xml_controller_summary import analyze_flat_xml, result_to_dict
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
_SUMMARY_CACHE: dict[tuple[str, int, int, str], dict[str, Any]] = {}
_MAX_CACHE_ENTRIES = 256


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
                if cache_key in _SUMMARY_CACHE:
                    return copy.deepcopy(_SUMMARY_CACHE[cache_key])
        except Exception:
            cache_key = None

    try:
        flat = flat_xml(file_path)
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
    res_dict = result_to_dict(res)

    if use_cache and cache_key is not None:
        with _CACHE_LOCK:
            if len(_SUMMARY_CACHE) >= _MAX_CACHE_ENTRIES:
                _SUMMARY_CACHE.clear()
            _SUMMARY_CACHE[cache_key] = copy.deepcopy(res_dict)

    return res_dict
