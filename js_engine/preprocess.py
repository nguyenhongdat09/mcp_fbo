"""Preprocess JavaScript source for ANTLR ECMAScript parser."""

from __future__ import annotations

import html
import re

_HTML_ENTITY_RE = re.compile(r"&(lt|gt|amp|quot|apos);", re.I)


def preprocess_js(source: str) -> str:
    """Clean and prepare JS code extracted from FBO XML."""
    if not source:
        return ""

    # 1. Unescape basic XML entities if they exist inside CDATA/text
    if _HTML_ENTITY_RE.search(source):
        source = html.unescape(source)

    # 2. Normalize carriage returns
    source = source.replace("\r\n", "\n").replace("\r", "\n")

    return source
