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
        confirm_overwrite=True,
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


def test_ac_t3_dir_1_is_directory_error(setup_projects):
    """AC-T3-DIR-1: object=bin khi expand_dirs=false -> khong bao missing_on_source gia, bao is_directory."""
    src, tgt = setup_projects
    res = clone_things(
        object="bin",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        expand_dirs=False,
    )
    assert res["success"] is False
    assert res["error_code"] == "is_directory"
    assert "thư mục" in res["message"] or "directory" in res["message"].lower()


def test_ac_t3_dir_2_expand_dirs_true(setup_projects):
    """AC-T3-DIR-2: expand_dirs=true tren thu muc -> danh sach file con."""
    src, tgt = setup_projects
    res = clone_things(
        object="bin",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        expand_dirs=True,
    )
    assert res["success"] is True
    assert "bin/fsdMail.dll" in res["will_copy"]
    assert "bin/callMailXS.dll" in res["will_copy"]
    assert "bin/clsFileUpload.dll" in res["will_copy"]


def test_ac_t3_glob_1_max_files_guard(setup_projects):
    """AC-T3-GLOB-1: glob vuot max_files -> dry-run truncated, execute too_many_files."""
    src, tgt = setup_projects
    # Dry-run with max_files=2
    res_dry = clone_things(
        object="bin/*",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=2,
        execute=False,
    )
    assert res_dry["success"] is True
    assert res_dry["truncated"] is True
    assert len(res_dry["planned"]) == 2
    assert "truncated_max_files" in res_dry["warnings"]

    # Execute with max_files=2
    res_exec = clone_things(
        object="bin/*",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=2,
        execute=True,
    )
    assert res_exec["success"] is False
    assert res_exec["error_code"] == "too_many_files"


def test_ac_t3_glob_2_narrow_glob(setup_projects):
    """AC-T3-GLOB-2: Glob hep khong bi anh huong boi max_files."""
    src, tgt = setup_projects
    res = clone_things(
        object="App_Data/Controllers/Templates/Mail/*.html",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=100,
    )
    assert res["success"] is True
    assert res["truncated"] is False
    assert "App_Data/Controllers/Templates/Mail/foo.html" in res["will_copy"]


