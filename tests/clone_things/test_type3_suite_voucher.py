"""Tests for clone_things type=3 suite voucher expansion (AC-SUITE-*).

Covers docs/doc/gemini/GEMINI-clone-things-suite-voucher.md:
- get_suite_candidates mở rộng (Query/Notify/Report.Config/Templates.Rpt/
  Include/Command/GNEditCheckTable, Include/{c}Grid.ent)
- prefix-family scan whitelist dirs (MR* → DDV*)
- rename_suite_basename cho prefix file + Extra.{p}Detail + GNEditCheckTable{c}
- Main/*.aspx bất quy tắc → warning suite_aspx_missing, không prefix-scan
"""

from __future__ import annotations

import pytest

from clone_things import clone_things
from clone_things.type3_file_clone import (
    expand_suite_prefix_files,
    rename_suite_basename,
    suite_prefix,
)


@pytest.fixture
def voucher_project(tmp_path):
    """Source project giả lập suite MRTran (prefix MR) theo fixture doc."""
    src = tmp_path / "FBISP2421"
    tgt = tmp_path / "FBISP2421_TGT"
    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)
    (src / "Web.config").write_text("<configuration/>", encoding="utf-8")

    def w(rel: str, text: str = "x"):
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    # Templated {c} files
    w("App_Data/Controllers/Grid/MRTran.xml")
    w("App_Data/Controllers/Filter/MRTran.xml")
    w("App_Data/Controllers/Dir/MRTran.xml")
    w("App_Data/Controllers/Lookup/MRTran.xml")
    w("App_Data/Controllers/Query/MRTran.xml")
    w("App_Data/Controllers/Notify/MRTran.xml")
    w("App_Data/Controllers/Report/MRTran.xml")
    w("App_Data/Controllers/Report/Config/MRTran.ent")
    w("App_Data/Controllers/Templates/Rpt/MRTran.xsd")
    w("App_Data/Controllers/Include/Command/GNEditCheckTableMRTran.txt")

    # Prefix-family {p}* files (basename KHÔNG chứa MRTran)
    w("App_Data/Controllers/Grid/MRApproval.xml")
    w("App_Data/Controllers/Grid/MRApprovalItem.xml")
    w("App_Data/Controllers/Grid/MRApprovalFiles.xml")
    w("App_Data/Controllers/Grid/MRDetail.xml")
    w("App_Data/Controllers/Filter/MRApproval.xml")
    w("App_Data/Controllers/Include/XML/MRReferenceFields.txt")
    w("App_Data/Controllers/Include/XML/MRReferenceView.txt")
    w("App_Data/Controllers/Include/XML/Config/Fields/MRField.txt")
    w("App_Data/Controllers/Include/XML/Config/Fields/MRView.txt")
    w("App_Data/Controllers/Include/Extra.MRDetail")
    w("App_Data/Controllers/Include/MRGrid.ent")  # {c}Grid.ent dạng prefix

    # Trang .aspx tên bất quy tắc — KHÔNG được scan
    w("Main/inctpx0.aspx")

    # File prefix gần giống nhưng KHÔNG phải MR — không được quét
    w("App_Data/Controllers/Include/hrRMRequest.txt")
    w("App_Data/Controllers/Grid/PX0.xml")

    return src, tgt


def _pairs(res):
    """(relative, target_relative) từ planned."""
    return {p["relative"]: p["target_relative"] for p in res["planned"]}


# ---------------------------------------------------------------------------
# Helpers unit
# ---------------------------------------------------------------------------


def test_suite_prefix_helper():
    assert suite_prefix("MRTran") == "MR"
    assert suite_prefix("DDVTran") == "DDV"
    assert suite_prefix("InputInvoice") == "InputInvoice"
    assert suite_prefix("SimpleCtrl") == "SimpleCtrl"


def test_rename_suite_basename_unit():
    # prefix file
    assert (
        rename_suite_basename("MRApproval.xml", "MR", "DDV", "MRTran", "DDVTran")
        == "DDVApproval.xml"
    )
    # templated {c}
    assert (
        rename_suite_basename("MRTran.xml", "MR", "DDV", "MRTran", "DDVTran")
        == "DDVTran.xml"
    )
    # Extra.{p}Detail lệch prefix
    assert (
        rename_suite_basename("Extra.MRDetail", "MR", "DDV", "MRTran", "DDVTran")
        == "Extra.DDVDetail"
    )
    # GNEditCheckTable{c}
    assert (
        rename_suite_basename(
            "GNEditCheckTableMRTran.txt", "MR", "DDV", "MRTran", "DDVTran"
        )
        == "GNEditCheckTableDDVTran.txt"
    )
    # không match gì → giữ nguyên
    assert (
        rename_suite_basename("random.txt", "MR", "DDV", "MRTran", "DDVTran")
        == "random.txt"
    )


# ---------------------------------------------------------------------------
# AC-SUITE-* từ doc
# ---------------------------------------------------------------------------


