"""Unit tests for search_files tool.

Covers AC-SF-1 to AC-SF-4 from docs/doc/gemini/GEMINI-mcp-agent-gaps.md.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from search_files import search_files


@pytest.fixture
def search_dir(tmp_path):
    root = tmp_path / "project_root"
    root.mkdir(parents=True, exist_ok=True)

    # ClientScript/jAjax.js
    cs = root / "ClientScript"
    cs.mkdir(parents=True, exist_ok=True)
    js_content = """
    function send() {
        // Calling acceptSendMail helper
        acceptSendMail(data, options);
    }
    """
    (cs / "jAjax.js").write_text(js_content, encoding="utf-8")

    # Main/Uploads/AjaxWeb.aspx
    main = root / "Main" / "Uploads"
    main.mkdir(parents=True, exist_ok=True)
    (main / "AjaxWeb.aspx").write_text("<div>acceptSendMail</div>", encoding="utf-8")

    # Denied file: Controllers/Dir/Test.f
    ctrl = root / "Controllers" / "Dir"
    ctrl.mkdir(parents=True, exist_ok=True)
    (ctrl / "Test.f").write_bytes(b"acceptSendMail inside encrypted f file")

    # Binary file: bin/foo.dll
    bdir = root / "bin"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "foo.dll").write_bytes(b"\x00\x01\x02acceptSendMail\x00")

    # Many matches file for limit testing
    many_file = root / "many.txt"
    many_lines = ["line with keyword match\n" for _ in range(200)]
    many_file.write_text("".join(many_lines), encoding="utf-8")

    return root


def test_ac_sf_1_search_pattern_found(search_dir):
    """AC-SF-1: Search acceptSendMail duoi ClientScript hoac project root -> >=1 hit."""
    res = search_files(
        root=str(search_dir),
        pattern="acceptSendMail",
    )
    assert res["success"] is True
    assert res["total_matches"] >= 2
    paths = [m["path"] for m in res["matches"]]
    assert any("ClientScript/jAjax.js" in p for p in paths)
    assert any("Main/Uploads/AjaxWeb.aspx" in p for p in paths)


def test_ac_sf_2_f_and_binary_not_searched(search_dir):
    """AC-SF-2: *.f va file binary khong bi doc/khop."""
    res = search_files(
        root=str(search_dir),
        pattern="acceptSendMail",
    )
    assert res["success"] is True
    paths = [m["path"] for m in res["matches"]]
    assert not any(p.endswith(".f") for p in paths)
    assert not any(p.endswith(".dll") for p in paths)


def test_ac_sf_3_max_total_matches_truncated(search_dir):
    """AC-SF-3: Vuot max_total_matches -> truncated=true, khong no token."""
    res = search_files(
        root=str(search_dir),
        pattern="match",
        include_glob="many.txt",
        max_matches_per_file=20,
        max_total_matches=10,
    )
    assert res["success"] is True
    assert len(res["matches"]) == 10
    assert res["truncated"] is True


def test_ac_sf_4_root_not_found():
    """AC-SF-4: root khong ton tai -> error ro rang."""
    res = search_files(
        root="E:/Path/Does/Not/Exist/12345",
        pattern="test",
    )
    assert res["success"] is False
    assert res["error_code"] == "root_not_found"


def test_ac_sf2_1_and_sf2_4_priority_candidate_sorting(tmp_path):
    """AC-SF2-1 & AC-SF2-4: Ưu tiên candidate có tên/custom prefix; prefer_name_match=False miss khi scan alphabet."""
    root = tmp_path / "app_controllers"
    # Create 10 standard alphabetical files in Admin/
    admin = root / "Admin"
    admin.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        (admin / f"AFile{i:02d}.xml").write_text("<root>nothing</root>", encoding="utf-8")

    # Create target file in Grid/zccnslkdhtpnc.xml
    grid = root / "Grid"
    grid.mkdir(parents=True, exist_ok=True)
    (grid / "zccnslkdhtpnc.xml").write_text(
        "<root>\nfunction acceptSendMail(ids) {}\n</root>",
        encoding="utf-8",
    )

    # With prefer_name_match=True and max_files=3, Grid/zccnslkdhtpnc.xml is prioritized
    res_true = search_files(
        root=str(root),
        pattern="acceptSendMail",
        max_files=3,
        prefer_name_match=True,
    )
    assert res_true["success"] is True
    assert len(res_true["matches"]) >= 1
    assert any("Grid/zccnslkdhtpnc.xml" in m["path"] for m in res_true["matches"])
    assert res_true["files_candidate"] == 11
    assert res_true["files_scanned"] <= 3

    # With prefer_name_match=False and max_files=3, scans alphabetically (Admin/AFile*) and misses
    res_false = search_files(
        root=str(root),
        pattern="acceptSendMail",
        max_files=3,
        prefer_name_match=False,
    )
    assert res_false["success"] is True
    assert len(res_false["matches"]) == 0
    assert res_false["truncated"] is True
    assert res_false["truncated_reason"] == "max_files"


def test_ac_sf2_2_files_candidate_and_truncated_warning(tmp_path):
    """AC-SF2-2: Truncated rỗng -> files_candidate > files_scanned, reason=max_files, warning rõ ràng."""
    root = tmp_path / "warn_proj"
    root.mkdir(parents=True, exist_ok=True)
    for i in range(5):
        (root / f"file_{i}.xml").write_text("<root>content</root>", encoding="utf-8")

    res = search_files(
        root=str(root),
        pattern="nonexistent_pattern_123",
        max_files=2,
    )
    assert res["success"] is True
    assert res["truncated"] is True
    assert res["truncated_reason"] == "max_files"
    assert res["files_candidate"] == 5
    assert res["files_scanned"] == 2
    assert len(res["matches"]) == 0
    assert any("candidates not opened" in w for w in res["warnings"])


def test_ac_sf2_3_root_narrow_clientscript(search_dir):
    """AC-SF2-3: Root hẹp ClientScript không regress."""
    cs_dir = search_dir / "ClientScript"
    res = search_files(
        root=str(cs_dir),
        pattern="acceptSendMail",
        max_files=50,
    )
    assert res["success"] is True
    assert res["total_matches"] >= 1
    assert any("jAjax.js" in m["path"] for m in res["matches"])


def test_ac_sf2_5_f_files_never_read_even_matching_name(tmp_path):
    """AC-SF2-5: File *.f không bao giờ được quét hay đọc dù tên khớp pattern."""
    root = tmp_path / "deny_proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "acceptSendMail.f").write_bytes(b"acceptSendMail content")
    (root / "acceptSendMail.xml").write_text("<root>acceptSendMail</root>", encoding="utf-8")

    res = search_files(
        root=str(root),
        pattern="acceptSendMail",
        max_files=10,
    )
    assert res["success"] is True
    assert all(not m["path"].endswith(".f") for m in res["matches"])
    assert any(m["path"].endswith(".xml") for m in res["matches"])


def test_ac_nit_sf_1_to_3_warnings_format(tmp_path):
    """AC-NIT-SF-1, SF-2, SF-3: Format warning khi truncated_reason=max_files & rỗng vs không rỗng."""
    root = tmp_path / "nit_proj"
    root.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        (root / f"test_{i:02d}.xml").write_text(f"<root>content {i}</root>", encoding="utf-8")

    # Match found + truncated: warning contains candidates not opened
    res_hit = search_files(
        root=str(root),
        pattern="content",
        max_files=4,
    )
    assert res_hit["success"] is True
    assert res_hit["truncated"] is True
    assert res_hit["truncated_reason"] == "max_files"
    assert len(res_hit["matches"]) > 0
    assert any("6 candidates not opened (files_candidate=10)" in w for w in res_hit["warnings"])
    assert not any("not found" in w for w in res_hit["warnings"])

    # No match + truncated: includes warning not to conclude not-found
    res_empty = search_files(
        root=str(root),
        pattern="missing_keyword",
        max_files=4,
    )
    assert res_empty["success"] is True
    assert res_empty["truncated"] is True
    assert len(res_empty["matches"]) == 0
    assert any("6 candidates not opened (files_candidate=10)" in w for w in res_empty["warnings"])
    assert any("do not conclude \"not found\"" in w for w in res_empty["warnings"])

    # Not truncated: warnings is empty
    res_full = search_files(
        root=str(root),
        pattern="content",
        max_files=50,
    )
    assert res_full["success"] is True
    assert res_full["truncated"] is False
    assert res_full["warnings"] == []

