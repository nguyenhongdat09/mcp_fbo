"""Chèn dòng <page> vào <!--Customize--> của App_Data/PageMetadata.xml khi
clone trên program mới (SP30+)."""

from pathlib import Path

from clone_things.page_registry import (
    build_page_line,
    clone_page_line,
    find_page_entries,
    insert_customize_page,
    insert_page_line,
    page_attrs_from_aspx,
    register_page_line,
    suggest_template,
    page_needed_features,
)
from clone_things.service import clone_things
from clone_things.type4_template import run_type4_template

BOM = b"\xef\xbb\xbf"

_META = Path("App_Data") / "PageMetadata.xml"


def _page(id_, ctrl, tpl="Page.001", v=None):
    return (
        f'<page id="{id_}" v="{v or "Trang " + id_}" e="Page" controller="{ctrl}" '
        f'readOnly="true" filterMode="true" template="{tpl}"/>'
    )


def _mk_page_meta(proj: Path, customize: bool = True):
    inner = (
        "  <!--Customize-->\r\n  <!--End Customize-->\r\n"
        if customize else ""
    )
    (proj / _META).write_bytes(
        BOM + f'<pages>\r\n{inner}</pages>\r\n'.encode("utf-8")
    )


def _mk_sp30(tmp_path: Path, name="FBISP30", ids=("aaa", "mmm", "zzz")) -> Path:
    proj = tmp_path / name
    (proj / "App_Data" / "Metadata" / "Fragments").mkdir(parents=True)
    (proj / "App_Data" / "Metadata" / "Fragments" / "Page.001.xml").write_text(
        "<resources/>", encoding="utf-8"
    )
    _mk_page_meta(proj)
    lines = [_page(i, f"Ctrl_{i}") for i in ids]
    lines[1] = _page("zclctt", "zclctt")  # controller nguồn, nằm giữa file
    text = "\r\n".join(lines) + "\r\n"
    (proj / "App_Data" / "Metadata" / "Page.001.xml").write_bytes(
        BOM + text.encode("utf-8")
    )
    fdir = proj / "App_Data" / "Controllers" / "Filter"
    fdir.mkdir(parents=True)
    (fdir / "zclctt.xml").write_text(
        '<filter><title v="Báo cáo" e=""/></filter>', encoding="utf-8"
    )
    return proj


def _cfg(tmp_path):
    return {"clone_things": {"sql_temp_folder": str(tmp_path), "open_file": False}}


def _lines(proj: Path) -> list[str]:
    raw = (proj / "App_Data" / "Metadata" / "Page.001.xml").read_bytes()
    return raw.decode("utf-8-sig").splitlines()


def _meta_lines(proj: Path) -> list[str]:
    raw = (proj / _META).read_bytes()
    return raw.decode("utf-8-sig").splitlines()


def test_clone_page_line_only_changes_id_and_controller():
    out = clone_page_line(_page("zclctt", "zclctt"), "zcnew", "ZCNew")
    assert out == _page("zcnew", "ZCNew", v="Trang zclctt")


def test_build_page_line_escapes_and_order():
    line = build_page_line("x", "X", "Quyết & 'a'", "E", True, False, "Page.001")
    assert line == (
        '<page id="x" v="Quyết &amp; &apos;a&apos;" e="E" controller="X" '
        'readOnly="true" template="Page.001"/>'
    )


def test_insert_keeps_bom_crlf_and_sorted(tmp_path):
    proj = _mk_sp30(tmp_path)
    f = proj / "App_Data" / "Metadata" / "Page.001.xml"
    before = f.read_bytes()
    r = insert_page_line(f, _page("bbb", "B"), "bbb", execute=False)
    assert f.read_bytes() == before  # dry-run không ghi
    assert r["position"] == "sorted"
    insert_page_line(f, _page("bbb", "B"), "bbb", execute=True)
    raw = f.read_bytes()
    assert raw.startswith(BOM) and b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    ids = [ln.split('"')[1] for ln in raw.decode("utf-8-sig").splitlines()]
    assert ids == ["aaa", "bbb", "zclctt", "zzz"]


