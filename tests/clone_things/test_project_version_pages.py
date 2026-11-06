"""Program mới (SP30+) khai báo trang bằng <page> trong Metadata; bản cũ giữ Main/*.aspx."""

from pathlib import Path

import pytest

from clone_things.service import clone_things
from find_connect_by_path.project_version import is_metadata_project, parse_sp_major


@pytest.mark.parametrize(
    "path,major,is_new",
    [
        ("z:/FBI/DIVN/FBISP30", 30, True),
        ("\\\\172.168.5.14\\CustomerPro\\FBI\\DIVN\\FBISP3012\\", 30, True),
        ("//srv/FBI/X/FBISP4005", 40, True),
        ("//srv/FBI/TTI_FBI/FBISP2422", 24, False),
        ("//srv/FBI/CHUBB/SP2264", 22, False),
        ("//srv/FBI/proj", None, False),
    ],
)
def test_parse_sp_major(path, major, is_new):
    assert parse_sp_major(path) == major
    assert is_metadata_project(path) is is_new


FILTER_XML = '<filter><title v="Báo cáo" e=""/></filter>'
PAGE_LINE = (
    '<page id="zclctt" v="Báo cáo" e="Rpt" controller="zclctt" '
    'readOnly="true" filterMode="true" template="Page.001"/>\n'
)


def _mk(tmp_path: Path, name: str, with_page: bool) -> Path:
    proj = tmp_path / name
    fdir = proj / "App_Data" / "Controllers" / "Filter"
    fdir.mkdir(parents=True)
    (fdir / "zclctt.xml").write_text(FILTER_XML, encoding="utf-8")
    if with_page:
        mdir = proj / "App_Data" / "Metadata"
        mdir.mkdir(parents=True)
        (mdir / "Page.001.xml").write_text(
            '<page id="other" controller="Other" template="Page.001"/>\n' + PAGE_LINE,
            encoding="utf-8",
        )
    # aspx giả: bản mới KHÔNG được quét Main
    (proj / "Main").mkdir()
    (proj / "Main" / "rpt_x.aspx").write_text(
        '<x Controller="zclctt"/>', encoding="utf-8"
    )
    return proj


def _cfg(tmp_path):
    return {"clone_things": {"sql_temp_folder": str(tmp_path), "open_file": False}}


def test_new_program_reports_page_not_aspx(tmp_path):
    proj = _mk(tmp_path, "FBISP30", with_page=True)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    warn = " ".join(res["warnings"])
    assert "suite_page_detected" in warn
    assert "Page.001.xml:2 id=zclctt template=Page.001" in warn
    assert "suite_aspx" not in warn
    planned = {p["relative"] for p in res["planned"]}
    assert "Main/rpt_x.aspx" not in planned
    assert "<page" in " ".join(res["next_steps"])


def test_new_program_page_missing(tmp_path):
    proj = _mk(tmp_path, "FBISP30", with_page=False)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    assert any("suite_page_missing" in w for w in res["warnings"])


def test_legacy_program_keeps_aspx_detect(tmp_path):
    proj = _mk(tmp_path, "FBISP2422", with_page=True)
    res = clone_things(
        type=6, object="saveas:zclctt->zcbcdt",
        project_source=str(proj), open_file=False, config=_cfg(tmp_path),
    )
    warn = " ".join(res["warnings"])
    assert "suite_aspx_detected" in warn
    assert "suite_page" not in warn
    assert "Main/rpt_x.aspx" in {p["relative"] for p in res["planned"]}
