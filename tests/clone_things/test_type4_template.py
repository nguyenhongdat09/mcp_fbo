"""Tests cho clone_things type=4 — paste template suite vào project đích."""
from __future__ import annotations

import pytest

from clone_things.type4_template import list_templates, run_type4_template

ALL_TEMPLATES = {"category_1_key", "category_multi_key",
                 "category_1_key_detail", "category_multi_key_detail",
                 "report_normal", "report_pivot", "report_mau"}


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
