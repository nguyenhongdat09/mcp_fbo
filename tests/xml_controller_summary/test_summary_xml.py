"""Unit tests for xml_controller_summary module."""

import pytest
from xml_controller_summary import analyze_flat_xml, result_to_dict

MINI_SVTRAN_FLAT = """<?xml version="1.0" encoding="utf-8"?>
<dir table="d81$$partition$current" code="stt_rec" title="Hóa đơn dịch vụ" xmlns="urn:schemas-ai-erp:data-dir">
  <fields>
    <field name="ma_kh" allowNulls="false">
      <items controller="Customer" />
      <clientScript><![CDATA[onchange="onChange$Voucher$Customer(this);"]]></clientScript>
    </field>
    <field name="tk" allowNulls="false">
      <items controller="Account" />
      <clientScript><![CDATA[onchange="onChange$Voucher$DebitAccount(this);"]]></clientScript>
    </field>
    <field name="ty_gia" type="Decimal" />
    <field name="ngay_ct" type="DateTime" allowNulls="false" />
    <field name="stt_rec" hidden="true" />
    <field name="status" items="1, 2">
      <items style="CheckBox" />
    </field>
  </fields>

  <commands>
    <command event="Loading">
      <text><![CDATA[
        declare @x int
        select * from options where name = 'm_round'
        select top 1 * from d81$$partition$current
        select * from voucher_temp
        exec sp_executesql @q
      ]]></text>
    </command>
    <command event="Checking">
      <text><![CDATA[
        function check$Save(f) {
            if (!f.getItemValue('ma_kh')) {
                $message.show('Chua nhap ma khach');
                return false;
            }
            return true;
        }
      ]]></text>
    </command>
  </commands>

  <script>
    <text><![CDATA[
      function init$Voucher$(f) {
          f.executeExpression('ty_gia');
      }
      function onChange$Voucher$Customer(o) {
          var f = o.parentForm;
          f.request('Customer', 'Customer', ['ma_kh'], o);
      }
      function onChange$Voucher$DebitAccount(o) {
          o.parentForm.request('DebitAccount', 'DebitAccount', ['tk'], o);
      }
    ]]></text>
  </script>

  <actions>
    <action id="Customer">
      <text><![CDATA[
        select ma_kh, ten_kh from dmkh where ma_kh = @ma_kh
        select top 1 * from v20dmctnk
        select top 1 * from zvdmloaidt
      ]]></text>
    </action>
    <action id="DebitAccount">
      <text><![CDATA[
        select tk, ten_tk from dmtk where tk = @tk
      ]]></text>
    </action>
  </actions>

  <encrypted>
    SOME_ENCRYPTED_BINARY_DATA
  </encrypted>
</dir>
"""

MINI_FILTER_FLAT = """<?xml version="1.0" encoding="utf-8"?>
<filter title="Lọc hóa đơn" xmlns="urn:schemas-ai-erp:data-dir">
  <fields>
    <field name="ngay_ct1" type="DateTime" />
    <field name="ngay_ct2" type="DateTime" />
    <field name="ma_kh">
      <items controller="Customer" />
    </field>
  </fields>
  <queries>
    <query>
      <text><![CDATA[
        select * from m81$ join dmkh on m81$.ma_kh = dmkh.ma_kh
      ]]></text>
    </query>
  </queries>
</filter>
"""

MINI_PVDETAIL_GRID_FLAT = """<?xml version="1.0" encoding="utf-8"?>
<grid table="d81" code="stt_rec" xmlns="urn:schemas-ai-erp:data-dir">
  <fields>
    <field name="ma_vt" allowNulls="false">
      <items controller="Item" />
    </field>
    <field name="so_luong" type="Decimal" />
    <field name="gia_nt0" type="Decimal" />
    <field name="tien_nt0" type="Decimal" />
  </fields>
  <script>
    <text><![CDATA[
      function load$Grid$(g) {
        g.$a = {
          gia0_tg: '[gia0]:=[gia_nt0]*[$ty_gia]',
          tien_nt0: '[tien_nt0]:=[so_luong]*[gia_nt0]',
          tien0: '[tien0]:=[so_luong]*[gia0]',
          t_so_luong: ['t_so_luong', 'so_luong'],
          t_tien_nt0: ['t_tien_nt0', 'tien_nt0']
        };
      }
      function onChange$Item(o) {
        o.grid.request(o, 'Item', 'Item', ['ma_vt'], o.grid.$h, true);
      }
      function onDownload(g) {
        g.request(g, 'Download', a, []);
      }
      function showRelated(g) {
        g.showForm('PVOrderFilter');
        g.showForm('PVDetailImport');
      }
    ]]></text>
  </script>
</grid>
"""


