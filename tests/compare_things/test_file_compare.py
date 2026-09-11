"""Unit tests for kind=file comparison in compare_things."""

import os
from pathlib import Path
import pytest
from compare_things import compare_things


def test_tc_file_01_identical_lf(tmp_path: Path):
    fa = tmp_path / "a.txt"
    fb = tmp_path / "b.txt"
    content = "line1\nline2\nline3\n"
    fa.write_bytes(content.encode("utf-8"))
    fb.write_bytes(content.encode("utf-8"))

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    assert res["summary"]["identical_content"] is True
    assert res["summary"]["only_line_ending_diff"] is False
    assert res["summary"]["status"] == "identical"
    assert len(res["compared"]) == 1
    item = res["compared"][0]
    assert item["content"]["hunk_count"] == 0
    assert "noop" in item["next_actions"]


def test_tc_file_02_crlf_vs_lf(tmp_path: Path):
    fa = tmp_path / "a_crlf.txt"
    fb = tmp_path / "b_lf.txt"
    fa.write_bytes(b"line1\r\nline2\r\n")
    fb.write_bytes(b"line1\nline2\n")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb), ignore_line_endings=True)
    assert res["success"] is True
    assert res["summary"]["identical_content"] is True
    assert res["summary"]["only_line_ending_diff"] is True
    assert res["summary"]["status"] == "identical"
    assert "ignore_line_ending_only" in res["next_actions"]
    assert res["compared"][0]["content"]["hunk_count"] == 0


def test_tc_file_03_different_content_hunks(tmp_path: Path):
    fa = tmp_path / "a.txt"
    fb = tmp_path / "b.txt"
    fa.write_text("line1\nline2_old\nline3\n", encoding="utf-8")
    fb.write_text("line1\nline2_new\nline3\n", encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    assert res["summary"]["identical_content"] is False
    assert res["summary"]["status"] == "different"
    assert "review_hunks" in res["next_actions"]

    item = res["compared"][0]
    hunks = item["content"]["hunks"]
    assert len(hunks) >= 1
    hunk = hunks[0]
    assert hunk["a_line_start"] == 2
    assert hunk["b_line_start"] == 2
    # Contract: preview is omitted or empty by default in diff-only mode
    assert "preview" not in hunk or hunk["preview"] == []

    # If include_text_snippets=True, preview is included
    res_snippets = compare_things(kind="file", file_a=str(fa), file_b=str(fb), include_text_snippets=True)
    hunk_s = res_snippets["compared"][0]["content"]["hunks"][0]
    assert any("-" in p for p in hunk_s["preview"])
    assert any("+" in p for p in hunk_s["preview"])


def test_tc_file_04_ignore_line_endings_false(tmp_path: Path):

    fa = tmp_path / "a.txt"
    fb = tmp_path / "b.txt"
    fa.write_bytes(b"line1\r\nline2\r\n")
    fb.write_bytes(b"line1\nline2\n")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb), ignore_line_endings=False)
    assert res["success"] is True
    assert res["summary"]["identical_content"] is False
    assert res["summary"]["status"] == "different"
    assert res["compared"][0]["content"]["hunk_count"] >= 1


def test_tc_file_05_file_not_found():
    res = compare_things(kind="file", file_a="E:\\non_existent_file_a_xyz.txt", file_b="E:\\non_existent_file_b_xyz.txt")
    assert res["success"] is False
    assert res["error_code"] == "file_not_found"


def test_tc_file_06_binary_different(tmp_path: Path):
    fa = tmp_path / "a.bin"
    fb = tmp_path / "b.bin"
    fa.write_bytes(b"\x00\x01\x02\x03")
    fb.write_bytes(b"\x00\x01\x02\x04\x05")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    item = res["compared"][0]
    assert item["file_a"]["is_binary"] is True
    assert item["file_b"]["is_binary"] is True
    assert item["status"] == "different"
    assert "compare_binary_meta_only" in item["next_actions"]
    assert "size" in item["meta_diff"]


def test_tc_file_07_mode_hunks_unified_diff(tmp_path: Path):
    fa = tmp_path / "a.txt"
    fb = tmp_path / "b.txt"
    lines_a = [f"line {i}" for i in range(50)]
    lines_b = [f"line {i} modified" for i in range(50)]
    fa.write_text("\n".join(lines_a), encoding="utf-8")
    fb.write_text("\n".join(lines_b), encoding="utf-8")

    res = compare_things(
        kind="file",
        file_a=str(fa),
        file_b=str(fb),
        mode="hunks",
        max_diff_lines=10,
        include_unified_diff=True,
    )
    assert res["success"] is True
    item = res["compared"][0]
    assert item["content"]["diff_truncated"] is True
    assert "... [diff truncated]" in item["content"]["unified_diff"]



def test_tc_file_08_utf8_bom_vs_no_bom(tmp_path: Path):
    fa = tmp_path / "bom.txt"
    fb = tmp_path / "nobom.txt"
    content = "Hello FastBusiness"
    fa.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    fb.write_bytes(content.encode("utf-8"))

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    assert res["summary"]["identical_content"] is True
    assert res["summary"]["content_same_bytes_differ"] is True
    assert res["summary"]["only_line_ending_diff"] is False
    assert "BOM" in res["message"]


def test_tc_file_09_whitespace_ignore_diff_reason(tmp_path: Path):
    fa = tmp_path / "ws1.txt"
    fb = tmp_path / "ws2.txt"
    fa.write_text("   hello   \n", encoding="utf-8")
    fb.write_text("hello\n", encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb), ignore_whitespace=True)
    assert res["success"] is True
    assert res["summary"]["identical_content"] is True
    assert res["summary"]["content_same_bytes_differ"] is True
    assert res["summary"]["only_line_ending_diff"] is False
    assert "khoảng trắng" in res["message"]
