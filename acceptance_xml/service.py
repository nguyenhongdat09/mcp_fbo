"""Service acceptance_xml — format XML + auto UTF-8 BOM + check legacy.

Port pipeline từ extension fbo-autocomplete (CheckLegacy + FormatXML +
Utf8BomHandler) sang MCP tool.

Flow per file: validate .xml -> resolve path -> đọc+decode ->
[format ghi đè nếu bật] -> [auto thêm UTF-8 BOM nếu UTF-8 no-BOM] ->
check legacy full -> JSON per-file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastbusiness_mcp.utils.file_utils import decode_bytes
from xml_fbograph.utils.any_path import resolve_any_path

from .bom import ensure_utf8_bom, is_utf8_no_bom
from .check_legacy import check_legacy, check_message_duplicates, classify_path
from .entity_contents import get_entity_contents
from .xml_beautify import xml_beautify

_SEV_ORDER = {"error": 3, "warning": 2, "information": 1, "hint": 1}


def _split_paths(file_paths: Union[str, List[str], None]) -> List[str]:
    if not file_paths:
        return []
    if isinstance(file_paths, str):
        parts = file_paths.split(",")
    else:
        parts = []
        for item in file_paths:
            parts.extend(str(item).split(","))
    return [p.strip().strip('"').strip("'") for p in parts if p and p.strip()]


def _status_of(diagnostics: List[dict]) -> str:
    worst = 0
    for d in diagnostics:
        worst = max(worst, _SEV_ORDER.get(d.get("severity", "error"), 3))
    if worst >= 3:
        return "error"
    if worst >= 1:
        return "warning"
    return "ok"


def _dominant_eol(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return "\r\n" if crlf >= lf else "\n"


def _process_one(
    path_str: str,
    do_format: bool,
    reference_file: str,
    indent_step,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "file": path_str,
        "status": "error",
        "formatted": False,
        "changed": False,
        "bom_added": False,
        "diagnostics": [],
    }

    # Resolve path (abs / relative / sticky project / UNC)
    resolved = resolve_any_path(path_str, reference_file)
    if not resolved.ok:
        err = resolved.error or {}
        result["status"] = "error"
        code = err.get("error_code") or "resolve_failed"
        msg = err.get("message") or {
            "path_not_found": f"File không tồn tại: {path_str}",
            "no_project_context": f"Path tương đối nhưng chưa có project context: {path_str}",
        }.get(code, f"Không resolve được path ({code}): {path_str}")
        if err.get("hint"):
            msg += f" — {err['hint']}"
        result["message"] = msg
        if err.get("tried"):
            result["tried"] = err["tried"]
        return result

    abs_path = resolved.abs_path
    result["file"] = abs_path

    p = Path(abs_path)
    try:
        raw = p.read_bytes()
    except OSError as e:
        result["message"] = f"Không đọc được file: {e}"
        return result
    if not raw:
        result["message"] = "File rỗng"
        return result

    text, enc = decode_bytes(raw)
    needs_bom = is_utf8_no_bom(raw)
    content_for_check = text

    # --- Format (ghi đè) nếu bật ---
    if do_format:
        try:
            formatted = xml_beautify(text, indent_step)
            eol = _dominant_eol(text)
            if eol != "\n":
                formatted = formatted.replace("\r\n", "\n").replace("\n", eol)
            target_enc = "utf-8-sig" if needs_bom else enc
            try:
                out_bytes = formatted.encode(target_enc)
            except LookupError:
                target_enc = "utf-8-sig"
                out_bytes = formatted.encode(target_enc)
            try:
                p.write_bytes(out_bytes)
                result["formatted"] = True
                result["changed"] = out_bytes != raw
                result["bom_added"] = needs_bom
            except OSError as e:
                result["format_error"] = f"Không ghi được file sau format: {e}"
            content_for_check = formatted
        except Exception as e:  # format lỗi -> vẫn check trên nội dung gốc
            result["format_error"] = f"Format thất bại: {e}"
    else:
        # Không format: auto BOM byte-level (chức năng ẩn)
        if needs_bom:
            result["bom_added"] = ensure_utf8_bom(abs_path)

    # --- Check legacy (full) ---
    kind = classify_path(abs_path)
    norm = abs_path.replace("\\", "/").lower()
    is_message_xml = norm.endswith("/options/message.xml")

    if kind == "other" and not is_message_xml:
        result["status"] = "skipped"
        result["message"] = (
            "File .xml không nằm trong Controllers\\{Dir,Grid,Filter} — "
            "bỏ qua check legacy" + (", đã format/BOM nếu bật" if do_format or result["bom_added"] else "")
        )
        return result

    try:
        if is_message_xml and kind == "other":
            diags = check_message_duplicates(content_for_check)
        else:
            entity_contents = get_entity_contents(abs_path)
            diags = check_legacy(abs_path, content_for_check, entity_contents)
    except Exception as e:
        result["message"] = f"Check legacy thất bại: {e}"
        return result

    result["diagnostics"] = diags
    result["status"] = _status_of(diags)
    return result


def acceptance_xml(
    file_paths: Union[str, List[str]],
    format: Optional[bool] = None,
    reference_file: str = "",
    format_in_acceptance_default: bool = False,
    indent_step=4,
) -> Dict[str, Any]:
    """Format (tuỳ config/param) + auto UTF-8 BOM + check legacy cho 1..n file .xml.

    - file_paths: 1 path hoặc CSV nhiều path (hoặc list).
    - format: True/False override; None -> theo config format_in_acceptance.
    - File không phải .xml -> invalid_files, vẫn xử lý file còn lại.
    """
    do_format = format_in_acceptance_default if format is None else bool(format)

    results: List[Dict[str, Any]] = []
    invalid_files: List[Dict[str, str]] = []

    seen: set[str] = set()
    for raw_entry in _split_paths(file_paths):
        key = raw_entry.lower()
        if key in seen:
            continue
        seen.add(key)

        if Path(raw_entry).suffix.lower() != ".xml":
            invalid_files.append(
                {"input": raw_entry, "reason": "Không phải file .xml — chỉ chấp nhận .xml"}
            )
            results.append(
                {
                    "file": raw_entry,
                    "status": "invalid",
                    "formatted": False,
                    "changed": False,
                    "bom_added": False,
                    "diagnostics": [],
                    "message": "Không phải file .xml — chỉ chấp nhận .xml",
                }
            )
            continue

        results.append(_process_one(raw_entry, do_format, reference_file, indent_step))

    counts = {"total": len(results), "ok": 0, "warning": 0, "error": 0,
              "skipped": 0, "invalid": 0, "formatted": 0, "bom_added": 0}
    for r in results:
        st = r.get("status", "error")
        counts[st] = counts.get(st, 0) + 1
        if r.get("formatted"):
            counts["formatted"] += 1
        if r.get("bom_added"):
            counts["bom_added"] += 1

    return {
        "success": True,
        "format_enabled": do_format,
        "summary": counts,
        "invalid_files": invalid_files,
        "results": results,
    }
