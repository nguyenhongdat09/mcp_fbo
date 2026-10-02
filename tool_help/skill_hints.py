"""related_skills — gợi ý skill FBO liên quan theo text step/UR.

Các step thiết kế/sửa layout, JS grid, mẫu in... thường route vào
read_local_file hoặc no_match và agent phải tự nhớ skill. Module này map
keyword → skill name để response kèm ``related_skills`` ngay trên step.

Thêm hint mới = thêm 1 tuple (regex, [skill,...]) vào SKILL_HINTS.
"""
from __future__ import annotations

import re

SKILL_HINTS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(
        r"pattern.{0,10}view|view\s*item|anchor|\bsplit\b|chen\s*ngang|"
        r"(ẩn|hiện|hide|show).{0,15}(field|cột|column)|ẩn\s*(field|cột)|"
        r"layout|tab\s*thông\s*tin|columns=|kéo\s*(form|field)",
        re.IGNORECASE | re.UNICODE), ["fbo-design-view-field"]),
    (re.compile(
        r"dòng\s*lọc|allowfilter|lọc\s*cột|lọc\s*trên\s*grid|tổng\s*cộng",
        re.IGNORECASE | re.UNICODE), ["fbo_grid_filter"]),
    (re.compile(
        r"onchange|onfocus|g\.\$?a|g\.request|f\.request|flowmulti|"
        r"grid\s*toolbar|readOnly.*dòng|fill.{0,10}grid|clear.{0,10}grid|"
        r"executeexpression|cancelEvent",
        re.IGNORECASE | re.UNICODE), ["fbo-js-skill"]),
    (re.compile(
        r"excel|\.xlsx|pivot|mẫu\s*in|templatefile",
        re.IGNORECASE | re.UNICODE),
        ["fbo-excel-pivot-template", "excel-mcp"]),
    (re.compile(
        r"\brs_|\bzc_|proc\s*báo\s*cáo|sổ\s*chi\s*tiết|report\s*proc|"
        r"drill|truy\s*ngược",
        re.IGNORECASE | re.UNICODE), ["fbo-procedure-create-report"]),
    (re.compile(
        r"đồ\s*thị|\bgraph\b|\bchart\b",
        re.IGNORECASE | re.UNICODE), ["fbo-procedure-create-report"]),
    (re.compile(
        r"partition|\$\d{6}|\$yyyymm|%partition|phân\s*kỳ",
        re.IGNORECASE | re.UNICODE), ["fbo-partition-table-knowledge"]),
    (re.compile(
        r"hddt|hóa\s*đơn\s*điện\s*tử|e-?invoice|einvoice|dmhddtbs",
        re.IGNORECASE | re.UNICODE),
        ["fbo-create-hddt", "fbo_hddt_external"]),
    (re.compile(
        r"import.*xml|hddv|inputinvoice|upload\s*invoice",
        re.IGNORECASE | re.UNICODE), ["fbo-create-hddv"]),
    (re.compile(
        r"lấy\s*dữ\s*liệu|retrieve|stt_rec_|fsdsttrcrefer|đã\s*lấy|còn\s*lại",
        re.IGNORECASE | re.UNICODE), ["fbo-update-qty-link-voucher"]),
    (re.compile(
        r"kiểu\s*duyệt|trình\s*duyệt|phê\s*duyệt|\bapv\b|dmkieuduyet|"
        r"dmloaiduyet",
        re.IGNORECASE | re.UNICODE),
        ["fbo-approval-category-dimension"]),
    (re.compile(
        r"(tạo|thêm).{0,15}danh\s*mục|category.{0,10}(mới|new)",
        re.IGNORECASE | re.UNICODE), ["fbo-create-category"]),
    (re.compile(
        r"(tạo|thêm).{0,15}(chứng\s*từ|voucher)",
        re.IGNORECASE | re.UNICODE), ["fbo-create-vocuher"]),
    (re.compile(
        r"quy\s*đổi|hệ\s*số|he_so|\bdvt\b|đơn\s*vị\s*tính",
        re.IGNORECASE | re.UNICODE), ["fbo-quy-doi-dvt"]),
    (re.compile(
        r"gửi\s*mail|fsdmail|send\s*mail|email",
        re.IGNORECASE | re.UNICODE), ["fbo-send-mail-customize"]),
]


def skill_hints(text: str) -> list[str]:
    """Trả list skill name (dedupe, giữ thứ tự) match text step/UR."""
    out: list[str] = []
    seen: set[str] = set()
    for rx, skills in SKILL_HINTS:
        if rx.search(text or ""):
            for s in skills:
                if s not in seen:
                    seen.add(s)
                    out.append(s)
    return out