def test_ac_t3_err_1_unknown_preset_details(setup_projects):
    """AC-T3-ERR-1: preset:foobar -> message co foobar va error_code=unknown_preset."""
    src, tgt = setup_projects
    res = clone_things(
        object="preset:foobar",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is False
    assert res["error_code"] == "unknown_preset"
    assert "foobar" in res["message"]


def test_ac_t3_ow_1_and_2_soft_gate(setup_projects):
    """AC-T3-OW-1 & AC-T3-OW-2: confirm_overwrite soft-gate."""
    src, tgt = setup_projects
    (tgt / "bin").mkdir(parents=True, exist_ok=True)
    (tgt / "bin" / "fsdMail.dll").write_bytes(b"TARGET_EXISTING_CONTENT")

    # OW-1: overwrite=true, confirm_overwrite=false -> khong de exists
    res1 = clone_things(
        object="bin/fsdMail.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=True,
        overwrite=True,
        confirm_overwrite=False,
    )
    assert res1["success"] is True
    assert res1["copied"] == []
    assert res1["needs_user_confirm"] is True
    assert (tgt / "bin" / "fsdMail.dll").read_bytes() == b"TARGET_EXISTING_CONTENT"

    # OW-2: ca hai true -> de duoc
    res2 = clone_things(
        object="bin/fsdMail.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=True,
        overwrite=True,
        confirm_overwrite=True,
    )
    assert res2["success"] is True
    assert "bin/fsdMail.dll" in res2["copied"]
    assert (tgt / "bin" / "fsdMail.dll").read_bytes() == b"DLL_CONTENT_SRC_1"


def test_ac_t3_pre_1_list_presets():
    """AC-T3-PRE-1: list presets tra mail va ajax."""
    res = clone_things(
        type=3,
        list_presets=True,
    )
    assert res["success"] is True
    assert res["mode"] == "list_presets"
    preset_names = [p["name"] for p in res["presets"]]
    assert "mail" in preset_names
    assert "ajax" in preset_names


def test_summary_counts_and_copy_filter(setup_projects):
    """P2: summary_counts va copy_filter."""
    src, tgt = setup_projects
    (tgt / "bin").mkdir(parents=True, exist_ok=True)
    (tgt / "bin" / "fsdMail.dll").write_bytes(b"DLL_CONTENT_SRC_1")  # same content
    (tgt / "ClientScript").mkdir(parents=True, exist_ok=True)
    (tgt / "ClientScript" / "jAjax.js").write_bytes(b"DIFF_CONTENT")  # diff content

    res = clone_things(
        object="bin/fsdMail.dll,bin/callMailXS.dll,ClientScript/jAjax.js,Filter/Test.f",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    sc = res["summary_counts"]
    assert sc["missing_on_target"] == 1  # callMailXS.dll
    assert sc["exists_same"] == 1        # fsdMail.dll
    assert sc["exists_different"] == 1   # jAjax.js
    assert sc["denied"] == 1             # Test.f
    assert sc["will_copy"] == 1          # default copy_filter=missing -> only callMailXS.dll


def test_ac_t3_samp_1_planned_sample_size_and_summary_counts(tmp_path):
    """AC-T3-SAMP-1: glob lớn + max_files=15 + default sample -> len(planned) <= 10, summary_counts & meta.total_expanded."""
    src = tmp_path / "src_samp"
    tgt = tmp_path / "tgt_samp"
    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)

    # Populate 25 files on src
    for i in range(25):
        (src / f"file_{i:02d}.txt").write_text(f"content {i}", encoding="utf-8")

    res = clone_things(
        object="*.txt",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=15,
        planned_sample_size=5,
        execute=False,
    )
    assert res["success"] is True
    assert res["truncated"] is True
    assert len(res["planned"]) == 5
    assert res["summary_counts"]["missing_on_target"] == 15
    assert res["meta"]["total_expanded"] == 25
    assert res["meta"]["file_count"] == 5
    assert res["meta"]["planned_omitted"] == 10
    assert any("planned_truncated: showing 5 of 15 processed" in w for w in res["warnings"])


def test_ac_t3_samp_2_narrow_untruncated_keeps_full_planned(setup_projects):
    """AC-T3-SAMP-2: dry-run hẹp (không truncate) -> planned giữ đủ mọi file, omitted = 0."""
    src, tgt = setup_projects
    res = clone_things(
        object="App_Data/Controllers/Templates/Mail/*.html",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=50,
        planned_sample_size=10,
        execute=False,
    )
    assert res["success"] is True
    assert res["truncated"] is False
    assert len(res["planned"]) == 1
    assert res["meta"]["planned_omitted"] == 0
    assert not any("planned_truncated" in w for w in res["warnings"])


def test_ac_t3_samp_3_execute_budget_enforced(tmp_path):
    """AC-T3-SAMP-3: execute=true chỉ copy trong budget max_files (hoặc fail too_many_files nếu vượt)."""
    src = tmp_path / "src_exec"
    tgt = tmp_path / "tgt_exec"
    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)

    for i in range(5):
        (src / f"doc_{i}.txt").write_text(f"data {i}", encoding="utf-8")

    # Within budget: 5 files <= max_files=10 -> all copied
    res_ok = clone_things(
        object="*.txt",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=10,
        execute=True,
    )
    assert res_ok["success"] is True
    assert len(res_ok["copied"]) == 5

    # Over budget with execute=True -> guard error too_many_files
    res_err = clone_things(
        object="*.txt",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=3,
        execute=True,
    )
    assert res_err["success"] is False
    assert res_err["error_code"] == "too_many_files"


