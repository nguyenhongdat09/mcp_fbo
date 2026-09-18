"""suggest_edit service — trả gợi ý str_replace đầy đủ, agent giữ quyền execute.

READ-ONLY TUYỆT ĐỐI: module này không bao giờ ghi file. Nó chỉ locate vùng
target, resolve file vật lý (kể cả khi code nằm trong entity .ent), build
old_string exact + expand context cho unique, render diff_preview và chạy
post-edit check trong memory.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from xml_fbograph.utils.any_path import project_switch_message, resolve_any_path
from xml_controller_summary.extract import extract_controller_blocks
from xml_controller_summary.snippet import (
    find_block,
    find_js_function_in_text,
    line_of,
    list_js_function_names,
)

_MAX_DIFF_CHARS = 4000


def _detect_encoding(p: Path) -> str:
    """Trả codec name cho response field 'encoding' — dựa trên detect_bom_encoding."""
    from fastbusiness_mcp.utils.file_utils import detect_bom_encoding

    try:
        raw = p.read_bytes()[:8192]
    except Exception:
        return "utf-8"
    enc = detect_bom_encoding(raw)
    if enc == "utf-16":
        return "utf-16-le" if raw.startswith(b"\xff\xfe") else "utf-16-be"
    if enc:
        return enc
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1258"


def _read_text(p: Path) -> str:
    from fastbusiness_mcp.utils.file_utils import decode_bytes

    try:
        raw = p.read_bytes()
    except Exception:
        return ""
    if not raw:
        return ""
    text, _enc = decode_bytes(raw)
    return text


def _display_path(p: Path, project_root: Optional[Path]) -> str:
    if project_root is not None:
        controllers_root = (project_root / "App_Data" / "Controllers").resolve()
        for base in (controllers_root, project_root.resolve()):
            try:
                return str(p.resolve().relative_to(base))
            except ValueError:
                continue
    return str(p)


def _entities_for(xml_path: Path) -> List[Tuple[str, Path, str]]:
    """[(name, source_path, content)] của các general entity khai báo trong xml."""
    try:
        from find_entity_by_xml.entity_resolver import get_entities_for_file

        general, _param, _mtimes = get_entities_for_file(xml_path)
    except Exception:
        return []
    out: List[Tuple[str, Path, str]] = []
    for name, ent in (general or {}).items():
        src = (ent or {}).get("sourceFile") or (ent or {}).get("resolvedPath")
        if not src:
            continue
        ep = Path(src)
        out.append((name, ep, _read_text(ep)))
    return out


def _err(code: str, **extra) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"success": False, "error_code": code}
    payload.update(extra)
    return payload


@dataclass
class _Target:
    phys_path: Path
    content: str
    start: int
    end: int
    kind: str
    name: str
    origin: str  # "file" | "entity:<name>" | "entity"


def _block_anchor(selector: str) -> str:
    kind, _, val = selector.partition(":")
    val = val.strip()
    attr = {"action": "id", "command": "event", "field": "name"}.get(kind.strip().lower())
    if attr and val:
        return f'{attr}="{val}"'
    return ""


def _locate_symbol(main_p: Path, raw_main: str, symbol: str) -> Tuple[Optional[_Target], Dict[str, Any]]:
    matches = find_js_function_in_text(raw_main, symbol)
    if matches:
        m = matches[0]
        return (
            _Target(main_p, raw_main, m.start, m.end, "js_function", m.name, "file"),
            {},
        )
    for ent_name, ep, content in _entities_for(main_p):
        em = find_js_function_in_text(content, symbol)
        if em:
            m = em[0]
            return (
                _Target(ep, content, m.start, m.end, "js_function", m.name, f"entity:{ent_name}"),
                {},
            )
    # available_functions: ưu tiên flat (thấy cả function trong entity)
    available: List[str] = []
    if main_p.suffix.lower() == ".xml":
        try:
            from find_entity_by_xml.facade import flat_xml

            available = list_js_function_names(flat_xml(str(main_p)))
        except Exception:
            pass
    if not available:
        available = list_js_function_names(raw_main)
    return None, _err(
        "symbol_not_found", symbol=symbol, available_functions=available
    )


def _locate_block(main_p: Path, raw_main: str, selector: str) -> Tuple[Optional[_Target], Dict[str, Any]]:
    # 1) Thử trên raw trước — block nằm ngay trong file gốc
    blocks = extract_controller_blocks(raw_main)
    matches, available = find_block(blocks, selector)
    for m in matches:
        if m.raw:
            pos = raw_main.find(m.raw)
            if pos >= 0:
                return (
                    _Target(main_p, raw_main, pos, pos + len(m.raw), m.kind, m.name, "file"),
                    {},
                )

    # 2) Không thấy trong raw → flat + tìm block raw trong entity files
    try:
        from find_entity_by_xml.facade import flat_xml

        flat = flat_xml(str(main_p))
    except Exception:
        flat = ""
    if flat:
        blocks = extract_controller_blocks(flat)
        matches, available = find_block(blocks, selector)
    if not matches:
        return None, _err("block_not_found", block=selector, available=available)

    m = matches[0]
    anchor = _block_anchor(selector)
    for ent_name, ep, content in _entities_for(main_p):
        pos = content.find(m.raw) if m.raw else -1
        if pos >= 0:
            return (
                _Target(ep, content, pos, pos + len(m.raw), m.kind, m.name, f"entity:{ent_name}"),
                {},
            )
        if anchor:
            apos = content.find(anchor)
            if apos >= 0:
                # Căn tới đầu tag chứa anchor rồi tìm raw block từ đó
                tag_start = content.rfind("<", 0, apos)
                seg_start = tag_start if tag_start >= 0 else apos
                if m.raw:
                    rpos = content.find(m.raw, seg_start)
                    if rpos >= 0:
                        return (
                            _Target(ep, content, rpos, rpos + len(m.raw), m.kind, m.name, f"entity:{ent_name}"),
                            {},
                        )
                return (
                    _Target(ep, content, seg_start, apos + len(anchor), m.kind, m.name, f"entity:{ent_name}"),
                    {},
                )
    # Block tồn tại trong flat nhưng không map được file vật lý → KHÔNG trả
    # old_string từ flat (anchor sẽ miss trên file raw — anti-pattern).
    return None, _err(
        "physical_file_not_resolved",
        block=selector,
        hint="Block thấy trong flat view nhưng không xác định được file vật lý (entity inline/generated?). Xem get_xml_entities(mode='path').",
    )


def _locate_lines(main_p: Path, raw_main: str, start_line: int, end_line: int) -> Tuple[Optional[_Target], Dict[str, Any]]:
    if start_line > 0 and end_line > 0 and start_line > end_line:
        return None, _err(
            "invalid_range",
            start_line=start_line,
            end_line=end_line,
            message=f"start_line ({start_line}) > end_line ({end_line})",
        )
    lines = raw_main.split("\n")
    total = len(lines)
    s = start_line if start_line and start_line > 0 else 1
    e = end_line if end_line and end_line > 0 else total
    if total == 0 or s > total:
        return None, _err(
            "line_out_of_range", start_line=start_line, end_line=end_line, total_lines=total
        )
    e = min(e, total)
    if e < s:
        e = s
    # đổi line range -> char offset
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln) + 1)
    start = offsets[s - 1]
    end = offsets[e] - 1 if e < len(offsets) else len(raw_main)
    end = min(end, len(raw_main))
    return (
        _Target(main_p, raw_main, start, end, "lines", f"lines:{s}-{e}", "file"),
        {},
    )


def _locate_old_string(main_p: Path, raw_main: str, old_string: str) -> Tuple[Optional[_Target], Dict[str, Any]]:
    pos = raw_main.find(old_string)
    if pos >= 0:
        return (
            _Target(main_p, raw_main, pos, pos + len(old_string), "old_string", "old_string", "file"),
            {},
        )
    for ent_name, ep, content in _entities_for(main_p):
        pos = content.find(old_string)
        if pos >= 0:
            return (
                _Target(ep, content, pos, pos + len(old_string), "old_string", "old_string", f"entity:{ent_name}"),
                {},
            )
    # closest_match: fuzzy trên từng dòng của file gốc
    closest = []
    first_lines = [l for l in old_string.split("\n") if l.strip()][:3]
    if first_lines:
        main_lines = raw_main.split("\n")
        for probe in first_lines:
            close = difflib.get_close_matches(probe.strip(), [l.strip() for l in main_lines], n=1, cutoff=0.5)
            for c in close:
                for idx, l in enumerate(main_lines, 1):
                    if l.strip() == c:
                        closest.append({"line": idx, "text": l.strip()[:200]})
                        break
    return None, _err(
        "old_string_not_found",
        closest_match=closest[:3],
        hint="old_string không khớp file vật lý — thường do whitespace/encoding. Xem closest_match hoặc dùng symbol/block/lines.",
    )


def _expand_to_unique(content: str, start: int, end: int, max_expand: int) -> Tuple[int, int, int, bool, int, List[int]]:
    """Snap về biên dòng rồi expand context cho tới khi unique hoặc chạm max_expand.

    Trả (start, end, match_count, expanded, expanded_lines, occurrence_lines).
    expanded=True khi anchor PHẢI nới ra để unique (span gốc non-unique hoặc
    đã pad dòng); expanded_lines = số dòng đã pad so với span gốc.
    """
    lines = content.split("\n")
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln) + 1)

    def line_range_to_pos(lo_idx: int, hi_idx: int) -> Tuple[int, int]:
        s = offsets[lo_idx]
        e = offsets[hi_idx + 1] - 1 if hi_idx + 1 < len(offsets) else len(content)
        return s, min(e, len(content))

    lo = line_of(content, start) - 1
    hi = line_of(content, max(start, end - 1)) - 1
    req_lines = hi - lo + 1
    orig_count = content.count(content[start:end]) if end > start else 1

    def count(lo_i: int, hi_i: int) -> int:
        s, e = line_range_to_pos(lo_i, hi_i)
        return content.count(content[s:e])

    expanded = 0
    c = count(lo, hi)
    while c > 1 and expanded < max_expand:
        if lo > 0:
            lo -= 1
            expanded += 1
            c = count(lo, hi)
        if c > 1 and expanded < max_expand and hi < len(lines) - 1:
            hi += 1
            expanded += 1
            c = count(lo, hi)

    s, e = line_range_to_pos(lo, hi)
    occurrences: List[int] = []
    if c > 1:
        needle = content[s:e]
        pos = content.find(needle)
        while pos >= 0 and len(occurrences) < 20:
            occurrences.append(line_of(content, pos))
            pos = content.find(needle, pos + 1)

    expanded_flag = orig_count > 1 or expanded > 0
    extra_lines = (hi - lo + 1) - req_lines
    expanded_lines = (
        extra_lines
        if extra_lines > 0
        else (1 if expanded_flag and (s, e) != (start, end) else 0)
    )
    return s, e, c, expanded_flag, expanded_lines, occurrences


def _js_parse_source(source: str) -> Dict[str, Any]:
    """Parse JS THẬT bằng js_engine (ANTLR4, qua preprocess_js).

    - parser không chạy được (import lỗi/exception) -> js_parse="unchecked"
      (CẤM trả "ok" giả).
    - ParseResult.errors non-empty -> "failed" + errors[{line,column,message}].
    - parse xong sạch -> "ok".
    """
    try:
        from js_engine.generated.JavaScriptLexer import JavaScriptLexer  # noqa: F401
        from js_engine.generated.JavaScriptParser import JavaScriptParser  # noqa: F401
    except Exception as exc:
        return {
            "js_parse": "unchecked",
            "errors": [{"message": f"parser unavailable: {exc}"}],
        }
    try:
        from js_engine import parse as _parse

        res = _parse(source)
    except Exception as exc:
        return {
            "js_parse": "unchecked",
            "errors": [{"message": f"parser unavailable: {exc}"}],
        }
    if res.status == "ok" and not res.errors:
        return {"js_parse": "ok", "errors": []}
    return {
        "js_parse": "failed",
        "errors": [
            {"line": e.line, "column": e.column, "message": e.message}
            for e in res.errors[:20]
        ],
    }


def _flat_line_offset(flat: str, line: int) -> int:
    """Offset ký tự của đầu dòng `line` (1-based) trong flat."""
    pos = 0
    for _ in range(max(0, line - 1)):
        nxt = flat.find("\n", pos)
        if nxt < 0:
            return len(flat)
        pos = nxt + 1
    return pos


def _post_edit_check(main_p: Path, target: _Target, new_content: str) -> Any:
    """Re-parse new_content trong memory — KHÔNG ghi file."""
    if target.origin != "file":
        return {
            "status": "skipped_entity",
            "hint": "target nằm trong entity/include — sau khi edit gọi read_local_file(read_option=3) trên controller chính để check parse_status.",
        }

    suffix = target.phys_path.suffix.lower()
    if suffix == ".js":
        return _js_parse_source(new_content)

    if suffix == ".xml":
        try:
            from find_entity_by_xml.entity_expander import XmlEntityExpander
            from xml_controller_summary.analyze import analyze_sql_chunks
            from xml_controller_summary.extract import extract_controller_blocks

            res = XmlEntityExpander.expand_xml_entities(str(target.phys_path), new_content)
            flat = res.get("flat_text", "")
            extracted = extract_controller_blocks(flat)

            errors: List[Dict[str, Any]] = []
            js_status = "empty" if not extracted.js_chunks else "ok"
            for chunk in extracted.js_chunks:
                r = _js_parse_source(chunk.content)
                st = r.get("js_parse")
                if st == "unchecked":
                    js_status = "unchecked"
                    errors.extend(r.get("errors") or [])
                    break
                if st == "failed":
                    js_status = "failed"
                    # map line chunk-local -> line trong flat view
                    base_line = chunk.line
                    if chunk.content:
                        pos = flat.find(
                            chunk.content, _flat_line_offset(flat, chunk.line)
                        )
                        if pos >= 0:
                            base_line = line_of(flat, pos)
                    for e in r.get("errors") or []:
                        e2 = dict(e)
                        if e2.get("line"):
                            e2["line"] = base_line + e2["line"] - 1
                        e2["chunk"] = chunk.source
                        errors.append(e2)

            sql_summary, _sql_warns = analyze_sql_chunks(extracted.sql_chunks)
            out: Dict[str, Any] = {
                "js_parse": js_status,
                "sql_parse": sql_summary.parse_status,
                "errors": errors[:20],
            }
            return out
        except Exception as exc:
            return {
                "js_parse": "unchecked",
                "sql_parse": "unchecked",
                "errors": [{"message": f"parser unavailable: {exc}"}],
            }

    return {"status": "skipped", "reason": "file không phải controller .xml hay .js — không có parser phù hợp"}


def _locate_in_buffer(
    buffer: str, edit: Dict[str, Any]
) -> Tuple[Optional[Tuple[int, int, str, str]], Dict[str, Any]]:
    """Locate vùng target của 1 edit trên buffer in-memory.

    Selector giống bản đơn: old_string > symbol > block > start_line+end_line.
    Trả ((start, end, kind, name), {}) hoặc (None, error_dict).
    """
    sel_old = edit.get("old_string") or ""
    sel_sym = edit.get("symbol") or ""
    sel_blk = edit.get("block") or ""
    s_line = int(edit.get("start_line") or 0)
    e_line = int(edit.get("end_line") or 0)

    if sel_old:
        pos = buffer.find(sel_old)
        if pos < 0:
            return None, _err(
                "old_string_not_found",
                hint="old_string không khớp buffer hiện tại (sau các edit trước).",
            )
        return (pos, pos + len(sel_old), "old_string", "old_string"), {}

    if sel_sym:
        matches = find_js_function_in_text(buffer, sel_sym)
        if not matches:
            from xml_controller_summary.snippet import find_js_function_generic

            matches = find_js_function_generic(buffer, sel_sym)
            matches = [m for m in matches if m.end >= 0]
        if not matches:
            from xml_controller_summary.snippet import (
                list_js_function_names,
                list_js_function_names_generic,
            )

            avail = list_js_function_names(buffer)
            if not avail:
                avail = list_js_function_names_generic(buffer)
            return None, _err(
                "symbol_not_found", symbol=sel_sym, available_functions=avail[:50]
            )
        m = matches[0]
        return (m.start, m.end, "js_function", m.name), {}

    if sel_blk:
        blocks = extract_controller_blocks(buffer)
        matches, available = find_block(blocks, sel_blk)
        for m in matches:
            if m.raw:
                pos = buffer.find(m.raw)
                if pos >= 0:
                    return (pos, pos + len(m.raw), m.kind, m.name), {}
        return None, _err("block_not_found", block=sel_blk, available=available)

    if s_line or e_line:
        if s_line > 0 and e_line > 0 and s_line > e_line:
            return None, _err(
                "invalid_range",
                start_line=s_line,
                end_line=e_line,
                message=f"start_line ({s_line}) > end_line ({e_line})",
            )
        lines = buffer.split("\n")
        total = len(lines)
        s = s_line if s_line > 0 else 1
        e = e_line if e_line > 0 else total
        if total == 0 or s > total:
            return None, _err(
                "line_out_of_range",
                start_line=s_line,
                end_line=e_line,
                total_lines=total,
            )
        e = min(e, total)
        if e < s:
            e = s
        offsets = [0]
        for ln in lines:
            offsets.append(offsets[-1] + len(ln) + 1)
        start = offsets[s - 1]
        end = offsets[e] - 1 if e < len(offsets) else len(buffer)
        return (start, min(end, len(buffer)), "lines", f"lines:{s}-{e}"), {}

    return None, _err(
        "missing_target",
        message="Mỗi edit cần 1 trong: symbol / block / start_line+end_line / old_string",
    )


def _suggest_edits_batch(
    p: Path,
    raw_main: str,
    project_root: Optional[Path],
    edits: List[Dict[str, Any]],
    max_expand: int,
) -> Dict[str, Any]:
    """Apply tuần tự edits[] trên buffer in-memory — edit sau được khớp text
    do edit trước tạo (rename dây chuyền). READ-ONLY, không ghi file."""
    buffer = raw_main
    applied_spans: List[Tuple[int, int]] = []  # vùng new_string đã ghi (coords buffer hiện tại)
    results: List[Dict[str, Any]] = []
    applied = 0
    stop_error: Optional[Dict[str, Any]] = None

    for i, edit in enumerate(edits):
        if not isinstance(edit, dict):
            stop_error = _err("invalid_edit", message="edits[i] phải là object {selector, new_string}")
            results.append({"index": i, "success": False, "error_code": "invalid_edit"})
            break

        loc, err = _locate_in_buffer(buffer, edit)
        if err or loc is None:
            err = err or _err("missing_target")
            results.append({"index": i, "success": False, **{k: v for k, v in err.items() if k != "success"}})
            stop_error = err
            break
        s0, e0, kind, name = loc

        s, e, match_count, expanded, expanded_lines, occurrences = _expand_to_unique(
            buffer, s0, e0, max_expand or 0
        )
        if match_count != 1:
            results.append(
                {
                    "index": i,
                    "success": False,
                    "error_code": "old_string_not_unique",
                    "match_count": match_count,
                    "occurrences": [{"line_start": ln} for ln in occurrences],
                }
            )
            stop_error = _err(
                "old_string_not_unique",
                match_count=match_count,
                hint="old_string xuất hiện nhiều chỗ sau max_expand — thêm anchor hoặc tăng max_expand.",
            )
            break

        # Overlap: vùng replace cắt ngang vùng đã ghi trước đó (không chứa trọn)
        anchor = buffer[s:e]
        if any(
            s < we and e > ws and not (s >= ws and e <= we)
            for ws, we in applied_spans
        ):
            results.append(
                {
                    "index": i,
                    "success": False,
                    "error_code": "overlap_detected",
                    "hint": "Vùng edit chồng lấn vùng đã sửa trước đó — tách edit hoặc gộp lại.",
                }
            )
            stop_error = _err("overlap_detected")
            break

        new_s = edit.get("new_string") or ""
        buffer = buffer[:s] + new_s + buffer[e:]
        applied_spans.append((s, s + len(new_s)))
        applied += 1
        results.append(
            {
                "index": i,
                "success": True,
                "old_string": anchor,
                "match_count": 1,
                "expanded_for_uniqueness": expanded,
                "expanded_lines": expanded_lines,
                "target": {"kind": kind, "name": name},
            }
        )

    diff_preview = None
    post_edit_check: Any = None
    if applied > 0:
        diff_lines = list(
            difflib.unified_diff(
                raw_main.split("\n"),
                buffer.split("\n"),
                fromfile=_display_path(p, project_root),
                tofile=_display_path(p, project_root) + " (edited)",
                n=3,
                lineterm="",
            )
        )
        diff_preview = "\n".join(diff_lines)
        if len(diff_preview) > _MAX_DIFF_CHARS:
            diff_preview = diff_preview[:_MAX_DIFF_CHARS] + "\n... (diff truncated)"
        post_edit_check = _post_edit_check(
            p, _Target(p, buffer, 0, len(buffer), "batch", "edits", "file"), buffer
        )

    resp: Dict[str, Any] = {
        "success": stop_error is None,
        "mode": "suggest_edit",
        "physical_file": str(p),
        "display_file": _display_path(p, project_root),
        "origin": "file",
        "encoding": _detect_encoding(p),
        "edits": results,
        "edits_applied": applied,
        "diff_preview": diff_preview,
        "post_edit_check": post_edit_check,
        "warnings": [],
    }
    if stop_error is not None:
        resp["error_code"] = stop_error.get("error_code")
        if stop_error.get("hint"):
            resp["hint"] = stop_error["hint"]
    if isinstance(post_edit_check, dict) and post_edit_check.get("js_parse") == "failed":
        resp["instructions"] = (
            "code mới parse FAIL — không nên ghi; xem post_edit_check.errors."
        )
    return resp


def suggest_edit(
    file_path: str,
    reference_file: str = "",
    symbol: str = "",
    block: str = "",
    start_line: int = 0,
    end_line: int = 0,
    old_string: str = "",
    new_string: str = "",
    max_expand: int = 10,
    edits: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Tính toán suggest str_replace — READ-ONLY, không ghi file."""
    if not file_path or not str(file_path).strip():
        return _err("invalid_path", message="file_path khong duoc de trong")

    resolved = resolve_any_path(file_path, reference_file)
    if not resolved.ok:
        err = dict(resolved.error or {"success": False, "error_code": "path_not_found"})
        err.setdefault("project_root", resolved.project_root)
        err.setdefault("resolved_via", resolved.resolved_via)
        return err

    result = _suggest_edit_impl(
        resolved,
        symbol=symbol,
        block=block,
        start_line=start_line,
        end_line=end_line,
        old_string=old_string,
        new_string=new_string,
        max_expand=max_expand,
        edits=edits,
    )
    # Sticky context visibility — echo project + cảnh báo khi context trôi
    if isinstance(result, dict):
        result.setdefault("project_root", resolved.project_root)
        result.setdefault("resolved_via", resolved.resolved_via)
        warn = project_switch_message(resolved.switched_from, resolved.project_root)
        if warn:
            warns = result.setdefault("warnings", [])
            if isinstance(warns, list):
                warns.append(warn)
    return result


