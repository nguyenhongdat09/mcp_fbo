"""Thuộc tính khuôn (tinyv/tinye), khuôn theo control aspx, và khai Aggregation.q."""

from pathlib import Path

from clone_things.config_registry import is_query_controller, register_query_aggregation
from clone_things.page_registry import (
    build_page_line,
    ensure_template_attrs,
    page_attrs_from_aspx,
    register_page_clone,
    template_needs,
)
from clone_things.service import clone_things

BOM = b"\xef\xbb\xbf"
FRAG_020 = (
    "<resources><fragment>#Write('@@tinyv') #Write('@@tinye') @@title</fragment></resources>"
)


def _mk_sp30(tmp_path: Path, name="FBISP30") -> Path:
    proj = tmp_path / name
    frag = proj / "App_Data" / "Metadata" / "Fragments"
    frag.mkdir(parents=True)
    (frag / "Page.001.xml").write_text("<resources/>", encoding="utf-8")
    (frag / "Page.020.xml").write_text(FRAG_020, encoding="utf-8")
    meta = proj / "App_Data" / "Metadata"
    (meta / "Page.001.xml").write_text("", encoding="utf-8")
    (meta / "Page.020.xml").write_bytes(
        BOM + b'<page id="rpt_a" v="A" e="A e" tinyv="A" tinye="A e" controller="RptA" template="Page.020"/>\r\n'
    )
    (proj / "App_Data" / "PageMetadata.xml").write_bytes(
        BOM + b'<pages>\r\n  <!--Customize-->\r\n  <!--End Customize-->\r\n</pages>\r\n'
    )
    return proj


def test_template_needs_reads_placeholders(tmp_path):
    proj = _mk_sp30(tmp_path)
    assert template_needs(proj, "Page.020") == {"tinyv", "tinye"}
    assert template_needs(proj, "Page.001") == set()
    assert template_needs(proj, "Page.999") == set()


def test_build_page_line_adds_needed_attrs():
    line = build_page_line("x", "X", "Tiêu đề", "Title", True, True, "Page.020", {"tinyv", "tinye"})
    assert 'tinyv="Tiêu đề"' in line and 'tinye="Title"' in line
    assert line.index("tinye") < line.index("controller")
    assert "tinyv" not in build_page_line("x", "X", "a", "b", True, True, "Page.001")


def test_ensure_template_attrs_only_fills_missing():
    line = '<page id="a" v="V" e="E" controller="C" template="Page.020"/>'
    out = ensure_template_attrs(line, {"tinyv", "tinye"})
    assert 'tinyv="V"' in out and 'tinye="E"' in out
    assert ensure_template_attrs(out, {"tinyv", "tinye"}) == out


def test_register_page_clone_fills_attrs_when_source_lacks_them(tmp_path):
    proj = _mk_sp30(tmp_path)
    src = {
        "file": "Page.020.xml", "line_no": 1, "id": "old", "template": "Page.020",
        "text": '<page id="old" v="Cũ" e="Old" controller="Old" template="Page.020"/>',
    }
    res = register_page_clone(proj, src, "NewRpt", True)
    assert res["status"] == "added"
    text = (proj / "App_Data/PageMetadata.xml").read_text(encoding="utf-8-sig")
    line = [ln for ln in text.splitlines() if 'id="newrpt"' in ln][0]
    assert 'tinyv="Cũ"' in line and 'tinye="Old"' in line


ASPX = (
    '<%@ Page MasterPageFile="~/Main/MasterPage.master" v="Bao cao" e="Report" %>\r\n'
    "{script}"
    '<fastbusiness:reportextender id="MainReport" runat="server" filtermode="true" '
    'readonly="true" controller="rptX" />\r\n'
)


def _aspx(controls):
    if not controls:
        return ASPX.format(script="")
    loads = "".join(f'ResourcePanel.Controls.Add(LoadControl("{c}"))\r\n' for c in controls)
    return ASPX.format(script=f'<script runat="server">\r\n{loads}</script>\r\n')


