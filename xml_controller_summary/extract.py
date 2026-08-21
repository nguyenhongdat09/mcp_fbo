"""Extract script, command, action, query, and field blocks from flat XML."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Literal

ENCRYPTED_RE = re.compile(
    r"<(encrypted|Encrypted)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

CDATA_IN_TEXT_RE = re.compile(
    r"<text>\s*<!\[CDATA\[(.*?)\]\]>\s*</text>",
    re.DOTALL | re.IGNORECASE,
)

CDATA_ANY_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)

SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.DOTALL | re.IGNORECASE)
COMMAND_RE = re.compile(r"<command\b([^>]*)>(.*?)</command>", re.DOTALL | re.IGNORECASE)
ACTION_RE = re.compile(r"<action\b([^>]*)>(.*?)</action>", re.DOTALL | re.IGNORECASE)
QUERY_RE = re.compile(r"<query\b([^>]*)>(.*?)</query>", re.DOTALL | re.IGNORECASE)
FIELD_RE = re.compile(
    r"<field\b([^>/]*)(?:/>|>(.*?)</field>)",
    re.DOTALL | re.IGNORECASE,
)
ITEMS_RE = re.compile(r"<items\b([^>]*)/?>", re.IGNORECASE)
CLIENT_SCRIPT_RE = re.compile(r"<clientScript\b[^>]*>(.*?)</clientScript>", re.DOTALL | re.IGNORECASE)
TITLE_RE = re.compile(r"<title\b([^>]*)/?>", re.IGNORECASE)

ATTR_RE = re.compile(r'([a-zA-Z0-9_:\-]+)\s*=\s*["\']([^"\']*)["\']')

_SQL_HEAD = re.compile(
    r"^\s*(declare|select|if\s+exists|exec(?:ute)?|with|insert|update|delete|create|alter|drop|begin)\b",
    re.IGNORECASE,
)
_JS_HINT = re.compile(
    r"(function\s+|var\s+f\s*=\s*this|\$message|sender\.parentForm)",
    re.IGNORECASE,
)
_FBO_IFDEF_RE = re.compile(r"#(IF|ELSE|THEN|END)\b[^\r\n]*", re.IGNORECASE)


@dataclass
class JsChunk:
    source: str
    line: int
    content: str


@dataclass
class SqlChunk:
    kind: Literal["command", "action", "query"]
    event: str | None
    id: str | None
    line: int
    content: str
    lang: Literal["sql", "js"] = "sql"
    has_ifdef: bool = False


@dataclass
class RawField:
    name: str
    attrs: dict[str, str] = field(default_factory=dict)
    items_attrs: dict[str, str] = field(default_factory=dict)
    client_script: str = ""
    line: int = 0


@dataclass
class ExtractedBlocks:
    js_chunks: list[JsChunk] = field(default_factory=list)
    sql_chunks: list[SqlChunk] = field(default_factory=list)
    fields: list[RawField] = field(default_factory=list)
    root_attrs: dict[str, str] = field(default_factory=dict)
    title_v: str | None = None
    title_e: str | None = None
    skipped_encrypted_count: int = 0
    warnings: list[str] = field(default_factory=list)


def parse_attrs(attr_str: str) -> dict[str, str]:
    """Extract XML attributes from a tag string."""
    return dict(ATTR_RE.findall(attr_str))


def strip_encrypted(text: str) -> tuple[str, int]:
    """Strip <encrypted> tags and replace with comments."""
    count = 0

    def _repl(_m):
        nonlocal count
        count += 1
        return "/* encrypted_skipped */"

    cleaned = ENCRYPTED_RE.sub(_repl, text)
    return cleaned, count


def extract_cdata_from_inner(inner_text: str) -> str:
    """Extract CDATA content from inside an element, or fallback to plain text."""
    if not inner_text:
        return ""
    m_text = CDATA_IN_TEXT_RE.search(inner_text)
    if m_text:
        return m_text.group(1).strip()

    m_cdata = CDATA_ANY_RE.search(inner_text)
    if m_cdata:
        return m_cdata.group(1).strip()

    plain = re.sub(r"<[^>]+>", "", inner_text).strip()
    return html.unescape(plain)


def sniff_checking(cdata_content: str) -> Literal["sql", "js"]:
    """Sniff whether Checking command is JavaScript or T-SQL."""
    stripped = cdata_content.strip()
    if not stripped:
        return "sql"

    if _SQL_HEAD.search(stripped):
        return "sql"

    if _JS_HINT.search(stripped):
        return "js"

    # Default to SQL if ambiguous
    return "sql"


def preprocess_sql_fragment(raw_sql: str) -> tuple[str, bool]:
    """Clean comments, comment-out FBO #IF/#ELSE preprocessor directives, and detect ifdef signal."""
    if not raw_sql:
        return "", False

    has_ifdef = bool(_FBO_IFDEF_RE.search(raw_sql))
    cleaned = raw_sql

    if has_ifdef:
        cleaned = _FBO_IFDEF_RE.sub("-- \\g<0>", cleaned)

    return cleaned, has_ifdef


