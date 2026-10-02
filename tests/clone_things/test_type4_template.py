"""Tests cho clone_things type=4 — paste template suite vào project đích."""
from __future__ import annotations

import pytest

from clone_things.type4_template import list_templates, run_type4_template

ALL_TEMPLATES = {"category_1_key", "category_multi_key",
                 "category_1_key_detail", "category_multi_key_detail",
                 "report_normal", "report_pivot", "report_mau",
                 "report_check", "retrieve_flow_parition_table",
                 "retrieve_flow_single_table",
                 "voucher_normal_currency", "voucher_normal_no_currency",
                 "voucher_approval_currency",
                 "voucher_approval_no_currency"}


def test_list_templates():
    tpls = list_templates()
    names = {t["name"] for t in tpls}
    assert ALL_TEMPLATES <= names
    assert "category_2_key" not in names      # đã đổi tên


def test_list_mode_via_object():
    res = run_type4_template(object="?")
    assert res["mode"] == "list_templates"
    assert res["templates"]


def test_unknown_template():
    res = run_type4_template(object="khong_co")
    assert res["success"] is False
    assert res["error_code"] == "template_not_found"


def test_missing_new_name(tmp_path):
    res = run_type4_template(object="category_1_key",
                             project_target=str(tmp_path))
    assert res["success"] is False
    assert res["error_code"] == "invalid_new_name"


def test_dry_run_lists_files(tmp_path):
    res = run_type4_template(object="category_1_key",
                             new_name="zccnsldkbctdo",
                             project_target=str(tmp_path))
    assert res["success"] is True and res["dry_run"] is True
    dsts = [f["dst"] for f in res["files"]]
    assert "App_Data/Controllers/Dir/zccnsldkbctdo.xml" in dsts
    assert ("App_Data/Controllers/Filter/zccnsldkbctdoImport.xml"
            in dsts)
    assert not (tmp_path / "App_Data").exists()   # dry-run không ghi


