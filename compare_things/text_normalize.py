"""Text normalization helpers for compare_things."""

from __future__ import annotations

import re
from typing import List, Tuple


def strip_bom(text: str) -> str:
    """Strip UTF-8 / UTF-16 BOM from the beginning of string if present."""
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def detect_line_ending(raw_bytes: bytes) -> str:
    """Detect predominant line ending from raw bytes."""
    has_crlf = b"\r\n" in raw_bytes
    # Check for standalone \r or \n
    # Replace \r\n with empty to see if standalone \r or \n remain
    without_crlf = raw_bytes.replace(b"\r\n", b"")
    has_lf = b"\n" in without_crlf
    has_cr = b"\r" in without_crlf

    if has_crlf and not has_lf and not has_cr:
        return "crlf"
    if has_lf and not has_crlf and not has_cr:
        return "lf"
    if has_cr and not has_crlf and not has_lf:
        return "cr"
    if (has_crlf and (has_lf or has_cr)) or (has_lf and has_cr):
        return "mixed"
    return "none"


def normalize_text_lines(
    text: str,
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
) -> List[str]:
    """
    Normalize text into list of lines:
    - Strip BOM
    - Normalize CRLF/CR to LF if ignore_line_endings=True
    - When ignore_line_endings=False, preserve \r to distinguish CRLF vs LF
    - Strip leading/trailing whitespace on each line if ignore_whitespace=True
    """
    text = strip_bom(text)
    if ignore_line_endings:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.splitlines()
        if ignore_whitespace:
            lines = [line.strip() for line in lines]
    else:
        # Split on \n only so \r remains at the end of line
        raw = text.split("\n")
        if text.endswith("\n"):
            raw.pop()
        if ignore_whitespace:
            # Strip spaces and tabs, but preserve \r
            lines = [line.strip(" \t") for line in raw]
        else:
            lines = raw

    return lines

