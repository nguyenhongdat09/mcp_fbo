"""Xuất Excel thường từ Grid XML — port exportToExcel (exceljs) sang openpyxl.

Template assets/mau_chuan.xlsx:
- Row 9  : header token  ?h_<field>  (nền EDF5FF, bold, center, border)
- Row 10 : data token    !2.<field>{b:systotal=0}  (numFmt, border)
- Merge A6:last6, A7:last7 (điều kiện lọc), toàn bộ cột width 16.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
TEMPLATE_PATH = _ASSETS_DIR / "mau_chuan.xlsx"

_HEADER_FILL = PatternFill(fill_type="solid", fgColor="FFEDF5FF")
_HEADER_FONT = Font(name="Times New Roman", size=11, bold=True)
_VALUE_FONT = Font(name="Times New Roman", size=11)
_THIN_SIDE = Side(style="thin", color="FF000000")
_CELL_BORDER = Border(top=_THIN_SIDE, left=_THIN_SIDE, bottom=_THIN_SIDE, right=_THIN_SIDE)

_HEADER_ROW = 9
_VALUE_ROW = 10
_DATE_FMT = "dd/mm/yyyy"


def export_normal_excel(
    headers: Sequence[Tuple[str, str, str]],
    output_path: str,
    template_path: str | Path | None = None,
) -> str:
    """Ghi headers [h_<name>, !2.<name>, numFmt] vào template, lưu ra output_path.

    Trả về output_path đã ghi.
    """
    if not headers:
        raise ValueError("headers rỗng — không có field nào để xuất Excel.")

    tpl = Path(template_path) if template_path else TEMPLATE_PATH
    if not tpl.exists():
        raise FileNotFoundError(f"Không tìm thấy template: {tpl}")

    wb = load_workbook(str(tpl))
    ws = wb.worksheets[0]

    for i, (h_name, value_token, fmt) in enumerate(headers):
        col = get_column_letter(i + 1)
        fmt = fmt or "General"

        header_cell = ws[f"{col}{_HEADER_ROW}"]
        header_cell.value = "?" + str(h_name).replace("%l", "")
        header_cell.fill = _HEADER_FILL
        header_cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        header_cell.font = _HEADER_FONT

        value_cell = ws[f"{col}{_VALUE_ROW}"]
        value_cell.value = str(value_token) + "{b:systotal=0}"
        value_cell.number_format = fmt
        value_cell.alignment = Alignment(
            vertical="center",
            horizontal="left" if fmt == "@" else ("center" if fmt == _DATE_FMT else "right"),
            wrap_text=True,
        )
        value_cell.font = _VALUE_FONT

        header_cell.border = _CELL_BORDER
        value_cell.border = _CELL_BORDER

    last_col = get_column_letter(len(headers))
    ws.merge_cells(f"A6:{last_col}6")
    ws.merge_cells(f"A7:{last_col}7")
    ws["A6"].alignment = Alignment(horizontal="center")
    ws["A7"].alignment = Alignment(horizontal="center")

    for col_cells in ws.iter_cols(min_col=1, max_col=ws.max_column):
        ws.column_dimensions[col_cells[0].column_letter].width = 16

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(out))
    return str(out)