def test_analyze_dir_tran():
    res = analyze_flat_xml(MINI_SVTRAN_FLAT, source_path=r"E:\CustomerPro\App_Data\Controllers\Dir\SVTran.xml")
    d = result_to_dict(res)

    assert d["success"] is True
    assert d["mode"] == "summary"
    assert d["spec_version"] == "1.0"
    assert d["file"] == r"Dir\SVTran.xml"
    assert d["controller"]["folder_type"] == "Dir"
    assert d["controller"]["db_table"] == "d81$$partition$current"

    # JS Assertions
    assert "init$Voucher$" in d["js"]["functions"]
    assert "onChange$Voucher$Customer" in d["js"]["functions"]
    assert "onChange$Voucher$DebitAccount" in d["js"]["functions"]
    assert "check$Save" in d["js"]["functions"]
    assert "Customer" in d["js"]["request_actions"]
    assert "DebitAccount" in d["js"]["request_actions"]
    assert any("request" in c for c in d["js"]["calls"])
    assert "$message.show" in d["js"]["calls"]
    assert "f.executeExpression" in d["js"]["calls"]

    # SQL Assertions
    tables_lower = [t.lower() for t in d["sql"]["tables"]]
    assert "options" in tables_lower
    assert "d81$$partition$current" in tables_lower
    assert "dmkh" in tables_lower
    assert "dmtk" in tables_lower
    assert "v20dmctnk" in tables_lower
    assert "zvdmloaidt" in tables_lower
    assert "voucher_temp" in tables_lower
    assert "sp_executesql" in [p.lower() for p in d["sql"]["procs"]]

    # Views heuristic tightness: v20dmctnk and zvdmloaidt ARE views; voucher_temp is NOT
    views_lower = [v.lower() for v in d["sql"]["views"]]
    assert "v20dmctnk" in views_lower
    assert "zvdmloaidt" in views_lower
    assert "voucher_temp" not in views_lower

    assert "partition" in d["sql"]["signals"]
    assert "dynamic_sql" in d["sql"]["signals"]
    assert "encrypted_skipped" in d["sql"]["signals"]

    # Field Assertions
    ma_kh = next(f for f in d["fields"] if f["name"] == "ma_kh")
    assert ma_kh["type"] == "char"
    assert ma_kh["lookup"] == "Customer"
    assert ma_kh["onchange"] == "onChange$Voucher$Customer"
    assert ma_kh["allowNulls"] is False

    ty_gia = next(f for f in d["fields"] if f["name"] == "ty_gia")
    assert ty_gia["type"] == "number"

    ngay_ct = next(f for f in d["fields"] if f["name"] == "ngay_ct")
    assert ngay_ct["type"] == "date"

    stt_rec = next(f for f in d["fields"] if f["name"] == "stt_rec")
    assert stt_rec["hidden"] is True

    status_f = next(f for f in d["fields"] if f["name"] == "status")
    assert status_f["type"] == "checkbox"

    # Meta Assertions
    assert d["meta"]["skipped_encrypted_blocks"] == 1

    # Omit empty grid formulas & show forms for Dir
    assert "grid_formulas" not in d
    assert "show_forms" not in d
    assert "related_controllers" not in d


