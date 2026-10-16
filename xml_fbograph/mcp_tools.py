import json
import sys
from pathlib import Path
from typing import Optional

# Setup paths to ensure clean execution and imports
sys.path.append(str(Path(__file__).parent.parent.resolve()))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from xml_fbograph.utils.path_helper import ProjectPathHelper
from xml_fbograph.utils.any_path import project_switch_message, resolve_any_path


def _is_controller_xml(p: Path, project_root: Optional[Path]) -> bool:
    """True khi p là .xml trực thuộc Dir/Grid/Filter dưới App_Data/Controllers."""
    if p.suffix.lower() != ".xml" or project_root is None:
        return False
    controllers_root = (project_root / "App_Data" / "Controllers").resolve()
    try:
        rel = p.resolve().relative_to(controllers_root)
    except ValueError:
        return False
    return len(rel.parts) == 2 and rel.parts[0].lower() in {"dir", "grid", "filter"}


def _display_path(p: Path, project_root: Optional[Path]) -> str:
    """Path hiển thị trong response: rel tới Controllers hoặc project root."""
    if project_root is not None:
        controllers_root = (project_root / "App_Data" / "Controllers").resolve()
        for base in (controllers_root, project_root.resolve()):
            try:
                return str(p.resolve().relative_to(base))
            except ValueError:
                continue
    return str(p)


def _snippet_origin(p: Path, symbol: str) -> str:
    """'file' nếu symbol định nghĩa trong file gốc; 'entity:<name>'/'entity' nếu trong include."""
    import re as _re

    from xml_fbograph.parsers.xml_parser import read_file_content

    raw = read_file_content(p) or ""
    esc = _re.escape(symbol)
    if _re.search(r"(?<![\w$])function\s+" + esc + r"\s*\(", raw) or _re.search(
        r"(?<![\w$])" + esc + r"\s*=\s*", raw
    ):
        return "file"

    # Thử locate entity chứa định nghĩa (v1: best-effort, fallback 'entity')
    try:
        from find_entity_by_xml.entity_resolver import (
            get_entities_for_file,
            read_file_content as read_ent_file,
        )

        general, _param, _mtimes = get_entities_for_file(p)
        func_re = _re.compile(r"(?<![\w$])function\s+" + esc + r"\s*\(")
        for name, ent in (general or {}).items():
            src = (ent or {}).get("sourceFile") or (ent or {}).get("resolvedPath")
            if not src:
                continue
            content = read_ent_file(src) or ""
            if func_re.search(content):
                return f"entity:{name}"
    except Exception:
        pass
    return "entity"


def _snippet_response(p: Path, project_root: Optional[Path], view: str,
                      snippets: list, warnings: list) -> str:
    return json.dumps(
        {
            "success": True,
            "mode": "snippet",
            "file": _display_path(p, project_root),
            "view": view,
            "snippets": snippets,
            "warnings": warnings,
        },
        indent=2,
        ensure_ascii=False,
    )


def _snippet_error(code: str, p: Path, project_root: Optional[Path], **extra) -> str:
    payload = {
        "success": False,
        "mode": "snippet",
        "error_code": code,
        "file": _display_path(p, project_root),
    }
    payload.update(extra)
    return json.dumps(payload, indent=2, ensure_ascii=False)


_PLAIN_SCRIPT_EXTS = {".aspx", ".html", ".htm", ".cshtml"}
_MAX_LINE_CHARS_DEFAULT = 2000
_DUMP_CAP_CHARS = 80_000
_MINIFIED_WINDOW = 500


