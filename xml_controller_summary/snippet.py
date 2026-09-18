"""Snippet extraction helpers — trích 1 function JS / 1 block SQL-XML / khoảng dòng.

Dùng cho ``read_local_file`` snippet mode. Số dòng trả về là của view đang dùng
(flat cho controller XML, raw cho file thường).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from xml_controller_summary.extract import (
    COMMAND_RE,
    SCRIPT_RE,
    ExtractedBlocks,
    RawField,
    SqlChunk,
)
from xml_controller_summary.fallback_regex import JS_FUNCTION_RE

_IDENT = r"[a-zA-Z0-9_$]+"
_IDENT_BOUNDARY = r"(?<![\w$])"

# Generic JS patterns cho file thường (.js/.aspx/.html/.cshtml) — không theo
# convention controller (foo$bar). name có thể chứa dấu chấm (foo.bar = function).
JS_GENERIC_PATTERNS: list[re.Pattern] = [
    re.compile(r"function\s+(?P<name>[$\w]+)\s*\("),
    re.compile(r"(?:var|let|const)\s+(?P<name>[$\w]+)\s*=\s*function"),
    re.compile(r"(?P<name>[$\w.$]+)\s*=\s*function"),
    re.compile(r"(?P<name>[$\w]+)\s*:\s*function"),
    re.compile(r"(?:var|let|const)\s+(?P<name>[$\w]+)\s*=\s*\("),
]

_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)
_SCRIPT_SRC_RE = re.compile(r"\bsrc\s*=", re.IGNORECASE)


def _symbol_patterns(name: str) -> list[tuple[re.Pattern, str]]:
    """Regex tìm định nghĩa function/biến JS theo thứ tự ưu tiên."""
    esc = re.escape(name)
    return [
        (re.compile(_IDENT_BOUNDARY + r"function\s+" + esc + r"\s*\("), "function"),
        (re.compile(_IDENT_BOUNDARY + esc + r"\s*=\s*function\b"), "assign_function"),
        (
            re.compile(_IDENT_BOUNDARY + r"(?:var|let|const)\s+" + esc + r"\s*=\s*"),
            "var",
        ),
    ]


def _find_matching_brace(text: str, open_pos: int) -> int:
    """Vị trí `}` đóng tương ứng với `{` tại open_pos; bỏ qua string/comment. -1 nếu không thấy."""
    depth = 0
    i = open_pos
    n = len(text)
    in_str: Optional[str] = None
    in_line_comment = False
    in_block_comment = False
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_line_comment:
            if c == "\n":
                in_line_comment = False
        elif in_block_comment:
            if c == "*" and nxt == "/":
                in_block_comment = False
                i += 1
        elif in_str:
            if c == "\\":
                i += 1
            elif c == in_str:
                in_str = None
        else:
            if c == "/" and nxt == "/":
                in_line_comment = True
                i += 1
            elif c == "/" and nxt == "*":
                in_block_comment = True
                i += 1
            elif c in "'\"`":
                in_str = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


@dataclass
class JsFunctionMatch:
    name: str
    kind: str  # function | assign_function | var
    start: int  # offset trong text
    end: int  # offset kết thúc (inclusive)


# ---------------------------------------------------------------------------
# AST path: js_engine (ANTLR4) — range chính xác, fallback regex bên dưới
# ---------------------------------------------------------------------------

_CDATA_OPEN_RE = re.compile(r"<!\[CDATA\[")
_CDATA_CLOSE_RE = re.compile(r"\]\]>")
_TEXT_TAG_RE = re.compile(r"</?text\b[^>]*>", re.IGNORECASE)
_ENTITY_REF_RE = re.compile(r"&([A-Za-z_][\w$.]*);")
_FBO_MACRO_AT_RE = re.compile(r"@@(?=[\w$])")
_COMMAND_CHECKING_RE = re.compile(r'event\s*=\s*["\']checking["\']', re.IGNORECASE)

# ctx expression được bind tên qua assignment/vardecl/property
_EXPR_WRAPPER_CTXS = {
    "FunctionExpressionContext",
    "AnonymousFunctionContext",
    "ExpressionSequenceContext",
    "ParenthesizedExpressionContext",
}
_FUNC_EXPR_CTXS = {
    "AnonymousFunctionDeclContext",
    "ArrowFunctionContext",
    "NamedFunctionContext",
}


def _blank(m: re.Match) -> str:
    return " " * len(m.group(0))


def _scrub_xml_region(inner: str) -> str:
    """Thay wrapper XML/CDATA bằng whitespace (giữ nguyên offset) để parse JS."""
    s = _CDATA_OPEN_RE.sub(_blank, inner)
    s = _CDATA_CLOSE_RE.sub(_blank, s)
    s = _TEXT_TAG_RE.sub(_blank, s)
    s = _ENTITY_REF_RE.sub(lambda m: " " + m.group(1) + " ", s)
    return s


def _scrub_js_macros(js_text: str) -> str:
    """``@@var`` -> ``__var`` (giữ length) — dùng khi parse thô không ra tree."""
    return _FBO_MACRO_AT_RE.sub("__", js_text)


def _iter_js_regions(text: str) -> list[tuple[int, str]]:
    """[(abs_offset, js_source)] — file JS thường -> toàn text; XML -> từng
    <script>/<command event="Checking"> body đã scrub wrapper."""
    if not text:
        return []
    regions: list[tuple[int, str]] = []
    if "<" in text:
        for m in SCRIPT_RE.finditer(text):
            scrub = _scrub_xml_region(m.group(2))
            if scrub.strip():
                regions.append((m.start(2), scrub))
        for m in COMMAND_RE.finditer(text):
            if not _COMMAND_CHECKING_RE.search(m.group(1) or ""):
                continue
            scrub = _scrub_xml_region(m.group(2))
            if scrub.strip():
                regions.append((m.start(2), scrub))
    if not regions:
        # Pure JS, hoặc XML không script — parse fail thì caller fallback regex.
        regions = [(0, text)]
    return regions


def _engine_tree(js_text: str):
    """Parse raw (không preprocess — giữ offset); trả ParseResult có tree hoặc None."""
    try:
        from js_engine import parse as _js_parse

        res = _js_parse(js_text, preprocess=False)
        if getattr(res, "tree", None) is not None:
            return res
    except Exception:
        pass
    return None


def _ctx_text(ctx) -> Optional[str]:
    try:
        return ctx.getText() if ctx is not None else None
    except Exception:
        return None


def _ctx_first(ctx, *methods: str) -> Optional[str]:
    for mn in methods:
        fn = getattr(ctx, mn, None)
        if not callable(fn):
            continue
        try:
            v = fn()
        except Exception:
            v = None
        txt = _ctx_text(v)
        if txt:
            return txt
    return None


def _decl_anchor_start(decl_ctx) -> int:
    """Start của var-statement chứa decl (gồm keyword var/let/const)."""
    p = getattr(decl_ctx, "parentCtx", None)
    if p is not None and type(p).__name__ == "SingleVariableDeclarationContext":
        return p.start.start
    return decl_ctx.start.start


def _func_expr_binding(func_ctx):
    """(name, anchor_ctx) khi function expression được bind cho tên.

    ``lhs = function..`` / ``var name = function..`` / ``name: function..``.
    """
    node = func_ctx
    p = getattr(node, "parentCtx", None)
    hops = 0
    while p is not None and type(p).__name__ in _EXPR_WRAPPER_CTXS and hops < 6:
        node = p
        p = getattr(p, "parentCtx", None)
        hops += 1
    if p is None:
        return None, None
    tname = type(p).__name__
    if tname == "AssignmentExpressionContext":
        exprs = p.singleExpression()
        if exprs and len(exprs) >= 2 and p.Assign() is not None and exprs[-1] is node:
            return _ctx_text(exprs[0]), p
        return None, None
    if tname == "VariableDeclarationContext":
        return _ctx_first(p, "assignable"), p
    if tname == "PropertyExpressionAssignmentContext":
        return _ctx_first(p, "propertyName"), p
    return None, None


def _expr_has_function(node, depth: int = 0) -> bool:
    if node is None or depth > 8:
        return False
    if type(node).__name__ in _FUNC_EXPR_CTXS or type(node).__name__ == "FunctionExpressionContext":
        return True
    for ch in getattr(node, "children", None) or []:
        if _expr_has_function(ch, depth + 1):
            return True
    return False


def _collect_js_functions(node, out: list) -> None:
    """Đệ quy walk parse tree — gom (name, start, end_exclusive, kind)."""
    tname = type(node).__name__
    if tname == "FunctionDeclarationContext":
        name = _ctx_first(node, "identifier")
        if name:
            out.append((name, node.start.start, node.stop.stop + 1, "function"))
    elif tname in ("FunctionPropertyContext", "MethodDefinitionContext"):
        # method shorthand name(){} trong object literal / class
        name = _ctx_first(node, "propertyName", "classElementName")
        if name:
            out.append((name, node.start.start, node.stop.stop + 1, "function"))
    elif tname in ("PropertyGetterContext", "PropertySetterContext"):
        inner = node.getter() if tname == "PropertyGetterContext" else node.setter()
        name = _ctx_first(inner, "identifier", "classElementName") if inner else None
        if name:
            out.append((name, node.start.start, node.stop.stop + 1, "function"))
    elif tname in ("AnonymousFunctionDeclContext", "ArrowFunctionContext"):
        name, anchor = _func_expr_binding(node)
        if name:
            start = (
                _decl_anchor_start(anchor)
                if type(anchor).__name__ == "VariableDeclarationContext"
                else anchor.start.start
            )
            out.append((name, start, node.stop.stop + 1, "assign_function"))
    elif tname == "VariableDeclarationContext":
        # `var name = <expr>` non-function (object literal, IIFE result...)
        if (
            getattr(node, "Assign", None) is not None
            and node.Assign() is not None
            and not _expr_has_function(node.singleExpression())
        ):
            name = _ctx_first(node, "assignable")
            if name:
                out.append((name, _decl_anchor_start(node), node.stop.stop + 1, "var"))
    for ch in getattr(node, "children", None) or []:
        _collect_js_functions(ch, out)


def _ast_function_spans(js_text: str) -> Optional[list]:
    """[(name, start, end_excl, kind)] từ AST; None khi parser không ra tree."""
    if not js_text or not js_text.strip():
        return []
    res = _engine_tree(js_text)
    if res is None:
        res = _engine_tree(_scrub_js_macros(js_text))
    if res is None or getattr(res, "tree", None) is None:
        return None
    out: list = []
    _collect_js_functions(res.tree, out)
    out.sort(key=lambda t: t[1])
    return out


def find_js_function_ast(text: str, name: str) -> list[JsFunctionMatch]:
    """Match function ``name`` qua AST js_engine; [] khi không parse/không thấy.

    Match khi ``fname == name`` hoặc ``fname`` kết thúc ``.{name}``.
    """
    matches: list[JsFunctionMatch] = []
    if not text or not name:
        return matches
    for base, js_src in _iter_js_regions(text):
        spans = _ast_function_spans(js_src)
        if not spans:
            continue
        for nm, s, e, kind in spans:
            if nm == name or nm.endswith("." + name):
                matches.append(
                    JsFunctionMatch(name=nm, kind=kind, start=base + s, end=base + e)
                )
    matches.sort(key=lambda m: m.start)
    return matches


def list_js_function_names_ast(text: str) -> list[str]:
    """Tên function từ AST (đầy đủ: declaration, assign, ``X: function``, shorthand)."""
    names: list[str] = []
    for _base, js_src in _iter_js_regions(text):
        spans = _ast_function_spans(js_src)
        if not spans:
            continue
        for nm, _s, _e, kind in spans:
            if kind == "var":
                continue  # available_functions chỉ liệt function thật
            if nm not in names:
                names.append(nm)
    return names


def find_js_function_in_text(text: str, name: str) -> list[JsFunctionMatch]:
    """Tìm định nghĩa `name` trong source text (flat XML hoặc file .js thường).

    Ưu tiên range từ AST js_engine; fallback regex + brace-match khi
    không parse được (minified/broken) hoặc AST không thấy tên.
    """
    ast = find_js_function_ast(text, name)
    if ast:
        return ast
    matches: list[JsFunctionMatch] = []
    if not text or not name:
        return matches
    for pattern, kind in _symbol_patterns(name):
        for m in pattern.finditer(text):
            brace = text.find("{", m.end())
            if brace == -1:
                continue
            # Giới hạn: `{` phải nằm gần (trước `;` hoặc `)` cân bằng xa — đủ cho ES5 FBO)
            semi = text.find(";", m.end())
            if semi != -1 and semi < brace:
                continue
            close = _find_matching_brace(text, brace)
            if close == -1:
                close = brace
            matches.append(JsFunctionMatch(name=name, kind=kind, start=m.start(), end=close + 1))
        if matches:
            break
    return matches


def list_js_function_names(text: str) -> list[str]:
    """Tên các function JS khai báo trong text (phục vụ available_functions)."""
    seen: list[str] = []
    for name in list_js_function_names_ast(text):
        if name not in seen:
            seen.append(name)
    for name in JS_FUNCTION_RE.findall(text or ""):
        if name not in seen:
            seen.append(name)
    return seen


def list_js_function_names_generic(text: str, limit: int = 50) -> list[str]:
    """Tên function JS trong file thường theo JS_GENERIC_PATTERNS (kể cả tên minified)."""
    seen: list[str] = []
    for name in list_js_function_names_ast(text):
        if name not in seen:
            seen.append(name)
    for pattern in JS_GENERIC_PATTERNS:
        for m in pattern.finditer(text or ""):
            name = m.group("name")
            if name not in seen:
                seen.append(name)
                if len(seen) >= limit:
                    return seen
    return seen


def find_js_function_generic(text: str, name: str) -> list[JsFunctionMatch]:
    """Tìm định nghĩa `name` trong source JS thường bằng JS_GENERIC_PATTERNS.

    Match khi ``fname == name`` hoặc ``fname`` kết thúc bằng ``.{name}``
    (agent hay gõ `bar` cho `foo.bar = function`). Range lấy bằng
    brace-matching; không brace-match được (minified/cú pháp lạ) → end=-1
    để caller fallback về dòng match ± context_lines.

    Ưu tiên range từ AST js_engine; fallback regex khi không parse được.
    """
    ast = find_js_function_ast(text, name)
    if ast:
        for m in ast:
            m.kind = "generic"
        return ast
    matches: list[JsFunctionMatch] = []
    if not text or not name:
        return matches
    seen_starts: set[int] = set()
    for pattern in JS_GENERIC_PATTERNS:
        for m in pattern.finditer(text):
            fname = m.group("name")
            if fname != name and not fname.endswith("." + name):
                continue
            key = m.start("name")
            if key in seen_starts:
                continue
            seen_starts.add(key)
            brace = text.find("{", m.end())
            semi = text.find(";", m.end())
            if brace == -1 or (semi != -1 and semi < brace):
                matches.append(
                    JsFunctionMatch(name=fname, kind="generic", start=m.start(), end=-1)
                )
                continue
            close = _find_matching_brace(text, brace)
            matches.append(
                JsFunctionMatch(
                    name=fname,
                    kind="generic",
                    start=m.start(),
                    end=close + 1 if close != -1 else -1,
                )
            )
    matches.sort(key=lambda x: x.start)
    return matches


def extract_script_blocks(text: str) -> list[tuple[int, str]]:
    """Trích các khối ``<script ...>...</script>`` trong file .aspx/.html/.cshtml.

    Trả list ``(content_start_offset, content)`` — offset là vị trí trong text gốc
    (raw file), để map line number về raw. Bỏ ``<script src=...>`` không body.
    """
    blocks: list[tuple[int, str]] = []
    for m in _SCRIPT_BLOCK_RE.finditer(text or ""):
        open_tag = m.group(0)[: m.group(0).find(">") + 1]
        body = m.group(1)
        if _SCRIPT_SRC_RE.search(open_tag) and not body.strip():
            continue
        blocks.append((m.start(1), body))
    return blocks


def line_of(text: str, pos: int) -> int:
    """Số dòng 1-based của offset pos trong text."""
    return text.count("\n", 0, pos) + 1


def format_snippet_text(
    source_text: str,
    start_pos: int,
    end_pos: int,
    context_lines: int = 0,
    line_numbers: bool = True,
) -> tuple[int, int, str]:
    """Cắt đoạn [start_pos, end_pos) theo biên dòng, pad context, prefix NNN|.

    Trả về (line_start, line_end, text).
    """
    line_start = line_of(source_text, start_pos)
    line_end = line_of(source_text, max(start_pos, end_pos - 1))
    lines = source_text.split("\n")
    lo = max(1, line_start - max(0, context_lines))
    hi = min(len(lines), line_end + max(0, context_lines))
    body = lines[lo - 1 : hi]
    if line_numbers:
        text = "\n".join(f"{idx}|{line}" for idx, line in enumerate(body, start=lo))
    else:
        text = "\n".join(body)
    return lo, hi, text


def format_snippet_lines(
    source_text: str,
    line_start: int,
    line_end: int,
    context_lines: int = 0,
    line_numbers: bool = True,
) -> tuple[int, int, str]:
    """Cắt khoảng dòng 1-based (inclusive), pad context, prefix NNN|."""
    lines = source_text.split("\n")
    total = len(lines)
    lo = max(1, line_start - max(0, context_lines))
    hi = min(total, line_end + max(0, context_lines))
    body = lines[lo - 1 : hi]
    if line_numbers:
        text = "\n".join(f"{idx}|{line}" for idx, line in enumerate(body, start=lo))
    else:
        text = "\n".join(body)
    return lo, hi, text


# ---------------------------------------------------------------------------
# Block selector: action:<id> | command:<event> | field:<name> | query:<index>
# ---------------------------------------------------------------------------


@dataclass
class BlockMatch:
    kind: str  # sql_block | field
    name: str  # selector đã match, vd "action:GetCreatedVoucher"
    line: int
    raw: str


def _eq_ci(a: Optional[str], b: str) -> bool:
    return (a or "").lower() == b.lower()


def find_block(blocks: ExtractedBlocks, selector: str) -> tuple[list[BlockMatch], dict]:
    """Tìm block theo selector. Trả về (matches, available) — available để báo lỗi."""
    available = {
        "actions": sorted({c.id for c in blocks.sql_chunks if c.kind == "action" and c.id}),
        "commands": sorted({c.event for c in blocks.sql_chunks if c.kind == "command" and c.event}),
        "queries": sum(1 for c in blocks.sql_chunks if c.kind == "query"),
        "fields": [f.name for f in blocks.fields][:50],
    }
    if not selector or ":" not in selector:
        return [], available

    sel_kind, _, sel_val = selector.partition(":")
    sel_kind = sel_kind.strip().lower()
    sel_val = sel_val.strip()
    matches: list[BlockMatch] = []

    if sel_kind == "field":
        for f in blocks.fields:
            if _eq_ci(f.name, sel_val):
                matches.append(
                    BlockMatch(kind="field", name=f"field:{f.name}", line=f.line, raw=f.raw)
                )
        return matches, available

    if sel_kind == "query":
        queries = [c for c in blocks.sql_chunks if c.kind == "query"]
        try:
            idx = int(sel_val)
        except ValueError:
            idx = 0
        if idx >= 1 and idx <= len(queries):
            c = queries[idx - 1]
            matches.append(
                BlockMatch(kind="sql_block", name=f"query:{idx}", line=c.line, raw=c.raw)
            )
        elif not sel_val:
            for i, c in enumerate(queries, 1):
                matches.append(
                    BlockMatch(kind="sql_block", name=f"query:{i}", line=c.line, raw=c.raw)
                )
        return matches, available

    if sel_kind in ("action", "command"):
        for c in blocks.sql_chunks:
            if c.kind != sel_kind:
                continue
            key = c.id if sel_kind == "action" else c.event
            if _eq_ci(key, sel_val):
                matches.append(
                    BlockMatch(
                        kind="sql_block",
                        name=f"{sel_kind}:{key}",
                        line=c.line,
                        raw=c.raw,
                    )
                )
        return matches, available

    return matches, available