def test_analyze_filter_empty_js():
    res = analyze_flat_xml(MINI_FILTER_FLAT, source_path="Controllers/Filter/SVFilter.xml")
    d = result_to_dict(res)

    assert d["success"] is True
    assert d["file"] == r"Filter\SVFilter.xml"
    assert d["controller"]["folder_type"] == "Filter"
    assert d["js"]["parse_status"] == "empty"
    assert len(d["js"]["functions"]) == 0

    tables_lower = [t.lower() for t in d["sql"]["tables"]]
    assert "m81$" in tables_lower
    assert "dmkh" in tables_lower

    assert len(d["fields"]) == 3
    ngay_ct1 = next(f for f in d["fields"] if f["name"] == "ngay_ct1")
    assert ngay_ct1["type"] == "date"


def test_grid_ga_formulas_and_show_form():
    res = analyze_flat_xml(MINI_PVDETAIL_GRID_FLAT, source_path="Controllers/Grid/PVDetail.xml")
    d = result_to_dict(res)

    assert d["success"] is True
    assert d["file"] == r"Grid\PVDetail.xml"
    assert d["controller"]["folder_type"] == "Grid"

    # Grid formulas assertions
    assert "grid_formulas" in d
    gf = d["grid_formulas"]
    assert "expressions" in gf
    assert "aggregates" in gf

    assert gf["expressions"]["gia0_tg"] == "[gia0]:=[gia_nt0]*[$ty_gia]"
    assert gf["expressions"]["tien_nt0"] == "[tien_nt0]:=[so_luong]*[gia_nt0]"
    assert gf["expressions"]["tien0"] == "[tien0]:=[so_luong]*[gia0]"

    assert gf["aggregates"]["t_so_luong"] == ["t_so_luong", "so_luong"]
    assert gf["aggregates"]["t_tien_nt0"] == ["t_tien_nt0", "tien_nt0"]

    # JS actions & calls assertions
    assert "Item" in d["js"]["request_actions"]
    assert "Download" in d["js"]["request_actions"]
    assert "o.grid.request" in d["js"]["calls"]
    assert "g.showForm" in d["js"]["calls"]

    # Show forms & related controllers assertions
    assert "show_forms" in d
    assert d["show_forms"] == ["PVDetailImport", "PVOrderFilter"]

    assert "related_controllers" in d
    related = d["related_controllers"]
    assert "PVDetailImport" in related
    assert "PVOrderFilter" in related
    assert "PVOrderGrid" in related
    assert "PVOrderMultiGrid" in related
    assert "PVOrderForm" in related
    assert "PVOrderMultiForm" in related
    assert "PVOrderLookup" in related
    # PVDetailImport should not expand suffix because it does not end with Filter
    assert "PVDetailImportGrid" not in related


def test_checking_routed_to_sql():
    xml_checking_sql = """<?xml version="1.0" encoding="utf-8"?>
<dir xmlns="urn:schemas-ai-erp:data-dir">
  <commands>
    <command event="Checking">
      <text><![CDATA[
        declare @status char(1)
        select @status = status from d81$$partition$current where stt_rec = @stt_rec
      ]]></text>
    </command>
  </commands>
</dir>
"""
    res = analyze_flat_xml(xml_checking_sql, source_path="Controllers/Dir/CheckSql.xml")
    d = result_to_dict(res)

    assert d["success"] is True
    assert "checking_routed_to_sql" in d["meta"]["warnings"]
    assert "checking_routed_to_sql" in d["sql"]["signals"]
    assert "d81$$partition$current" in [t.lower() for t in d["sql"]["tables"]]


def test_fbo_ifdef_signal():
    xml_ifdef = """<?xml version="1.0" encoding="utf-8"?>
<dir xmlns="urn:schemas-ai-erp:data-dir">
  <commands>
    <command event="Loading">
      <text><![CDATA[
        #IF @@view = 1 #THEN
        select * from d91
        #ELSE
        select * from d81
        #END
      ]]></text>
    </command>
  </commands>
</dir>
"""
    res = analyze_flat_xml(xml_ifdef, source_path="Controllers/Dir/IfDef.xml")
    d = result_to_dict(res)

    assert d["success"] is True
    assert "fbo_ifdef" in d["sql"]["signals"]
    tables_lower = [t.lower() for t in d["sql"]["tables"]]
    assert "d91" in tables_lower
    assert "d81" in tables_lower