def _symbol_snippet_plain(p: Path, project_root: Optional[Path], source_text: str,
                          chunks: list, symbol: str, context_lines: int,
                          line_numbers: bool, max_line_chars: int,
                          warnings: list) -> str:
    """Symbol trên file thường (.js/.aspx/...) qua generic JS extractor.

    chunks: list (content_start_offset, chunk_text) — offset map về raw file.
    """
    from xml_controller_summary.snippet import (
        find_js_function_generic,
        format_snippet_lines,
        format_snippet_text,
        line_of,
        list_js_function_names_generic,
    )

    lines = source_text.split("\n")
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln) + 1)

    max_line_chars = max_line_chars or _MAX_LINE_CHARS_DEFAULT
    minified = any(len(l) > max_line_chars for l in lines)

    found: list = []  # (abs_start, abs_end|None, name)
    available: list = []
    for base, chunk in chunks:
        for m in find_js_function_generic(chunk, symbol):
            abs_s = base + m.start
            abs_e = base + m.end if m.end is not None and m.end >= 0 else None
            found.append((abs_s, abs_e, m.name))
        for nm in list_js_function_names_generic(chunk):
            if nm not in available:
                available.append(nm)

    if not found:
        extra = {"symbol": symbol, "available_functions": available[:50]}
        if minified:
            extra["note"] = "file minified — tên có thể không đầy đủ"
        return _snippet_error("symbol_not_found", p, project_root, **extra)

    snippets = []
    for abs_s, abs_e, name in found:
        line_no = line_of(source_text, abs_s)
        line_text = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
        item = {"kind": "js_function", "name": name, "origin": "file"}
        if len(line_text) > max_line_chars:
            # Minified: cửa sổ ±_MINIFIED_WINDOW ký tự quanh match, không dump cả dòng
            col = abs_s - offsets[line_no - 1]
            win_lo = max(0, col - _MINIFIED_WINDOW)
            win_hi = min(len(line_text), col + _MINIFIED_WINDOW)
            text = line_text[win_lo:win_hi]
            if line_numbers:
                text = (
                    f"{line_no}|"
                    + ("…" if win_lo > 0 else "")
                    + text
                    + ("…" if win_hi < len(line_text) else "")
                )
            item.update(
                line_start=line_no,
                line_end=line_no,
                text=text,
                line_truncated=True,
                line_total_chars=len(line_text),
            )
        elif abs_e is None:
            # Fallback: không brace-match được → dòng match ± context_lines
            ls, le, text = format_snippet_lines(
                source_text, line_no, line_no, context_lines, line_numbers
            )
            item.update(line_start=ls, line_end=le, text=text, brace_fallback=True)
        else:
            ls, le, text = format_snippet_text(
                source_text, abs_s, abs_e, context_lines, line_numbers
            )
            item.update(line_start=ls, line_end=le, text=text)
        snippets.append(item)
    return _snippet_response(p, project_root, "raw", snippets, warnings)


