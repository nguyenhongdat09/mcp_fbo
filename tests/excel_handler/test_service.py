from pathlib import Path

import pytest
from pydantic import ValidationError

from excel_handler import ExcelHandlerRequest, excel_handler
from excel_handler.service import _default_output_path

from test_grid_parser import NORMAL_GRID_XML, PIVOT_GRID_XML


def _write_grid(tmp_path: Path, xml: str, name: str = "rpt.xml") -> Path:
    grid_dir = tmp_path / "App_Data" / "Controllers" / "Grid"
    grid_dir.mkdir(parents=True)
    f = grid_dir / name
    f.write_text(xml, encoding="utf-8")
    return f


def test_request_csv_normalization(tmp_path):
    grid = _write_grid(tmp_path, NORMAL_GRID_XML)
    req = ExcelHandlerRequest(grid_file=str(grid), value_fields=["a", " b ", ""], row_fields="")
    assert req.value_fields == "a,b"
    assert req.row_fields is None  # chuỗi rỗng → None → auto default


def test_request_validation(tmp_path):
    with pytest.raises(ValidationError):
        ExcelHandlerRequest(grid_file=str(tmp_path / "none.xml"))  # không tồn tại
    not_grid = tmp_path / "Other" / "x.xml"
    not_grid.parent.mkdir(parents=True)
    not_grid.write_text("<grid/>", encoding="utf-8")
    with pytest.raises(ValidationError, match="Grid"):
        ExcelHandlerRequest(grid_file=str(not_grid))  # không trong thư mục Grid
    with pytest.raises(ValidationError):
        ExcelHandlerRequest(grid_file=str(_write_grid(tmp_path, NORMAL_GRID_XML)), sai_param=1)


def test_default_output_path(tmp_path):
    grid = _write_grid(tmp_path, NORMAL_GRID_XML, "abc.xml")
    out = _default_output_path(grid)
    assert out == grid.parents[1] / "Templates" / "Excel" / "abc.xlsx"
    # fallback: không có Controllers → cùng thư mục
    plain = tmp_path / "Grid2" / "x.xml"
    assert _default_output_path(plain) == plain.parent / "x.xlsx"


def test_excel_name(tmp_path):
    grid = _write_grid(tmp_path, NORMAL_GRID_XML, "rpt.xml")
    result = excel_handler(grid_file=str(grid), excel_name="rpt_01")
    assert Path(result.output_path).name == "rpt_01.xlsx"  # tự thêm đuôi
    assert Path(result.output_path).parent.name == "Excel"
    assert Path(result.output_path).exists()

    result2 = excel_handler(grid_file=str(grid), excel_name="rpt_02.xlsx")
    assert Path(result2.output_path).name == "rpt_02.xlsx"


def test_excel_name_validation(tmp_path):
    grid = _write_grid(tmp_path, NORMAL_GRID_XML, "rpt.xml")
    with pytest.raises(ValidationError, match="TÊN file"):
        excel_handler(grid_file=str(grid), excel_name="sub/dir/rpt_01.xlsx")
    with pytest.raises(ValidationError, match="HOẶC"):
        excel_handler(grid_file=str(grid), excel_name="a.xlsx", output_path="b.xlsx")


def test_excel_handler_normal(tmp_path):
    grid = _write_grid(tmp_path, NORMAL_GRID_XML, "rpt_normal.xml")
    result = excel_handler(grid_file=str(grid))
    assert result.mode == "normal"
    out = Path(result.output_path)
    assert out.exists()
    assert out.parent.name == "Excel"
    assert result.headers == ["h_ma_kh", "h_ten_kh", "h_tien", "h_ngay"]
    # không có file Report đi kèm → skip inject nhưng vẫn export
    assert result.report_update.status == "report_not_found"


def test_excel_handler_normal_updates_report(tmp_path):
    grid = _write_grid(tmp_path, NORMAL_GRID_XML, "rpt_normal.xml")
    report = grid.parents[1] / "Report" / grid.name
    report.parent.mkdir(parents=True)
    report.write_text("<report><fields>\n</fields></report>", encoding="utf-8-sig")

    result = excel_handler(grid_file=str(grid))
    assert result.report_update.status == "updated"
    assert "h_ma_kh" in result.report_update.added_fields
    assert "h_nam" in result.report_update.added_fields

    new_xml = report.read_text(encoding="utf-8-sig")
    assert 'name="h_ma_kh"' in new_xml
    # chạy lại lần 2 → đã đủ field
    result2 = excel_handler(grid_file=str(grid))
    assert result2.report_update.status == "up_to_date"


def test_excel_handler_pivot_dispatch(tmp_path, monkeypatch):
    grid = _write_grid(tmp_path, PIVOT_GRID_XML, "rpt_pivot.xml")
    called = {}

    def fake_export(row, col, val, out):
        called.update(row=row, col=col, val=val, out=out)
        return out

    monkeypatch.setattr("excel_handler.service.export_pivot_excel", fake_export)
    result = excel_handler(grid_file=str(grid))
    assert result.mode == "pivot"
    assert result.row_fields == "xsearch,systotal,?h_xsearch,?h_systotal"
    assert called["col"] == "xpivot,npivot"
    assert called["val"] == "fund,assets,group_bank,amount_vnd,interest,settle_date"


def test_excel_handler_pivot_override(tmp_path, monkeypatch):
    grid = _write_grid(tmp_path, PIVOT_GRID_XML, "rpt_pivot.xml")
    called = {}
    monkeypatch.setattr(
        "excel_handler.service.export_pivot_excel",
        lambda r, c, v, o: called.update(row=r, col=c, val=v) or o,
    )
    excel_handler(grid_file=str(grid), row_fields="ma_kh", column_fields="xpivot", value_fields=["tien"])
    assert called["row"] == "ma_kh"
    assert called["val"] == "tien"


def test_excel_handler_request_or_kwargs(tmp_path):
    grid = _write_grid(tmp_path, NORMAL_GRID_XML)
    with pytest.raises(TypeError):
        excel_handler(ExcelHandlerRequest(grid_file=str(grid)), output_path="x.xlsx")
