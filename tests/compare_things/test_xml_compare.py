"""Unit tests for kind=xml comparison in compare_things."""

from pathlib import Path
import pytest
from compare_things import compare_things


@pytest.fixture
def mock_projects(tmp_path: Path):
    src_root = tmp_path / "SourceProj"
    tgt_root = tmp_path / "TargetProj"

    src_ctrl = src_root / "App_Data" / "Controllers" / "Dir"
    tgt_ctrl = tgt_root / "App_Data" / "Controllers" / "Dir"

    src_ctrl.mkdir(parents=True)
    tgt_ctrl.mkdir(parents=True)

    (src_root / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (tgt_root / "Web.config").write_text("<configuration/>", encoding="utf-8")

    return src_root, tgt_root


def test_tc_xml_01_identical(mock_projects):
    src_root, tgt_root = mock_projects
    fa = src_root / "App_Data" / "Controllers" / "Dir" / "Same.xml"
    fb = tgt_root / "App_Data" / "Controllers" / "Dir" / "Same.xml"

    xml_content = "<dir><title>Test</title></dir>"
    fa.write_text(xml_content, encoding="utf-8")
    fb.write_text(xml_content, encoding="utf-8")

    res = compare_things(
        kind="xml",
        project_source=str(src_root),
        project_target=str(tgt_root),
        object="Dir/Same.xml",
    )
    assert res["success"] is True
    assert "Dir/Same.xml" in res["summary"]["identical"]
    item = res["compared"][0]
    assert item["status"] == "identical"
    assert item["relative_path"] == "Dir/Same.xml"


def test_tc_xml_02_different(mock_projects):
    src_root, tgt_root = mock_projects
    fa = src_root / "App_Data" / "Controllers" / "Dir" / "Diff.xml"
    fb = tgt_root / "App_Data" / "Controllers" / "Dir" / "Diff.xml"

    fa.write_text("<dir>\n  <field name=\"a\"/>\n</dir>", encoding="utf-8")
    fb.write_text("<dir>\n  <field name=\"b\"/>\n</dir>", encoding="utf-8")

    res = compare_things(
        kind="xml",
        project_source=str(src_root),
        project_target=str(tgt_root),
        object="Dir/Diff.xml",
    )
    assert res["success"] is True
    assert "Dir/Diff.xml" in res["summary"]["different"]
    item = res["compared"][0]
    assert item["status"] == "different"
    assert item["content"]["hunk_count"] >= 1
    assert "review_hunks" in res["next_actions"]


def test_tc_xml_03_missing_on_target(mock_projects):
    src_root, tgt_root = mock_projects
    fa = src_root / "App_Data" / "Controllers" / "Dir" / "OnlySrc.xml"
    fa.write_text("<dir/>", encoding="utf-8")

    res = compare_things(
        kind="xml",
        project_source=str(src_root),
        project_target=str(tgt_root),
        object="Dir/OnlySrc.xml",
    )
    assert res["success"] is True
    assert "Dir/OnlySrc.xml" in res["summary"]["missing_on_target"]
    assert "copy_missing_to_target" in res["next_actions"]


def test_tc_xml_04_path_traversal(mock_projects):
    src_root, tgt_root = mock_projects
    res = compare_things(
        kind="xml",
        project_source=str(src_root),
        project_target=str(tgt_root),
        object="Dir/../../Secret.xml",
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_object"
    assert "traversal" in res["error"].lower()
