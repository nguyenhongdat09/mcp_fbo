"""Unit tests for xml_fbograph/utils/any_path.py — universal path resolver.

Covers resolve_any_path (abs file/dir, relative qua controllers_root/project_root)
+ sticky project context (_LAST_PROJECT_ROOT/_PROJECT_ROOTS LRU).
"""

from __future__ import annotations

import pytest
from pathlib import Path

from xml_fbograph.utils.any_path import (
    known_projects,
    reset_sticky_context,
    resolve_any_path,
    set_project_root,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_sticky_context()
    yield
    reset_sticky_context()


@pytest.fixture
def fbo_project(tmp_path):
    proj = tmp_path / "PROJ"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")

    ctrl = proj / "App_Data" / "Controllers" / "Dir"
    ctrl.mkdir(parents=True, exist_ok=True)
    xml = ctrl / "SOTran.xml"
    xml.write_text("<dir/>", encoding="utf-8")

    cs = proj / "ClientScript"
    cs.mkdir(parents=True, exist_ok=True)
    js = cs / "jAjax.js"
    js.write_text("var a = 1;", encoding="utf-8")

    return proj


def test_resolve_abs_file(fbo_project):
    xml = fbo_project / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"
    res = resolve_any_path(str(xml))
    assert res.ok is True
    assert res.kind == "file"
    assert res.resolved_via == "absolute"
    assert res.project_root is not None
    assert Path(res.project_root).resolve() == fbo_project.resolve()


def test_resolve_abs_dir(fbo_project):
    cs = fbo_project / "ClientScript"
    res = resolve_any_path(str(cs))
    assert res.ok is True
    assert res.kind == "dir"


def test_abs_not_found(fbo_project):
    res = resolve_any_path(str(fbo_project / "ClientScriptt"))
    assert res.ok is False
    assert res.error["error_code"] == "path_not_found"
    assert res.error["tried"]
    assert "hint" in res.error  # gần giống ClientScript


def test_relative_no_context():
    res = resolve_any_path("Dir/SOTran.xml")
    assert res.ok is False
    assert res.error["error_code"] == "no_project_context"


def test_relative_via_reference_file(fbo_project):
    xml = fbo_project / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"
    res = resolve_any_path("Dir/SOTran.xml", reference_file=str(xml))
    assert res.ok is True
    assert res.kind == "file"
    assert Path(res.abs_path).resolve() == xml.resolve()


def test_relative_via_sticky(fbo_project):
    # set sticky bằng 1 call abs
    xml = fbo_project / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"
    assert resolve_any_path(str(xml)).ok is True

    res = resolve_any_path("ClientScript/jAjax.js")
    assert res.ok is True
    assert res.resolved_via == "sticky_context"
    assert res.abs_path.endswith("jAjax.js")

    res2 = resolve_any_path("ClientScript")
    assert res2.ok is True
    assert res2.kind == "dir"


def test_relative_prefers_controllers(fbo_project):
    """'Dir/SOTran.xml' khớp Controllers trước project_root."""
    xml = fbo_project / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"
    resolve_any_path(str(xml))
    res = resolve_any_path("Dir/SOTran.xml")
    assert res.ok is True
    assert Path(res.abs_path).resolve() == xml.resolve()


def test_relative_not_found_lists_known(fbo_project):
    xml = fbo_project / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"
    resolve_any_path(str(xml))
    res = resolve_any_path("NoSuch/thing.xyz")
    assert res.ok is False
    assert res.error["error_code"] == "path_not_found"
    assert res.error["known_projects"]
    assert len(res.error["tried"]) >= 2  # Controllers + project_root


def test_sticky_lru_multi_project(tmp_path):
    for name in ("PA", "PB"):
        proj = tmp_path / name
        (proj / "ClientScript").mkdir(parents=True)
        (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
        (proj / "ClientScript" / "lib.js").write_text(f"// {name}", encoding="utf-8")

    pa = tmp_path / "PA"
    pb = tmp_path / "PB"
    resolve_any_path(str(pa / "ClientScript"))
    resolve_any_path(str(pb / "ClientScript"))

    assert known_projects()[0].endswith("PB")

    # reference_file override -> PA dù resolve sau
    res = resolve_any_path("ClientScript/lib.js", reference_file=str(pa / "ClientScript" / "lib.js"))
    assert res.ok is True
    assert "\\PA\\" in res.abs_path or "/PA/" in res.abs_path


def test_set_project_root_dedup(tmp_path):
    for name in ("X", "Y"):
        proj = tmp_path / name
        proj.mkdir(parents=True, exist_ok=True)
        (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
    set_project_root(str(tmp_path / "X"))
    set_project_root(str(tmp_path / "Y"))
    set_project_root(str(tmp_path / "X"))
    projs = known_projects()
    assert len(projs) == 2
    assert projs[0].endswith("X")
