"""Tests cho clone_things type=6 — save-as/copy từ chức năng có sẵn."""

from pathlib import Path

from clone_things.service import clone_things
from clone_things.type6_save_as import parse_saveas_spec


FILTER_XML = """<?xml version="1.0" encoding="utf-8"?>
<filter table="" code="">
  <title v="Báo cáo lưu chuyển tiền tệ theo phương pháp trực tiếp cho nhiều kỳ" e="Cash flow direct"/>
  <command><![CDATA[EXEC zc_lctt @ngay1, @ngay2]]></command>
</filter>
"""

FILTER_XML_2 = """<?xml version="1.0" encoding="utf-8"?>
<filter>
  <title v="Báo cáo lưu chuyển tiền tệ theo phương pháp gián tiếp" e=""/>
</filter>
"""


def _mk_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    fdir = proj / "App_Data" / "Controllers" / "Filter"
    gdir = proj / "App_Data" / "Controllers" / "Grid"
    rdir = proj / "App_Data" / "Controllers" / "Report"
    mdir = proj / "Main"
    for d in (fdir, gdir, rdir, mdir):
        d.mkdir(parents=True, exist_ok=True)
    (fdir / "zclctt.xml").write_text(FILTER_XML, encoding="utf-8")
    (gdir / "zclctt.xml").write_text("<grid/>", encoding="utf-8")
    (rdir / "zclctt.xml").write_text("<report/>", encoding="utf-8")
    (mdir / "zclctt.aspx").write_text("page", encoding="utf-8")
    return proj


def _mk_project_full(tmp_path: Path) -> Path:
    """Fixture đầy đủ: Report XML khai báo templateFile lệch prefix ctrl +
    aspx tên lệch (detect theo Controller=) + Graph XML + .xsd designer."""
    proj = tmp_path / "proj"
    fdir = proj / "App_Data" / "Controllers" / "Filter"
    rdir = proj / "App_Data" / "Controllers" / "Report"
    edir = proj / "App_Data" / "Controllers" / "Templates" / "Excel"
    tdir = proj / "App_Data" / "Controllers" / "Templates" / "Rpt"
    mdir = proj / "Main"
    for d in (fdir, rdir, edir, tdir, mdir):
        d.mkdir(parents=True, exist_ok=True)
    (fdir / "zclctt.xml").write_text(FILTER_XML, encoding="utf-8")
    (fdir / "zclcttGraph.xml").write_text(
        '<filter><title v="Graph"/></filter>', encoding="utf-8")
    (rdir / "zclctt.xml").write_text(
        '<report><form templateFile="rpt_abc_01.xlsx" '
        'reportFile="zclctt.rpt"/></report>',
        encoding="utf-8")
    (edir / "rpt_abc_01.xlsx").write_bytes(b"x")
    (tdir / "zclctt.rpt").write_bytes(b"r")
    (tdir / "zclctt.xsd").write_bytes(b"s")
    (mdir / "rpt_abc.aspx").write_text(
        '<fbo:Report Controller="zclctt"/>', encoding="utf-8")
    return proj


def _cfg(tmp_path):
    return {"clone_things": {"sql_temp_folder": str(tmp_path),
                             "open_file": False}}


# ---------------- parse grammar ----------------

def test_parse_ctrl_plain():
    kind, src, dst, err = parse_saveas_spec("saveas:zclctt->zcbcdt")
    assert (kind, src, dst, err) == ("ctrl", "zclctt", "zcbcdt", None)


def test_parse_ctrl_prefix_and_xml():
    assert parse_saveas_spec("saveas:ctrl:zclctt->zcbcdt")[0] == "ctrl"
    kind, src, _, _ = parse_saveas_spec("saveas:Filter/zclctt.xml->zcbcdt")
    assert (kind, src) == ("ctrl", "zclctt")


def test_parse_title_auto_and_prefix():
    kind, src, dst, err = parse_saveas_spec(
        "saveas:Báo cáo lưu chuyển tiền tệ->zcbcdt")
    assert (kind, src, dst) == ("title", "Báo cáo lưu chuyển tiền tệ", "zcbcdt")
    assert parse_saveas_spec("saveas:title:Báo cáo X->zcx")[0] == "title"


def test_parse_invalid():
    assert parse_saveas_spec("zclctt->zcbcdt")[3] == "invalid_object"
    assert parse_saveas_spec("saveas:zclctt")[3] == "invalid_object"
    assert parse_saveas_spec("saveas:zclctt->bad name")[3] == "invalid_rename"


# ---------------- ctrl direct ----------------

def test_type6_ctrl_dry_run(tmp_path):
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert res["type"] == 6
    assert res["source_ctrl"] == "zclctt"
    assert res["dest_ctrl"] == "zcbcdt"
    assert res["execute"] is False  # dry-run kế thừa type=3
    rels = {p["relative"] for p in res["planned"]}
    assert "App_Data/Controllers/Filter/zclctt.xml" in rels
    # target renamed
    tgts = {p["target_relative"] for p in res["planned"]}
    assert "App_Data/Controllers/Filter/zcbcdt.xml" in tgts
    assert "Main/zcbcdt.aspx" in tgts


def test_type6_ctrl_execute_copies(tmp_path):
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt", execute=True,
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    new_filter = proj / "App_Data" / "Controllers" / "Filter" / "zcbcdt.xml"
    assert new_filter.is_file()
    assert "lưu chuyển tiền tệ" in new_filter.read_text(encoding="utf-8")
    assert (proj / "Main" / "zcbcdt.aspx").is_file()


# ---------------- title resolve ----------------

def test_type6_title_disk_fallback(tmp_path):
    """Title resolve bằng quét <title> trên disk."""
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6,
        object="saveas:title:Báo cáo lưu chuyển tiền tệ->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert res["source_ctrl"] == "zclctt"
    assert "lưu chuyển tiền tệ" in res["source_title"].lower()


