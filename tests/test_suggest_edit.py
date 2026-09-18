"""Unit tests for suggest_edit tool (read-only).

Covers AC-SE-1..7 từ docs/doc/gemini/GEMINI-mcp-path-resolver-suggest-edit.md.
Mọi test đều assert KHÔNG file nào bị ghi (mtime giữ nguyên).
"""

from __future__ import annotations

import os

import pytest
from pathlib import Path

from suggest_edit import suggest_edit
from xml_fbograph.utils.any_path import reset_sticky_context


@pytest.fixture(autouse=True)
def _reset_sticky():
    reset_sticky_context()
    yield
    reset_sticky_context()


@pytest.fixture
def grid_project(tmp_path):
    """Project có Grid controller với script + action + entity include."""
    proj = tmp_path / "GRID_PROJ"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")

    grid_dir = proj / "App_Data" / "Controllers" / "Grid"
    grid_dir.mkdir(parents=True, exist_ok=True)

    ent_file = grid_dir / "extFunc.ent"
    ent_file.write_text(
        "function helperFromEntity() {\n\treturn 42;\n}\n",
        encoding="utf-8",
    )

    xml_file = grid_dir / "SOTran.xml"
    xml_file.write_text(
        "\n".join(
            [
                '<?xml version="1.0"?>',
                "<!DOCTYPE grid [",
                '<!ENTITY extFunc SYSTEM "extFunc.ent">',
                "]>",
                '<grid id="SOTran">',
                "<script><text><![CDATA[",
                "function open$CreateVoucher(g) {",
                "\tvar f = g.parentForm;",
                "\tif (f) {",
                "\t\tf.request('GetCreatedVoucher');",
                "\t}",
                "\treturn true;",
                "}",
                "]]>",
                "&extFunc;",
                "</text></script>",
                '<action id="GetCreatedVoucher"><text><![CDATA[',
                "select top 1 stt_rec from fsdSttRecRef where ma_ct = 'SO'",
                "]]></text></action>",
                "<fields><field name=\"ma_kh\"/></fields>",
                "</grid>",
            ]
        ),
        encoding="utf-8",
    )
    return proj, xml_file, ent_file


def _mtime(p: Path) -> int:
    return os.stat(p).st_mtime_ns


def test_ac_se_1_symbol_suggest(grid_project):
    """AC-SE-1: symbol + new_string -> old_string exact, match_count=1, diff + post_edit_check."""
    _, xml_file, _ = grid_project
    before = _mtime(xml_file)
    res = suggest_edit(
        str(xml_file),
        symbol="open$CreateVoucher",
        new_string="function open$CreateVoucher(g) {\n\treturn false;\n}",
    )
    assert res["success"] is True
    assert res["origin"] == "file"
    assert res["target"]["kind"] == "js_function"
    assert res["match_count"] == 1
    assert res["expanded_for_uniqueness"] is False
    # old_string là text EXACT từ raw file (giữ nguyên \r\n của file vật lý)
    raw = xml_file.read_bytes().decode("utf-8")
    assert res["old_string"] in raw
    assert "function open$CreateVoucher(g) {" in res["old_string"]
    assert res["diff_preview"] and "open$CreateVoucher" in res["diff_preview"]
    assert res["post_edit_check"]["js_parse"] == "ok"
    assert res["post_edit_check"]["sql_parse"] == "ok"
    assert _mtime(xml_file) == before  # không ghi file


def test_ac_se_2_entity_origin(grid_project):
    """AC-SE-2: target trong .ent -> physical_file trỏ file include + post_edit_check skipped."""
    _, xml_file, ent_file = grid_project
    res = suggest_edit(
        str(xml_file),
        symbol="helperFromEntity",
        new_string="function helperFromEntity() {\n\treturn 43;\n}",
    )
    assert res["success"] is True
    assert res["origin"].startswith("entity")
    assert Path(res["physical_file"]).resolve() == ent_file.resolve()
    assert "function helperFromEntity()" in res["old_string"]
    assert res["post_edit_check"]["status"] == "skipped_entity"


