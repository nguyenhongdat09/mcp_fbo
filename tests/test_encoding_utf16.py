"""Unit tests for UTF-16/UTF-32 decode fixes (AC-ENC-*).

Covers docs/doc/gemini/GEMINI-mcp-encoding-utf16.md:
- search_files không skip file UTF-16 (BOM check trước _is_binary)
- query_database type=2 đọc được .sql UTF-16
- shared decode_bytes / detect_bom_encoding
- write_file preserve encoding cũ
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from fastbusiness_mcp.utils.file_utils import (
    decode_bytes,
    detect_bom_encoding,
    read_file,
    write_file,
)
from search_files import search_files
from xml_fbograph.utils.any_path import reset_sticky_context


@pytest.fixture(autouse=True)
def _reset_sticky():
    reset_sticky_context()
    yield
    reset_sticky_context()


@pytest.fixture
def enc_dir(tmp_path):
    root = tmp_path / "enc_proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "Web.config").write_text("<configuration/>", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# decode_bytes / detect_bom_encoding unit tests
# ---------------------------------------------------------------------------


def test_detect_bom_order_utf32_before_utf16():
    """AC-ENC-4 tiền đề: FF FE 00 00 phải ra utf-32, không nhầm utf-16."""
    assert detect_bom_encoding(b"\xff\xfe\x00\x00X") == "utf-32"
    assert detect_bom_encoding(b"\x00\x00\xfe\xffX") == "utf-32"
    assert detect_bom_encoding(b"\xff\xfeA\x00") == "utf-16"
    assert detect_bom_encoding(b"\xfe\xff\x00A") == "utf-16"
    assert detect_bom_encoding(b"\xef\xbb\xbfA") == "utf-8-sig"
    assert detect_bom_encoding(b"SELECT 1") is None


def test_decode_bytes_utf16_bom():
    text, enc = decode_bytes("SELECT * FROM dmct".encode("utf-16"))
    assert enc == "utf-16"
    assert "dmct" in text
    assert not text.startswith("\ufeff")  # codec 'utf-16' tự ăn BOM


def test_decode_bytes_utf16_no_bom():
    """AC-ENC-3: UTF-16LE KHÔNG BOM — utf-8 decode 'thành công giả' → retry utf-16."""
    raw = "SELECT * FROM dmct".encode("utf-16-le")  # không BOM
    text, enc = decode_bytes(raw)
    assert enc == "utf-16"
    assert "dmct" in text


def test_decode_bytes_utf32_bom():
    """AC-ENC-4: UTF-32LE BOM decode đúng, không nhầm utf-16."""
    raw = "SELECT 1".encode("utf-32-le")
    raw = b"\xff\xfe\x00\x00" + raw  # utf-32-le encode không tự thêm BOM
    text, enc = decode_bytes(raw)
    assert enc == "utf-32"
    assert "SELECT 1" in text


def test_decode_bytes_cp1258_vietnamese():
    """AC-ENC-7: cp1258 tiếng Việt không BOM → decode cp1258."""
    # 'ê' (0xEA) + 'µ'... dùng bytes cp1258 trực tiếp — utf-8 decode fail → cp1258
    raw = "SELECT * FROM dm".encode("ascii") + b"\xea" + b"kho"
    text, enc = decode_bytes(raw)
    assert enc == "cp1258"
    assert "dm" in text and "kho" in text


def test_decode_bytes_utf8_plain():
    text, enc = decode_bytes(b"SELECT 1")
    assert enc == "utf-8"
    assert text == "SELECT 1"


# ---------------------------------------------------------------------------
# search_files
# ---------------------------------------------------------------------------


def test_ac_enc_1_search_files_utf16_bom(enc_dir):
    """AC-ENC-1: search 'dmct' trên file .sql UTF-16LE BOM → match (trước: skip lặng)."""
    sql = enc_dir / "01.GenSQL_app.sql"
    sql.write_bytes("CREATE TABLE dmct (ma_ct char(3));\nGO\n".encode("utf-16"))

    res = search_files(root=str(enc_dir), pattern="dmct", include_glob="*.sql")
    assert res["success"] is True
    assert res["total_matches"] >= 1
    assert any("01.GenSQL_app.sql" in m["path"] for m in res["matches"])


def test_ac_enc_3_read_sql_file_utf16_no_bom(tmp_path):
    """AC-ENC-3: file UTF-16LE không BOM → decode_bytes retry utf-16 qua \\x00."""
    from query_database.query_resolver import read_sql_file

    f = tmp_path / "no_bom.sql"
    f.write_bytes("SELECT * FROM dmct".encode("utf-16-le"))  # không BOM

    sql, _label = read_sql_file(str(f))
    assert "\x00" not in sql
    assert "SELECT * FROM dmct" in sql

    content = read_file(str(f))
    assert content is not None and "dmct" in content


def test_ac_enc_5_real_binary_still_skipped(enc_dir):
    """AC-ENC-5: file binary thật (\\x00 random, không BOM) → search_files vẫn skip."""
    dll = enc_dir / "foo.dll"
    dll.write_bytes(b"\x01\x02\x00\x03dmct\xff\x00\xfe\x10")
    txt = enc_dir / "ok.txt"
    txt.write_text("dmct here", encoding="utf-8")

    res = search_files(root=str(enc_dir), pattern="dmct")
    assert res["success"] is True
    paths = [m["path"] for m in res["matches"]]
    assert any(p.endswith("ok.txt") for p in paths)
    assert not any(p.endswith("foo.dll") for p in paths)


# ---------------------------------------------------------------------------
# file_utils.read_file / write_file
# ---------------------------------------------------------------------------


def test_ac_enc_read_file_utf16(tmp_path):
    f = tmp_path / "a.ent"
    f.write_bytes("entity value &B;".encode("utf-16"))
    content = read_file(str(f))
    assert content is not None
    assert "entity value" in content


def test_ac_enc_8_write_file_preserves_utf16(tmp_path):
    """AC-ENC-8: ghi vào file UTF-16 có sẵn → vẫn UTF-16+BOM; file mới → utf-8."""
    f = tmp_path / "old.sql"
    f.write_bytes("SELECT 1".encode("utf-16"))
    assert write_file(str(f), "SELECT 2") is True
    raw = f.read_bytes()
    assert raw.startswith(b"\xff\xfe")  # BOM giữ nguyên
    assert "SELECT 2" in raw.decode("utf-16")

    f2 = tmp_path / "new.sql"
    assert write_file(str(f2), "SELECT 3") is True
    assert f2.read_bytes() == b"SELECT 3"  # utf-8 không BOM


# ---------------------------------------------------------------------------
# query_database type=2 (file .sql UTF-16)
# ---------------------------------------------------------------------------


def test_ac_enc_2_read_sql_file_utf16(tmp_path):
    """AC-ENC-2: query_type=2 trên file .sql UTF-16LE → execute đúng (không garbage)."""
    from query_database.query_resolver import read_sql_file

    sql_file = tmp_path / "script.sql"
    sql_file.write_bytes("SELECT * FROM dmct\nGO\nSELECT 2".encode("utf-16"))

    sql, label = read_sql_file(str(sql_file))
    assert "\x00" not in sql
    assert "SELECT * FROM dmct" in sql
    assert label.startswith("sql_file:")


def test_ac_enc_6_entity_resolver_utf16(tmp_path):
    """AC-ENC-6: file .xml/.ent UTF-16 vẫn resolve entity bình thường."""
    from find_entity_by_xml.entity_resolver import (
        clear_cache,
        get_entities_for_file,
        read_file_content,
    )

    proj = tmp_path / "PROJ16"
    ctrl = proj / "App_Data" / "Controllers" / "Grid"
    ctrl.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")

    (ctrl / "extFunc.ent").write_bytes(
        "function helperFromEntity() { return 42; }".encode("utf-16")
    )
    xml = ctrl / "T16.xml"
    xml.write_bytes(
        (
            '<?xml version="1.0"?>\n'
            "<!DOCTYPE grid [\n"
            '<!ENTITY extFunc SYSTEM "extFunc.ent">\n'
            "]>\n"
            '<grid id="T16"><text>&extFunc;</text></grid>\n'
        ).encode("utf-16")
    )

    clear_cache()
    try:
        content = read_file_content(xml)
        assert content is not None and "<!ENTITY extFunc" in content

        general, _param, _mt = get_entities_for_file(str(xml))
        assert "extFunc" in general
        assert general["extFunc"].get("systemUrl") == "extFunc.ent"
    finally:
        clear_cache()
