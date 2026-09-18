"""Tests for check_things + get_xml_entities mode='checking' (AC-CHK-*).

Covers docs/doc/gemini/GEMINI-mcp-check-things.md.
"""

from __future__ import annotations

import pytest

from check_things import check_entities
from check_things.file_resolver import resolve_checking_files
from find_entity_by_xml import get_xml_entities
from find_entity_by_xml.entity_resolver import clear_cache
from xml_fbograph.utils.any_path import reset_sticky_context


@pytest.fixture(autouse=True)
def _reset():
    reset_sticky_context()
    clear_cache()
    yield
    clear_cache()
    reset_sticky_context()


@pytest.fixture
def chk_project(tmp_path):
    """Project đích có file Main.xml nhiều lỗi + Clean.xml sạch."""
    proj = tmp_path / "CHK_PROJ"
    d = proj / "App_Data" / "Controllers" / "Dir"
    d.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")

    # File chính: dùng &entA; &entChain; &UndeclaredB; &inlined;
    # - extMiss → SYSTEM Missing.ent THIẾU (missing_files, is_parameter=False)
    # - ExtMissP → param entity SYSTEM MissingP.ent THIẾU (is_parameter=True)
    # - entA.ent chứa &UndeclaredC; → undeclared TRANSITIVE (BFS)
    # - entChain.ent chứa &entDeep; → entDeep declared → OK
    # - &Commented; chỉ trong comment → KHÔNG tính
    (d / "Main.xml").write_text(
        "\n".join(
            [
                '<?xml version="1.0"?>',
                "<!DOCTYPE dir [",
                '<!ENTITY entA SYSTEM "entA.ent">',
                '<!ENTITY entChain SYSTEM "entChain.ent">',
                '<!ENTITY extMiss SYSTEM "Missing.ent">',
                '<!ENTITY % ExtMissP SYSTEM "MissingP.ent">',
                '<!ENTITY entDeep "noi dung deep">',
                '<!ENTITY inlined "inline &entDeep;">',
                "%ExtMissP;",
                "]>",
                '<dir id="Main">',
                "<text>&entA; &entChain; &UndeclaredB; &inlined;</text>",
                "<!-- &Commented; khong tinh -->",
                "</dir>",
            ]
        ),
        encoding="utf-8",
    )
    (d / "entA.ent").write_text("text dung &UndeclaredC;", encoding="utf-8")
    (d / "entChain.ent").write_text("x &entDeep;", encoding="utf-8")

    (d / "entClean.ent").write_text("clean content, no refs", encoding="utf-8")
    (d / "Clean.xml").write_text(
        "\n".join(
            [
                '<?xml version="1.0"?>',
                "<!DOCTYPE dir [",
                '<!ENTITY entClean SYSTEM "entClean.ent">',
                "]>",
                '<dir id="Clean"><text>&entClean;</text></dir>',
            ]
        ),
        encoding="utf-8",
    )
    return proj


@pytest.fixture
def src_project(tmp_path):
    """Project NGUỒN chứa file thiếu + Main.xml khai &UndeclaredB;."""
    proj = tmp_path / "SRC_PROJ"
    d = proj / "App_Data" / "Controllers" / "Dir"
    d.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
    # File thiếu ở đích nhưng CÓ ở nguồn
    (d / "Missing.ent").write_text("entity content from source", encoding="utf-8")
    (d / "MissingP.ent").write_text("param ent", encoding="utf-8")
    # Main.xml trên source khai UndeclaredB → undeclared ở đích → status='ok'
    (d / "Main.xml").write_text(
        "\n".join(
            [
                '<?xml version="1.0"?>',
                "<!DOCTYPE dir [",
                '<!ENTITY entA SYSTEM "entA.ent">',
                '<!ENTITY entChain SYSTEM "entChain.ent">',
                '<!ENTITY extMiss SYSTEM "Missing.ent">',
                '<!ENTITY % ExtMissP SYSTEM "MissingP.ent">',
                '<!ENTITY entDeep "noi dung deep">',
                '<!ENTITY inlined "inline &entDeep;">',
                '<!ENTITY UndeclaredB "khai tren source">',
                "%ExtMissP;",
                "]>",
                '<dir id="Main"><text>&entA;</text></dir>',
            ]
        ),
        encoding="utf-8",
    )
    (d / "entA.ent").write_text("src entA", encoding="utf-8")
    (d / "entChain.ent").write_text("src entChain", encoding="utf-8")
    return proj