def test_ac_se_3_expand_unique(tmp_path):
    """AC-SE-3: old_string trùng -> expand context tới unique; quá max_expand -> error."""
    f = tmp_path / "dup.js"
    f.write_text(
        "// header a\nvar x = 1;\n// mid\nvar x = 1;\n// tail\n",
        encoding="utf-8",
    )
    # Trùng 2 chỗ -> expand cho tới unique
    res = suggest_edit(str(f), start_line=2, end_line=2)
    assert res["success"] is True
    assert res["expanded_for_uniqueness"] is True
    assert res["match_count"] == 1
    assert "// header a" in res["old_string"]

    # Không expand được (max_expand=0) -> old_string_not_unique + occurrences
    res2 = suggest_edit(str(f), start_line=2, end_line=2, max_expand=0)
    assert res2["success"] is False
    assert res2["error_code"] == "old_string_not_unique"
    assert res2["match_count"] == 2
    assert len(res2["occurrences"]) == 2


def test_ac_se_4_bad_js_detected_before_write(tmp_path):
    """AC-SE-4: new_string lỗi cú pháp JS -> post_edit_check báo lỗi trước khi ghi."""
    f = tmp_path / "ok.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    before = _mtime(f)
    res = suggest_edit(
        str(f),
        symbol="ok",
        new_string="function ok( { syntax broken",
    )
    assert res["success"] is True
    assert res["post_edit_check"]["js_parse"] != "ok"
    assert res["post_edit_check"]["errors"]
    assert _mtime(f) == before


def test_ac_se_5_no_new_string(grid_project):
    """AC-SE-5: không new_string -> chỉ location + old_string, không diff."""
    _, xml_file, _ = grid_project
    res = suggest_edit(str(xml_file), symbol="open$CreateVoucher")
    assert res["success"] is True
    assert res["old_string"]
    assert res["diff_preview"] is None
    assert res["post_edit_check"] is None


def test_ac_se_6_missing_and_f_file(tmp_path):
    """AC-SE-6: file không tồn tại / .f -> error rõ, không ghi gì."""
    res = suggest_edit(str(tmp_path / "no_such_file.xml"), symbol="x")
    assert res["success"] is False
    assert res["error_code"] == "path_not_found"

    f_file = tmp_path / "enc.f"
    f_file.write_bytes(b"\x00\x01 encrypted")
    before = _mtime(f_file)
    res2 = suggest_edit(str(f_file), symbol="x")
    assert res2["success"] is False
    assert res2["error_code"] == "encrypted_file"
    assert _mtime(f_file) == before


def test_ac_se_7_cp1258_encoding(tmp_path):
    """AC-SE-7: encoding trả đúng cho file CP1258."""
    f = tmp_path / "cp1258.js"
    # byte 0xEA không hợp lệ utf-8 -> detect cp1258
    f.write_bytes(b"var s = 'ti\xea ng';\n")
    res = suggest_edit(str(f), start_line=1, end_line=1)
    assert res["success"] is True
    assert res["encoding"] == "cp1258"


def test_ac_se_block_and_old_string_modes(grid_project, tmp_path):
    """Bổ sung: block mode trên controller + old_string truyền tay."""
    _, xml_file, _ = grid_project
    res = suggest_edit(str(xml_file), block="action:GetCreatedVoucher")
    assert res["success"] is True
    assert res["target"]["kind"] == "sql_block"
    assert "fsdSttRecRef" in res["old_string"]
    raw = xml_file.read_bytes().decode("utf-8")
    assert res["old_string"] in raw

    # old_string truyền tay không thấy -> closest_match
    res2 = suggest_edit(str(xml_file), old_string="function khongCoDau() {}")
    assert res2["success"] is False
    assert res2["error_code"] == "old_string_not_found"

    # old_string truyền tay đúng -> match_count=1
    res3 = suggest_edit(str(xml_file), old_string="f.request('GetCreatedVoucher');")
    assert res3["success"] is True
    assert res3["match_count"] == 1


def test_ac_se_relative_path_via_sticky(grid_project):
    """suggest_edit.file_path qua resolver: relative chạy sau call abs."""
    _, xml_file, _ = grid_project
    suggest_edit(str(xml_file), symbol="open$CreateVoucher")
    res = suggest_edit("Grid/SOTran.xml", symbol="open$CreateVoucher")
    assert res["success"] is True