def _suggest_edit_impl(
    resolved: Any,
    symbol: str = "",
    block: str = "",
    start_line: int = 0,
    end_line: int = 0,
    old_string: str = "",
    new_string: str = "",
    max_expand: int = 10,
    edits: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    p = Path(resolved.abs_path)
    if resolved.kind == "dir" or p.is_dir():
        return _err("path_is_dir", file=str(p), message="suggest_edit cần file, không phải folder")
    if p.suffix.lower() == ".f":
        return _err("encrypted_file", file=str(p), message="File .f mã hóa — không đọc/sửa được")

    project_root = Path(resolved.project_root).resolve() if resolved.project_root else None
    raw_main = _read_text(p)

    # --- Batch mode: edits[] mutually exclusive với selector đơn ---
    if edits is not None:
        if symbol or block or start_line or end_line or old_string:
            return _err(
                "ambiguous_target",
                message="Không truyền đồng thời edits[] và selector top-level (symbol/block/start_line/end_line/old_string).",
            )
        if not isinstance(edits, list) or not edits:
            return _err("missing_target", message="edits phải là list không rỗng")
        return _suggest_edits_batch(p, raw_main, project_root, edits, max_expand or 0)

    # --- Locate target: old_string > symbol > block > lines ---
    target: Optional[_Target] = None
    error: Dict[str, Any] = {}
    if old_string:
        target, error = _locate_old_string(p, raw_main, old_string)
    elif symbol:
        target, error = _locate_symbol(p, raw_main, symbol)
    elif block:
        target, error = _locate_block(p, raw_main, block)
    elif start_line or end_line:
        target, error = _locate_lines(p, raw_main, start_line, end_line)
    else:
        return _err(
            "missing_target",
            message="Cần 1 trong: symbol / block / start_line+end_line / old_string",
        )
    if target is None:
        error.setdefault("success", False)
        error["file"] = _display_path(p, project_root)
        return error

    # --- Build old_string exact + expand cho unique ---
    s, e, match_count, expanded, expanded_lines, occurrences = _expand_to_unique(
        target.content, target.start, target.end, max_expand or 0
    )
    old_str = target.content[s:e]
    if match_count != 1:
        return _err(
            "old_string_not_unique",
            file=_display_path(target.phys_path, project_root),
            match_count=match_count,
            occurrences=[{"line_start": ln} for ln in occurrences],
            hint="old_string xuất hiện nhiều chỗ sau max_expand — tự thêm anchor (dòng trên/dưới đặc trưng) hoặc tăng max_expand.",
        )

    raw_line_start = line_of(target.content, s)
    raw_line_end = line_of(target.content, max(s, e - 1))
    encoding = _detect_encoding(target.phys_path)

    # --- diff_preview + post_edit_check (in memory) khi có new_string ---
    diff_preview = None
    post_edit_check: Any = None
    if new_string:
        new_content = target.content[:s] + new_string + target.content[e:]
        diff_lines = list(
            difflib.unified_diff(
                target.content.split("\n"),
                new_content.split("\n"),
                fromfile=_display_path(target.phys_path, project_root),
                tofile=_display_path(target.phys_path, project_root) + " (edited)",
                n=3,
                lineterm="",
            )
        )
        diff_preview = "\n".join(diff_lines)
        if len(diff_preview) > _MAX_DIFF_CHARS:
            diff_preview = diff_preview[:_MAX_DIFF_CHARS] + "\n... (diff truncated)"
        post_edit_check = _post_edit_check(p, target, new_content)

    instructions = (
        "Dùng old_string làm anchor cho StrReplace trên physical_file; không cần chỉnh gì thêm."
        if not expanded
        else "old_string đã được expand thêm context để unique — dùng NGUYÊN old_string làm anchor cho StrReplace trên physical_file."
    )
    if isinstance(post_edit_check, dict) and post_edit_check.get("js_parse") == "failed":
        instructions = (
            "code mới parse FAIL — không nên ghi; xem post_edit_check.errors."
        )
    if target.origin != "file":
        instructions += " (origin=entity: code sống trong file include — edit physical_file, KHÔNG phải file .xml gốc.)"

    return {
        "success": True,
        "mode": "suggest_edit",
        "physical_file": str(target.phys_path),
        "display_file": _display_path(target.phys_path, project_root),
        "origin": target.origin,
        "encoding": encoding,
        "target": {"kind": target.kind, "name": target.name},
        "raw_line_start": raw_line_start,
        "raw_line_end": raw_line_end,
        "old_string": old_str,
        "match_count": match_count,
        "expanded_for_uniqueness": expanded,
        "expanded_lines": expanded_lines,
        "new_string": new_string,
        "diff_preview": diff_preview,
        "post_edit_check": post_edit_check,
        "instructions": instructions,
        "warnings": [],
    }