def test_insert_unsorted_appends_and_handles_no_trailing_newline(tmp_path):
    f = tmp_path / "Page.003.xml"
    f.write_text(_page("user", "U") + "\n" + _page("cakb", "C"), encoding="utf-8")
    insert_page_line(f, _page("new", "N"), "new", execute=True)
    got = f.read_text(encoding="utf-8").splitlines()
    assert [x.split('"')[1] for x in got] == ["user", "cakb", "new"]


def test_saveas_adds_page_line_on_sp30(tmp_path):
    proj = _mk_sp30(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt", project_source=str(proj),
        execute=True, open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert res["page_entry"]["status"] == "added"
    assert res["page_entry"]["id"] == "zcbcdt"
    got = _meta_lines(proj)
    new = [ln.strip() for ln in got if 'controller="zcbcdt"' in ln]
    assert new == [_page("zcbcdt", "zcbcdt", v="Trang zclctt")]
    assert any("zcbcdt.aspx" in s for s in res["next_steps"])
    # chạy lại: id đã có → không nhân đôi
    res2 = clone_things(
        type=6, object="saveas:zclctt->zcbcdt", project_source=str(proj),
        execute=True, open_file=False, config=_cfg(tmp_path),
    )
    pe2 = res2["page_entry"]
    assert pe2 is None or pe2["status"] in ("id_exists", "controller_exists")
    assert sum('controller="zcbcdt"' in ln for ln in _meta_lines(proj)) == 1


def test_saveas_dry_run_does_not_write(tmp_path):
    proj = _mk_sp30(tmp_path)
    before = (proj / _META).read_bytes()
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt", project_source=str(proj),
        open_file=False, config=_cfg(tmp_path),
    )
    assert res["page_entry"]["status"] == "planned"
    assert (proj / _META).read_bytes() == before


def test_saveas_ambiguous_source_page_not_auto(tmp_path):
    proj = _mk_sp30(tmp_path)
    f = proj / "App_Data" / "Metadata" / "Page.001.xml"
    f.write_bytes(
        f.read_bytes() + (_page("zclctt2", "zclctt") + "\r\n").encode("utf-8")
    )
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt", project_source=str(proj),
        execute=True, open_file=False, config=_cfg(tmp_path),
    )
    assert res["page_entry"]["status"] == "ambiguous_source_page"
    assert any("page_not_registered" in w for w in res["warnings"])
    assert not any('controller="zcbcdt"' in ln for ln in _meta_lines(proj))


def test_saveas_legacy_project_untouched(tmp_path):
    proj = _mk_sp30(tmp_path, name="FBISP2422")
    before = (proj / "App_Data" / "Metadata" / "Page.001.xml").read_bytes()
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt", project_source=str(proj),
        execute=True, open_file=False, config=_cfg(tmp_path),
    )
    assert res["page_entry"] is None
    assert (proj / "App_Data" / "Metadata" / "Page.001.xml").read_bytes() == before


def test_page_attrs_from_aspx_simple_vs_complex():
    simple = (
        '<%@ Page v="V" e="E"%><FastBusiness:ReportExtender ReadOnly="true" '
        'FilterMode="false" Controller="Foo" />'
    )
    a = page_attrs_from_aspx(simple)
    assert a == {"controller": "Foo", "v": "V", "e": "E", "read_only": True,
                 "filter_mode": False, "template": "Page.001"}
    assert page_attrs_from_aspx(simple + "<script runat=\"server\"></script>") is None
    assert page_attrs_from_aspx('<%@ Register Assembly="Flow" %>' + simple) is None


def test_type4_report_on_sp30_adds_page_not_aspx(tmp_path):
    proj = _mk_sp30(tmp_path)
    res = run_type4_template(
        object="report_normal", new_name="zctest",
        project_target=str(proj), execute=True,
    )
    assert res["success"] is True
    assert not (proj / "Main").exists()
    pe = res["page_entries"]
    assert len(pe) == 1 and pe[0]["status"] == "added" and pe[0]["id"] == "zctest"
    line = [ln for ln in _meta_lines(proj) if 'id="zctest"' in ln][0]
    assert 'controller="zctest"' in line and 'filterMode="true"' in line
    assert 'template="Page.001"' in line
    assert "{{title_v}}" in res["unresolved_placeholders"]
    assert "<page" in res["edit_guide"]
    assert "Main/" not in res["edit_guide"] and "aspx'" not in res["edit_guide"].replace(".aspx'", "")


