"""Pretty-print XML — port từ vkXmlBeautify.js (mikeburgh.xml-format / vkBeautify),
giữ nguyên xử lý <clientScript> của FastBusiness. MIT (vkBeautify)."""

from __future__ import annotations

import re

_SPACE_MAP = {i: " " * i for i in range(1, 13)}


def _create_shift_arr(step) -> list[str]:
    if isinstance(step, str) and not step.lstrip("-").isdigit():
        space = step
    else:
        try:
            n = int(step)
        except (TypeError, ValueError):
            n = 4
        space = _SPACE_MAP.get(n, "    ")

    shift = ["\n"]
    for _ in range(100):
        shift.append(shift[-1] + space)
    return shift


_RE_COMMENT_OPEN = re.compile(r"<!--")
_RE_COMMENT_CLOSE = re.compile(r"-->")
_RE_CDATA_OPEN = re.compile(r"<!\[CDATA\[")
_RE_CDATA_CLOSE = re.compile(r"\]\]>")
_RE_DOCTYPE = re.compile(r"<!DOCTYPE")
_RE_DOCTYPE_END = re.compile(r"\]>")
_RE_CLIENT_OPEN = re.compile(r"<clientScript>")
_RE_CLIENT_CLOSE = re.compile(r"</clientScript>")
_RE_CLOSE_TAG_START = re.compile(r"^</[^<>!?/\s]")
_RE_OPEN_TAG_START = re.compile(r"^<[^<>!?/\s]")
_RE_CLOSE_TAG_NAME = re.compile(r"^</[^<>!?/\s]+")
_RE_OPEN_TAG_NAME = re.compile(r"^<[^<>!?/\s]+")
_RE_ANY_CLOSE = re.compile(r"</")
_RE_OPEN_TAG_ANYWHERE = re.compile(r"<[^<>!?/\s]")
_RE_SELF_CLOSE = re.compile(r"/>")


def xml_beautify(text: str, indent_step=4) -> str:
    """Format XML. indent_step: số khoảng trắng (1-12) hoặc '\\t'."""
    if indent_step is None:
        indent_step = 4

    ar = text.strip().replace("<", "~::~<").split("~::~")
    in_comment = in_cdata = in_doctype = in_client_script = False
    deep_real = 0
    deep = 0
    out = ""
    shift = _create_shift_arr(indent_step)

    for ix, chunk in enumerate(ar):
        if in_comment:
            out += chunk
            if _RE_COMMENT_CLOSE.search(chunk):
                in_comment = False
        elif in_cdata:
            out += chunk
            if _RE_CDATA_CLOSE.search(chunk):
                in_cdata = False
        elif _RE_COMMENT_OPEN.search(chunk):
            out = out.strip() + shift[deep] + chunk
            in_comment = True
            if _RE_COMMENT_CLOSE.search(chunk):
                in_comment = False
        elif _RE_CDATA_OPEN.search(chunk):
            out += chunk
            in_cdata = True
            if _RE_CDATA_CLOSE.search(chunk):
                in_cdata = False
        elif _RE_CDATA_CLOSE.search(chunk):
            out += chunk
            in_cdata = False
        elif _RE_DOCTYPE.search(chunk):
            out = out.strip() + shift[deep] + chunk.strip()
            in_doctype = True
            if _RE_DOCTYPE_END.search(chunk):
                in_doctype = False
        elif in_doctype and _RE_DOCTYPE_END.search(chunk):
            out += shift[min(deep + 1, 100)] + chunk.strip()
            in_doctype = False
        elif in_doctype:
            out += shift[min(deep + 1, 100)] + chunk.strip()
        elif _RE_CLIENT_OPEN.search(chunk):
            out = out.strip() + shift[deep] + chunk
            in_client_script = True
        elif in_client_script and _RE_CLIENT_CLOSE.search(chunk):
            out += chunk
            in_client_script = False
        elif (
            ix > 0
            and _RE_CLOSE_TAG_START.search(chunk)
            and _RE_OPEN_TAG_START.search(ar[ix - 1])
            and _RE_CLOSE_TAG_NAME.search(chunk).group(0).replace("/", "")
            == _RE_OPEN_TAG_NAME.search(ar[ix - 1]).group(0)
        ):
            if deep_real > 0:
                deep_real -= 1
            if deep_real <= 100:
                deep = deep_real
            out += chunk
        elif _RE_ANY_CLOSE.search(chunk):
            if deep_real > 0:
                deep_real -= 1
            if deep_real <= 100:
                deep = deep_real
            out = out.strip() + shift[deep] + chunk
        elif _RE_OPEN_TAG_ANYWHERE.search(chunk):
            out = out.strip() + shift[deep] + chunk
            deep_real += 1
            if _RE_SELF_CLOSE.search(chunk):
                deep_real -= 1
            if deep_real <= 100:
                deep = deep_real
        else:
            out += chunk

    return out.strip()