def test_analyze_empty_input():
    res = analyze_flat_xml("", source_path="Dir/Empty.xml")
    d = result_to_dict(res)

    assert d["success"] is False
    assert d["js"]["parse_status"] == "empty"
    assert d["sql"]["parse_status"] == "empty"
    assert "empty_flat_xml" in d["meta"]["warnings"]


def test_dir_item_category_title_noise_onclick():
    xml_item = """<?xml version="1.0" encoding="utf-8"?>
<dir table="dmvt" code="ma_vt" xmlns="urn:schemas-ai-erp:data-dir">
  <title v="vật tư" e="Item"></title>
  <fields>
    <field name="ma_vt" allowNulls="false" />
    <field name="lo_yn">
      <items style="CheckBox" />
      <clientScript><![CDATA[onclick="onChangeLot(this);"]]></clientScript>
    </field>
  </fields>
  <commands>
    <command event="Loading">
      <text><![CDATA[
        EXEC sp_executesql N'select * from dmvt', N'@x nvarchar(33)'
      ]]></text>
    </command>
  </commands>
</dir>
"""
    res = analyze_flat_xml(xml_item, source_path=r"E:\CustomerPro\App_Data\Controllers\Dir\Item.xml")
    d = result_to_dict(res)

    assert d["success"] is True
    assert d["controller"]["title_v"] == "vật tư"
    assert d["controller"]["title_e"] == "Item"
    assert d["controller"]["db_table"] == "dmvt"
    assert d["controller"]["code_field"] == "ma_vt"

    # Procs should contain sp_executesql, but NOT nvarchar
    assert "sp_executesql" in d["sql"]["procs"]
    assert "nvarchar" not in d["sql"]["procs"]

    # lo_yn onclick handler should be mapped to onchange
    lo_yn = next(f for f in d["fields"] if f["name"] == "lo_yn")
    assert lo_yn["type"] == "checkbox"
    assert lo_yn["onchange"] == "onChangeLot"


def test_grid_item_ticket_and_show_dollar_form():
    xml_grid_item = """<?xml version="1.0" encoding="utf-8"?>
<grid table="dmvt" code="ma_vt" xmlns="urn:schemas-ai-erp:data-dir">
  <title v="Danh mục hàng hóa - vật tư" e="Item List"></title>
  <fields>
    <field name="ma_vt" />
    <field name="ten_vt%l" />
  </fields>
  <commands>
    <command event="Loading">
      <text><![CDATA[
        insert into @@sysDatabaseName..ticket values(@ticket, 1, 'Item', 'a', N'b', '@@appDatabaseName', getdate());
        select @ticket as value
      ]]></text>
    </command>
    <command event="Closing">
      <text><![CDATA[
        select 'dispose$Grid(this);' as message
      ]]></text>
    </command>
  </commands>
  <script>
    <text><![CDATA[
      function on$GridItem$ExecuteCommand(g) {
        show$Form(g, 'ItemImport');
      }
      function show$Form(g, c) {
        (g._authorize == 1) ? g.showForm(c) : $message.show('No permission');
      }
    ]]></text>
  </script>
</grid>
"""
    res = analyze_flat_xml(xml_grid_item, source_path=r"E:\CustomerPro\App_Data\Controllers\Grid\Item.xml")
    d = result_to_dict(res)

    assert d["success"] is True
    assert d["controller"]["title_v"] == "Danh mục hàng hóa - vật tư"
    assert d["controller"]["title_e"] == "Item List"

    # SQL: ticket table extracted, parse_status is ok
    assert "ticket" in d["sql"]["tables"]
    assert d["sql"]["parse_status"] == "ok"

    # show_forms: show$Form wrapper extracted
    assert "show_forms" in d
    assert d["show_forms"] == ["ItemImport"]
    assert d["related_controllers"] == ["ItemImport"]


