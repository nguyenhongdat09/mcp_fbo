from pathlib import Path

import pytest

from excel_handler.report_fields import update_report_fields

from test_grid_parser import NORMAL_GRID_XML, PIVOT_GRID_XML


def _setup(tmp_path: Path, grid_xml: str, report_xml: str | None):
    grid_dir = tmp_path / "App_Data" / "Controllers" / "Grid"
    grid_dir.mkdir(parents=True)
    grid = grid_dir / "rpt.xml"
    grid.write_text(grid_xml, encoding="utf-8")
    report = tmp_path / "App_Data" / "Controllers" / "Report" / "rpt.xml"
    if report_xml is not None:
        report.parent.mkdir(parents=True)
        report.write_text(report_xml, encoding="utf-8-sig")
    return grid, report


REPORT_XML = """<?xml version="1.0" encoding="utf-8"?>
<report>
  <fields>
    <field name="h_tu_ngay" type="String"><header v="Tu ngay" e="From"/></field>
    <field name="x" type="Decimal"><header v="X" e="X"/></field>
  </fields>
</report>
"""


def test_update_report_fields_injects_missing(tmp_path):
    grid, report = _setup(tmp_path, NORMAL_GRID_XML, REPORT_XML)
    res = update_report_fields(grid, grid.read_text(encoding="utf-8-sig"))
    assert res.status == "updated"
    # h_tu_ngay đã có → không thêm lại; x không phải h_* thì không quan tâm
    assert "h_tu_ngay" not in res.added_fields
    assert "h_ma_kh" in res.added_fields
    assert "h_nam" in res.added_fields

    new_xml = report.read_text(encoding="utf-8-sig")
    assert new_xml.count('name="h_ma_kh"') == 1
    assert '<header v="Ma KH" e="Cust" />' in new_xml
    assert new_xml.count("<fields>") == 1  # inject đúng trong block cũ
    # BOM giữ nguyên
    assert report.read_bytes()[:3] == b"\xef\xbb\xbf"


def test_update_report_fields_up_to_date(tmp_path):
    defs_xml = "\n".join(
        f'<field name="{n}" type="String"><header v="" e=""/></field>'
        for n in [
            "h_ma_kh", "h_ten_kh", "h_tien", "h_ngay",
            "h_tu_ngay", "h_den_ngay", "h_tu_ky", "h_den_ky", "h_nam",
        ]
    )
    report_xml = f"<report><fields>{defs_xml}</fields></report>"
    grid, report = _setup(tmp_path, NORMAL_GRID_XML, report_xml)
    res = update_report_fields(grid, grid.read_text(encoding="utf-8-sig"))
    assert res.status == "up_to_date"
    assert res.added_fields == []


def test_update_report_fields_not_found(tmp_path):
    grid, _ = _setup(tmp_path, NORMAL_GRID_XML, None)
    res = update_report_fields(grid, grid.read_text(encoding="utf-8-sig"))
    assert res.status == "report_not_found"


def test_update_report_fields_no_fields_block(tmp_path):
    grid, _ = _setup(tmp_path, NORMAL_GRID_XML, "<report><data/></report>")
    res = update_report_fields(grid, grid.read_text(encoding="utf-8-sig"))
    assert res.status == "no_fields_block"


def test_update_report_fields_pivot_grid(tmp_path):
    # pivot grid: chỉ inject 5 field mặc định còn thiếu
    grid, report = _setup(tmp_path, PIVOT_GRID_XML, "<report><fields>\n</fields></report>")
    res = update_report_fields(grid, grid.read_text(encoding="utf-8-sig"))
    assert res.status == "updated"
    assert res.added_fields == ["h_tu_ngay", "h_den_ngay", "h_tu_ky", "h_den_ky", "h_nam"]
