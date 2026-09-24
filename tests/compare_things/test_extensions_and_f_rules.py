"""Unit tests for compare_things extension rules: all extensions except .f.

Specification: docs/doc/doc_fix/FIX-compare_things-all-extensions-except-f.md
- TC-EXT-01: kind=file hai .txt khác 1 dòng -> different + line ranges
- TC-EXT-02: kind=file hai .ent identical -> identical
- TC-EXT-03: kind=file file_a (hoặc file_b) đuôi .f -> unsupported_extension_f / không diff content
- TC-EXT-04: kind=folder có a.f + b.txt -> a.f skipped; b.txt so bình thường
- TC-EXT-05: kind=xml object Include/x.ent -> invalid_object + hướng dẫn kind=file (P0)
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from compare_things import compare_things
from compare_things.file_compare import compare_files


def test_tc_ext_01_txt_different_line_ranges(tmp_path: Path):
    """TC-EXT-01: kind=file hai .txt khác 1 dòng -> different + line ranges."""
    fa = tmp_path / "test1.txt"
    fb = tmp_path / "test2.txt"
    fa.write_text("line 1\nline 2 original\nline 3\n", encoding="utf-8")
    fb.write_text("line 1\nline 2 modified\nline 3\n", encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    assert res["summary"]["status"] == "different"
    assert res["summary"]["identical_content"] is False

    compared = res["compared"][0]
    hunks = compared["content"]["hunks"]
    assert len(hunks) >= 1
    hunk = hunks[0]
    assert hunk["a_line_start"] == 2
    assert hunk["b_line_start"] == 2


def test_tc_ext_02_ent_identical(tmp_path: Path):
    """TC-EXT-02: kind=file hai .ent identical -> identical."""
    fa = tmp_path / "EntityConfig.ent"
    fb = tmp_path / "EntityConfig_copy.ent"
    content = '<!ENTITY % CommonConfig SYSTEM "Common.ent">\n%CommonConfig;\n'
    fa.write_text(content, encoding="utf-8")
    fb.write_text(content, encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    assert res["summary"]["status"] == "identical"
    assert res["summary"]["identical_content"] is True
    assert res["compared"][0]["content"]["hunk_count"] == 0


def test_tc_ext_03_file_f_unsupported_extension(tmp_path: Path):
    """TC-EXT-03: kind=file file_a đuôi .f -> unsupported_extension_f / không diff content."""
    fa = tmp_path / "AccountBalanceAdjustment.f"
    fb = tmp_path / "AccountBalanceAdjustment.xml"
    fa.write_bytes(b"\x00\x01\x02ENCRYPTED")
    fb.write_text("<controller></controller>", encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is False
    assert res["error_code"] == "unsupported_extension_f"
    assert "không so sánh" in res["message"].lower() or ".f" in res["message"].lower()
    assert ".f" in res["error"].lower()

    # Thử với .F (chữ hoa)
    fa_upper = tmp_path / "Something.F"
    fa_upper.write_bytes(b"\x00\x01\x02ENCRYPTED")
    res_upper = compare_things(kind="file", file_a=str(fb), file_b=str(fa_upper))
    assert res_upper["success"] is False
    assert res_upper["error_code"] == "unsupported_extension_f"

    # Gọi trực tiếp compare_files
    res_direct = compare_files(file_a=str(fa), file_b=str(fb))
    assert res_direct["status"] == "skipped_encrypted_ext"
    assert res_direct["error_code"] == "unsupported_extension_f"
    assert res_direct["content"]["hunk_count"] == 0


def test_tc_ext_03b_file_xsd_unsupported(tmp_path: Path):
    """kind=file file đuôi .xsd -> unsupported_extension_xsd / không diff content."""
    fa = tmp_path / "Rpt.xsd"
    fb = tmp_path / "Rpt.xml"
    fa.write_text("<xs:schema/>", encoding="utf-8")
    fb.write_text("<controller></controller>", encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is False
    assert res["error_code"] == "unsupported_extension_xsd"

    res_direct = compare_files(file_a=str(fa), file_b=str(fb))
    assert res_direct["error_code"] == "unsupported_extension_xsd"
    assert res_direct["content"]["hunk_count"] == 0

    # kind=xml với object .xsd
    proj_src = tmp_path / "px_src"
    proj_tgt = tmp_path / "px_tgt"
    (proj_src / "App_Data" / "Controllers" / "Templates" / "Rpt").mkdir(parents=True)
    (proj_tgt / "App_Data" / "Controllers" / "Templates" / "Rpt").mkdir(parents=True)
    (proj_src / "App_Data" / "Controllers" / "Templates" / "Rpt" / "r.xsd").write_text("<xs:schema/>")
    res_xml = compare_things(
        kind="xml",
        project_source=str(proj_src),
        project_target=str(proj_tgt),
        object="Templates/Rpt/r.xsd",
    )
    assert res_xml["success"] is False
    assert res_xml["error_code"] == "unsupported_extension_xsd"


def test_tc_ext_04_folder_skips_f(tmp_path: Path):
    """TC-EXT-04: kind=folder có a.f + b.txt -> a.f skipped; b.txt so bình thường."""
    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # File .f xuất hiện ở dir_a (hoặc cả hai bên)
    (dir_a / "voucher.f").write_bytes(b"ENCRYPTED_A")
    (dir_b / "voucher.f").write_bytes(b"ENCRYPTED_B")
    (dir_a / "extra.F").write_bytes(b"ENCRYPTED_EXTRA")

    # File .xsd schema — cũng bị loại khỏi so sánh
    (dir_a / "report.xsd").write_text("<xs:schema>a</xs:schema>", encoding="utf-8")
    (dir_b / "report.xsd").write_text("<xs:schema>b</xs:schema>", encoding="utf-8")

    # File .txt hợp lệ
    (dir_a / "readme.txt").write_text("same content", encoding="utf-8")
    (dir_b / "readme.txt").write_text("same content", encoding="utf-8")

    # File .ent khác nội dung
    (dir_a / "include.ent").write_text("a=1\n", encoding="utf-8")
    (dir_b / "include.ent").write_text("a=2\n", encoding="utf-8")

    res = compare_things(
        kind="folder",
        folder_a=str(dir_a),
        folder_b=str(dir_b),
        compare_content=True,
    )
    assert res["success"] is True
    summary = res["summary"]

    # File .f không được xuất hiện trong missing hay different
    assert "voucher.f" not in summary["missing_on_a"]
    assert "voucher.f" not in summary["missing_on_b"]
    assert "voucher.f" not in summary["different_content"]
    assert "voucher.f" not in summary["different_meta"]
    assert "extra.f" not in summary["missing_on_a"]
    assert "extra.f" not in summary["missing_on_b"]
    assert "extra.F" not in summary["missing_on_b"]

    # File .xsd cũng không xuất hiện trong missing hay different
    assert "report.xsd" not in summary["missing_on_a"]
    assert "report.xsd" not in summary["missing_on_b"]
    assert "report.xsd" not in summary["different_content"]
    assert "report.xsd" not in summary["different_meta"]

    # summary đếm đúng skipped_f_count (.f + .xsd)
    assert summary["skipped_f_count"] >= 3

    # File .ent và .txt được so sánh bình thường
    assert "readme.txt" not in summary["different_content"]
    assert "include.ent" in summary["different_content"]


def test_tc_ext_05_xml_object_ent_rejected_suggest_file(tmp_path: Path):
    """TC-EXT-05: kind=xml object Include/x.ent -> invalid_object + hướng dẫn kind=file (P0)."""
    proj_src = tmp_path / "proj_src"
    proj_tgt = tmp_path / "proj_tgt"
    (proj_src / "App_Data" / "Controllers" / "Include").mkdir(parents=True)
    (proj_tgt / "App_Data" / "Controllers" / "Include").mkdir(parents=True)

    (proj_src / "App_Data" / "Controllers" / "Include" / "voucher.ent").write_text("<!ENTITY test '1'>", encoding="utf-8")
    (proj_tgt / "App_Data" / "Controllers" / "Include" / "voucher.ent").write_text("<!ENTITY test '2'>", encoding="utf-8")

    res = compare_things(
        kind="xml",
        project_source=str(proj_src),
        project_target=str(proj_tgt),
        object="Include/voucher.ent",
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_object"
    assert "kind='file'" in res["error"]
    assert "kind='file'" in res["message"] or "kind='folder'" in res["message"]

    # Thử với .txt
    res_txt = compare_things(
        kind="xml",
        project_source=str(proj_src),
        project_target=str(proj_tgt),
        object="Include/voucher.txt",
    )
    assert res_txt["success"] is False
    assert res_txt["error_code"] == "invalid_object"

    # Thử với .f qua kind=xml
    res_f = compare_things(
        kind="xml",
        project_source=str(proj_src),
        project_target=str(proj_tgt),
        object="Filter/voucher.f",
    )
    assert res_f["success"] is False
    assert res_f["error_code"] == "unsupported_extension_f"