def test_page_attrs_template_by_control():
    assert page_attrs_from_aspx(_aspx([]))["template"] == "Page.001"
    assert page_attrs_from_aspx(_aspx(["Chart.ascx"]))["template"] == "Page.004"
    assert page_attrs_from_aspx(_aspx(["TreeView.ascx"]))["template"] == "Page.005"
    assert page_attrs_from_aspx(_aspx(["ExtenderControls.ascx"])) is None
    assert page_attrs_from_aspx(_aspx(["Chart.ascx", "TreeView.ascx"])) is None


def test_is_query_controller():
    for ok in ("QueryTrialBalance", "zus_QueryIncomeStatementMultiPeriod", "zifrs_QueryX"):
        assert is_query_controller(ok)
    for no in ("rptTrialBalance", "zcdmkblktkvasvtd", "Quarter", "MyQuery"):
        assert not is_query_controller(no)


def _agg(proj: Path, body: str, crlf=True):
    p = proj / "App_Data" / "Controllers" / "Grid" / "Config"
    p.mkdir(parents=True, exist_ok=True)
    nl = "\r\n" if crlf else "\n"
    (p / "Aggregation.q").write_bytes(
        BOM + (nl.join(body.split("\n"))).encode("utf-8")
    )
    return p / "Aggregation.q"


def test_register_query_aggregation_adds_once_keeps_bom_and_eol(tmp_path):
    proj = _mk_sp30(tmp_path)
    f = _agg(
        proj, '<controller name="QueryA" description=""/>\n<controller name="QueryB" description=""/>'
    )
    res = register_query_aggregation(proj, ["zifrs_QueryX", "rptNotQuery"], True)
    assert [r["status"] for r in res] == ["added"]
    raw = f.read_bytes()
    assert raw.startswith(BOM)
    text = raw.decode("utf-8-sig")
    assert text.endswith('<controller name="zifrs_QueryX" description=""/>\r\n')
    assert text.count("\r\n") == 3 and "\n" not in text.replace("\r\n", "")
    again = register_query_aggregation(proj, ["zifrs_QueryX"], True)
    assert again[0]["status"] == "exists"
    assert f.read_bytes().decode("utf-8-sig").count("zifrs_QueryX") == 1


def test_register_query_aggregation_dry_run_and_missing_file(tmp_path):
    proj = _mk_sp30(tmp_path)
    assert register_query_aggregation(proj, ["QueryZ"], False)[0]["status"] == "file_missing"
    f = _agg(proj, '<controller name="QueryA" description=""/>')
    before = f.read_bytes()
    assert register_query_aggregation(proj, ["QueryZ"], False)[0]["status"] == "planned"
    assert f.read_bytes() == before


def test_type3_copy_of_query_grid_registers_aggregation(tmp_path):
    src = tmp_path / "TA" / "FBISP2261"
    gdir = src / "App_Data" / "Controllers" / "Grid"
    gdir.mkdir(parents=True)
    (gdir / "zus_QueryX.xml").write_text("<grid/>", encoding="utf-8")
    tgt = _mk_sp30(tmp_path)
    f = _agg(tgt, '<controller name="QueryA" description=""/>')
    res = clone_things(
        type=3,
        object="App_Data/Controllers/Grid/zus_QueryX.xml->zifrs_QueryX.xml",
        project_source=str(src), project_target=str(tgt), execute=True,
    )
    assert res["success"] is True
    assert res["target_generation"] == "metadata"
    assert [a["status"] for a in res["aggregation_entries"]] == ["added"]
    assert 'name="zifrs_QueryX"' in f.read_text(encoding="utf-8-sig")
    # dry-run không ghi thêm
    f2 = _agg(tgt, '<controller name="QueryA" description=""/>')
    clone_things(
        type=3,
        object="App_Data/Controllers/Grid/zus_QueryX.xml->zifrs_QueryY.xml",
        project_source=str(src), project_target=str(tgt), execute=False,
    )
    assert "zifrs_QueryY" not in f2.read_text(encoding="utf-8-sig")