def test_ac_nit_t3_1_to_3_prompt_truncate_sample(tmp_path):
    """AC-NIT-T3-1, T3-2, T3-3: user_prompt truncate theo sample exists, có câu 'N file exists khác đã ẩn'."""
    src = tmp_path / "src_nit"
    tgt = tmp_path / "tgt_nit"
    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)

    # Populate 20 files on both src and tgt with different content
    for i in range(20):
        (src / f"lib_{i:02d}.dll").write_bytes(f"SRC_{i}".encode("utf-8"))
        (tgt / f"lib_{i:02d}.dll").write_bytes(f"TGT_{i}".encode("utf-8"))

    # AC-NIT-T3-1: max_files=15, planned_sample_size=5 -> truncated
    res_trunc = clone_things(
        object="*.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=15,
        planned_sample_size=5,
        execute=False,
    )
    assert res_trunc["success"] is True
    assert res_trunc["truncated"] is True
    assert len(res_trunc["planned"]) == 5
    assert len(res_trunc["exists_on_target"]) == 5
    # AC-NIT-T3-3: summary_counts preserves full processed numbers
    assert res_trunc["summary_counts"]["exists_different"] == 15
    # user_prompt contains sample and notice of hidden exists
    prompt = res_trunc["user_prompt"]
    assert "10 file exists khác đã ẩn (truncated)" in prompt
    # Ensure it only lists <= 5 individual file items, not all 15
    assert prompt.count("(content=different)") == 5

    # AC-NIT-T3-2: narrow untruncated -> full list in user_prompt without hidden note
    res_single = clone_things(
        object="lib_01.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=False,
    )
    assert res_single["success"] is True
    assert res_single["truncated"] is False
    assert "lib_01.dll (content=different)" in res_single["user_prompt"]
    assert "đã ẩn" not in res_single["user_prompt"]


def test_ac_cf_1_2_3_copy_filter_different_warnings_and_blocked(setup_projects):
    """AC-CF-1, AC-CF-2, AC-CF-3: copy_filter=different warnings, blocked_different, and permissions."""
    src, tgt = setup_projects
    (tgt / "ClientScript").mkdir(parents=True, exist_ok=True)
    (tgt / "ClientScript" / "jAjax.js").write_bytes(b"DIFFERENT_JS_ON_TARGET")

    # AC-CF-1: copy_filter=different + overwrite=false -> will_copy empty, blocked_different populated, warning present
    res1 = clone_things(
        object="ClientScript/jAjax.js",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        copy_filter="different",
        overwrite=False,
    )
    assert res1["success"] is True
    assert res1["will_copy"] == []
    assert "ClientScript/jAjax.js" in res1["blocked_different"]
    assert any("copy_filter_different_blocked" in w for w in res1["warnings"])
    assert "overwrite=false" in res1["agent_message"]

    # AC-CF-2: copy_filter=different + overwrite=true + confirm_overwrite=true dry-run -> will_copy has file
    res2 = clone_things(
        object="ClientScript/jAjax.js",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        copy_filter="different",
        overwrite=True,
        confirm_overwrite=True,
        execute=False,
    )
    assert res2["success"] is True
    assert "ClientScript/jAjax.js" in res2["will_copy"]
    assert res2["blocked_different"] == []

    # AC-CF-3: copy_filter=missing does not trigger copy_filter_different_blocked warning
    res3 = clone_things(
        object="ClientScript/jAjax.js",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        copy_filter="missing",
        overwrite=False,
    )
    assert res3["success"] is True
    assert not any("copy_filter_different_blocked" in w for w in res3["warnings"])