def _read_snippet(p: Path, project_root: Optional[Path], *, symbol: str, block: str,
                  start_line: int, end_line: int, context_lines: int,
                  line_numbers: bool, max_line_chars: int = _MAX_LINE_CHARS_DEFAULT) -> str:
    """Snippet mode của read_local_file — trả JSON {mode:'snippet', snippets[]}."""
    from xml_fbograph.parsers.xml_parser import read_file_content
    from xml_controller_summary.snippet import (
        extract_script_blocks,
        find_block,
        find_js_function_in_text,
        format_snippet_lines,
        format_snippet_text,
        line_of,
        list_js_function_names,
    )

    warnings: list = []
    is_controller = _is_controller_xml(p, project_root)

    if symbol and (start_line or end_line):
        warnings.append("symbol_overrides_lines")
        start_line = 0
        end_line = 0

    # --- symbol: trích function JS ---
    if symbol:
        suffix = p.suffix.lower()
        if not is_controller and suffix in _PLAIN_SCRIPT_EXTS | {".js"}:
            source_text = read_file_content(p) or ""
            chunks = (
                extract_script_blocks(source_text)
                if suffix in _PLAIN_SCRIPT_EXTS
                else [(0, source_text)]
            )
            return _symbol_snippet_plain(
                p, project_root, source_text, chunks, symbol,
                context_lines, line_numbers, max_line_chars, warnings,
            )

        if is_controller:
            view = "flat"
            try:
                from find_entity_by_xml.facade import flat_xml

                source_text = flat_xml(str(p))
            except Exception as e:
                return _snippet_error("flat_failed", p, project_root, message=str(e))
        else:
            view = "raw"
            source_text = read_file_content(p) or ""

        matches = find_js_function_in_text(source_text, symbol)
        if not matches:
            return _snippet_error(
                "symbol_not_found",
                p,
                project_root,
                symbol=symbol,
                available_functions=list_js_function_names(source_text),
            )

        origin = "file" if view == "raw" else _snippet_origin(p, symbol)
        if origin != "file":
            warnings.append(
                "symbol nằm trong entity/include — số dòng là của flat view; "
                "xem get_xml_entities(mode='path') để biết file vật lý, "
                "không str_replace theo số dòng này."
            )

        snippets = []
        for m in matches:
            ls, le, text = format_snippet_text(
                source_text, m.start, m.end, context_lines, line_numbers
            )
            snippets.append(
                {
                    "kind": "js_function",
                    "name": m.name,
                    "line_start": ls,
                    "line_end": le,
                    "origin": origin,
                    "text": text,
                }
            )
        return _snippet_response(p, project_root, view, snippets, warnings)

    # --- block: action:<id> / command:<event> / field:<name> / query:<n> ---
    if block:
        if not is_controller:
            return _snippet_error(
                "block_not_supported_for_plain_file",
                p,
                project_root,
                message="block chi ho tro .xml truc thuoc Dir/Grid/Filter; dung start_line/end_line hoac symbol cho file khac",
            )
        try:
            from find_entity_by_xml.facade import flat_xml
            from xml_controller_summary.extract import extract_controller_blocks

            flat = flat_xml(str(p))
        except Exception as e:
            return _snippet_error("flat_failed", p, project_root, message=str(e))

        blocks = extract_controller_blocks(flat)
        matches, available = find_block(blocks, block)
        if not matches:
            return _snippet_error(
                "block_not_found",
                p,
                project_root,
                block=block,
                available=available,
            )

        origin = "file" if block.split(":", 1)[-1] in (read_file_content(p) or "") else "entity"
        if origin != "file":
            warnings.append(
                "block nằm trong entity/include — số dòng là của flat view; "
                "xem get_xml_entities(mode='path') để biết file vật lý."
            )

        snippets = []
        for m in matches:
            raw_block = m.raw or ""
            start_pos = flat.find(raw_block) if raw_block else -1
            if raw_block and start_pos >= 0:
                ls, le, text = format_snippet_text(
                    flat, start_pos, start_pos + len(raw_block), context_lines, line_numbers
                )
            else:
                ls, le, text = m.line, m.line, raw_block
            snippets.append(
                {
                    "kind": m.kind,
                    "name": m.name,
                    "line_start": ls,
                    "line_end": le,
                    "origin": origin,
                    "text": text,
                }
            )
        return _snippet_response(p, project_root, "flat", snippets, warnings)

    # --- lines: cắt khoảng dòng trên raw ---
    if start_line > 0 and end_line > 0 and start_line > end_line:
        return _snippet_error(
            "invalid_range",
            p,
            project_root,
            start_line=start_line,
            end_line=end_line,
            message=f"start_line ({start_line}) > end_line ({end_line})",
        )
    raw_text = read_file_content(p) or ""
    total_lines = len(raw_text.split("\n")) if raw_text else 0
    s = start_line if start_line and start_line > 0 else 1
    e = end_line if end_line and end_line > 0 else total_lines
    if total_lines == 0 or s > total_lines:
        return _snippet_error(
            "line_out_of_range",
            p,
            project_root,
            start_line=start_line,
            end_line=end_line,
            total_lines=total_lines,
        )
    if e > total_lines:
        e = total_lines
    if e < s:
        e = s
    ls, le, text = format_snippet_lines(raw_text, s, e, context_lines, line_numbers)
    return _snippet_response(
        p,
        project_root,
        "raw",
        [
            {
                "kind": "lines",
                "name": f"lines:{s}-{e}",
                "line_start": ls,
                "line_end": le,
                "origin": "file",
                "text": text,
            }
        ],
        warnings,
    )


