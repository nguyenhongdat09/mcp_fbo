"""AddFieldToReport — inject field h_* từ Grid XML vào file Report XML FBO.

Port từ fbo-autocomplete ConvertGridToHeader.addFieldToReport:
- Report XML = file cùng tên trong thư mục anh em 'Report' (Grid → Report).
- Sinh danh sách `<field name="h_*">` từ Grid (build_header_field_defs),
  lọc field chưa tồn tại rồi chèn trước </fields> của khối <fields> CUỐI.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .grid_parser import build_header_field_defs

_FIELDS_BLOCK_RE = re.compile(r"<fields\b[^>]*>[\s\S]*?</fields>|<fields\s*/>", re.IGNORECASE)
_FIELD_NAME_RE = re.compile(r'<field\s+name="([^"]+)"', re.IGNORECASE)


class ReportUpdate(BaseModel):
    """Kết quả bước AddFieldToReport trước khi export Excel."""

    report_path: Optional[str] = Field(
        default=None, description="Path file Report XML đích (Controllers/Report/<tên_grid>.xml)."
    )
    status: Literal["updated", "up_to_date", "report_not_found", "no_fields_block"] = Field(
        description=(
            "'updated' = đã inject field h_* mới vào Report XML; "
            "'up_to_date' = Report XML đã có đủ field; "
            "'report_not_found' = không có file Report XML cùng tên (bỏ qua, vẫn export); "
            "'no_fields_block' = Report XML không có khối <fields> để inject."
        )
    )
    added_fields: List[str] = Field(
        default_factory=list, description="Tên field h_* mới được inject (rỗng nếu không thêm)."
    )


def update_report_fields(grid_path: Path, grid_xml: str) -> ReportUpdate:
    """Chạy AddFieldToReport cho file Grid — inject field h_* thiếu vào Report XML.

    Không raise khi Report XML thiếu/không inject được — trả status trong ReportUpdate.
    """
    report_path = grid_path.parent.parent / "Report" / grid_path.name
    if not report_path.exists():
        return ReportUpdate(report_path=str(report_path), status="report_not_found")

    report_xml = report_path.read_text(encoding="utf-8-sig")
    blocks = list(_FIELDS_BLOCK_RE.finditer(report_xml))
    if not blocks:
        return ReportUpdate(report_path=str(report_path), status="no_fields_block")

    last = blocks[-1]
    existing = set(_FIELD_NAME_RE.findall(last.group(0)))

    missing = [fx for name, fx in build_header_field_defs(grid_xml) if name not in existing]
    if not missing:
        return ReportUpdate(report_path=str(report_path), status="up_to_date")

    block = last.group(0)
    close_idx = block.rfind("</fields>")
    if close_idx < 0:
        return ReportUpdate(report_path=str(report_path), status="no_fields_block")

    new_block = block[:close_idx] + "\n".join(missing) + "\n</fields>"
    new_xml = report_xml[: last.start()] + new_block + report_xml[last.end() :]
    report_path.write_text(new_xml, encoding="utf-8-sig")

    added = [_FIELD_NAME_RE.search(fx).group(1) for fx in missing]
    return ReportUpdate(
        report_path=str(report_path), status="updated", added_fields=added
    )