def extract_controller_blocks(flat_text: str) -> ExtractedBlocks:
    """Parse flat XML text into JS, SQL, and Field blocks."""
    cleaned_text, enc_count = strip_encrypted(flat_text)
    res = ExtractedBlocks(skipped_encrypted_count=enc_count)

    # 1. Root controller attributes
    root_match = re.search(r"<([a-zA-Z0-9_\-]+)\b([^>]*)>", cleaned_text)
    if root_match:
        res.root_attrs = parse_attrs(root_match.group(2))

    # 1b. <title v="..." e="..."> child element attributes
    title_match = TITLE_RE.search(cleaned_text)
    if title_match:
        title_attrs = parse_attrs(title_match.group(1))
        res.title_v = title_attrs.get("v") or None
        res.title_e = title_attrs.get("e") or None

    # Fallback to root attrs if child <title> was not specified
    if not res.title_v and res.root_attrs.get("title"):
        res.title_v = res.root_attrs.get("title")
    if not res.title_e and res.root_attrs.get("title2"):
        res.title_e = res.root_attrs.get("title2")

    # Helper to estimate line numbers
    def get_line(pos: int) -> int:
        return cleaned_text.count("\n", 0, pos) + 1

    # 2. <script> tags -> JS
    for m in SCRIPT_RE.finditer(cleaned_text):
        cdata = extract_cdata_from_inner(m.group(2))
        if cdata:
            res.js_chunks.append(
                JsChunk(
                    source="script",
                    line=get_line(m.start()),
                    content=cdata,
                )
            )

    # 3. <command> tags
    for m in COMMAND_RE.finditer(cleaned_text):
        attrs = parse_attrs(m.group(1))
        event = attrs.get("event")
        cdata = extract_cdata_from_inner(m.group(2))
        line = get_line(m.start())

        if event and event.lower() == "checking":
            lang = sniff_checking(cdata)
            if lang == "js":
                if cdata:
                    res.js_chunks.append(
                        JsChunk(
                            source="command:Checking",
                            line=line,
                            content=cdata,
                        )
                    )
            else:
                res.warnings.append("checking_routed_to_sql")
                cleaned_sql, ifdef = preprocess_sql_fragment(cdata)
                res.sql_chunks.append(
                    SqlChunk(
                        kind="command",
                        event=event,
                        id=None,
                        line=line,
                        content=cleaned_sql,
                        lang="sql",
                        has_ifdef=ifdef,
                    )
                )
        else:
            cleaned_sql, ifdef = preprocess_sql_fragment(cdata)
            res.sql_chunks.append(
                SqlChunk(
                    kind="command",
                    event=event,
                    id=None,
                    line=line,
                    content=cleaned_sql,
                    lang="sql",
                    has_ifdef=ifdef,
                )
            )

    # 4. <action> tags -> SQL
    for m in ACTION_RE.finditer(cleaned_text):
        attrs = parse_attrs(m.group(1))
        action_id = attrs.get("id")
        cdata = extract_cdata_from_inner(m.group(2))
        line = get_line(m.start())
        cleaned_sql, ifdef = preprocess_sql_fragment(cdata)
        res.sql_chunks.append(
            SqlChunk(
                kind="action",
                event=None,
                id=action_id,
                line=line,
                content=cleaned_sql,
                lang="sql",
                has_ifdef=ifdef,
            )
        )

    # 5. <query> tags -> SQL
    for m in QUERY_RE.finditer(cleaned_text):
        cdata = extract_cdata_from_inner(m.group(2))
        line = get_line(m.start())
        cleaned_sql, ifdef = preprocess_sql_fragment(cdata)
        res.sql_chunks.append(
            SqlChunk(
                kind="query",
                event=None,
                id=None,
                line=line,
                content=cleaned_sql,
                lang="sql",
                has_ifdef=ifdef,
            )
        )

    # 6. <field> tags
    for m in FIELD_RE.finditer(cleaned_text):
        attrs = parse_attrs(m.group(1))
        field_name = attrs.get("name", "")
        if not field_name:
            continue

        inner = m.group(2) or ""
        items_attrs = {}
        items_match = ITEMS_RE.search(inner)
        if items_match:
            items_attrs = parse_attrs(items_match.group(1))

        client_script = ""
        cs_match = CLIENT_SCRIPT_RE.search(inner)
        if cs_match:
            client_script = extract_cdata_from_inner(cs_match.group(1))

        res.fields.append(
            RawField(
                name=field_name,
                attrs=attrs,
                items_attrs=items_attrs,
                client_script=client_script,
                line=get_line(m.start()),
            )
        )

    return res
