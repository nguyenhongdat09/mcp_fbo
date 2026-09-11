import pytest
import os
import shutil
from pathlib import Path

from compare_things.service import compare_things
from compare_things.xml_compare import scan_xml_seed_candidates, compare_xml
from compare_things.folder_compare import compare_folders


@pytest.fixture
def temp_xml_env(tmp_path):
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    
    src_ctrl = src / "App_Data" / "Controllers"
    tgt_ctrl = tgt / "App_Data" / "Controllers"
    
    (src_ctrl / "Include" / "XML").mkdir(parents=True, exist_ok=True)
    (tgt_ctrl / "Include" / "XML").mkdir(parents=True, exist_ok=True)
    (src_ctrl / "Dir").mkdir(parents=True, exist_ok=True)
    (tgt_ctrl / "Dir").mkdir(parents=True, exist_ok=True)
    
    # Source has APVHistoryFlowToolbar.xml
    (src_ctrl / "Include" / "XML" / "APVHistoryFlowToolbar.xml").write_text("<root>src</root>", encoding="utf-8")
    # Target missing APVHistoryFlowToolbar.xml
    
    # Both have APVFlowOther.xml
    (src_ctrl / "Include" / "XML" / "APVFlowOther.xml").write_text("<root>common</root>", encoding="utf-8")
    (tgt_ctrl / "Include" / "XML" / "APVFlowOther.xml").write_text("<root>common</root>", encoding="utf-8")
    
    # Target has an extra file
    (tgt_ctrl / "Dir" / "FlowTargetOnly.xml").write_text("<root>target</root>", encoding="utf-8")
    
    # Encrypted .f file (must be ignored)
    (src_ctrl / "Include" / "XML" / "APVHistoryFlowEncrypted.f").write_text("encrypted", encoding="utf-8")
    (tgt_ctrl / "Include" / "XML" / "APVHistoryFlowEncrypted.f").write_text("encrypted", encoding="utf-8")
    
    # Irrelevant file
    (src_ctrl / "Dir" / "Customer.xml").write_text("<root>cust</root>", encoding="utf-8")
    (tgt_ctrl / "Dir" / "Customer.xml").write_text("<root>cust</root>", encoding="utf-8")
    
    return src, tgt


def test_scan_xml_seed_candidates(temp_xml_env):
    src, tgt = temp_xml_env
    src_ctrl = src / "App_Data" / "Controllers"
    tgt_ctrl = tgt / "App_Data" / "Controllers"
    
    candidates, total_hits, truncated = scan_xml_seed_candidates(
        controllers_src=src_ctrl,
        controllers_tgt=tgt_ctrl,
        seed="Flow",
        max_objects=50,
    )
    
    assert not truncated
    assert total_hits == 3
    # Sorted
    assert "Include/XML/APVFlowOther.xml" in candidates
    assert "Include/XML/APVHistoryFlowToolbar.xml" in candidates
    assert "Dir/FlowTargetOnly.xml" in candidates
    # .f excluded
    assert not any(c.endswith(".f") for c in candidates)
    # Customer.xml not matching
    assert "Dir/Customer.xml" not in candidates


def test_compare_xml_with_seed(temp_xml_env):
    src, tgt = temp_xml_env
    
    res = compare_things(
        kind="xml",
        project_source=str(src),
        project_target=str(tgt),
        seed="APVHistoryFlow",
    )
    
    assert res["success"] is True
    assert res["seed"] == "APVHistoryFlow"
    assert res["summary"]["seed_hits"] == 1
    assert "Include/XML/APVHistoryFlowToolbar.xml" in res["summary"]["missing_on_target"]
    assert len(res["summary"]["missing_on_target"]) == 1
    assert "Tìm thấy 1 file XML từ seed 'APVHistoryFlow'" in res["message"]


def test_compare_xml_seed_no_match(temp_xml_env):
    src, tgt = temp_xml_env
    
    res = compare_things(
        kind="xml",
        project_source=str(src),
        project_target=str(tgt),
        seed="NonExistentKeywordXYZ",
    )
    
    assert res["success"] is False
    assert res["error_code"] == "no_matching_objects"
    assert "Không tìm thấy file XML nào khớp với seed" in res["message"]


def test_compare_xml_seed_and_object_union(temp_xml_env):
    src, tgt = temp_xml_env
    
    res = compare_things(
        kind="xml",
        project_source=str(src),
        project_target=str(tgt),
        object="Dir/Customer.xml",
        seed="APVHistoryFlow",
    )
    
    assert res["success"] is True
    assert "Dir/Customer.xml" in res["summary"]["identical"]
    assert "Include/XML/APVHistoryFlowToolbar.xml" in res["summary"]["missing_on_target"]