def test_ac_suite_1_prefix_expansion_full(voucher_project):
    """AC-SUITE-1: suite:MRTran -> DDVTran dry-run → planned gồm Query/Notify/
    Report.Config/Include/Command/GNEditCheckTable/Include/XML/Fields + prefix."""
    src, tgt = voucher_project
    res = clone_things(
        object="suite:MRTran -> DDVTran",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    pairs = _pairs(res)

    # Templated mới
    assert pairs["App_Data/Controllers/Query/MRTran.xml"] == (
        "App_Data/Controllers/Query/DDVTran.xml"
    )
    assert pairs["App_Data/Controllers/Notify/MRTran.xml"] == (
        "App_Data/Controllers/Notify/DDVTran.xml"
    )
    assert pairs["App_Data/Controllers/Report/Config/MRTran.ent"] == (
        "App_Data/Controllers/Report/Config/DDVTran.ent"
    )
    assert pairs["App_Data/Controllers/Templates/Rpt/MRTran.xsd"] == (
        "App_Data/Controllers/Templates/Rpt/DDVTran.xsd"
    )
    assert pairs["App_Data/Controllers/Include/Command/GNEditCheckTableMRTran.txt"] == (
        "App_Data/Controllers/Include/Command/GNEditCheckTableDDVTran.txt"
    )

    # ≥ 18 file (doc AC-SUITE-1)
    assert len(pairs) >= 18
    assert res["meta"]["total_expanded"] == len(pairs)
    # warning prefix expansion
    assert any("suite_prefix_expanded" in w for w in res["warnings"])


def test_ac_suite_2_prefix_rename(voucher_project):
    """AC-SUITE-2: mọi file startswith MR → rename DDV; templated {c} vẫn đúng."""
    src, tgt = voucher_project
    res = clone_things(
        object="suite:MRTran -> DDVTran",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    pairs = _pairs(res)

    assert pairs["App_Data/Controllers/Grid/MRApproval.xml"] == (
        "App_Data/Controllers/Grid/DDVApproval.xml"
    )
    assert pairs["App_Data/Controllers/Grid/MRApprovalItem.xml"] == (
        "App_Data/Controllers/Grid/DDVApprovalItem.xml"
    )
    assert pairs["App_Data/Controllers/Grid/MRDetail.xml"] == (
        "App_Data/Controllers/Grid/DDVDetail.xml"
    )
    assert pairs["App_Data/Controllers/Filter/MRApproval.xml"] == (
        "App_Data/Controllers/Filter/DDVApproval.xml"
    )
    assert pairs["App_Data/Controllers/Include/XML/Config/Fields/MRField.txt"] == (
        "App_Data/Controllers/Include/XML/Config/Fields/DDVField.txt"
    )
    assert pairs["App_Data/Controllers/Include/XML/Config/Fields/MRView.txt"] == (
        "App_Data/Controllers/Include/XML/Config/Fields/DDVView.txt"
    )
    assert pairs["App_Data/Controllers/Include/MRGrid.ent"] == (
        "App_Data/Controllers/Include/DDVGrid.ent"
    )
    # templated {c} vẫn đúng
    assert pairs["App_Data/Controllers/Grid/MRTran.xml"] == (
        "App_Data/Controllers/Grid/DDVTran.xml"
    )


def test_ac_suite_3_extra_prefix_pattern(voucher_project):
    """AC-SUITE-3: Extra.MRDetail → Extra.DDVDetail (pattern lệch prefix)."""
    src, tgt = voucher_project
    res = clone_things(
        object="suite:MRTran -> DDVTran",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    pairs = _pairs(res)
    assert pairs["App_Data/Controllers/Include/Extra.MRDetail"] == (
        "App_Data/Controllers/Include/Extra.DDVDetail"
    )


def test_ac_suite_4_aspx_not_scanned_warns(voucher_project):
    """AC-SUITE-4: Main/inctpx0.aspx KHÔNG vào planned; warning suite_aspx_missing."""
    src, tgt = voucher_project
    res = clone_things(
        object="suite:MRTran -> DDVTran",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    rels = list(_pairs(res).keys())
    assert not any(r.startswith("Main/") for r in rels)
    assert "Main/inctpx0.aspx" not in rels
    assert any("suite_aspx_missing" in w for w in res["warnings"])


def test_ac_suite_5_no_rename_also_expands(voucher_project):
    """AC-SUITE-5: suite:MRTran (không rename) → prefix files expand (rel, rel)."""
    src, tgt = voucher_project
    res = clone_things(
        object="suite:MRTran",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    assert res["success"] is True
    pairs = _pairs(res)
    # prefix file vẫn vào planned, giữ nguyên tên
    assert pairs["App_Data/Controllers/Grid/MRApproval.xml"] == (
        "App_Data/Controllers/Grid/MRApproval.xml"
    )
    assert pairs["App_Data/Controllers/Include/Extra.MRDetail"] == (
        "App_Data/Controllers/Include/Extra.MRDetail"
    )
    assert pairs["App_Data/Controllers/Query/MRTran.xml"] == (
        "App_Data/Controllers/Query/MRTran.xml"
    )
    assert any("suite_prefix_expanded" in w for w in res["warnings"])


def test_ac_suite_6_similar_prefix_not_scanned(voucher_project):
    """AC-SUITE-6: hrRMRequest.txt / PX0.xml (prefix gần giống) → KHÔNG quét."""
    src, tgt = voucher_project
    res = clone_things(
        object="suite:MRTran -> DDVTran",
        project_source=str(src),
        project_target=str(tgt),
        type=3,
    )
    rels = list(_pairs(res).keys())
    assert "App_Data/Controllers/Include/hrRMRequest.txt" not in rels
    assert "App_Data/Controllers/Grid/PX0.xml" not in rels


def test_ac_suite_7_empty_suite_unchanged(tmp_path):
    """AC-SUITE-7: suite: trên source không file nào → suite_empty như cũ."""
    src = tmp_path / "empty_src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "Web.config").write_text("<configuration/>", encoding="utf-8")

    res = clone_things(
        object="suite:ZZZTran",
        project_source=str(src),
        type=3,
    )
    assert res["success"] is False
    assert res["error_code"] == "suite_empty"
    assert any("suite_empty" in w for w in res["warnings"])
