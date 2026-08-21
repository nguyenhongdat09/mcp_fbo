"""Extraction of g.$a formulas and g.showForm related controllers from Grid/Dir scripts."""

from __future__ import annotations

import re
from typing import Any
from xml_controller_summary.models import GridFormulas

SHOW_FORM_RE = re.compile(r"\bg\s*\.\s*showForm\s*\(\s*['\"]([a-zA-Z0-9_\$]+)['\"]\s*\)")
SHOW_DOLLAR_FORM_RE = re.compile(r"\bshow\$Form\s*\(\s*[^,]+,\s*['\"]([a-zA-Z0-9_\$]+)['\"]\s*\)")
G_A_START_RE = re.compile(r"\bg(?:\.\$a|\['\$a'\]|\[\"\$a\"\])\s*=\s*\{", re.IGNORECASE)
FILTER_SUFFIXES = ("Grid", "MultiGrid", "Form", "MultiForm", "Lookup")


def strip_js_comments(source: str) -> str:
    """Remove single-line and multi-line comments from JavaScript source."""
    if not source:
        return ""
    # Remove single line comments
    clean = re.sub(r"//.*$", "", source, flags=re.MULTILINE)
    # Remove multi-line comments
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL)
    return clean


def extract_brace_body(source: str, start_index: int) -> str | None:
    """Extract content inside matching braces { ... } starting at start_index (the opening brace)."""
    depth = 0
    in_single_quote = False
    in_double_quote = False
    escape = False
    start_pos = -1

    for i in range(start_index, len(source)):
        char = source[i]

        if escape:
            escape = False
            continue

        if char == "\\":
            escape = True
            continue

        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue

        if not in_single_quote and not in_double_quote:
            if char == "{":
                if depth == 0:
                    start_pos = i + 1
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and start_pos != -1:
                    return source[start_pos:i]

    return None


def parse_g_a_object_content(body: str) -> GridFormulas | None:
    """Parse key-value pairs in g.$a object body into expressions and aggregates."""
    if not body or not body.strip():
        return None

    expressions: dict[str, str] = {}
    aggregates: dict[str, list[str]] = {}

    # Tokenize entries separated by comma (outside quotes/brackets)
    entries: list[str] = []
    current: list[str] = []
    depth_bracket = 0
    in_sq = False
    in_dq = False
    esc = False

    for char in body:
        if esc:
            current.append(char)
            esc = False
            continue

        if char == "\\":
            current.append(char)
            esc = True
            continue

        if char == "'" and not in_dq:
            in_sq = not in_sq
            current.append(char)
            continue

        if char == '"' and not in_sq:
            in_dq = not in_dq
            current.append(char)
            continue

        if not in_sq and not in_dq:
            if char == "[":
                depth_bracket += 1
            elif char == "]":
                depth_bracket = max(0, depth_bracket - 1)
            elif char == "," and depth_bracket == 0:
                entries.append("".join(current).strip())
                current = []
                continue

        current.append(char)

    if current:
        entries.append("".join(current).strip())

    for entry in entries:
        if not entry or ":" not in entry:
            continue
        colon_idx = entry.index(":")
        raw_key = entry[:colon_idx].strip().strip("'\"")
        raw_val = entry[colon_idx + 1:].strip()

        if not raw_key:
            continue

        # Case 1: String expression: '...' or "..."
        if (raw_val.startswith("'") and raw_val.endswith("'")) or (raw_val.startswith('"') and raw_val.endswith('"')):
            val_str = raw_val[1:-1].replace("\\'", "'").replace('\\"', '"').strip()
            # If string contains := or [col]
            expressions[raw_key] = val_str
        # Case 2: Array aggregate: [ 't_x', 'x' ]
        elif raw_val.startswith("[") and raw_val.endswith("]"):
            arr_inner = raw_val[1:-1].strip()
            # Extract all string literals inside array
            str_items = re.findall(r"['\"]([^'\"]*)['\"]", arr_inner)
            if len(str_items) == 2:
                aggregates[raw_key] = [str_items[0].strip(), str_items[1].strip()]

    if not expressions and not aggregates:
        return None

    return GridFormulas(expressions=expressions, aggregates=aggregates)


def extract_g_a_formulas(js_source: str) -> GridFormulas | None:
    """Search for g.$a = { ... } declaration in JS source and parse formulas."""
    clean_js = strip_js_comments(js_source)
    m = G_A_START_RE.search(clean_js)
    if not m:
        return None

    brace_start = m.end() - 1  # The '{' character index
    body = extract_brace_body(clean_js, brace_start)
    if body is None:
        return None

    return parse_g_a_object_content(body)


def derive_related_from_show_form(target_form: str) -> list[str]:
    """Derive related controller candidates from a target form name (FBO Graph rule)."""
    candidates = [target_form]
    if target_form.endswith("Filter"):
        prefix = target_form[:-6]  # strip 'Filter'
        for suffix in FILTER_SUFFIXES:
            candidates.append(f"{prefix}{suffix}")
    return candidates


def extract_show_forms_and_related(js_source: str) -> tuple[list[str], list[str]]:
    """Extract g.showForm calls and show$Form wrappers, then derive candidate related controllers."""
    clean_js = strip_js_comments(js_source)
    show_forms_set: set[str] = set()

    for match in SHOW_FORM_RE.finditer(clean_js):
        form_name = match.group(1).strip()
        if form_name:
            show_forms_set.add(form_name)

    for match in SHOW_DOLLAR_FORM_RE.finditer(clean_js):
        form_name = match.group(1).strip()
        if form_name:
            show_forms_set.add(form_name)

    if not show_forms_set:
        return [], []

    show_forms = sorted(show_forms_set)
    related_set: set[str] = set()
    for sf in show_forms:
        for rel in derive_related_from_show_form(sf):
            related_set.add(rel)

    return show_forms, sorted(related_set)