def test_execute_writes_and_rewrites(tmp_path):
    res = run_type4_template(object="category_1_key",
                             new_name="zccnsldkbctdo",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 6
    d = tmp_path / "App_Data/Controllers/Dir/zccnsldkbctdo.xml"
    assert d.is_file()
    body = d.read_text(encoding="utf-8")
    assert "zccnsldkbctdo" in body
    assert "zccntttdcd" not in body          # token gốc đã thay sạch
    assert "{{controller}}" not in body
    assert 'table="zccnsldkbctdo"' in body   # {{table}} đã fill
    imp = tmp_path / ("App_Data/Controllers/Filter/"
                      "zccnsldkbctdoImport.xml")
    assert "zccnsldkbctdoImport" in imp.read_text(encoding="utf-8")


def test_detail_suffixes(tmp_path):
    """category_multi_key_detail → Grid/{new}detail.xml + detail2."""
    res = run_type4_template(object="category_multi_key_detail",
                             new_name="zcabcd",
                             project_target=str(tmp_path),
                             execute=True)
    dsts = {f["dst"] for f in res["files"]}
    assert "App_Data/Controllers/Dir/zcabcd.xml" in dsts
    assert "App_Data/Controllers/Grid/zcabcd.xml" in dsts
    assert "App_Data/Controllers/Grid/zcabcddetail.xml" in dsts
    assert "App_Data/Controllers/Grid/zcabcddetail2.xml" in dsts
    body = (tmp_path / "App_Data/Controllers/Grid/zcabcddetail2.xml"
            ).read_text(encoding="utf-8")
    assert 'table="zcabcdct2"' in body       # {{table_detail2}} đã fill
    assert "{{table_detail2}}" not in body
    assert "zcabcddetail2" in body           # {{ctrl_detail2}} đã fill


def test_unresolved_placeholders_reported(tmp_path):
    """Token không khai báo trong manifest → báo unresolved_placeholders."""
    res = run_type4_template(object="report_mau",
                             new_name="zctest",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True
    assert "{{ma_maubc}}" in res["unresolved_placeholders"]
    assert res["edit_guide"]


def test_skip_existing_no_overwrite(tmp_path):
    run_type4_template(object="category_1_key", new_name="zccnsldkbctdo",
                       project_target=str(tmp_path), execute=True)
    res = run_type4_template(object="category_1_key",
                             new_name="zccnsldkbctdo",
                             project_target=str(tmp_path), execute=True)
    assert all(f["status"] == "skipped_exists" for f in res["files"])


def test_report_check_writes(tmp_path):
    """report_check → Grid có tag machinery + Filter keys + Report @$keys."""
    res = run_type4_template(object="report_check",
                             new_name="zctestcheck",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 4
    dsts = {f["dst"] for f in res["files"]}
    assert "App_Data/Controllers/Filter/zctestcheck.xml" in dsts
    assert "App_Data/Controllers/Grid/zctestcheck.xml" in dsts
    assert "App_Data/Controllers/Report/zctestcheck.xml" in dsts
    assert "Main/zctestcheck.aspx" in dsts
    aspx = (tmp_path / "Main/zctestcheck.aspx").read_text(encoding="utf-8")
    assert 'Controller="zctestcheck"' in aspx

    grid = (tmp_path / "App_Data/Controllers/Grid/zctestcheck.xml"
            ).read_text(encoding="utf-8")
    assert 'name="tag"' in grid
    assert "toggle$Grid" in grid and "on$GridReport$ExecuteCommand" in grid
    assert "<response>" in grid and 'action id="Action1"' in grid
    assert 'command="Print"' in grid
    assert "zctestcheck" in grid and "{{controller}}" not in grid

    flt = (tmp_path / "App_Data/Controllers/Filter/zctestcheck.xml"
           ).read_text(encoding="utf-8")
    assert 'name="keys"' in flt and 'filterSource="Infinite"' in flt
    assert "rs_zctestcheck" in flt                   # {{proc}} đã fill

    rpt = (tmp_path / "App_Data/Controllers/Report/zctestcheck.xml"
           ).read_text(encoding="utf-8")
    assert "@$keys" in rpt and "rs_zctestcheckPrint" in rpt
    assert "{{proc_print}}" not in rpt


def test_retrieve_flow_partition_writes(tmp_path):
    """retrieve_flow_parition_table → suite {X}Filter/MultiForm/MultiGrid/
    Lookup + retrieve.sql; {{identity}} fill, chủ {{...}} khác unresolved."""
    res = run_type4_template(object="retrieve_flow_parition_table",
                             new_name="zcTESTPO",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 5
    dsts = {f["dst"] for f in res["files"]}
    assert "App_Data/Controllers/Filter/zcTESTPOFilter.xml" in dsts
    assert "App_Data/Controllers/Filter/zcTESTPOMultiForm.xml" in dsts
    assert "App_Data/Controllers/Grid/zcTESTPOMultiGrid.xml" in dsts
    assert "App_Data/Controllers/Lookup/zcTESTPOLookup.xml" in dsts
    assert "RetrieveTemp/zcTESTPO_retrieve.sql" in dsts

    flt = (tmp_path / "App_Data/Controllers/Filter/zcTESTPOFilter.xml"
           ).read_text(encoding="utf-8")
    assert "zcTESTPOFilter" in flt
    assert '<!ENTITY Identity "zcTESTPO">' in flt
    assert "&Identity;" in flt           # &Identity;Lookup/MultiForm resolve lúc runtime
    assert "{{identity}}" not in flt
    assert "{{src_ext}}" in flt          # placeholder agent phải fill

    grid = (tmp_path / "App_Data/Controllers/Grid/zcTESTPOMultiGrid.xml"
            ).read_text(encoding="utf-8")
    assert "zcTESTPOMultiGrid" in grid   # ENTITY Identity literal
    assert "{{src_taken_col}}" in grid

    sql = (tmp_path / "RetrieveTemp/zcTESTPO_retrieve.sql"
           ).read_text(encoding="utf-8")
    assert "fsd_addFields" in sql and "CREATE PROCEDURE" in sql
    assert "{{proc_name}}" in sql
    # handlebars của extension phải được flatten, không sót {{#if}}/{{#each}}
    assert "{{#if" not in sql and "{{#each" not in sql

    unresolved = set(res["unresolved_placeholders"])
    assert "{{src_taken_col}}" in unresolved
    assert "{{src_ext}}" in unresolved
    assert res["edit_guide"]


def test_retrieve_flow_single_writes(tmp_path):
    res = run_type4_template(object="retrieve_flow_single_table",
                             new_name="zcWIMO",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 5
    flt = (tmp_path / "App_Data/Controllers/Filter/zcWIMOFilter.xml"
           ).read_text(encoding="utf-8")
    assert "{{src_master_table}}" in flt          # single: bảng cố định
    assert "{{src_inquiry_table}}" in flt
    sql = (tmp_path / "RetrieveTemp/zcWIMO_retrieve.sql"
           ).read_text(encoding="utf-8")
    assert "{{src_detail_table}}" in sql
    assert "{{#if" not in sql


def test_voucher_normal_no_currency_writes(tmp_path):
    """voucher_normal_no_currency → suite {X}Tran + {X}Detail + aspx +
    voucher.sql; KHÔNG có file APV, KHÔNG có entity ngoại tệ."""
    res = run_type4_template(object="voucher_normal_no_currency",
                             new_name="PLH",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 17
    dsts = {f["dst"] for f in res["files"]}
    assert "App_Data/Controllers/Dir/PLHTran.xml" in dsts
    assert "App_Data/Controllers/Grid/PLHDetail.xml" in dsts
    assert "Main/zcplhd.aspx" in dsts
    assert "RetrieveTemp/PLH_voucher.sql" in dsts
    assert not any("Approval" in d for d in dsts)

    direc = (tmp_path / "App_Data/Controllers/Dir/PLHTran.xml"
             ).read_text(encoding="utf-8")
    assert 'id="PLH"' in direc
    assert 'table="mplh$000000"' in direc
    assert 'controller="PLHDetail"' in direc
    assert "APVApprove" not in direc and "APVXMLFields" not in direc
    assert "GetExchangeRate" not in direc
    assert "ScriptCurrency" not in direc
    assert "{{x}}" not in direc
    pass

    sql = (tmp_path / "RetrieveTemp/PLH_voucher.sql"
           ).read_text(encoding="utf-8")
    assert "mplh$" in sql and "dplh$" in sql
    assert "aplh$" not in sql and "dmctduyet" not in sql


def test_voucher_normal_currency_writes(tmp_path):
    """voucher_normal_currency → có currency machinery, KHÔNG APV."""
    res = run_type4_template(object="voucher_normal_currency",
                             new_name="PLH",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 17
    direc = (tmp_path / "App_Data/Controllers/Dir/PLHTran.xml"
             ).read_text(encoding="utf-8")
    assert "XMLGetExchangeRate" in direc
    assert "ScriptCurrency" in direc and "CurrencyResponse" in direc
    assert 'name="ma_nt"' in direc and 'name="ty_gia"' in direc
    assert "objectBehavior$Voucher$Currency" in direc
    assert "APVApprove" not in direc
    sql = (tmp_path / "RetrieveTemp/PLH_voucher.sql"
           ).read_text(encoding="utf-8")
    assert "t_tien_nt" in sql and "dmtgnt" in sql


def test_voucher_approval_no_currency_writes(tmp_path):
    """voucher_approval_no_currency → +Approval suite + 2 aspx, KHÔNG NT."""
    res = run_type4_template(object="voucher_approval_no_currency",
                             new_name="PLH",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 23
    dsts = {f["dst"] for f in res["files"]}
    assert "App_Data/Controllers/Grid/PLHApproval.xml" in dsts
    assert "App_Data/Controllers/Grid/PLHApprovalItem.xml" in dsts
    assert "App_Data/Controllers/Grid/PLHApprovalFiles.xml" in dsts
    assert "App_Data/Controllers/Filter/PLHApproval.xml" in dsts
    assert "Main/zcdplhd.aspx" in dsts

    direc = (tmp_path / "App_Data/Controllers/Dir/PLHTran.xml"
             ).read_text(encoding="utf-8")
    assert "&APVApprove;" in direc and "&APVCheckApprove;" in direc
    assert "&APVDelete;" in direc and "&APVXMLFields;" in direc
    assert 'APVController "PLHApproval"' in direc
    assert "{{apv_type}}" in direc          # placeholder kiểu duyệt còn chờ fill
    assert "GetExchangeRate" not in direc and "ScriptCurrency" not in direc

    apv = (tmp_path / "App_Data/Controllers/Grid/PLHApproval.xml"
           ).read_text(encoding="utf-8")
    assert 'APVController "PLHApproval"' in apv
    assert "PLHApproval" in apv and 'table="mplh$000000"' in apv
    assert "APVApprovalGridCommand" in apv
    aspx = (tmp_path / "Main/zcdplhd.aspx").read_text(encoding="utf-8")
    assert 'Controller="PLHApproval"' in aspx

    sql = (tmp_path / "RetrieveTemp/PLH_voucher.sql"
           ).read_text(encoding="utf-8")
    assert "aplh$" in sql and "dmctduyet" in sql
    assert "kieu_duyet" in sql and "u_status" in sql


def test_voucher_approval_currency_writes(tmp_path):
    """voucher_approval_currency → FULL: APV suite + currency machinery."""
    res = run_type4_template(object="voucher_approval_currency",
                             new_name="PLH",
                             project_target=str(tmp_path),
                             execute=True)
    assert res["success"] is True and len(res["written"]) == 23
    direc = (tmp_path / "App_Data/Controllers/Dir/PLHTran.xml"
             ).read_text(encoding="utf-8")
    # APV
    assert "&APVApprove;" in direc and 'APVController "PLHApproval"' in direc
    assert "{{apv_type}}" in direc
    # Currency
    assert "XMLGetExchangeRate" in direc
    assert "objectBehavior$Voucher$Currency" in direc
    assert 'name="ma_nt"' in direc
    detail = (tmp_path / "App_Data/Controllers/Grid/PLHDetail.xml"
              ).read_text(encoding="utf-8")
    assert 'name="tien_nt"' in detail


def test_no_binary_assets():
    """Không có .xlsx/.rpt nào trong bất kỳ manifest nào."""
    from clone_things.type4_template import template_root
    import yaml
    for mf in template_root().glob("*/manifest.yaml"):
        files = (yaml.safe_load(mf.read_text(encoding="utf-8"))
                 or {}).get("files") or []
        for f in files:
            src = f.get("src") if isinstance(f, dict) else f
            assert not src.lower().endswith((".xlsx", ".rpt")), src


def test_service_routes_type4(tmp_path):
    from clone_things import clone_things
    res = clone_things(type=4, object="?", project_target="")
    assert res["mode"] == "list_templates"
