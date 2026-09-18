"""Unit tests for clone_things type=3 rename features.

Covers AC-R-01 through AC-R-23 from docs/doc/gemini/GEMINI-clone_things-type3-rename.md.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from clone_things import clone_things


@pytest.fixture
def rename_proj(tmp_path):
    """Set up source and target projects for rename testing without Web.config."""
    src = tmp_path / "src_proj"
    src.mkdir(parents=True, exist_ok=True)

    (src / "Config").mkdir(parents=True, exist_ok=True)
    (src / "Config" / "MRTran.ent").write_text("MRTran ent content", encoding="utf-8")

    (src / "Foo" / "Bar").mkdir(parents=True, exist_ok=True)
    (src / "Foo" / "Bar" / "MRTran.ent").write_text("Foo Bar MRTran ent content", encoding="utf-8")

    (src / "A.ent").write_text("A content", encoding="utf-8")
    (src / "B.ent").write_text("B content", encoding="utf-8")
    (src / "C.ent").write_text("C content", encoding="utf-8")

    tgt = tmp_path / "tgt_proj"
    tgt.mkdir(parents=True, exist_ok=True)

    return src, tgt


def test_ac_r_01_dry_run_rename_missing_target(rename_proj):
    """AC-R-01: Config/MRTran.ent->DDVTran.ent, project_target="" dry-run -> planned missing_on_target, target_relative=Config/DDVTran.ent; disk không đổi."""
    src, _ = rename_proj
    res = clone_things(
        object="Config/MRTran.ent->DDVTran.ent",
        project_source=str(src),
        project_target="",
        type=3,
        execute=False,
    )
    assert res["success"] is True
    assert res["project_target"] == res["project_source"]
    planned = res["planned"]
    assert len(planned) == 1
    assert planned[0]["status"] == "missing_on_target"
    assert planned[0]["relative"] == "Config/MRTran.ent"
    assert planned[0]["target_relative"] == "Config/DDVTran.ent"
    assert "Config/MRTran.ent" in res["will_copy"]
    assert not (src / "Config" / "DDVTran.ent").exists()


def test_ac_r_02_execute_rename(rename_proj):
    """AC-R-02: execute -> DDVTran.ent tạo, content == source, MRTran.ent còn nguyên, copied."""
    src, _ = rename_proj
    res = clone_things(
        object="Config/MRTran.ent->DDVTran.ent",
        project_source=str(src),
        project_target="",
        type=3,
        execute=True,
    )
    assert res["success"] is True
    assert "Config/MRTran.ent" in res["copied"]
    assert (src / "Config" / "DDVTran.ent").exists()
    assert (src / "Config" / "DDVTran.ent").read_text(encoding="utf-8") == "MRTran ent content"
    assert (src / "Config" / "MRTran.ent").exists()


def test_ac_r_03_dst_basename_only_sibling(rename_proj):
    """AC-R-03: DST basename-only -> sibling cùng folder."""
    src, _ = rename_proj
    res = clone_things(
        object="Foo/Bar/MRTran.ent->DDVTran.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res["success"] is True
    assert res["planned"][0]["target_relative"] == "Foo/Bar/DDVTran.ent"


def test_ac_r_04_dst_with_slash_relative_target_root(rename_proj):
    """AC-R-04: DST có / -> relative từ root_target."""
    src, _ = rename_proj
    res = clone_things(
        object="Foo/Bar/MRTran.ent->Other/Dir/DDVTran.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res["success"] is True
    assert res["planned"][0]["target_relative"] == "Other/Dir/DDVTran.ent"


def test_ac_r_05_dst_exists_no_overwrite_prompt(rename_proj):
    """AC-R-05: dst đã có + overwrite=false -> exists_on_target (+target_relative) + needs_user_confirm + user_prompt chứa tên dst."""
    src, _ = rename_proj
    (src / "Config" / "DDVTran.ent").write_text("existing content", encoding="utf-8")

    res = clone_things(
        object="Config/MRTran.ent->DDVTran.ent",
        project_source=str(src),
        project_target="",
        type=3,
        execute=False,
        overwrite=False,
    )
    assert res["success"] is True
    assert res["needs_user_confirm"] is True
    assert "Config/DDVTran.ent" in res["user_prompt"]
    assert res["planned"][0]["status"] == "exists_on_target"
    assert res["planned"][0]["target_relative"] == "Config/DDVTran.ent"
    assert res["exists_on_target"][0]["target_relative"] == "Config/DDVTran.ent"


def test_ac_r_06_dst_exists_overwrite_confirm(rename_proj):
    """AC-R-06: overwrite+confirm -> đè dst; copied."""
    src, _ = rename_proj
    (src / "Config" / "DDVTran.ent").write_text("old content", encoding="utf-8")

    res = clone_things(
        object="Config/MRTran.ent->DDVTran.ent",
        project_source=str(src),
        project_target="",
        type=3,
        execute=True,
        overwrite=True,
        confirm_overwrite=True,
    )
    assert res["success"] is True
    assert "Config/MRTran.ent" in res["copied"]
    assert (src / "Config" / "DDVTran.ent").read_text(encoding="utf-8") == "MRTran ent content"


def test_ac_r_07_same_source_target(rename_proj):
    """AC-R-07: A.ent->A.ent -> same_source_target + skipped_same_source + warning; token duy nhất -> invalid_object."""
    src, _ = rename_proj

    # Token duy nhất: làm rỗng batch -> invalid_object
    res_single = clone_things(
        object="A.ent->A.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_single["success"] is False
    assert res_single["error_code"] == "invalid_object"
    assert "same_source_target" in res_single["message"]
    assert any("same_source_target" in w for w in res_single["warnings"])

    # Mixed token: item cùng tên bị skip và thêm vào skipped_same_source
    res_mixed = clone_things(
        object="A.ent->A.ent, B.ent->NewB.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_mixed["success"] is True
    assert "A.ent" in res_mixed["skipped_same_source"]
    assert res_mixed["summary_counts"]["same_source_target"] == 1
    assert any("same_source_target" in w and "A.ent" in w for w in res_mixed["warnings"])
    p_a = [p for p in res_mixed["planned"] if p["relative"] == "A.ent"][0]
    assert p_a["status"] == "same_source_target"
    p_b = [p for p in res_mixed["planned"] if p["relative"] == "B.ent"][0]
    assert p_b["status"] == "missing_on_target"


def test_ac_r_08_invalid_src_kinds(rename_proj):
    """AC-R-08: preset:mail->x -> rename_not_supported; dir->x không expand_dirs -> is_directory."""
    src, _ = rename_proj

    res_preset = clone_things(
        object="preset:mail->x",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_preset["success"] is False
    assert res_preset["error_code"] == "rename_not_supported"

    (src / "MyDir").mkdir(parents=True, exist_ok=True)
    res_dir = clone_things(
        object="MyDir->x/",
        project_source=str(src),
        project_target="",
        type=3,
        expand_dirs=False,
    )
    assert res_dir["success"] is False
    assert res_dir["error_code"] == "is_directory"


def test_ac_r_09_invalid_rename_syntax(rename_proj):
    """AC-R-09: A-> -> invalid_rename; A->../x -> path_outside_project; A->B->C -> invalid_rename."""
    src, _ = rename_proj

    res_empty_dst = clone_things(
        object="A.ent->",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_empty_dst["success"] is False
    assert res_empty_dst["error_code"] == "invalid_rename"

    res_outside = clone_things(
        object="A.ent->../x",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_outside["success"] is False
    assert res_outside["error_code"] == "path_outside_project"

    res_multi_arrow = clone_things(
        object="A.ent->B.ent->C.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_multi_arrow["success"] is False
    assert res_multi_arrow["error_code"] == "invalid_rename"


def test_ac_r_10_dst_denied_f(rename_proj):
    """AC-R-10: dst *.f -> denied."""
    src, _ = rename_proj
    res = clone_things(
        object="A.ent->B.f",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res["success"] is True
    assert res["planned"][0]["status"] == "denied"
    assert "A.ent" in res["skipped_denied"]


def test_ac_r_11_suite_old_to_new_same_project(rename_proj):
    """AC-R-11: suite:MRTran->DDVTran cùng project -> mọi file suite found -> DDVTran*; missing candidate không fail."""
    src, _ = rename_proj
    p_dir = src / "App_Data" / "Controllers" / "Dir"
    p_inc = src / "App_Data" / "Controllers" / "Include"
    p_mail = src / "App_Data" / "Controllers" / "Templates" / "Mail"
    p_dir.mkdir(parents=True, exist_ok=True)
    p_inc.mkdir(parents=True, exist_ok=True)
    p_mail.mkdir(parents=True, exist_ok=True)

    (p_dir / "MRTran.xml").write_text("<dir/>", encoding="utf-8")
    (p_inc / "Extender.MRTran").write_text("extender content", encoding="utf-8")
    (p_mail / "zmailMRTran.html").write_text("mail content", encoding="utf-8")

    res = clone_things(
        object="suite:MRTran->DDVTran",
        project_source=str(src),
        project_target="",
        type=3,
        execute=True,
    )
    assert res["success"] is True
    assert (p_dir / "DDVTran.xml").exists()
    assert (p_inc / "Extender.DDVTran").exists()
    assert (p_mail / "zmailDDVTran.html").exists()


def test_ac_r_12_mixed_tokens(rename_proj):
    """AC-R-12: A->B, C mixed -> A->B renamed, C same-name."""
    src, tgt = rename_proj
    res = clone_things(
        object="A.ent->RenamedA.ent, B.ent",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    p_a = [p for p in res["planned"] if p["relative"] == "A.ent"][0]
    assert p_a["target_relative"] == "RenamedA.ent"
    p_b = [p for p in res["planned"] if p["relative"] == "B.ent"][0]
    assert p_b["target_relative"] == "B.ent"


def test_ac_r_13_cross_project_rename(rename_proj):
    """AC-R-13: Cross-project rename src->dst OK."""
    src, tgt = rename_proj
    res = clone_things(
        object="Config/MRTran.ent->DDVTran.ent",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
        execute=True,
    )
    assert res["success"] is True
    assert (tgt / "Config" / "DDVTran.ent").exists()
    assert (tgt / "Config" / "DDVTran.ent").read_text(encoding="utf-8") == "MRTran ent content"


def test_ac_r_14_project_target_equals_source(rename_proj):
    """AC-R-14: project_target truyền = source -> y hệt rỗng."""
    src, _ = rename_proj
    res = clone_things(
        object="Config/MRTran.ent->DDVTran.ent",
        project_source=str(src),
        project_target=str(src),
        type=3,
    )
    assert res["success"] is True
    assert res["project_target"] == res["project_source"]
    assert res["planned"][0]["target_relative"] == "Config/DDVTran.ent"


def test_ac_r_15_target_relative_always_present_posix(rename_proj):
    """AC-R-15: planned luôn có target_relative; string lists POSIX /."""
    src, tgt = rename_proj
    res = clone_things(
        object="A.ent, B.ent->RenamedB.ent",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    for p in res["planned"]:
        assert "target_relative" in p
        assert "\\" not in p["relative"]
        assert "\\" not in p["target_relative"]


def test_ac_r_16_regression_type0_and_no_arrow(rename_proj):
    """AC-R-16: Regression: token không -> y hệt cũ; type=0 thiếu project_target vẫn invalid_project_target."""
    src, tgt = rename_proj

    # Type=0 requires project_target
    res0 = clone_things(
        object="TestProc",
        project_source=str(src),
        project_target="",
        type=0,
    )
    assert res0["success"] is False
    assert res0["error_code"] == "invalid_project_target"

    # Token without -> has relative == target_relative
    res3 = clone_things(
        object="A.ent",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res3["success"] is True
    assert res3["planned"][0]["relative"] == "A.ent"
    assert res3["planned"][0]["target_relative"] == "A.ent"


def test_ac_r_17_same_source_no_copy_even_with_overwrite(rename_proj):
    """AC-R-17: same_source_target + overwrite=true+confirm vẫn không copy lên chính nó."""
    src, _ = rename_proj
    res = clone_things(
        object="A.ent->A.ent, B.ent->RenamedB.ent",
        project_source=str(src),
        project_target="",
        type=3,
        execute=True,
        overwrite=True,
        confirm_overwrite=True,
    )
    assert res["success"] is True
    assert "A.ent" in res["skipped_same_source"]
    assert "A.ent" not in res["copied"]
    assert "B.ent" in res["copied"]


def test_ac_r_18_rl_patterns(rename_proj):
    """AC-R-18: MRTran.ent->rl(s,2,DDV) -> DDVTran.ent; ->rl(e,4,X) trên name-no-ext; ->rl(MR,DDV) first-occurrence."""
    src, _ = rename_proj

    res_s = clone_things(
        object="Config/MRTran.ent->rl(s,2,DDV)",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_s["planned"][0]["target_relative"] == "Config/DDVTran.ent"

    res_e = clone_things(
        object="Config/MRTran.ent->rl(e,4,X)",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_e["planned"][0]["target_relative"] == "Config/MRX.ent"

    res_rep = clone_things(
        object="Config/MRTran.ent->rl(MR,DDV)",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_rep["planned"][0]["target_relative"] == "Config/DDVTran.ent"


def test_ac_r_19_rlx_patterns(rename_proj):
    """AC-R-19: rlx(s,2,DDV) áp full basename (A.ent->biến cả ext nếu pattern đụng); rl() giữ nguyên .ent."""
    src, _ = rename_proj

    # rlx modifies full basename including .ent
    res_rlx = clone_things(
        object="A.ent->rlx(s,2,DDV)",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_rlx["planned"][0]["target_relative"] == "DDVent"

    # rl preserves .ent extension
    res_rl = clone_things(
        object="A.ent->rl(s,2,DDV)",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_rl["planned"][0]["target_relative"] == "DDV.ent"


def test_ac_r_20_glob_batch_rename(rename_proj):
    """AC-R-20: *.ent->rl(MR,DDV) glob batch -> từng file rename theo pattern, sibling; glob + literal dst -> invalid_rename."""
    src, _ = rename_proj
    p_glob = src / "GlobDir"
    p_glob.mkdir(parents=True, exist_ok=True)
    (p_glob / "MR1.ent").write_text("1", encoding="utf-8")
    (p_glob / "MR2.ent").write_text("2", encoding="utf-8")

    res_glob = clone_things(
        object="GlobDir/*.ent->rl(MR,DDV)",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_glob["success"] is True
    target_rels = [p["target_relative"] for p in res_glob["planned"]]
    assert "GlobDir/DDV1.ent" in target_rels
    assert "GlobDir/DDV2.ent" in target_rels

    # Glob with literal dst is invalid
    res_lit = clone_things(
        object="GlobDir/*.ent->DDV.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_lit["success"] is False
    assert res_lit["error_code"] == "invalid_rename"


def test_ac_r_21_dst_folder(rename_proj):
    """AC-R-21: A.ent->Sub/Dir/ -> Sub/Dir/A.ent (basename giữ); A.ent->Sub/Dir/B.ent -> dir + literal."""
    src, _ = rename_proj

    res_folder = clone_things(
        object="A.ent->Sub/Dir/",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_folder["success"] is True
    assert res_folder["planned"][0]["target_relative"] == "Sub/Dir/A.ent"

    res_file = clone_things(
        object="A.ent->Sub/Dir/B.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_file["success"] is True
    assert res_file["planned"][0]["target_relative"] == "Sub/Dir/B.ent"


def test_ac_r_22_suite_rename_pattern(rename_proj):
    """AC-R-22: suite:MRTran->rl(MRTran,DDVTran) hoặc ->rlx(...) -> rename trên full basename + warning suite_rename_full_basename; suite:A->Dir2/x -> invalid_rename."""
    src, _ = rename_proj
    p_dir = src / "App_Data" / "Controllers" / "Dir"
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "MRTran.xml").write_text("<dir/>", encoding="utf-8")

    res_pattern = clone_things(
        object="suite:MRTran->rl(MRTran,DDVTran)",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_pattern["success"] is True
    assert any("suite_rename_full_basename" in w for w in res_pattern["warnings"])
    assert res_pattern["planned"][0]["target_relative"] == "App_Data/Controllers/Dir/DDVTran.xml"

    # Suite with dir_part in dst is invalid
    res_dir = clone_things(
        object="suite:MRTran->Dir2/DDVTran",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res_dir["success"] is False
    assert res_dir["error_code"] == "invalid_rename"


def test_ac_r_23_src_abs_path_rename(rename_proj):
    """AC-R-23: src abs path + ->name -> resolve src_rel trong root, dst sibling — UNC OK."""
    src, _ = rename_proj
    abs_src_file = (src / "Config" / "MRTran.ent").resolve()

    res = clone_things(
        object=f"{abs_src_file}->DDVTran.ent",
        project_source=str(src),
        project_target="",
        type=3,
    )
    assert res["success"] is True
    assert res["planned"][0]["relative"] == "Config/MRTran.ent"
    assert res["planned"][0]["target_relative"] == "Config/DDVTran.ent"
