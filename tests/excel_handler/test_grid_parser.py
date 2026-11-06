import pytest

from excel_handler.grid_parser import (
    _FMT_AMOUNT,
    _FMT_DATE,
    build_header_field_defs,
    build_pivot_defaults,
    extract_grid_attrs,
    has_pivot_tag,
    parse_header_fields,
)

PIVOT_GRID_XML = """<?xml version="1.0" encoding="utf-8"?>
<grid type="Report" valid="systotal = 1">
  <title v="Cash Flow" e="Cash Flow"/>
  <pivot rowField="xsearch" columnField="xpivot" dataFields="fund, assets, group_bank, amount_vnd, interest, settle_date" indexTable="2" indexColumn="1" indexHeader="2" indexView="1"/>
  <fields>
    <field name="xsearch" width="0" hidden="true"><header v="" e=""/></field>
    <field name="fund" width="90"><header v="Fund" e="Fund"/></field>
    <field name="amount_vnd" type="Decimal" width="130" dataFormatString="@baseCurrencyAmountViewFormat"><header v="Amount in VND" e="Amount in VND"/></field>
    <field name="systotal" width="0" hidden="true"><header v="" e=""/></field>
  </fields>
  <views>
    <view id="Grid">
      <field name="xsearch"/>
      <field name="systotal"/>
    </view>
  </views>
</grid>
"""

NORMAL_GRID_XML = """<?xml version="1.0" encoding="utf-8"?>
<grid type="Report">
  <fields>
    <field name="ma_kh" width="90"><header v="Ma KH" e="Cust"/></field>
    <field name="ten_kh" width="180"><header v="Ten KH" e="Name"/></field>
    <field name="tien" type="Decimal" dataFormatString="@baseCurrencyAmountViewFormat"><header v="Tien" e="Amt"/></field>
    <field name="ngay" type="DateTime"><header v="Ngay" e="Date"/></field>
    <field name="xsearch" width="0" hidden="true"><header v="" e=""/></field>
  </fields>
  <views>
    <view id="Grid">
      <field name="ma_kh"/>
      <field name="ten_kh"/>
      <field name="tien"/>
      <field name="ngay"/>
      <field name="xsearch"/>
    </view>
  </views>
</grid>
"""


def test_has_pivot_tag():
    assert has_pivot_tag(PIVOT_GRID_XML) is True
    assert has_pivot_tag(NORMAL_GRID_XML) is False


def test_extract_grid_attrs():
    attrs = extract_grid_attrs(PIVOT_GRID_XML)
    assert attrs["rowField"] == "xsearch"
    assert attrs["columnField"] == "xpivot"
    assert attrs["dataFields"] == "fund, assets, group_bank, amount_vnd, interest, settle_date"


def test_build_pivot_defaults():
    d = build_pivot_defaults(PIVOT_GRID_XML)
    assert d["row_csv"] == "xsearch,systotal,?h_xsearch,?h_systotal"
    assert d["column_csv"] == "xpivot,npivot"
    assert d["value_csv"] == "fund,assets,group_bank,amount_vnd,interest,settle_date"


def test_parse_header_fields_normal():
    headers = parse_header_fields(NORMAL_GRID_XML)
    # xsearch hidden → loại; thứ tự theo <view id="Grid">
    assert [h[0] for h in headers] == ["h_ma_kh", "h_ten_kh", "h_tien", "h_ngay"]
    assert headers[0][1] == "!2.ma_kh"
    assert headers[0][2] == "@"
    assert headers[2][2] == _FMT_AMOUNT
    assert headers[3][2] == _FMT_DATE


def test_parse_header_fields_pivot_grid_empty():
    # Grid pivot: field trong view đều hidden → headers rỗng (đúng hành vi extension)
    assert parse_header_fields(PIVOT_GRID_XML) == []


def test_build_header_field_defs():
    defs = build_header_field_defs(NORMAL_GRID_XML)
    names = [n for n, _ in defs]
    # 4 field view có header (xsearch hidden bị loại) + 5 field mặc định
    assert names == [
        "h_ma_kh", "h_ten_kh", "h_tien", "h_ngay",
        "h_tu_ngay", "h_den_ngay", "h_tu_ky", "h_den_ky", "h_nam",
    ]
    ma_kh_xml = dict(defs)["h_ma_kh"]
    assert '<header v="Ma KH" e="Cust" />' in ma_kh_xml
    assert dict(defs)["h_tu_ngay"].count("<header") == 1

    # grid pivot: view toàn hidden → chỉ 5 field mặc định
    assert [n for n, _ in build_header_field_defs(PIVOT_GRID_XML)] == [
        "h_tu_ngay", "h_den_ngay", "h_tu_ky", "h_den_ky", "h_nam",
    ]
