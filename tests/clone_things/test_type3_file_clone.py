"""Unit tests for clone_things type=3 (file clone between projects).

Covers AC-T3-01 to AC-T3-17 from docs/doc/gemini/GEMINI-clone_things-type3-file-clone.md.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from clone_things import clone_things
from clone_things.type3_file_clone import HASH_MAX_BYTES, PRESETS


@pytest.fixture
def setup_projects(tmp_path):
    """Set up mock source and target projects without requiring Web.config."""
    src = tmp_path / "src_proj"
    tgt = tmp_path / "tgt_proj"

    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)

    # Populate source files
    (src / "bin").mkdir(parents=True, exist_ok=True)
    (src / "bin" / "fsdMail.dll").write_bytes(b"DLL_CONTENT_SRC_1")
    (src / "bin" / "callMailXS.dll").write_bytes(b"DLL_CONTENT_SRC_2")
    (src / "bin" / "clsFileUpload.dll").write_bytes(b"DLL_CONTENT_SRC_3")

    (src / "Main" / "Uploads").mkdir(parents=True, exist_ok=True)
    (src / "Main" / "Uploads" / "AjaxWeb.aspx").write_bytes(b"ASPX_CONTENT_1")
    (src / "Main" / "Uploads" / "AjaxWeb_Core.aspx").write_bytes(b"ASPX_CONTENT_2")

    (src / "ClientScript").mkdir(parents=True, exist_ok=True)
    (src / "ClientScript" / "jAjax.js").write_bytes(b"JS_CONTENT_SRC")

    # Some custom controllers
    (src / "App_Data" / "Controllers" / "Templates" / "Mail").mkdir(parents=True, exist_ok=True)
    (src / "App_Data" / "Controllers" / "Templates" / "Mail" / "foo.html").write_bytes(b"<html>mail</html>")
    (src / "App_Data" / "Controllers" / "Filter").mkdir(parents=True, exist_ok=True)
    (src / "App_Data" / "Controllers" / "Filter" / "Test.f").write_bytes(b"DENIED_F_CONTENT")

    return src, tgt


def test_ac_t3_01_dry_run_missing_target(setup_projects):
    """AC-T3-01: dry-run thiếu target → missing_on_target; disk đích không đổi."""
    src, tgt = setup_projects
    res = clone_things(
        object="bin/fsdMail.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=False,
    )
    assert res["success"] is True
    assert res["type"] == 3
    assert res["execute"] is False
    assert res["overwrite"] is False
    assert "bin/fsdMail.dll" in res["will_copy"]
    assert res["copied"] == []
    # Target disk has not changed
    assert not (tgt / "bin" / "fsdMail.dll").exists()

    planned = res["planned"]
    assert len(planned) == 1
    assert planned[0]["status"] == "missing_on_target"
    assert planned[0]["relative"] == "bin/fsdMail.dll"


def test_ac_t3_02_execute_missing_on_target(setup_projects):
    """AC-T3-02: execute=true chỉ tạo file thiếu; copied."""
    src, tgt = setup_projects
    res = clone_things(
        object="bin/fsdMail.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=True,
    )
    assert res["success"] is True
    assert res["execute"] is True
    assert "bin/fsdMail.dll" in res["copied"]
    assert (tgt / "bin" / "fsdMail.dll").exists()
    assert (tgt / "bin" / "fsdMail.dll").read_bytes() == b"DLL_CONTENT_SRC_1"


def test_ac_t3_03_and_17_exists_on_target_no_overwrite(setup_projects):
    """AC-T3-03 & AC-T3-17: file đã có target + overwrite=false → không đè, user_prompt sinh ra."""
    src, tgt = setup_projects
    (tgt / "ClientScript").mkdir(parents=True, exist_ok=True)
    (tgt / "ClientScript" / "jAjax.js").write_bytes(b"JS_CONTENT_DIFFERENT_ON_TARGET")

    res = clone_things(
        object="ClientScript/jAjax.js",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=True,
        overwrite=False,
    )
    assert res["success"] is True
    assert res["copied"] == []
    assert "ClientScript/jAjax.js" in res["skipped_exists"]
    assert res["needs_user_confirm"] is True
    assert "ClientScript/jAjax.js (content=different)" in res["user_prompt"]
    # Verify target file has NOT been overwritten
    assert (tgt / "ClientScript" / "jAjax.js").read_bytes() == b"JS_CONTENT_DIFFERENT_ON_TARGET"


def test_ac_t3_03b_overwrite_true_after_confirm(setup_projects):
    """AC-T3-03b: overwrite=true sau confirm → mới ghi đè; copied gồm path đó."""
    src, tgt = setup_projects
    (tgt / "ClientScript").mkdir(parents=True, exist_ok=True)
    (tgt / "ClientScript" / "jAjax.js").write_bytes(b"JS_CONTENT_DIFFERENT_ON_TARGET")

    res = clone_things(
        object="ClientScript/jAjax.js",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=True,
        overwrite=True,
    )
    assert res["success"] is True
    assert "ClientScript/jAjax.js" in res["copied"]
    assert res["skipped_exists"] == []
    assert res["needs_user_confirm"] is False
    assert (tgt / "ClientScript" / "jAjax.js").read_bytes() == b"JS_CONTENT_SRC"


def test_ac_t3_04_missing_on_source(setup_projects):
    """AC-T3-04: missing source → missing_on_source."""
    src, tgt = setup_projects
    res = clone_things(
        object="bin/nonexistent.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    assert "bin/nonexistent.dll" in res["missing_on_source"]
    assert res["copied"] == []


def test_ac_t3_05_glob_matching(setup_projects):
    """AC-T3-05: glob chỉ match files thỏa điều kiện."""
    src, tgt = setup_projects
    res = clone_things(
        object="bin/*Mail*.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    will_copy = set(res["will_copy"])
    assert "bin/fsdMail.dll" in will_copy
    assert "bin/callMailXS.dll" in will_copy
    assert "bin/clsFileUpload.dll" not in will_copy


def test_ac_t3_06_preset_mail(setup_projects):
    """AC-T3-06: preset mail đúng whitelist; file thiếu trên source không fail cả batch."""
    src, tgt = setup_projects
    res = clone_things(
        object="mail",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    assert "bin/fsdMail.dll" in res["will_copy"]
    assert "ClientScript/jAjax.js" in res["will_copy"]
    # zcCallMail.dll was not created on source, so it's in missing_on_source
    assert "bin/zcCallMail.dll" in res["missing_on_source"]


def test_ac_t3_07_path_outside_project(setup_projects):
    """AC-T3-07: ../ thoát root → path_outside_project."""
    src, tgt = setup_projects
    res = clone_things(
        object="../outside.txt",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is False
    assert res["error_code"] == "path_outside_project"


def test_ac_t3_08_deny_f_files(setup_projects):
    """AC-T3-08: *.f denied."""
    src, tgt = setup_projects
    res = clone_things(
        object="App_Data/Controllers/Filter/Test.f",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=True,
    )
    assert res["success"] is True
    assert "App_Data/Controllers/Filter/Test.f" in res["skipped_denied"]
    assert res["copied"] == []
    assert not (tgt / "App_Data" / "Controllers" / "Filter" / "Test.f").exists()


def test_ac_t3_11_union_preset_and_paths(setup_projects):
    """AC-T3-11: mail,App_Data/.../foo.html → preset expand + path thêm."""
    src, tgt = setup_projects
    res = clone_things(
        object="mail,App_Data/Controllers/Templates/Mail/foo.html",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    will_copy = set(res["will_copy"])
    assert "bin/fsdMail.dll" in will_copy
    assert "App_Data/Controllers/Templates/Mail/foo.html" in will_copy


def test_ac_t3_12_preset_unknown(setup_projects):
    """AC-T3-12: preset:unknown → unknown_preset."""
    src, tgt = setup_projects
    res = clone_things(
        object="preset:unknown",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is False
    assert res["error_code"] == "unknown_preset"


def test_ac_t3_13_tmp_path_fallback_resolve_root(setup_projects):
    """AC-T3-13: tmp_path chỉ có bin/ (không Web.config) → resolve root OK qua fallback."""
    src, tgt = setup_projects
    # Neither src nor tgt has Web.config or App_Data at root
    assert not (src / "Web.config").exists()
    res = clone_things(
        object="bin/fsdMail.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    assert res["project_source"] == str(src).replace("\\", "/")
    assert res["project_target"] == str(tgt).replace("\\", "/")


def test_ac_t3_14_large_file_size_and_mtime(setup_projects):
    """AC-T3-14: file > 32MB: same theo size + |Δmtime| < 1s; hash null + warning."""
    src, tgt = setup_projects
    large_src = src / "bin" / "large.dat"
    large_tgt = tgt / "bin" / "large.dat"

    # Create dummy file entry with simulated size > 32MB
    (tgt / "bin").mkdir(parents=True, exist_ok=True)
    large_src.write_bytes(b"x")
    large_tgt.write_bytes(b"x")

    with patch("clone_things.type3_file_clone.HASH_MAX_BYTES", 5):
        # When HASH_MAX_BYTES is 5, file with 1 byte is <= 5 bytes,
        # so let's make it 10 bytes
        large_src.write_bytes(b"0123456789")
        large_tgt.write_bytes(b"0123456789")
        # Ensure mtimes match
        mtime = time.time()
        os.utime(large_src, (mtime, mtime))
        os.utime(large_tgt, (mtime, mtime))

        res = clone_things(
            object="bin/large.dat",
            project_source=str(src),
            project_target=str(tgt),
            type=3,
        )
        assert res["success"] is True
        planned = res["planned"][0]
        assert planned["status"] == "exists_on_target"
        assert planned["content"] == "same"
        assert planned["hash_source"] is None
        assert planned["hash_target"] is None
        assert any("hash_skipped_large_file" in w for w in res["warnings"])


def test_ac_t3_15_copy_permission_denied_failed_object(setup_projects):
    """AC-T3-15: copy Permission denied → failed: [{relative, error}]."""
    src, tgt = setup_projects
    with patch("shutil.copy2", side_effect=PermissionError("Locked by process")):
        res = clone_things(
            object="bin/fsdMail.dll",
            project_source=str(src),
            project_target=str(tgt),
            type=3,
            execute=True,
        )
        assert res["success"] is True
        assert len(res["failed"]) == 1
        assert res["failed"][0]["relative"] == "bin/fsdMail.dll"
        assert "Locked by process" in res["failed"][0]["error"]


def test_ac_t3_16_relative_posix_slash(setup_projects):
    """AC-T3-16: mọi relative trong JSON dùng /."""
    src, tgt = setup_projects
    res = clone_things(
        object="bin\\fsdMail.dll,Main\\Uploads\\AjaxWeb.aspx",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    for item in res["planned"]:
        assert "\\" not in item["relative"]
        assert "/" in item["relative"]
    for p in res["will_copy"]:
        assert "\\" not in p
