"""Parse Grid XML FBO — port nguyên logic regex từ fbo-autocomplete.

Nguồn gốc:
- ConvertGridToPivotExcel.js: _extractGridAttrs / _extractGridViewFieldNames / _buildDefaults
- ConvertGridToHeader.js: CvtToFieldReport (headersMap + view fields → token excel)
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

_PIVOT_TAG_RE = re.compile(r"<pivot\b[^>]*\/?>", re.IGNORECASE)
_GRID_TAG_RE = re.compile(r"<grid\b[^>]*>", re.IGNORECASE)
_VIEW_GRID_TAG_RE = re.compile(r"<view\b[^>]*\bid\s*=\s*[\"']Grid[\"'][^>]*>", re.IGNORECASE)
_VIEW_CLOSE_RE = re.compile(r"</view>", re.IGNORECASE)

# <field ...>...</field> (không self-closing) — block field đầy đủ trong <fields>
_FIELD_BLOCK_RE = re.compile(r"<field[^>]*>.*?</field>", re.IGNORECASE | re.DOTALL)
# <field name="x"/> self-closing — field trong <view id="Grid"> (và các nơi khác)
_FIELD_SELF_CLOSING_RE = re.compile(r'<field\s+name="(.*?)"\s*/>', re.IGNORECASE)
_FIELD_NAME_IN_BLOCK_RE = re.compile(r'<field\b[^>]*\bname\s*=\s*"([^"]*)"', re.IGNORECASE)

_HEADER_V_RE = re.compile(r'<header[^>]*\bv="([^"]*)"', re.IGNORECASE)
_HEADER_E_RE = re.compile(r'<header[^>]*\be="([^"]*)"', re.IGNORECASE)

# numFmt giống hệt ConvertGridToHeader.js
_FMT_AMOUNT = '_(* #,##0_);_(* (#,##0);_(* ""_);_(@_)'
_FMT_QUANTITY = '_(* #,##0.000_);_(* (#,##0.000);_(* ""_);_(@_)'
_FMT_FOREIGN = '_(* #,##0.00_);_(* (#,##0.00);_(* ""_);_(@_)'
_FMT_DATE = "dd/mm/yyyy"


def has_pivot_tag(xml: str) -> bool:
    """Có thẻ <pivot .../> → báo cáo xoay."""
    return _PIVOT_TAG_RE.search(xml) is not None


def _extract_attr(tag: str, attr_name: str) -> str:
    m = re.search(attr_name + r'\s*=\s*"([^"]*)"', tag, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def extract_grid_attrs(xml: str) -> Dict[str, str]:
    """rowField / columnField / dataFields — ưu tiên <pivot> → <grid> → <view id="Grid">."""
    pivot_m = _PIVOT_TAG_RE.search(xml)
    grid_m = _GRID_TAG_RE.search(xml)
    view_m = _VIEW_GRID_TAG_RE.search(xml)
    pivot_tag = pivot_m.group(0) if pivot_m else ""
    grid_tag = grid_m.group(0) if grid_m else ""
    view_tag = view_m.group(0) if view_m else ""
    return {
        "rowField": (
            _extract_attr(pivot_tag, "rowField")
            or _extract_attr(grid_tag, "rowField")
            or _extract_attr(view_tag, "rowField")
        ),
        "columnField": (
            _extract_attr(pivot_tag, "columnField")
            or _extract_attr(grid_tag, "columnField")
            or _extract_attr(view_tag, "columnField")
        ),
        "dataFields": (
            _extract_attr(pivot_tag, "dataFields")
            or _extract_attr(grid_tag, "dataFields")
            or _extract_attr(view_tag, "dataFields")
        ),
    }


def extract_grid_view_field_names(xml: str) -> List[str]:
    """Danh sách name của <field .../> bên trong <view id="Grid">...</view>."""
    start_m = _VIEW_GRID_TAG_RE.search(xml)
    if not start_m:
        return []
    inner = xml[start_m.end():]
    end_m = _VIEW_CLOSE_RE.search(inner)
    if not end_m:
        return []
    inner = inner[: end_m.start()]
    return [n.strip() for n in _FIELD_NAME_IN_BLOCK_RE.findall(inner) if n.strip()]


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in str(value).split(",") if x.strip()]


def _unique(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        k = str(item).lower()
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out


def _to_row_token(name: str) -> str:
    """Field view → token row input dạng ?h_<name>."""
    n = (name or "").strip()
    if not n:
        return n
    return n if re.match(r"^\?h_", n, re.IGNORECASE) else "?h_" + n


def _is_field_in_data_fields(token: str, data_fields: List[str]) -> bool:
    t = (token or "").strip()
    if not t:
        return True
    base = re.sub(r"^\?h_", "", t, flags=re.IGNORECASE)
    for d in data_fields:
        x = (d or "").strip().lower()
        if x and (x == t.lower() or x == base.lower()):
            return True
    return False


def build_pivot_defaults(xml: str) -> Dict[str, str]:
    """Defaults row/column/value csv — port _buildDefaults của ConvertGridToPivotExcel.js."""
    attrs = extract_grid_attrs(xml)
    data_fields = _split_csv(attrs["dataFields"])

    row_candidates: List[str] = []
    if attrs["rowField"]:
        row_candidates.append(attrs["rowField"])
        row_candidates.append("systotal")
    for name in extract_grid_view_field_names(xml):
        row_candidates.append(_to_row_token(name))

    row_defaults = _unique(
        [x for x in row_candidates if not _is_field_in_data_fields(x, data_fields)]
    )
    col_defaults = _unique([x for x in [attrs["columnField"], "npivot"] if x])
    value_defaults = _unique(data_fields)

    return {
        "row_csv": ",".join(row_defaults),
        "column_csv": ",".join(col_defaults),
        "value_csv": ",".join(value_defaults),
    }


def _headers_map(xml: str) -> Dict[str, Dict[str, str]]:
    """name -> {v, e, fmt} cho field không hidden và có <header v=".." e=".."/>."""
    headers_map: Dict[str, Dict[str, str]] = {}
    for m in _FIELD_BLOCK_RE.finditer(xml):
        field = m.group(0)
        hidden_m = re.search(r'hidden="([^"]*)"', field)
        if hidden_m and hidden_m.group(1) == "true":
            continue
        name_m = re.search(r'name="([^"]*)"', field)
        v_m = _HEADER_V_RE.search(field)
        e_m = _HEADER_E_RE.search(field)
        type_m = re.search(r'type="([^"]*)"', field)
        dt_m = re.search(r'dataFormatString="([^"]*)"', field)
        if not (name_m and v_m and e_m):
            continue
        fmt = ""
        if dt_m:
            datatype = dt_m.group(1)
            if "Price" in datatype or "Amount" in datatype:
                fmt = _FMT_AMOUNT
            elif "quantity" in datatype:
                fmt = _FMT_QUANTITY
            elif "foreign" in datatype:
                fmt = _FMT_FOREIGN
        if type_m and type_m.group(1) == "DateTime":
            fmt = _FMT_DATE
        headers_map[name_m.group(1)] = {"v": v_m.group(1), "e": e_m.group(1), "fmt": fmt}
    return headers_map


def parse_header_fields(xml: str) -> List[Tuple[str, str, str]]:
    """Port CvtToFieldReport: trả list [h_<name>, !2.<name>, numFmt] theo thứ tự field view.

    - Bỏ field hidden="true"; chỉ nhận field có <header v=".." e=".."/>.
    - numFmt theo dataFormatString/type; default '@'.
    """
    hmap = _headers_map(xml)
    headers: List[Tuple[str, str, str]] = []
    for fm in _FIELD_SELF_CLOSING_RE.finditer(xml):
        field_name = fm.group(1)
        if field_name in hmap:
            headers.append(("h_" + field_name, "!2." + field_name, hmap[field_name]["fmt"] or "@"))
    return headers


# 5 field header mặc định AddFieldToReport luôn append (y hệt extension)
_DEFAULT_HEADER_FIELDS = [
    ("h_tu_ngay", "Từ ngày", "From Date"),
    ("h_den_ngay", "Đến ngày", "To Date"),
    ("h_tu_ky", "Từ kỳ", "From Period"),
    ("h_den_ky", "Đến kỳ", "To Period"),
    ("h_nam", "Năm", "Year"),
]


def build_header_field_defs(xml: str) -> List[Tuple[str, str]]:
    """Port phần newFields của CvtToFieldReport — list [(name, field_xml)].

    Mỗi field trong <view id="Grid"> có header → `<field name="h_<name>" .../>`
    (strip %l), kèm 5 field mặc định h_tu_ngay/h_den_ngay/h_tu_ky/h_den_ky/h_nam.
    """
    hmap = _headers_map(xml)
    defs: List[Tuple[str, str]] = []
    for fm in _FIELD_SELF_CLOSING_RE.finditer(xml):
        field_name = fm.group(1)
        if field_name not in hmap:
            continue
        h = hmap[field_name]
        h_name = ("h_" + field_name).replace("%l", "")
        field_xml = (
            f'<field name="{h_name}" type= "String">\n'
            f'    <header v="{h["v"]}" e="{h["e"]}" />\n'
            f"</field>"
        )
        defs.append((h_name, field_xml))
    for name, v, e in _DEFAULT_HEADER_FIELDS:
        defs.append(
            (name, f'<field name="{name}" type="String" >\n    <header v="{v}" e="{e}" />\n</field>')
        )
    return defs