def mcp_read_local_file(file_path: str, reference_file: str = "", read_option: int = 3,
                        start_line: int = 0, end_line: int = 0, symbol: str = "",
                        block: str = "", context_lines: int = 0,
                        line_numbers: bool = True, old_string: str = "",
                        new_string: str = "", edits: Optional[list] = None,
                        max_expand: int = 10,
                        max_line_chars: int = _MAX_LINE_CHARS_DEFAULT) -> str:

    try:
        if not file_path or not str(file_path).strip():
            return "Loi: file_path khong duoc de trong"

        # read_option=4 — suggest_edit (READ-ONLY: gợi ý str_replace, không ghi file)
        if read_option == 4:
            from suggest_edit import suggest_edit as _suggest_edit

            return json.dumps(
                _suggest_edit(
                    file_path=file_path,
                    reference_file=reference_file,
                    symbol=symbol or "",
                    block=block or "",
                    start_line=start_line or 0,
                    end_line=end_line or 0,
                    old_string=old_string or "",
                    new_string=new_string or "",
                    max_expand=max_expand if max_expand is not None else 10,
                    edits=edits,
                ),
                indent=2,
                ensure_ascii=False,
            )

        resolved = resolve_any_path(file_path, reference_file)
        if not resolved.ok:
            err = dict(resolved.error or {"success": False})
            err.setdefault("project_root", resolved.project_root)
            err.setdefault("resolved_via", resolved.resolved_via)
            return json.dumps(err, indent=2, ensure_ascii=False)

        # Sticky context visibility — lộ project đã resolve + cảnh báo khi context trôi
        switch_warn = project_switch_message(resolved.switched_from, resolved.project_root)

        def _ctx_header() -> str:
            lines = [
                f"Project root: {resolved.project_root or 'null'}",
                f"Resolved via: {resolved.resolved_via}",
            ]
            if switch_warn:
                lines.append(f"[WARNING] {switch_warn}")
            return "\n".join(lines) + "\n\n"

        p = Path(resolved.abs_path)
        project_root = Path(resolved.project_root).resolve() if resolved.project_root else None

        # Sandbox check: khi detect được project thì file phải nằm trong project
        if project_root is not None:
            try:
                p.resolve().relative_to(project_root)
            except ValueError:
                return f"Loi: Duong dan nam ngoai thu muc du an: {file_path}"

        # Gate .xsd: file schema/kiến trúc — không cần đọc
        if p.suffix.lower() == ".xsd":
            return f"Loi: File .xsd la file schema/kien truc, khong can doc: {file_path}"

        if symbol or block or start_line or end_line:
            snippet_out = _read_snippet(
                p,
                project_root,
                symbol=symbol or "",
                block=block or "",
                start_line=start_line or 0,
                end_line=end_line or 0,
                context_lines=context_lines or 0,
                line_numbers=bool(line_numbers),
                max_line_chars=max_line_chars or _MAX_LINE_CHARS_DEFAULT,
            )
            try:
                data = json.loads(snippet_out)
            except Exception:
                data = None
            if isinstance(data, dict):
                data["project_root"] = resolved.project_root
                data["resolved_via"] = resolved.resolved_via
                if switch_warn:
                    warns = data.setdefault("warnings", [])
                    if isinstance(warns, list):
                        warns.append(switch_warn)
                return json.dumps(data, indent=2, ensure_ascii=False)
            return _ctx_header() + snippet_out

        if resolved.project_root:
            helper = ProjectPathHelper(
                str(Path(resolved.project_root) / "App_Data" / "Controllers" / "Dir" / "dummy.xml")
            )
        else:
            helper = ProjectPathHelper(str(p))

        if read_option == 3:
            is_valid_summary_xml = False
            if p.suffix.lower() == ".xml":
                controllers_root = helper.get_controllers_path().resolve()
                try:
                    rel = p.relative_to(controllers_root)
                except ValueError:
                    p_str = str(p).replace("\\", "/")
                    c_str = str(controllers_root).replace("\\", "/")
                    if p_str.lower().startswith(c_str.lower().rstrip("/") + "/"):
                        rel_str = p_str[len(c_str.rstrip("/")) + 1:]
                        rel = Path(rel_str)
                    else:
                        rel = None

                if rel and len(rel.parts) == 2 and rel.parts[0].lower() in {"dir", "grid", "filter"}:
                    is_valid_summary_xml = True

            if not is_valid_summary_xml:
                read_option = 1
            else:
                from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
                from find_entity_by_xml.bridges.summary_xml_format import format_summary_xml_result
                try:
                    result = summary_xml(str(p))
                    if isinstance(result, dict):
                        result["project_root"] = resolved.project_root
                        result["resolved_via"] = resolved.resolved_via
                        if switch_warn:
                            warns = result.setdefault("warnings", [])
                            if isinstance(warns, list):
                                warns.append(switch_warn)
                    out = format_summary_xml_result(result)
                    if switch_warn:
                        out = f"[WARNING] {switch_warn}\n" + out
                    return out
                except Exception as e:
                    return f"[ERROR] read_local_file summary_xml\nLoi khi summary XML: {str(e)}"

        from xml_fbograph.parsers.xml_parser import read_file_content
        from find_entity_by_xml.facade import flat_xml

        if read_option == 2:
            try:
                content = flat_xml(str(p))
            except Exception as e:
                # Fallback to original content or display error
                return f"Loi khi doc flat XML: {str(e)}\n\nNoidung goc:\n{read_file_content(p)}"
        else:
            content = read_file_content(p)
        content = content or ""
        if len(content) > _DUMP_CAP_CHARS:
            # Full-dump cap: head + footer JSON structured — agent dùng
            # start_line/end_line hoặc symbol/block để đọc tiếp đúng vùng.
            footer = {
                "truncated": True,
                "total_chars": len(content),
                "total_lines": content.count("\n") + 1,
                "returned_chars": _DUMP_CAP_CHARS,
                "hint": (
                    "File quá dài — dùng start_line/end_line (đọc tiếp từ "
                    "dòng tiếp theo) hoặc symbol/block để lấy đúng vùng."
                ),
            }
            return (
                _ctx_header()
                + content[:_DUMP_CAP_CHARS]
                + "\n\n[TRUNCATED] "
                + json.dumps(footer, ensure_ascii=False)
            )
        return _ctx_header() + content
    except Exception as e:
        return f"Loi doc file: {str(e)}"

