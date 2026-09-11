"""Unit tests for folder comparison summary vs detail mode.

Specification: docs/doc/doc_fix/FIX-compare_things-folder-summary-vs-detail.md
1) detail=False (default): compared == []; summary lists are full; summary.truncated_compared == False.
2) detail=True: compared is populated per-file.
3) detail=True + max_objects=2: len(compared) == 2, truncated_compared == True, summary lists still full.
4) detail=True + detail_status="different_content": all compared items have status == "different_content".
5) Binary DLL mock: next_actions contains "investigate_version_dll" and NEVER "review_hunks".
"""

from pathlib import Path
import pytest
from compare_things import compare_things


@pytest.fixture
def mock_folder_pair(tmp_path: Path):
    """
    Creates a mock folder pair:
    - 5 files missing on B (only in A): miss_b_1.txt .. miss_b_5.txt
    - 2 files missing on A (only in B): miss_a_1.txt, miss_a_2.txt
    - 3 files with different content: diff_c_1.txt, diff_c_2.txt, diff_dll.dll (binary)
    - 2 files with different metadata (different size): diff_m_1.txt, diff_m_2.txt
    - 2 files identical: ident_1.txt, ident_2.txt
    """
    dir_a = tmp_path / "folder_a"
    dir_b = tmp_path / "folder_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # 5 missing on B
    for i in range(1, 6):
        (dir_a / f"miss_b_{i}.txt").write_text(f"a_{i}", encoding="utf-8")

    # 2 missing on A
    for i in range(1, 3):
        (dir_b / f"miss_a_{i}.txt").write_text(f"b_{i}", encoding="utf-8")

    # 3 different content
    (dir_a / "diff_c_1.txt").write_text("aaa1", encoding="utf-8")
    (dir_b / "diff_c_1.txt").write_text("bbb1", encoding="utf-8")
    (dir_a / "diff_c_2.txt").write_text("aaa2", encoding="utf-8")
    (dir_b / "diff_c_2.txt").write_text("bbb2", encoding="utf-8")
    (dir_a / "diff_dll.dll").write_bytes(b"\x00\x01\x02dll_a")
    (dir_b / "diff_dll.dll").write_bytes(b"\x00\x01\x02dll_b")

    import os
    import time
    now = time.time()

    # 2 different meta (same content, different mtime)
    (dir_a / "diff_m_1.txt").write_text("same_content_1", encoding="utf-8")
    (dir_b / "diff_m_1.txt").write_text("same_content_1", encoding="utf-8")
    os.utime(dir_a / "diff_m_1.txt", (now - 500, now - 500))
    os.utime(dir_b / "diff_m_1.txt", (now, now))

    (dir_a / "diff_m_2.txt").write_text("same_content_2", encoding="utf-8")
    (dir_b / "diff_m_2.txt").write_text("same_content_2", encoding="utf-8")
    os.utime(dir_a / "diff_m_2.txt", (now - 500, now - 500))
    os.utime(dir_b / "diff_m_2.txt", (now, now))

    # 2 identical (same content, same mtime)
    (dir_a / "ident_1.txt").write_text("same1", encoding="utf-8")
    (dir_b / "ident_1.txt").write_text("same1", encoding="utf-8")
    os.utime(dir_a / "ident_1.txt", (now, now))
    os.utime(dir_b / "ident_1.txt", (now, now))

    (dir_a / "ident_2.txt").write_text("same2", encoding="utf-8")
    (dir_b / "ident_2.txt").write_text("same2", encoding="utf-8")
    os.utime(dir_a / "ident_2.txt", (now, now))
    os.utime(dir_b / "ident_2.txt", (now, now))

    return dir_a, dir_b


def test_folder_default_detail_false(mock_folder_pair):
    """Test 1: Default detail=False -> compared is empty list, summary contains full inventory."""
    dir_a, dir_b = mock_folder_pair
    res = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
        meta_tolerance_seconds=10,
    )

    assert res["success"] is True
    assert res["detail"] is False
    assert res["compared"] == []

    summary = res["summary"]
    assert len(summary["missing_on_b"]) == 5
    assert len(summary["missing_on_a"]) == 2
    assert len(summary["different_content"]) == 3
    assert len(summary["different_meta"]) == 2
    assert summary["identical_meta_count"] == 2
    assert summary["truncated"] is False
    assert summary["truncated_compared"] is False
    assert summary["truncated_summary_names"] is False

    # Message must NOT contain "hunks ranges"
    assert "hunks ranges" not in res["message"]
    assert "hunks" not in res["message"]
    assert "khác nội dung: 3 file," in res["message"]


def test_folder_detail_true_full(mock_folder_pair):
    """Test 2: detail=True -> compared is populated per-file."""
    dir_a, dir_b = mock_folder_pair
    res = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
        meta_tolerance_seconds=10,
        detail=True,
    )

    assert res["success"] is True
    assert res["detail"] is True
    # 5 missing_b + 2 missing_a + 3 different_content + 2 different_meta = 12 items
    assert len(res["compared"]) == 12
    assert res["summary"]["truncated_compared"] is False


def test_folder_detail_true_max_objects_truncation(mock_folder_pair):
    """Test 3: detail=True + max_objects=2 -> compared is sliced, summary names remain full."""
    dir_a, dir_b = mock_folder_pair
    res = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
        meta_tolerance_seconds=10,
        detail=True,
        max_objects=2,
    )

    assert res["success"] is True
    assert res["detail"] is True
    assert len(res["compared"]) == 2
    assert res["summary"]["truncated_compared"] is True
    assert res["summary"]["truncated"] is True
    assert res["summary"]["truncated_summary_names"] is False

    # Summary lists must NOT be sliced by max_objects
    assert len(res["summary"]["missing_on_b"]) == 5
    assert len(res["summary"]["missing_on_a"]) == 2
    assert len(res["summary"]["different_content"]) == 3


def test_folder_detail_status_filter(mock_folder_pair):
    """Test 4: detail=True + detail_status='different_content' -> compared only contains matching status."""
    dir_a, dir_b = mock_folder_pair
    res = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
        detail=True,
        detail_status="different_content",
    )

    assert res["success"] is True
    assert res["detail"] is True
    assert len(res["compared"]) == 3
    for item in res["compared"]:
        assert item["status"] == "different_content"

    # Multi-status CSV filter
    res_multi = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
        detail=True,
        detail_status="different_content, missing_on_b",
    )
    assert len(res_multi["compared"]) == 8  # 3 different_content + 5 missing_on_b
    for item in res_multi["compared"]:
        assert item["status"] in ("different_content", "missing_on_b")


def test_folder_binary_dll_next_actions(mock_folder_pair):
    """Test 5: Binary DLL in compared does NOT have review_hunks, has investigate_version_dll."""
    dir_a, dir_b = mock_folder_pair
    res = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
        detail=True,
    )

    dll_item = next(x for x in res["compared"] if x["relative_path"] == "diff_dll.dll")
    assert dll_item["status"] == "different_content"
    assert "review_hunks" not in dll_item["next_actions"]
    assert "investigate_version_dll" in dll_item["next_actions"]

    # Text diff item DOES have review_hunks
    txt_item = next(x for x in res["compared"] if x["relative_path"] == "diff_c_1.txt")
    assert "review_hunks" in txt_item["next_actions"]

    # Top-level actions contain investigate_version_dll
    assert "investigate_version_dll" in res["next_actions"]
