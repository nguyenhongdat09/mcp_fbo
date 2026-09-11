"""Unit tests for text normalization in compare_things."""

import pytest
from compare_things.text_normalize import (
    detect_line_ending,
    normalize_text_lines,
    strip_bom,
)


def test_strip_bom():
    text_with_bom = "\ufeffHello World"
    assert strip_bom(text_with_bom) == "Hello World"
    assert strip_bom("Hello World") == "Hello World"


def test_detect_line_ending():
    assert detect_line_ending(b"line1\r\nline2\r\n") == "crlf"
    assert detect_line_ending(b"line1\nline2\n") == "lf"
    assert detect_line_ending(b"line1\rline2\r") == "cr"
    assert detect_line_ending(b"line1\r\nline2\n") == "mixed"
    assert detect_line_ending(b"single_line_no_newline") == "none"


def test_normalize_text_lines():
    text = "\ufeffLine 1  \r\nLine 2\r\n\r\nLine 3  "
    lines_default = normalize_text_lines(text, ignore_line_endings=True, ignore_whitespace=False)
    assert lines_default == ["Line 1  ", "Line 2", "", "Line 3  "]

    lines_stripped = normalize_text_lines(text, ignore_line_endings=True, ignore_whitespace=True)
    assert lines_stripped == ["Line 1", "Line 2", "", "Line 3"]