def test_type4_voucher_on_sp30_is_manual(tmp_path):
    proj = _mk_sp30(tmp_path)
    res = run_type4_template(
        object="voucher_normal_no_currency", new_name="PLH",
        project_target=str(proj), execute=True,
    )
    assert res["success"] is True
    assert [p["status"] for p in res["page_entries"]] == ["manual"]
    assert not (proj / "Main").exists()
    assert any("page_not_registered" in w for w in res["warnings"])


def test_type4_legacy_project_still_writes_aspx(tmp_path):
    proj = tmp_path / "FBISP2422"
    proj.mkdir()
    res = run_type4_template(
        object="report_normal", new_name="zctest",
        project_target=str(proj), execute=True,
    )
    assert (proj / "Main" / "zctest.aspx").is_file()
    assert res["page_entries"] == []


# ---------------- type=3 suite (chứng từ + controller duyệt đi kèm) ----------------

def _mk_voucher_sp30(tmp_path: Path) -> Path:
    proj = tmp_path / "FBISP30"
    meta = proj / "App_Data" / "Metadata"
    (meta / "Fragments").mkdir(parents=True)
    for t in ("Page.011", "Page.016"):
        (meta / "Fragments" / f"{t}.xml").write_text("<resources/>", encoding="utf-8")
    (meta / "Page.016.xml").write_text(
        _page("prctpn1", "PRTran", tpl="Page.016") + "\n", encoding="utf-8"
    )
    (meta / "Page.011.xml").write_text(
        _page("poduyet0", "PRApproval", tpl="Page.011") + "\n"
        + _page("shared", "SharedList", tpl="Page.011") + "\n",
        encoding="utf-8",
    )
    _mk_page_meta(proj)
    ctl = proj / "App_Data" / "Controllers"
    for sub, name in (
        ("Dir", "PRTran"), ("Grid", "PRTran"), ("Filter", "PRTran"),
        ("Grid", "PRApproval"), ("Filter", "PRApproval"),
        ("Grid", "SharedList"),
    ):
        (ctl / sub).mkdir(parents=True, exist_ok=True)
        (ctl / sub / f"{name}.xml").write_text("<x/>", encoding="utf-8")
    return proj


def test_suite_clone_registers_main_and_companion_pages(tmp_path):
    proj = _mk_voucher_sp30(tmp_path)
    res = clone_things(
        type=3, object="suite:PRTran->PLHTran",
        project_source=str(proj), execute=True,
    )
    assert res["success"] is True
    got = {p["dst_controller"]: p for p in res["page_entries"]}
    assert set(got) == {"PLHTran", "PLHApproval"}  # SharedList không đổi tên → bỏ qua
    assert all(p["status"] == "added" for p in got.values())
    meta_text = (proj / _META).read_text(encoding="utf-8-sig")
    assert 'id="plhtran"' in meta_text and 'controller="PLHTran"' in meta_text
    assert 'template="Page.016"' in meta_text
    assert 'id="plhapproval"' in meta_text and 'template="Page.011"' in meta_text
    assert "<!--Customize-->" in meta_text
    t11 = (proj / "App_Data" / "Metadata" / "Page.011.xml").read_text(encoding="utf-8")
    assert 'controller="SharedList"' in t11 and t11.count("SharedList") == 1


def test_suite_clone_dry_run_and_legacy_do_not_write(tmp_path):
    proj = _mk_voucher_sp30(tmp_path)
    f = proj / _META
    before = f.read_bytes()
    res = clone_things(
        type=3, object="suite:PRTran->PLHTran", project_source=str(proj)
    )
    assert {p["status"] for p in res["page_entries"]} == {"planned"}
    assert f.read_bytes() == before

    legacy = tmp_path / "old" / "FBISP2422"
    legacy.parent.mkdir()
    import shutil
    shutil.copytree(proj, legacy)
    res2 = clone_things(
        type=3, object="suite:PRTran->PLHTran",
        project_source=str(legacy), execute=True,
    )
    assert res2["page_entries"] == []
    assert "PLHTran" not in (legacy / _META).read_text(encoding="utf-8")


# ---------------- nguồn bản cũ (Main/*.aspx) -> đích SP30+ ----------------

