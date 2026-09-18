"""Preprocess JavaScript source for ANTLR ECMAScript parser."""

from __future__ import annotations

import html
import re

_HTML_ENTITY_RE = re.compile(r"&(lt|gt|amp|quot|apos);", re.I)

# FBO macro @@var@@ / @@var — không phải JS hợp lệ, đổi thành identifier.
_FBO_MACRO_RE = re.compile(r"@@([A-Za-z_$][\w$]*)(@@)?")

# General entity refs &name; còn sót sau expand (kể cả &Entity; không chuẩn).
# (?<![\w$]) tránh nuốt bitwise-and kiểu `x&y;`.
_XML_ENTITY_REF_RE = re.compile(r"(?<![\w$])&([A-Za-z_][\w$.]*);")


def preprocess_js(source: str) -> str:
    """Clean and prepare JS code extracted from FBO XML."""
    if not source:
        return ""

    # 1. Unescape basic XML entities if they exist inside CDATA/text
    if _HTML_ENTITY_RE.search(source):
        source = html.unescape(source)

    # 2. Normalize carriage returns
    source = source.replace("\r\n", "\n").replace("\r", "\n")

    # 3. FBO macros @@var@@ / @@var -> identifier (giữ parse hợp lệ)
    if "@@" in source:
        source = _FBO_MACRO_RE.sub(lambda m: "_fbo_" + m.group(1), source)

    # 4. Entity refs &name; chưa expand -> identifier (tránh fail giả)
    if "&" in source:
        source = _XML_ENTITY_REF_RE.sub(
            lambda m: "_ent_" + m.group(1).replace(".", "_"), source
        )

    return source