@pytest.fixture
def temp_folder_env(tmp_path):
    fa = tmp_path / "folder_a"
    fb = tmp_path / "folder_b"
    fa.mkdir()
    fb.mkdir()
    return fa, fb


def test_compare_folder_with_seed_filter(temp_folder_env):
    fa, fb = temp_folder_env
    
    (fa / "poctpo1.aspx").write_text("content 1", encoding="utf-8")
    (fb / "poctpo1.aspx").write_text("content 1", encoding="utf-8")
    
    (fa / "poctpo2.aspx").write_text("content 2", encoding="utf-8")
    (fb / "poctpo2.aspx").write_text("content 2", encoding="utf-8")
    
    (fa / "other_report.aspx").write_text("other", encoding="utf-8")
    (fb / "other_report.aspx").write_text("other", encoding="utf-8")
    
    res = compare_things(
        kind="folder",
        folder_a=str(fa),
        folder_b=str(fb),
        seed="poctpo",
        detail=False,
        meta_tolerance_seconds=3600,
    )
    
    assert res["success"] is True
    assert res["seed"] == "poctpo"
    assert res["summary"]["identical_meta_count"] == 2
    # other_report.aspx should be excluded by seed
    assert "other_report.aspx" not in res["summary"]["different_meta"]
    assert "other_report.aspx" not in res["summary"]["different_content"]


def test_folder_diff_reason_bom(temp_folder_env):
    fa, fb = temp_folder_env
    
    # Same normalized text, but A has UTF-8 BOM and B does not
    text = "Line 1\r\nLine 2\r\n"
    (fa / "test_bom.aspx").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    (fb / "test_bom.aspx").write_bytes(text.encode("utf-8"))
    
    res = compare_things(
        kind="folder",
        folder_a=str(fa),
        folder_b=str(fb),
        compare_content=True,
        detail=True,
    )
    
    assert res["success"] is True
    assert len(res["summary"]["different_content"]) == 0
    assert "test_bom.aspx" in res["summary"]["different_meta"]
    
    item = next(it for it in res["compared"] if it["relative_path"] == "test_bom.aspx")
    assert item["status"] == "different_meta"
    assert item["diff_reason"] == "bom"
    assert item["next_actions"] == ["ignore_normalized_bytes_diff"]


def test_folder_diff_reason_line_ending(temp_folder_env):
    fa, fb = temp_folder_env
    
    # Same lines, but CRLF vs LF
    (fa / "test_crlf.txt").write_bytes(b"Line 1\r\nLine 2\r\n")
    (fb / "test_crlf.txt").write_bytes(b"Line 1\nLine 2\n")
    
    res = compare_things(
        kind="folder",
        folder_a=str(fa),
        folder_b=str(fb),
        compare_content=True,
        detail=True,
    )
    
    assert res["success"] is True
    assert len(res["summary"]["different_content"]) == 0
    assert "test_crlf.txt" in res["summary"]["different_meta"]
    
    item = next(it for it in res["compared"] if it["relative_path"] == "test_crlf.txt")
    assert item["status"] == "different_meta"
    assert item["diff_reason"] == "line_ending"
    assert item["next_actions"] == ["ignore_normalized_bytes_diff"]


def test_folder_diff_reason_text_lines(temp_folder_env):
    fa, fb = temp_folder_env
    
    # Truly different content
    (fa / "diff.txt").write_text("Line A\nLine B\n", encoding="utf-8")
    (fb / "diff.txt").write_text("Line A\nLine C\n", encoding="utf-8")
    
    res = compare_things(
        kind="folder",
        folder_a=str(fa),
        folder_b=str(fb),
        compare_content=True,
        detail=True,
    )
    
    assert res["success"] is True
    assert "diff.txt" in res["summary"]["different_content"]
    
    item = next(it for it in res["compared"] if it["relative_path"] == "diff.txt")
    assert item["status"] == "different_content"
    assert item["diff_reason"] == "text_lines"
    assert item["next_actions"] == ["review_hunks"]
    assert item["content"]["hunk_count"] >= 1


def test_folder_diff_reason_binary(temp_folder_env):
    fa, fb = temp_folder_env
    
    # Binary difference
    (fa / "test.bin").write_bytes(b"\x00\x01\x02\x03")
    (fb / "test.bin").write_bytes(b"\x00\x01\x02\x04")
    
    res = compare_things(
        kind="folder",
        folder_a=str(fa),
        folder_b=str(fb),
        compare_content=True,
        detail=True,
    )
    
    assert res["success"] is True
    assert "test.bin" in res["summary"]["different_content"]
    
    item = next(it for it in res["compared"] if it["relative_path"] == "test.bin")
    assert item["status"] == "different_content"
    assert item["diff_reason"] == "binary"
    assert item["next_actions"] == ["investigate_version_dll"]
