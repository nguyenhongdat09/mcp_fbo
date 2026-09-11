"""Unit tests for xml_view="original"|"flat" in compare_things."""

from pathlib import Path
from unittest.mock import patch
import pytest
from compare_things import compare_things


def test_tc_xml_view_01_default_original(tmp_path):
    # Source and Target have identical raw text referencing entity
    src_dir = tmp_path / "src" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "tgt" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    xml_content = '<dir>&my_entity;</dir>'
    (src_dir / "Test.xml").write_text(xml_content, encoding="utf-8")
    (tgt_dir / "Test.xml").write_text(xml_content, encoding="utf-8")

    res = compare_things(
        kind="xml",
        project_source=str(tmp_path / "src"),
        project_target=str(tmp_path / "tgt"),
        object="Dir/Test.xml",
    )
    assert res["success"] is True
    assert res["summary"]["counts"]["identical"] == 1
    assert "Dir/Test.xml" in res["summary"]["identical"]
    item = res["compared"][0]
    assert item["status"] == "identical"
    assert item["content"]["line_basis"] == "original"


def test_tc_xml_view_02_flat_view_identical(tmp_path):
    src_dir = tmp_path / "src" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "tgt" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    (src_dir / "Test.xml").write_text('<dir>&ent1;</dir>', encoding="utf-8")
    (tgt_dir / "Test.xml").write_text('<dir>&ent2;</dir>', encoding="utf-8")

    with patch("compare_things.xml_compare.flat_xml") as mock_flat:
        # Both flatten to identical expanded content
        mock_flat.return_value = "<dir><field name=\"a\"/></dir>"

        res = compare_things(
            kind="xml",
            project_source=str(tmp_path / "src"),
            project_target=str(tmp_path / "tgt"),
            object="Dir/Test.xml",
            xml_view="flat",
        )
        assert res["success"] is True
        assert res["summary"]["counts"]["identical"] == 1
        assert "Dir/Test.xml" in res["summary"]["identical"]
        item = res["compared"][0]
        assert item["status"] == "identical"
        assert item["content"]["line_basis"] == "flat"


def test_tc_xml_view_03_flat_view_different(tmp_path):
    src_dir = tmp_path / "src" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "tgt" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    (src_dir / "Test.xml").write_text('<dir>&ent1;</dir>', encoding="utf-8")
    (tgt_dir / "Test.xml").write_text('<dir>&ent1;</dir>', encoding="utf-8")

    with patch("compare_things.xml_compare.flat_xml") as mock_flat:
        mock_flat.side_effect = [
            "<dir><field name=\"a\"/></dir>",
            "<dir><field name=\"b\"/></dir>",
        ]

        res = compare_things(
            kind="xml",
            project_source=str(tmp_path / "src"),
            project_target=str(tmp_path / "tgt"),
            object="Dir/Test.xml",
            xml_view="flat",
            mode="hunks",
        )
        assert res["success"] is True
        assert res["summary"]["counts"]["different"] == 1
        assert "Dir/Test.xml" in res["summary"]["different"]
        item = res["compared"][0]
        assert item["status"] == "different"
        assert item["content"]["line_basis"] == "flat"
        assert item["content"]["hunk_count"] > 0
        assert len(item["content"]["hunks"]) > 0



def test_tc_xml_view_04_alias_raw(tmp_path):
    src_dir = tmp_path / "src" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "tgt" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    (src_dir / "Test.xml").write_text('<dir>raw</dir>', encoding="utf-8")
    (tgt_dir / "Test.xml").write_text('<dir>raw</dir>', encoding="utf-8")

    res = compare_things(
        kind="xml",
        project_source=str(tmp_path / "src"),
        project_target=str(tmp_path / "tgt"),
        object="Dir/Test.xml",
        xml_view="raw",
    )
    assert res["success"] is True
    assert res["compared"][0]["content"]["line_basis"] == "original"


def test_tc_xml_view_05_invalid_xml_view():
    res = compare_things(
        kind="xml",
        project_source="E:\\Source",
        project_target="E:\\Target",
        object="Dir/Test.xml",
        xml_view="invalid_mode",
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_xml_view"


def test_tc_xml_view_06_ignored_for_other_kinds(tmp_path):
    src = tmp_path / "src" / "test.txt"
    tgt = tmp_path / "tgt" / "test.txt"
    src.parent.mkdir(parents=True)
    tgt.parent.mkdir(parents=True)
    src.write_text("hello", encoding="utf-8")
    tgt.write_text("hello", encoding="utf-8")

    res = compare_things(
        kind="file",
        file_a=str(src),
        file_b=str(tgt),
        xml_view="flat",
    )
    assert res["success"] is True
    assert res["summary"]["status"] == "identical"
    assert res["compared"][0]["status"] == "identical"




def test_tc_xml_view_07_flat_xml_failure_no_silent_fallback(tmp_path):
    src_dir = tmp_path / "src" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "tgt" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    (src_dir / "Test.xml").write_text('<dir>&missing_ent;</dir>', encoding="utf-8")
    (tgt_dir / "Test.xml").write_text('<dir>&missing_ent;</dir>', encoding="utf-8")

    with patch("compare_things.xml_compare.flat_xml") as mock_flat:
        mock_flat.side_effect = RuntimeError("DTD entity not found")

        res = compare_things(
            kind="xml",
            project_source=str(tmp_path / "src"),
            project_target=str(tmp_path / "tgt"),
            object="Dir/Test.xml",
            xml_view="flat",
        )
        assert res["success"] is True
        item = res["compared"][0]
        assert item["status"] == "error"
        assert "retry_xml_view_original" in res["next_actions"]
        assert "DTD entity not found" in item["message"]


def test_tc_xml_missing_both(tmp_path):
    src_dir = tmp_path / "src" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "tgt" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    res = compare_things(
        kind="xml",
        project_source=str(tmp_path / "src"),
        project_target=str(tmp_path / "tgt"),
        object="Dir/NonExistent.xml",
    )
    assert res["success"] is True
    assert "Dir/NonExistent.xml" in res["summary"]["missing_both"]
    assert res["compared"][0]["status"] == "missing_both"