ASPX_SIMPLE = (
    '<%@ Page AutoEventWireup="false" MasterPageFile="~/Main/MasterPage.master" '
    'Inherits="X" v="Danh mục US GAAP" e="US GAAP"%>\r\n'
    '<FastBusiness:ReportExtender ID="MainReport" runat="server" '
    'TargetControlID="panelReport" ReadOnly="true" Controller="zUSGAAP"/>'
)


def _mk_legacy_src(tmp_path: Path) -> Path:
    src = tmp_path / "TA" / "FBISP2261"
    for sub in ("Dir", "Grid", "Lookup"):
        d = src / "App_Data" / "Controllers" / sub
        d.mkdir(parents=True)
        (d / "zUSGAAP.xml").write_text("<x/>", encoding="utf-8")
    (src / "Main").mkdir()
    (src / "Main" / "zUSGAAP.aspx").write_text(ASPX_SIMPLE, encoding="utf-8")
    return src


def test_legacy_source_to_sp30_converts_aspx_to_page(tmp_path):
    src = _mk_legacy_src(tmp_path)
    tgt = _mk_sp30(tmp_path)
    res = clone_things(
        type=3, object="suite:zUSGAAP->zcdmtkifrs",
        project_source=str(src), project_target=str(tgt), execute=True,
    )
    assert res["success"] is True
    assert not (tgt / "Main").exists()  # không copy aspx sang đích
    assert (tgt / "App_Data/Controllers/Dir/zcdmtkifrs.xml").is_file()
    assert any("aspx_converted_to_page" in w for w in res["warnings"])
    pe = res["page_entries"]
    assert len(pe) == 1 and pe[0]["status"] == "added"
    assert pe[0]["src_controller"] == "zUSGAAP" and pe[0]["dst_controller"] == "zcdmtkifrs"
    line = [ln for ln in _meta_lines(tgt) if 'id="zcdmtkifrs"' in ln][0]
    assert 'controller="zcdmtkifrs"' in line and 'readOnly="true"' in line
    assert 'template="Page.001"' in line and "filterMode" not in line
    assert 'v="Danh mục US GAAP"' in line


def test_legacy_source_to_legacy_target_still_copies_aspx(tmp_path):
    src = _mk_legacy_src(tmp_path)
    tgt = tmp_path / "TB" / "FBISP2422"
    tgt.mkdir(parents=True)
    res = clone_things(
        type=3, object="suite:zUSGAAP->zcdmtkifrs",
        project_source=str(src), project_target=str(tgt), execute=True,
    )
    assert res["success"] is True
    assert (tgt / "Main" / "zcdmtkifrs.aspx").is_file()
    assert res["page_entries"] == []


# ---------------- <!--Customize--> của PageMetadata.xml ----------------

def test_insert_customize_existing_block(tmp_path):
    proj = _mk_sp30(tmp_path)
    r = insert_customize_page(proj, [_page("new1", "New1")], execute=True)
    assert r["status"] == "added" and r["position"] == "customize"
    lines = _meta_lines(proj)
    i_end = next(i for i, ln in enumerate(lines) if "End Customize" in ln)
    assert 'id="new1"' in lines[i_end - 1]
    raw = (proj / _META).read_bytes()
    assert raw.startswith(BOM) and b"\r\n" in raw


def test_insert_customize_creates_block_before_close(tmp_path):
    proj = _mk_sp30(tmp_path)
    _mk_page_meta(proj, customize=False)
    r = insert_customize_page(proj, [_page("new2", "New2")], execute=True)
    lines = _meta_lines(proj)
    i_c = next(i for i, ln in enumerate(lines) if "<!--Customize-->" in ln)
    i_e = next(i for i, ln in enumerate(lines) if "End Customize" in ln)
    i_p = next(i for i, ln in enumerate(lines) if "</pages>" in ln)
    assert i_c < i_e < i_p and 'id="new2"' in lines[i_c + 1]


def test_insert_customize_dry_run_no_write(tmp_path):
    proj = _mk_sp30(tmp_path)
    before = (proj / _META).read_bytes()
    r = insert_customize_page(proj, [_page("x", "X")], execute=False)
    assert r["status"] == "planned"
    assert (proj / _META).read_bytes() == before