def test_type6_title_auto_detect(tmp_path):
    """src có space/dấu → auto title."""
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6,
        object="saveas:Báo cáo lưu chuyển tiền tệ->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert res["source_ctrl"] == "zclctt"


def test_type6_title_ambiguous(tmp_path):
    proj = _mk_project(tmp_path)
    (proj / "App_Data" / "Controllers" / "Filter" / "zckhac.xml").write_text(
        FILTER_XML, encoding="utf-8")
    res = clone_things(
        type=6,
        object="saveas:title:Báo cáo lưu chuyển tiền tệ->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is False
    assert res["error_code"] == "ambiguous_source"
    assert {c["ctrl"] for c in res["candidates"]} == {"zclctt", "zckhac"}


def test_type6_title_not_found(tmp_path):
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6, object="saveas:title:Báo cáo không tồn tại->zcx",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is False
    assert res["error_code"] == "source_not_found"
    assert "hỏi user" in res["message"]


def test_type6_ctrl_suite_empty(tmp_path):
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6, object="saveas:ctrl:khongco->zcx",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is False
    assert res["error_code"] == "suite_empty"


# ---------------- sql extraction / export ----------------

def test_type6_extracts_procs_no_db(tmp_path):
    """Project fake không có Web.config → proc extract được nhưng không
    export (db_connections_missing warning)."""
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert "zc_lctt" in res["sql_objects"]
    assert res["path_to_pasted"] is None
    assert any("db_connections_missing" in w for w in res["warnings"])
    assert "zc_lctt" in res["sql_objects_unresolved"]


def test_type6_no_sql_refs(tmp_path):
    proj = _mk_project(tmp_path)
    (proj / "App_Data" / "Controllers" / "Filter" / "zcempty.xml").write_text(
        FILTER_XML_2, encoding="utf-8")
    res = clone_things(
        type=6, object="saveas:zcempty->zcnew",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert res["sql_objects"] == []
    assert any("no_sql_refs" in w for w in res["warnings"])


def test_type6_next_steps_mention_rename(tmp_path):
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    steps = " ".join(res["next_steps"])
    assert "đổi tên" in steps.lower() or "Đổi tên" in steps
    assert "PARSEONLY" in steps


# ---------------- suite coverage (mẫu in/aspx/Graph/xsd) ----------------

def test_type6_suite_covers_excel_template_and_aspx(tmp_path):
    """Mẫu Excel tên lệch prefix + aspx detect theo Controller= đều vào
    planned; same-project → same-name files trong skipped_same_source."""
    proj = _mk_project_full(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    planned = {p["relative"] for p in res["planned"]}
    assert "App_Data/Controllers/Templates/Excel/rpt_abc_01.xlsx" in planned
    assert "App_Data/Controllers/Templates/Rpt/zclctt.rpt" in planned
    assert "Main/rpt_abc.aspx" in planned
    assert any("suite_templates_found" in w for w in res["warnings"])
    assert any("suite_aspx_detected" in w for w in res["warnings"])
    # file tên lệch không đổi tên → same source/target → skip chủ đích
    same = res.get("skipped_same_source") or []
    assert "Main/rpt_abc.aspx" in same
    assert "App_Data/Controllers/Templates/Excel/rpt_abc_01.xlsx" in same


def test_type6_next_steps_xsd_graph_aspx(tmp_path):
    """next_steps giải thích .xsd denied + Graph content + aspx lệch tên."""
    proj = _mk_project_full(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    steps_txt = " ".join(res["next_steps"])
    assert ".xsd" in steps_txt and "designer" in steps_txt
    assert "Graph" in steps_txt and "entity" in steps_txt
    assert "Chart.ascx" in steps_txt
    assert ".aspx" in steps_txt and "Controller=" in steps_txt
    denied = res.get("skipped_denied") or []
    assert any(d.endswith(".xsd") for d in denied)


def test_type6_warnings_deduped(tmp_path):
    """_expand_suite_files chạy 2 lần (type6 + type3) → warning không nhân đôi."""
    proj = _mk_project_full(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert len(res["warnings"]) == len(set(res["warnings"]))


def test_type6_ambiguous_marks_suggested(tmp_path):
    """2 candidate cùng title, 1 hậu tố Graph → suggested=non-Graph + hint."""
    proj = _mk_project(tmp_path)
    (proj / "App_Data" / "Controllers" / "Filter" / "zclcttGraph.xml") \
        .write_text(FILTER_XML, encoding="utf-8")
    res = clone_things(
        type=6,
        object="saveas:title:Báo cáo lưu chuyển tiền tệ->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is False
    assert res["error_code"] == "ambiguous_source"
    sug = [c["ctrl"] for c in res["candidates"] if c.get("suggested")]
    assert sug == ["zclctt"]
    assert 'Controller="' in res["message"]


def test_type6_no_excel_template_next_step(tmp_path):
    """Suite không có Templates/Excel → next_steps nhắc tạo mẫu tay."""
    proj = _mk_project(tmp_path)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    steps_txt = " ".join(res["next_steps"])
    assert "Templates/Excel" in steps_txt


# ---------------- validation ----------------

def test_type6_requires_object(tmp_path):
    res = clone_things(type=6, object="", project_source=str(tmp_path),
                       open_file=False, config=_cfg(tmp_path))
    assert res["success"] is False
    assert res["error_code"] == "invalid_object"


def test_type6_bad_project_source(tmp_path):
    res = clone_things(type=6, object="saveas:zclctt->zcbcdt",
                       project_source="relative\\path",
                       open_file=False, config=_cfg(tmp_path))
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_source"