def _undeclared_names(res):
    return {r["entity_name"] for r in res["undeclared_entities"]}


# ---------------------------------------------------------------------------
# AC-CHK-* module-level (check_entities trực tiếp)
# ---------------------------------------------------------------------------


def test_ac_chk_1_undeclared_entity(chk_project):
    """AC-CHK-1: &UndeclaredB; dùng mà DOCTYPE không khai → undeclared_entities."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = check_entities([str(main)])
    assert res["success"] is True
    assert "UndeclaredB" in _undeclared_names(res)
    assert res["summary"]["undeclared_count"] >= 1


def test_ac_chk_2_missing_system_file(chk_project):
    """AC-CHK-2: SYSTEM entity trỏ file không tồn tại → missing_files."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = check_entities([str(main)])
    miss = res["missing_files"]
    paths = {r["missing_path"] for r in miss}
    assert any(p.endswith("Missing.ent") for p in paths)
    assert any(p.endswith("MissingP.ent") for p in paths)
    # param entity row có is_parameter=True
    prow = next(r for r in miss if r["missing_path"].endswith("MissingP.ent"))
    assert prow["is_parameter"] is True
    assert res["summary"]["missing_count"] >= 1
    assert res["summary"]["total"] >= 2


def test_ac_chk_4_clean_file(chk_project):
    """AC-CHK-4: file sạch → summary.total=0, mảng rỗng."""
    clean = chk_project / "App_Data" / "Controllers" / "Dir" / "Clean.xml"
    res = check_entities([str(clean)])
    assert res["success"] is True
    assert res["summary"]["total"] == 0
    assert res["missing_files"] == []
    assert res["undeclared_entities"] == []
    assert res["per_xml_summary"] == []
    assert res["summary"]["all_missing_have_source"] is True


def test_ac_chk_5_aspx_skipped(chk_project):
    """AC-CHK-5: input .aspx → skipped_files + warning, không crash."""
    aspx = chk_project / "Main" / "page.aspx"
    aspx.parent.mkdir(parents=True, exist_ok=True)
    aspx.write_text("<%@ Page %>", encoding="utf-8")

    res = check_entities([str(aspx)])
    assert res["success"] is True
    assert res["skipped_files"] == [os_norm(aspx)]
    assert res["checked_files"] == []
    assert any("aspx_resolution_not_supported" in w for w in res["warnings"])


def os_norm(p):
    import os

    return os.path.normpath(str(p))


def test_ac_chk_6_xml_missing_f_fallback(tmp_path):
    """AC-CHK-6: .xml thiếu nhưng .f tồn tại → dùng .f; cả 2 thiếu →
    row missing_path = chính file chọn."""
    proj = tmp_path / "F_PROJ"
    d = proj / "App_Data" / "Controllers" / "Dir"
    d.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
    # Only.f tồn tại (nội dung XML text — entity_resolver đọc bytes thường)
    (d / "Only.f").write_text(
        '<?xml version="1.0"?><!DOCTYPE dir [<!ENTITY a "v">]><dir><text>&a;</text></dir>',
        encoding="utf-8",
    )

    resolved = resolve_checking_files([str(d / "Only.xml")])
    assert len(resolved["xml_files"]) == 1
    assert resolved["xml_files"][0].lower().endswith(".f")

    res = check_entities([str(d / "Only.xml")])
    assert res["success"] is True
    assert res["summary"]["total"] == 0  # .f parse OK, &a; declared

    # Cả .xml và .f đều thiếu → missing_path = file chọn
    res2 = check_entities([str(d / "Nothing.xml")])
    assert res2["summary"]["missing_count"] == 1
    assert res2["missing_files"][0]["missing_path"].endswith("Nothing.xml")


