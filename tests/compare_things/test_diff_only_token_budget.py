"""Tests for diff-only-no-preview and token budget contract in compare_things."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from compare_things import compare_things
from compare_things.formatter import format_compare_result


def test_tc_diff_only_01_summary_no_preview_and_capped_hunks(tmp_path):
    """mode=summary: hunks <= max_hunks_summary (5), no preview, no unified_diff, hunk_count preserved."""
    # Create 2 files with 20 different regions
    lines_a = []
    lines_b = []
    for i in range(20):
        for c in range(10):
            lines_a.append(f"common_{i}_{c}")
            lines_b.append(f"common_{i}_{c}")
        lines_a.append(f"old_line_{i}")
        lines_b.append(f"new_line_{i}")


    fa = tmp_path / "a.txt"
    fb = tmp_path / "b.txt"
    fa.write_text("\n".join(lines_a), encoding="utf-8")
    fb.write_text("\n".join(lines_b), encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb), mode="summary")
    assert res["success"] is True
    assert res["role_a"] == "reference_clone_from"
    assert res["role_b"] == "editing"
    assert "So file B" in res["message"]
    assert "nguồn clone" in res["message"]

    content = res["compared"][0]["content"]
    assert content["hunk_count"] >= 20
    # Capped at default max_hunks_summary = 5
    assert len(content["hunks"]) == 5
    assert content["hunks_omitted"] == content["hunk_count"] - 5
    assert content["diff_truncated"] is True
    assert "unified_diff" not in content or content["unified_diff"] == ""

    for h in content["hunks"]:
        assert "preview" not in h or h["preview"] == []
        assert "a_line_start" in h
        assert "a_line_end" in h
        assert "b_line_start" in h
        assert "b_line_end" in h
        assert "lines_added" in h
        assert "lines_removed" in h


def test_tc_diff_only_02_mode_hunks_flags(tmp_path):
    """mode=hunks: no preview and no unified_diff by default; enabled only with flags."""
    fa = tmp_path / "a.txt"
    fb = tmp_path / "b.txt"
    fa.write_text("line1\nold2\nline3\n", encoding="utf-8")
    fb.write_text("line1\nnew2\nline3\n", encoding="utf-8")

    # Default mode=hunks
    res_default = compare_things(kind="file", file_a=str(fa), file_b=str(fb), mode="hunks")
    hunk_def = res_default["compared"][0]["content"]["hunks"][0]
    assert "preview" not in hunk_def or hunk_def["preview"] == []
    assert "unified_diff" not in res_default["compared"][0]["content"] or res_default["compared"][0]["content"]["unified_diff"] == ""

    # mode=hunks with include_unified_diff=True
    res_udiff = compare_things(kind="file", file_a=str(fa), file_b=str(fb), mode="hunks", include_unified_diff=True)
    assert res_udiff["compared"][0]["content"]["unified_diff"] != ""
    assert "old2" in res_udiff["compared"][0]["content"]["unified_diff"]

    # mode=hunks with include_text_snippets=True
    res_snip = compare_things(kind="file", file_a=str(fa), file_b=str(fb), mode="hunks", include_text_snippets=True)
    hunk_snip = res_snip["compared"][0]["content"]["hunks"][0]
    assert "preview" in hunk_snip and len(hunk_snip["preview"]) > 0


def test_tc_diff_only_03_xml_roles_and_message(tmp_path):
    """kind=xml: role_source/role_target and message reflect editing vs clone source."""
    src_dir = tmp_path / "SourceFAH" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "TargetAIH" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    (src_dir / "Customer.xml").write_text("<dir><field name=\"a\"/></dir>", encoding="utf-8")
    (tgt_dir / "Customer.xml").write_text("<dir><field name=\"b\"/></dir>", encoding="utf-8")

    res = compare_things(
        kind="xml",
        project_source=str(tmp_path / "SourceFAH"),
        project_target=str(tmp_path / "TargetAIH"),
        object="Dir/Customer.xml",
    )
    assert res["success"] is True
    assert res["role_source"] == "reference_clone_from"
    assert res["role_target"] == "editing"
    assert "TargetAIH (đang sửa)" in res["message"]
    assert "SourceFAH (nguồn clone)" in res["message"]
    assert "khác nhau (xem hunks ranges, không dán code)" in res["message"]


def test_tc_diff_only_04_sql_diff_ranges_and_signals_only():
    """kind=sql: different definitions output line ranges and signals, NO raw SQL code in hunks."""
    with patch("compare_things.sql_compare.resolve_project_dbs") as mock_dbs, \
         patch("compare_things.sql_compare.check_object_exists") as mock_exists, \
         patch("compare_things.sql_compare.check_is_encrypted") as mock_enc, \
         patch("compare_things.sql_compare.fetch_routine_definition") as mock_def:

        mock_dbs.return_value = {
            "app": {"server": "test", "database": "app_db"},
            "sys": {"server": "test", "database": "sys_db"},
        }
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_enc.return_value = False

        def get_def(proj, name, schema, db_type):
            if proj == "E:\\FAHASA":
                return "CREATE PROC dbo.ProcDiff AS\nSELECT 1\nSELECT * FROM vdmduyetuq"
            return "CREATE PROC dbo.ProcDiff AS\nSELECT 1\nSELECT * FROM dmduyet"

        mock_def.side_effect = get_def

        res = compare_things(
            kind="sql",
            project_source="E:\\FAHASA",
            project_target="E:\\AIH",
            object="dbo.ProcDiff",
        )
        assert res["success"] is True
        assert res["role_source"] == "reference_clone_from"
        assert res["role_target"] == "editing"
        assert "AIH (đang sửa)" in res["message"]
        assert "FAHASA (nguồn clone)" in res["message"]

        item = res["compared"][0]
        assert item["status"] == "different"
        assert "signals" in item
        content = item["content"]
        hunk = content["hunks"][0]
        assert "source_line_start" in hunk
        assert "source_line_end" in hunk
        assert "target_line_start" in hunk
        assert "target_line_end" in hunk
        # NO SQL code lines in preview!
        assert "preview" not in hunk or hunk["preview"] == []


def test_tc_diff_only_05_customer_xml_flat_summary_token_budget(tmp_path):
    """Simulate Customer.xml with 30 hunks in flat view: JSON size is <= 12,000 chars (<= 3k tokens)."""
    src_dir = tmp_path / "SourceFAH" / "App_Data" / "Controllers" / "Dir"
    src_dir.mkdir(parents=True)
    tgt_dir = tmp_path / "TargetAIH" / "App_Data" / "Controllers" / "Dir"
    tgt_dir.mkdir(parents=True)

    (src_dir / "Customer.xml").write_text("<dir>&dummy;</dir>", encoding="utf-8")
    (tgt_dir / "Customer.xml").write_text("<dir>&dummy;</dir>", encoding="utf-8")

    # Simulate 30 distinct hunk changes in flat expanded text
    lines_src = []
    lines_tgt = []
    for i in range(30):
        for c in range(10):
            lines_src.append(f"<field name=\"common_{i}_{c}\"/>")
            lines_tgt.append(f"<field name=\"common_{i}_{c}\"/>")
        lines_src.append(f"<field name=\"src_only_{i}\" length=\"100\"/>")
        lines_tgt.append(f"<field name=\"tgt_only_{i}\" length=\"50\"/>")


    with patch("compare_things.xml_compare.flat_xml") as mock_flat:
        mock_flat.side_effect = ["\n".join(lines_src), "\n".join(lines_tgt)]

        res = compare_things(
            kind="xml",
            project_source=str(tmp_path / "SourceFAH"),
            project_target=str(tmp_path / "TargetAIH"),
            object="Dir/Customer.xml",
            xml_view="flat",
            mode="summary",
        )

        assert res["success"] is True
        formatted = format_compare_result(res)
        chars = len(formatted)
        # Verify JSON length is comfortably under 12,000 characters (<= 3k tokens)
        assert chars <= 12000, f"Expected chars <= 12000, got {chars}"

        item = res["compared"][0]
        content = item["content"]
        assert content["hunk_count"] >= 30
        assert len(content["hunks"]) == 5
        assert content["hunks_omitted"] == content["hunk_count"] - 5
        assert content["diff_truncated"] is True
        for h in content["hunks"]:
            assert "preview" not in h or h["preview"] == []