def test_inline_page_in_metadata_is_found(tmp_path):
    proj = _mk_sp30(tmp_path)
    insert_customize_page(proj, [_page("invt", "Item")], execute=True)
    entries = find_page_entries(proj, "Item")
    assert len(entries) == 1 and entries[0]["id"] == "invt"
    assert entries[0]["file"] == "../PageMetadata.xml"


# ---------------- param page (register_page_line) ----------------

def test_page_param_adds_line(tmp_path):
    proj = _mk_sp30(tmp_path)
    res = clone_things(
        page=_page("zmenu1", "ZMenu1"), project_source=str(proj),
        execute=True, config=_cfg(tmp_path),
    )
    assert res["success"] is True and res["mode"] == "page_register"
    assert res["status"] == "added"
    assert any('id="zmenu1"' in ln for ln in _meta_lines(proj))


def test_page_param_dedup_and_missing_template(tmp_path):
    proj = _mk_sp30(tmp_path)
    res = clone_things(
        page=_page("zclctt", "ZZNew"), project_source=str(proj), execute=True,
        config=_cfg(tmp_path),
    )
    assert res["entries"][0]["status"] == "id_exists"
    res2 = clone_things(
        page=_page("new9", "zclctt"), project_source=str(proj), execute=True,
        config=_cfg(tmp_path),
    )
    assert res2["entries"][0]["status"] == "controller_exists"
    res3 = clone_things(
        page=_page("new9", "ZZNew", tpl="Page.999"), project_source=str(proj),
        execute=True, config=_cfg(tmp_path),
    )
    assert res3["entries"][0]["status"] == "template_missing"


def test_page_param_suggests_template(tmp_path):
    proj = _mk_sp30(tmp_path)
    line = '<page id="zrep1" v="R" e="R" controller="ZRpt1"/>'
    res = clone_things(page=line, project_source=str(proj), execute=True,
                       config=_cfg(tmp_path))
    e = res["entries"][0]
    assert e["status"] == "added" and e["suggested_template"] == "Page.001"
    assert 'template="Page.001"' in e["line"]


def test_page_param_invalid_line(tmp_path):
    proj = _mk_sp30(tmp_path)
    res = clone_things(page='<page v="x"/>', project_source=str(proj),
                       config=_cfg(tmp_path))
    assert res["entries"][0]["status"] == "invalid_page_line"


def test_page_param_merges_with_type3(tmp_path):
    src = _mk_voucher_sp30(tmp_path)
    tgt = _mk_voucher_sp30(tmp_path / "dst")
    res = clone_things(
        type=3, object="suite:PRTran->PLHTran",
        project_source=str(src), project_target=str(tgt), execute=True,
        page=_page("zextra", "ZExtra", tpl="Page.016"),
    )
    assert res["success"] is True
    assert res["page_param"]["status"] == "added"
    assert any('id="zextra"' in ln for ln in _meta_lines(tgt))


# ---------------- suggest_template ----------------

def _mk_frag(proj: Path, name: str, body: str):
    (proj / "App_Data" / "Metadata" / "Fragments" / f"{name}.xml").write_text(
        body, encoding="utf-8"
    )


def test_suggest_template_families(tmp_path):
    proj = _mk_sp30(tmp_path)
    _mk_frag(proj, "Page.011", "Init.Flow Include/APVSign.txt @render(X, f) HTML.MainSplitter")
    _mk_frag(proj, "Page.012", "Include/Extender.txt @render(X, f) @render(X, query) HTML.MainSplitter Script.Cryptography")
    _mk_frag(proj, "Query", "@render(X, query)")
    apv = suggest_template(proj, page_needed_features("ZApproval"), "ZApproval")
    assert apv[0]["template"] == "Page.011"
    vou = suggest_template(
        proj,
        page_needed_features("ZZTran", ["ExtenderControls.ascx QueryExtender"]),
        "ZZTran",
    )
    assert vou[0]["template"] == "Page.012"
    q = suggest_template(proj, page_needed_features("zus_QueryDemo"), "zus_QueryDemo")
    assert q[0]["template"] == "Query"
    plain = suggest_template(proj, page_needed_features("rptX"), "rptX")
    assert plain[0]["template"] == "Page.001"
