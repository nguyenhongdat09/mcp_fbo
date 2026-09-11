"""Unit tests for kind=folder in compare_things."""

import os
from pathlib import Path
import time
import pytest
from compare_things import compare_things


def test_tc_folder_01_missing_files(tmp_path: Path):
    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()

    (dir_a / "only_a.txt").write_text("hello", encoding="utf-8")
    (dir_b / "only_b.txt").write_text("world", encoding="utf-8")
    (dir_a / "common.txt").write_text("common", encoding="utf-8")
    (dir_b / "common.txt").write_text("common", encoding="utf-8")

    res = compare_things(kind="folder", folder_a=str(dir_a), folder_b=str(dir_b))
    assert res["success"] is True
    assert "only_a.txt" in res["summary"]["missing_on_b"]
    assert "only_b.txt" in res["summary"]["missing_on_a"]
    assert "copy_missing_to_b" in res["next_actions"]
    assert "copy_missing_to_a" in res["next_actions"]


def test_tc_folder_02_different_size(tmp_path: Path):
    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()

    (dir_a / "file.txt").write_text("short", encoding="utf-8")
    (dir_b / "file.txt").write_text("much longer content", encoding="utf-8")

    res = compare_things(kind="folder", folder_a=str(dir_a), folder_b=str(dir_b), detail=True)
    assert res["success"] is True
    assert "file.txt" in res["summary"]["different_meta"]
    item = next(x for x in res["compared"] if x["relative_path"] == "file.txt")
    assert "size" in item["meta_diff"]


def test_tc_folder_03_different_mtime(tmp_path: Path):
    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()

    fa = dir_a / "time.txt"
    fb = dir_b / "time.txt"
    fa.write_text("same", encoding="utf-8")
    fb.write_text("same", encoding="utf-8")

    now = time.time()
    os.utime(fa, (now - 100, now - 100))
    os.utime(fb, (now, now))

    # Tolerance 0 -> different
    res0 = compare_things(kind="folder", folder_a=str(dir_a), folder_b=str(dir_b), meta_tolerance_seconds=0)
    assert "time.txt" in res0["summary"]["different_meta"]

    # Tolerance 200 -> identical
    res200 = compare_things(kind="folder", folder_a=str(dir_a), folder_b=str(dir_b), meta_tolerance_seconds=200)
    assert res200["summary"]["identical_meta_count"] == 1
    assert "time.txt" not in res200["summary"]["different_meta"]


def test_tc_folder_04_omitted_identical_count_and_truncation(tmp_path: Path):
    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()

    for i in range(20):
        (dir_a / f"file_{i}.txt").write_text("content", encoding="utf-8")
        (dir_b / f"file_{i}.txt").write_text("content", encoding="utf-8")

    (dir_a / "extra.txt").write_text("extra", encoding="utf-8")

    res = compare_things(kind="folder", folder_a=str(dir_a), folder_b=str(dir_b), max_objects=5, meta_tolerance_seconds=3600)
    assert res["success"] is True
    assert res["summary"]["identical_meta_count"] == 20
    assert "extra.txt" in res["summary"]["missing_on_b"]


def test_tc_folder_05_include_glob(tmp_path: Path):
    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()

    (dir_a / "app.dll").write_text("dll", encoding="utf-8")
    (dir_a / "notes.txt").write_text("txt", encoding="utf-8")
    (dir_b / "app.dll").write_text("dll", encoding="utf-8")
    (dir_b / "notes.txt").write_text("txt", encoding="utf-8")

    res = compare_things(kind="folder", folder_a=str(dir_a), folder_b=str(dir_b), include_glob="*.dll")
    assert res["success"] is True
    assert res["summary"]["files_a"] == 1
    assert res["summary"]["files_b"] == 1


def test_tc_folder_06_compare_content_with_hunks(tmp_path: Path):
    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()

    # Same size, different text
    (dir_a / "diff.txt").write_text("abc1", encoding="utf-8")
    (dir_b / "diff.txt").write_text("xyz1", encoding="utf-8")

    res = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
        detail=True,
    )
    assert res["success"] is True
    assert "diff.txt" in res["summary"]["different_content"]
    item = next(x for x in res["compared"] if x["relative_path"] == "diff.txt")
    assert item["status"] == "different_content"
    assert "content" in item
    assert item["content"]["hunk_count"] >= 1