def test_ac_suite_1_to_4_expansion_and_union(setup_projects):
    """AC-SUITE-1, AC-SUITE-2, AC-SUITE-3, AC-SUITE-4: suite:{name} expansion, whitelist, union, sanitization."""
    src, tgt = setup_projects
    (src / "App_Data" / "Controllers" / "Filter").mkdir(parents=True, exist_ok=True)
    (src / "App_Data" / "Controllers" / "Grid").mkdir(parents=True, exist_ok=True)
    (src / "App_Data" / "Controllers" / "Dir").mkdir(parents=True, exist_ok=True)
    (src / "Main").mkdir(parents=True, exist_ok=True)
    (src / "App_Data" / "Controllers" / "Templates" / "Mail").mkdir(parents=True, exist_ok=True)

    (src / "App_Data" / "Controllers" / "Filter" / "zccnslkdhtpnc.xml").write_text("<filter/>", encoding="utf-8")
    (src / "App_Data" / "Controllers" / "Filter" / "zccnslkdhtpncForm.xml").write_text("<form/>", encoding="utf-8")
    (src / "App_Data" / "Controllers" / "Grid" / "zccnslkdhtpnc.xml").write_text("<grid/>", encoding="utf-8")
    (src / "Main" / "zccnslkdhtpnc.aspx").write_text("<%@ Page %>", encoding="utf-8")
    (src / "App_Data" / "Controllers" / "Templates" / "Mail" / "zccnslkdhtpnc.html").write_text("<html>mail</html>", encoding="utf-8")

    # AC-SUITE-1: suite:zccnslkdhtpnc expands existing candidates on source
    res1 = clone_things(
        object="suite:zccnslkdhtpnc",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res1["success"] is True
    planned_rels = [p["relative"] for p in res1["planned"]]
    assert "App_Data/Controllers/Filter/zccnslkdhtpnc.xml" in planned_rels
    assert "App_Data/Controllers/Filter/zccnslkdhtpncForm.xml" in planned_rels
    assert "App_Data/Controllers/Grid/zccnslkdhtpnc.xml" in planned_rels
    assert "Main/zccnslkdhtpnc.aspx" in planned_rels
    assert "App_Data/Controllers/Templates/Mail/zccnslkdhtpnc.html" in planned_rels

    # AC-SUITE-2: non-existent suite name -> suite_empty error/warning
    res2 = clone_things(
        object="suite:non_existent_controller",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res2["success"] is False
    assert res2["error_code"] == "suite_empty"
    assert any("suite_empty" in w for w in res2["warnings"])

    # AC-SUITE-3: union of suite:name and another file
    res3 = clone_things(
        object="suite:zccnslkdhtpnc,bin/fsdMail.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res3["success"] is True
    union_rels = [p["relative"] for p in res3["planned"]]
    assert "bin/fsdMail.dll" in union_rels
    assert "Main/zccnslkdhtpnc.aspx" in union_rels

    # AC-SUITE-4: sanitize controller name
    res4 = clone_things(
        object="suite:../../bad_escape",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res4["success"] is False
    assert res4["error_code"] == "invalid_object"


def test_ac_path_1_and_2_hints_on_missing_source(setup_projects):
    """AC-PATH-1, AC-PATH-2: hint App_Data/Controllers when shortened path misses on source."""
    src, tgt = setup_projects
    (src / "App_Data" / "Controllers" / "Options").mkdir(parents=True, exist_ok=True)
    (src / "App_Data" / "Controllers" / "Options" / "EmailConfig.xml").write_text("<config/>", encoding="utf-8")

    # AC-PATH-1: Options/EmailConfig.xml missing on source, but found under App_Data/Controllers/
    res1 = clone_things(
        object="Options/EmailConfig.xml",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res1["success"] is True
    assert "Options/EmailConfig.xml" in res1["missing_on_source"]
    assert "App_Data/Controllers/Options/EmailConfig.xml" in res1["suggestions"]
    assert any("path_suggestion" in w for w in res1["warnings"])

    # AC-PATH-2: Correct full path -> no suggestion spam
    res2 = clone_things(
        object="App_Data/Controllers/Options/EmailConfig.xml",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res2["success"] is True
    assert res2["missing_on_source"] == []
    assert res2["suggestions"] == []
    assert not any("path_suggestion" in w for w in res2["warnings"])


def test_ac_prompt_1_truncated_no_double_dot(tmp_path):
    """AC-PROMPT-1: truncated user_prompt does not contain '.. Bạn' or duplicate punctuation."""
    src = tmp_path / "src_prompt"
    tgt = tmp_path / "tgt_prompt"
    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)

    for i in range(20):
        (src / f"module_{i:02d}.dll").write_bytes(f"SRC_{i}".encode("utf-8"))
        (tgt / f"module_{i:02d}.dll").write_bytes(f"TGT_{i}".encode("utf-8"))

    res = clone_things(
        object="*.dll",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        max_files=15,
        planned_sample_size=5,
        execute=False,
    )
    assert res["success"] is True
    assert res["truncated"] is True
    prompt = res["user_prompt"]
    assert ".. Bạn" not in prompt
    assert "..." not in prompt or "…" in prompt  # Ellipsis character is ok, but not ".. " typo
    assert ".." not in prompt.replace("...", "").replace("..", "__double__") or "__double__" not in prompt
    assert ".. Bạn" not in prompt


def test_ac_suite_extended_and_sensitive_warnings(setup_projects):
    """Test AC-SUITE-R*, U*, I*, L*, REG and AC-SENS-*."""
    src, tgt = setup_projects

    # Create directories for controller 'POTran'
    p_report = src / "App_Data" / "Controllers" / "Report"
    p_upload = src / "App_Data" / "Controllers" / "Templates" / "Upload"
    p_include = src / "App_Data" / "Controllers" / "Include"
    p_lookup = src / "App_Data" / "Controllers" / "Lookup"
    p_filter = src / "App_Data" / "Controllers" / "Filter"

    p_report.mkdir(parents=True, exist_ok=True)
    p_upload.mkdir(parents=True, exist_ok=True)
    p_include.mkdir(parents=True, exist_ok=True)
    p_lookup.mkdir(parents=True, exist_ok=True)
    p_filter.mkdir(parents=True, exist_ok=True)

    # 1. Populate Report, Upload, Include, Lookup files for POTran
    (p_filter / "POTran.xml").write_text("<filter/>", encoding="utf-8")
    (p_report / "POTran.xml").write_text("<report/>", encoding="utf-8")
    (p_upload / "POTran.xml").write_text("<upload/>", encoding="utf-8")
    (p_upload / "POTranImportXml.xml").write_text("<import_xml/>", encoding="utf-8")
    (p_include / "Extender.POTran").write_text("extender content", encoding="utf-8")
    (p_include / "POTran.Nested").write_text("nested content", encoding="utf-8")
    (p_lookup / "POTran.xml").write_text("<lookup/>", encoding="utf-8")

    # Also put unrelated files in Include and Lookup
    (p_include / "Extender.OtherVoucher").write_text("other", encoding="utf-8")
    (p_lookup / "OtherLookup.xml").write_text("<lookup/>", encoding="utf-8")

    # Run suite:POTran
    res = clone_things(
        object="suite:POTran",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    planned_rels = [p["relative"] for p in res["planned"]]

    # AC-SUITE-R1: Report/{name}.xml in planned
    assert "App_Data/Controllers/Report/POTran.xml" in planned_rels

    # AC-SUITE-U1: Templates/Upload/{name}.xml in planned
    assert "App_Data/Controllers/Templates/Upload/POTran.xml" in planned_rels

    # AC-SUITE-U2: Templates/Upload/{name}ImportXml.xml in planned
    assert "App_Data/Controllers/Templates/Upload/POTranImportXml.xml" in planned_rels

    # AC-SUITE-I1: Include/Extender.{name} and {name}.Nested in planned
    assert "App_Data/Controllers/Include/Extender.POTran" in planned_rels
    assert "App_Data/Controllers/Include/POTran.Nested" in planned_rels

    # AC-SUITE-I3: unrelated Include files NOT in planned
    assert "App_Data/Controllers/Include/Extender.OtherVoucher" not in planned_rels

    # AC-SUITE-L1: Lookup/{name}.xml in planned
    assert "App_Data/Controllers/Lookup/POTran.xml" in planned_rels

    # AC-SUITE-L2: unrelated Lookup NOT in planned
    assert "App_Data/Controllers/Lookup/OtherLookup.xml" not in planned_rels

    # AC-SUITE-R2 & I2: Test suite for controller with only Filter (no Report, no Upload, no Include)
    (p_filter / "SimpleCtrl.xml").write_text("<filter/>", encoding="utf-8")
    res_simple = clone_things(
        object="suite:SimpleCtrl",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res_simple["success"] is True
    simple_rels = [p["relative"] for p in res_simple["planned"]]
    assert "App_Data/Controllers/Filter/SimpleCtrl.xml" in simple_rels
    assert len(simple_rels) == 1

    # AC-SENS-1: Web.config missing in dry-run triggers sensitive_path warning
    (src / "Web.config").write_text("<configuration/>", encoding="utf-8")
    res_sens = clone_things(
        object="Web.config",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res_sens["success"] is True
    assert "Web.config" in res_sens["will_copy"]
    assert any("sensitive_path" in w and "Web.config" in w for w in res_sens["warnings"])

    # AC-SENS-2: normal file does not trigger sensitive_path warning
    assert not any("sensitive_path" in w for w in res_simple["warnings"])




