from pathlib import Path

import pytest
from openpyxl import load_workbook

from excel_handler.normal_export import export_normal_excel


def test_export_normal_excel(tmp_path):
    headers = [
        ("h_ma_kh", "!2.ma_kh", "@"),
        ("h_tien", "!2.tien", '_(* #,##0_);_(* (#,##0);_(* ""_);_(@_)'),
        ("h_ngay", "!2.ngay", "dd/mm/yyyy"),
    ]
    out = tmp_path / "out.xlsx"
    result = export_normal_excel(headers, str(out))
    assert Path(result).exists()

    wb = load_workbook(str(out))
    ws = wb.worksheets[0]

    assert ws["A9"].value == "?h_ma_kh"
    assert ws["B9"].value == "?h_tien"
    assert ws["C9"].value == "?h_ngay"
    assert ws["A10"].value == "!2.ma_kh{b:systotal=0}"
    assert ws["B10"].value == "!2.tien{b:systotal=0}"

    assert ws["B10"].number_format == '_(* #,##0_);_(* (#,##0);_(* ""_);_(@_)'
    assert ws["A10"].alignment.horizontal == "left"
    assert ws["C10"].alignment.horizontal == "center"
    assert ws["B10"].alignment.horizontal == "right"

    merged = {str(r) for r in ws.merged_cells.ranges}
    assert "A6:C6" in merged
    assert "A7:C7" in merged
    assert ws["A6"].alignment.horizontal == "center"

    assert ws["A9"].fill.fgColor.rgb == "FFEDF5FF"
    assert ws["A9"].font.bold is True
    assert ws["A9"].border.top.style == "thin"


def test_export_normal_excel_empty_headers(tmp_path):
    with pytest.raises(ValueError, match="headers"):
        export_normal_excel([], str(tmp_path / "x.xlsx"))


def test_export_normal_excel_strip_percent_l(tmp_path):
    out = tmp_path / "out.xlsx"
    export_normal_excel([("h_ma%l_kh", "!2.ma_kh", "@")], str(out))
    ws = load_workbook(str(out)).worksheets[0]
    assert ws["A9"].value == "?h_ma_kh"
