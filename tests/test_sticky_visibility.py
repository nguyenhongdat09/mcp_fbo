"""AC-VIS-* — sticky context visibility (GEMINI-mcp-sticky-visibility.md).

Mọi tool qua resolve_any_path echo project_root + resolved_via; khi sticky
_LAST_PROJECT_ROOT đổi project (cũ non-null, khác mới) response kèm
warnings[] "project_root switched: X → Y". Warning là observability —
không đổi kết quả resolve.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xml_fbograph.mcp_tools import mcp_read_local_file
from xml_fbograph.utils.any_path import reset_sticky_context
from search_files import search_files
from suggest_edit import suggest_edit
from compare_things import compare_things


@pytest.fixture(autouse=True)
def _reset():
    reset_sticky_context()
    yield
    reset_sticky_context()


def _make_project(tmp_path: Path, name: str, marker: str) -> Path:
    proj = tmp_path / name
    ctrl = proj / "App_Data" / "Controllers" / "Dir"
    ctrl.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (ctrl / "SOTran.xml").write_text(
        f'<dir id="SOTran"><!-- {marker} --></dir>', encoding="utf-8"
    )
    cs = proj / "ClientScript"
    cs.mkdir(parents=True, exist_ok=True)
    (cs / "lib.js").write_text(
        f"// {marker}\nfunction sendMail_{marker}() {{\n\treturn '{marker}';\n}}\n",
        encoding="utf-8",
    )
    return proj


@pytest.fixture
def two_projects(tmp_path):
    pa = _make_project(tmp_path, "PROJ_A", "AAA")
    pb = _make_project(tmp_path, "PROJ_B", "BBB")
    return pa, pb


# ---------------------------------------------------------------------------
# AC-VIS-1: read_local_file relative → project_root + resolved_via
# ---------------------------------------------------------------------------


def test_ac_vis_1_read_local_file_relative_echoes_ctx(two_projects):
    pa, _ = two_projects
    xml = pa / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"
    mcp_read_local_file(str(xml), read_option=1)  # seed sticky

    # raw content (read_option=1) — text response kèm header ctx
    out = mcp_read_local_file("Dir/SOTran.xml", read_option=1)
    assert "AAA" in out  # vẫn trả đúng content
    assert "Project root:" in out
    assert str(pa) in out
    assert "Resolved via: sticky_context" in out

    # snippet mode — JSON response có 2 field top-level
    res = json.loads(
        mcp_read_local_file("ClientScript/lib.js", symbol="sendMail_AAA")
    )
    assert res["success"] is True
    assert res["resolved_via"] == "sticky_context"
    assert Path(res["project_root"]).resolve() == pa.resolve()


def test_ac_vis_1b_read_local_file_abs_echoes_ctx(two_projects):
    pa, _ = two_projects
    js = pa / "ClientScript" / "lib.js"
    res = json.loads(mcp_read_local_file(str(js), symbol="sendMail_AAA"))
    assert res["resolved_via"] == "absolute"
    assert Path(res["project_root"]).resolve() == pa.resolve()


def test_ac_vis_1c_read_option_4_echoes_ctx(two_projects):
    pa, _ = two_projects
    res = json.loads(
        mcp_read_local_file(
            str(pa / "ClientScript" / "lib.js"),
            read_option=4,
            symbol="sendMail_AAA",
        )
    )
    assert res["success"] is True
    assert res["mode"] == "suggest_edit"
    assert res["resolved_via"] == "absolute"
    assert Path(res["project_root"]).resolve() == pa.resolve()


def test_ac_vis_1d_suggest_edit_relative_echoes_ctx(two_projects):
    pa, _ = two_projects
    js = pa / "ClientScript" / "lib.js"
    suggest_edit(file_path=str(js), symbol="sendMail_AAA")  # seed sticky
    res = suggest_edit(file_path="ClientScript/lib.js", symbol="sendMail_AAA")
    assert res["success"] is True
    assert res["resolved_via"] == "sticky_context"
    assert Path(res["project_root"]).resolve() == pa.resolve()


# ---------------------------------------------------------------------------
# AC-VIS-2: search_files relative → project_root + resolved_via
# ---------------------------------------------------------------------------


def test_ac_vis_2_search_files_relative_echoes_ctx(two_projects):
    pa, _ = two_projects
    search_files(root=str(pa / "ClientScript"), pattern="sendMail")  # seed sticky

    res = search_files(root="ClientScript", pattern="sendMail")
    assert res["success"] is True
    assert res["resolved_via"] == "sticky_context"
    assert Path(res["project_root"]).resolve() == pa.resolve()


def test_ac_vis_2b_search_files_abs_echoes_ctx(two_projects):
    pa, _ = two_projects
    res = search_files(root=str(pa / "ClientScript"), pattern="sendMail")
    assert res["resolved_via"] == "absolute"
    assert Path(res["project_root"]).resolve() == pa.resolve()


# ---------------------------------------------------------------------------
# AC-VIS-3: call abs project B sau project A → warning đúng 1 lần
# ---------------------------------------------------------------------------


def test_ac_vis_3_switch_warns_once(two_projects):
    pa, pb = two_projects

    res_a = search_files(root=str(pa / "ClientScript"), pattern="sendMail")
    assert not any("project_root switched" in w for w in res_a["warnings"])

    res_b = search_files(root=str(pb / "ClientScript"), pattern="sendMail")
    warns = [w for w in res_b["warnings"] if "project_root switched" in w]
    assert len(warns) == 1
    assert "PROJ_A" in warns[0] and "PROJ_B" in warns[0]

    # call tiếp project B → không warn nữa
    res_b2 = search_files(root=str(pb / "ClientScript"), pattern="sendMail")
    assert not any("project_root switched" in w for w in res_b2["warnings"])


def test_ac_vis_3b_switch_warn_via_read_local_file(two_projects):
    pa, pb = two_projects
    mcp_read_local_file(
        str(pa / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"), read_option=1
    )
    out = mcp_read_local_file(
        str(pb / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"), read_option=1
    )
    assert "[WARNING] project_root switched:" in out
    assert "PROJ_A" in out and "PROJ_B" in out
    # content vẫn đúng project B
    assert "BBB" in out


def test_ac_vis_3c_switch_warn_via_compare_things(two_projects):
    pa, pb = two_projects
    fa = pa / "ClientScript" / "lib.js"
    fb = pb / "ClientScript" / "lib.js"
    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    assert Path(res["project_root"]).resolve() == pb.resolve()
    assert any("project_root switched" in w for w in res["warnings"])


# ---------------------------------------------------------------------------
# AC-VIS-4: fresh server không warn; abs ngoài project → project_root=null
# ---------------------------------------------------------------------------


def test_ac_vis_4_fresh_no_warn(two_projects):
    pa, _ = two_projects
    res = search_files(root=str(pa / "ClientScript"), pattern="sendMail")
    assert res["warnings"] == [] or not any(
        "project_root switched" in w for w in res["warnings"]
    )


def test_ac_vis_4b_abs_outside_project_null_root(tmp_path):
    outside = tmp_path / "loose.txt"
    outside.write_text("hello keyword", encoding="utf-8")

    res = search_files(root=str(outside), pattern="keyword")
    assert res["success"] is True
    assert res["project_root"] is None
    assert not any("project_root switched" in w for w in res["warnings"])

    out = mcp_read_local_file(str(outside), read_option=1)
    assert "Project root: null" in out
    assert "project_root switched" not in out
    assert "hello keyword" in out


# ---------------------------------------------------------------------------
# AC-VIS-5: warning là observability — resolve vẫn chạy bình thường
# ---------------------------------------------------------------------------


def test_ac_vis_5_warn_does_not_change_resolution(two_projects):
    pa, pb = two_projects
    search_files(root=str(pa / "ClientScript"), pattern="sendMail")  # sticky=A

    # call abs B → warn, sticky=B
    res_b = search_files(root=str(pb / "ClientScript"), pattern="sendMail_BBB")
    assert any("project_root switched" in w for w in res_b["warnings"])
    assert res_b["total_matches"] == 1  # B có marker BBB

    # relative tiếp theo resolve theo B (context đã trôi — warning báo đúng)
    res_rel = search_files(root="ClientScript", pattern="sendMail_BBB")
    assert res_rel["resolved_via"] == "sticky_context"
    assert res_rel["total_matches"] == 1
    assert Path(res_rel["project_root"]).resolve() == pb.resolve()


# ---------------------------------------------------------------------------
# AC-VIS-6: không regress — path_not_found giữ tried[]/known_projects
# ---------------------------------------------------------------------------


def test_ac_vis_6_path_not_found_no_regress(two_projects):
    pa, _ = two_projects
    search_files(root=str(pa / "ClientScript"), pattern="x")  # seed sticky

    res = search_files(root="NoSuchDir", pattern="x")
    assert res["success"] is False
    assert res["error_code"] == "path_not_found"
    assert res["tried"]
    assert res["known_projects"]

    res2 = json.loads(mcp_read_local_file("Dir/KhongCo.xml", read_option=1))
    assert res2["success"] is False
    assert res2["error_code"] == "path_not_found"
    assert res2["tried"]
    # field ctx vẫn echo (null) cho nhất quán
    assert "project_root" in res2