def test_ac_chk_8_transitive_undeclared(chk_project):
    """AC-CHK-8: &entA; → entA.ent chứa &UndeclaredC; undeclared → BFS bắt được."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = check_entities([str(main)])
    assert "UndeclaredC" in _undeclared_names(res)


def test_ac_chk_9_comment_not_counted(chk_project):
    """AC-CHK-9: &Commented; trong <!-- --> → KHÔNG tính undeclared."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = check_entities([str(main)])
    assert "Commented" not in _undeclared_names(res)


def test_ac_chk_declared_chain_ok(chk_project):
    """&entChain; → entChain.ent dùng &entDeep; đã khai báo → không undeclared."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = check_entities([str(main)])
    assert "entDeep" not in _undeclared_names(res)
    assert "entA" not in _undeclared_names(res)
    assert "entChain" not in _undeclared_names(res)


# ---------------------------------------------------------------------------
# AC-CHK-* qua get_xml_entities mode='checking'
# ---------------------------------------------------------------------------


def test_ac_chk_3_source_roots_mapping(chk_project, src_project):
    """AC-CHK-3: source_roots → missing row có source_index/label/path;
    undeclared khai ở source → status='ok'."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = get_xml_entities(
        str(main), mode="checking", source_roots=[str(src_project)]
    )
    assert res["success"] is True
    chk = res["checking"]

    miss = {r["missing_path"]: r for r in chk["missing_files"]}
    row = next(r for p, r in miss.items() if p.endswith("Missing.ent"))
    assert row["source_index"] == 0
    assert row["source_label"] == "Nguồn 1"
    assert row["source_file_path"].endswith("Missing.ent")

    und = {r["entity_name"]: r for r in chk["undeclared_entities"]}
    assert und["UndeclaredB"]["status"] == "ok"
    assert und["UndeclaredB"]["source_index"] == 0
    assert und["UndeclaredB"]["decl_file"]  # có vị trí khai báo trên source
    # UndeclaredC không khai trên source → vẫn missing
    assert und["UndeclaredC"]["status"] == "missing"


def test_ac_chk_7_combine_checking_and_list(chk_project):
    """AC-CHK-7: mode=['checking','list'] → trả cả entities + checking."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = get_xml_entities(str(main), mode=["checking", "list"])
    assert res["success"] is True
    assert "checking" in res
    assert "entities" in res  # list mode output
    names = {e["name"] for e in res["entities"]}
    assert "entA" in names


def test_ac_chk_10_old_modes_unchanged(chk_project):
    """AC-CHK-10: mode content/path/list không đổi behavior."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    res = get_xml_entities(str(main), entities=["inlined"], mode="content")
    assert res["success"] is True
    assert "checking" not in res
    ent = res["entities"][0]
    assert ent["found"] is True
    assert "entDeep" in ent["content"]

    res2 = get_xml_entities(str(main), mode="list")
    assert res2["success"] is True
    assert "checking" not in res2
    assert len(res2["entities"]) >= 1


def test_ac_chk_per_xml_and_errors_shape(chk_project):
    """Response shape: per_xml_summary chỉ file có lỗi + errors[] typed."""
    main = chk_project / "App_Data" / "Controllers" / "Dir" / "Main.xml"
    clean = chk_project / "App_Data" / "Controllers" / "Dir" / "Clean.xml"
    res = check_entities([str(main), str(clean)])
    px = res["per_xml_summary"]
    assert len(px) == 1  # chỉ Main.xml
    assert px[0]["xml_short"] == "Dir/Main.xml"
    assert px[0]["missing_count"] >= 1
    assert px[0]["undeclared_count"] >= 1
    types = {e["type"] for e in res["errors"]}
    assert "missing_file" in types and "undeclared_entity" in types
