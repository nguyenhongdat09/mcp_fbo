"""Unit tests for search_files tool.

Covers AC-SF-1 to AC-SF-4 from docs/doc/gemini/GEMINI-mcp-agent-gaps.md.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from search_files import search_files
from xml_fbograph.utils.any_path import reset_sticky_context


@pytest.fixture(autouse=True)
def _reset_sticky():
    reset_sticky_context()
    yield
    reset_sticky_context()


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
    """AC-SF-4: root khong ton tai -> error ro rang (path_not_found + tried[])."""
    res = search_files(
        root="E:/Path/Does/Not/Exist/12345",
        pattern="test",
    )
    assert res["success"] is False
    assert res["error_code"] == "path_not_found"
    assert res["tried"]


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


# ---------------------------------------------------------------------------
# AC-DEF-* — mode=definition / files_only (GEMINI-mcp-read-snippet-symbol.md)
# ---------------------------------------------------------------------------


@pytest.fixture
def def_project(tmp_path):
    """Project có symbol được định nghĩa + symbol chỉ được dùng."""
    root = tmp_path / "def_proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "Web.config").write_text("<configuration/>", encoding="utf-8")

    cs = root / "ClientScript"
    cs.mkdir(parents=True, exist_ok=True)
    (cs / "hwcrypto.js").write_text(
        "var Base64 = {\n\tencode: function(s) { return s; }\n};\n"
        "Base64.encode('x');\n",
        encoding="utf-8",
    )
    (cs / "jAjax.js").write_text(
        "function send() {\n\tBase64.encode(data);\n\tOnlyUsed.call();\n}\n"
        "function open$CreateVoucher(g) {\n\treturn g;\n}\n",
        encoding="utf-8",
    )
    (cs / "usage.js").write_text("OnlyUsed.more();\n", encoding="utf-8")
    return root


def test_ac_def_1_definition_found(def_project):
    """AC-DEF-1: symbol có định nghĩa -> definition_found=True + đúng file/dòng."""
    res = search_files(
        root=str(def_project / "ClientScript"),
        mode="definition",
        symbol="Base64",
        include_glob="*.js",
    )
    assert res["success"] is True
    assert res["mode"] == "definition"
    assert res["definition_found"] is True
    defs = res["definitions"]
    assert any("hwcrypto.js" in d["path"] and d["kind"] == "var" for d in defs)


def test_ac_def_2_usage_only_not_found(def_project):
    """AC-DEF-2: symbol chỉ được dùng -> definition_found=False + usage_hint."""
    res = search_files(
        root=str(def_project / "ClientScript"),
        mode="definition",
        symbol="OnlyUsed",
        include_glob="*.js",
    )
    assert res["success"] is True
    assert res["definition_found"] is False
    assert res["definitions"] == []
    assert "usage" in res["usage_hint"]


def test_ac_def_2b_truncated_not_concluded(tmp_path):
    """AC-DEF-2b: definition_found=false + truncated -> warning không kết luận."""
    root = tmp_path / "trunc_proj"
    root.mkdir(parents=True, exist_ok=True)
    for i in range(6):
        (root / f"f{i}.js").write_text(f"var x{i} = 1;\n", encoding="utf-8")
    res = search_files(
        root=str(root),
        mode="definition",
        symbol="Missing",
        include_glob="*.js",
        max_files=2,
        prefer_name_match=False,
    )
    assert res["success"] is True
    assert res["definition_found"] is False
    assert res["truncated"] is True
    assert any("Không kết luận" in w for w in res["warnings"])


def test_ac_def_3_symbol_with_dollar(def_project):
    """AC-DEF-3: symbol chứa '$' (open$CreateVoucher) -> escape đúng, tìm được."""
    res = search_files(
        root=str(def_project / "ClientScript"),
        mode="definition",
        symbol="open$CreateVoucher",
        include_glob="*.js",
    )
    assert res["success"] is True
    assert res["definition_found"] is True
    assert any(
        "jAjax.js" in d["path"] and d["kind"] == "function" for d in res["definitions"]
    )


def test_ac_def_4_mode_content_no_regress(search_dir):
    """AC-DEF-4: mode=content mặc định không regress."""
    res = search_files(root=str(search_dir), pattern="acceptSendMail")
    assert res["success"] is True
    assert res["total_matches"] >= 2
    res2 = search_files(root=str(search_dir), pattern="acceptSendMail", mode="content")
    assert res2["total_matches"] == res["total_matches"]


def test_ac_def_5_files_only_no_read(def_project):
    """AC-DEF-5: files_only không mở file nào (files_scanned=0)."""
    res = search_files(
        root=str(def_project / "ClientScript"),
        mode="files_only",
        include_glob="*.js",
    )
    assert res["success"] is True
    assert res["mode"] == "files_only"
    assert res["files_scanned"] == 0
    assert res["files_candidate"] == 3
    assert sorted(res["files"]) == ["hwcrypto.js", "jAjax.js", "usage.js"]


# ---------------------------------------------------------------------------
# AC-PATH-* — universal path resolver (GEMINI-mcp-read-snippet-symbol.md)
# ---------------------------------------------------------------------------


def test_ac_path_1_root_is_file(def_project):
    """AC-PATH-1: root = 1 file -> search đúng file đó, files_candidate=1."""
    target = def_project / "Main"
    target.mkdir(exist_ok=True)
    aspx = target / "cactpt1.aspx"
    aspx.write_text("<div>Base64 token</div>", encoding="utf-8")

    res = search_files(root=str(aspx), pattern="Base64")
    assert res["success"] is True
    assert res["files_candidate"] == 1
    assert res["total_matches"] == 1
    assert res["matches"][0]["path"] == "cactpt1.aspx"


def test_ac_path_2_relative_root_sticky(def_project):
    """AC-PATH-2: sau 1 call abs -> root='ClientScript' không cần reference_file."""
    from xml_fbograph.mcp_tools import mcp_read_local_file

    # 1 call abs bất kỳ -> set sticky project context
    mcp_read_local_file(str(def_project / "ClientScript" / "jAjax.js"), read_option=1)

    res = search_files(root="ClientScript", pattern="Base64")
    assert res["success"] is True
    assert res["total_matches"] >= 1
    assert any("hwcrypto.js" in m["path"] for m in res["matches"])


def test_ac_path_5_relative_not_found(def_project):
    """AC-PATH-5: relative không tồn tại -> path_not_found + tried[] + hint."""
    from xml_fbograph.mcp_tools import mcp_read_local_file

    mcp_read_local_file(str(def_project / "ClientScript" / "jAjax.js"), read_option=1)
    res = search_files(root="ClientScriptt", pattern="x")
    assert res["success"] is False
    assert res["error_code"] == "path_not_found"
    assert res["tried"]
    assert res["known_projects"]
    assert "hint" in res  # gần giống ClientScript


def test_ac_path_7_two_projects_reference_override(tmp_path):
    """AC-PATH-7: 2 project xen kẽ -> reference_file override đúng project."""
    proj_a = tmp_path / "PROJ_A"
    proj_b = tmp_path / "PROJ_B"
    for proj, marker in ((proj_a, "AAA"), (proj_b, "BBB")):
        cs = proj / "ClientScript"
        cs.mkdir(parents=True, exist_ok=True)
        (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
        (cs / "lib.js").write_text(f"var marker = '{marker}';\n", encoding="utf-8")

    # Sticky -> proj_a
    search_files(root=str(proj_a / "ClientScript"), pattern="marker")

    res = search_files(
        root="ClientScript",
        pattern="BBB",
        reference_file=str(proj_b / "ClientScript" / "lib.js"),
    )
    assert res["success"] is True
    assert res["total_matches"] == 1
    assert any("lib.js" in m["path"] for m in res["matches"])

    # Không truyền reference -> dùng project gần nhất (proj_b vừa resolve)
    res2 = search_files(root="ClientScript", pattern="BBB")
    assert res2["success"] is True
    assert res2["total_matches"] == 1
    res3 = search_files(root="ClientScript", pattern="AAA")
    assert res3["total_matches"] == 0  # proj_b không chứa AAA


def test_ac_path_8_abs_dir_no_regress(search_dir):
    """AC-PATH-8: root abs folder như cũ -> không regress."""
    res = search_files(root=str(search_dir), pattern="acceptSendMail")
    assert res["success"] is True
    assert res["total_matches"] >= 2


# ---------------------------------------------------------------------------
# AC-RX-* — regex-like pattern hint (GEMINI-mcp-read-cap-and-search-regex.md)
# ---------------------------------------------------------------------------


def test_ac_rx_1_regex_like_pattern_warns_literal(tmp_path):
    """AC-RX-1: pattern 'stt_rec_px|ngay_yc' không truyền regex → literal search
    + warnings có pattern_looks_like_regex + regex_hint=true."""
    root = tmp_path / "rx_proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (root / "a.txt").write_text("co stt_rec_px o day\n", encoding="utf-8")

    res = search_files(root=str(root), pattern="stt_rec_px|ngay_yc")
    assert res["success"] is True
    # literal → không match dòng chứa 'stt_rec_px' (vì không có '|' trong line)
    assert res["total_matches"] == 0
    assert res.get("regex_hint") is True
    assert any("pattern_looks_like_regex" in w for w in res["warnings"])


def test_ac_rx_2_regex_true_no_warning(tmp_path):
    """AC-RX-2: cùng pattern với regex=true → match thật, không warning."""
    root = tmp_path / "rx_proj2"
    root.mkdir(parents=True, exist_ok=True)
    (root / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (root / "a.txt").write_text("co stt_rec_px o day\nva ngay_yc nua\n", encoding="utf-8")

    res = search_files(root=str(root), pattern="stt_rec_px|ngay_yc", regex=True)
    assert res["success"] is True
    assert res["total_matches"] == 2
    assert "regex_hint" not in res
    assert not any("pattern_looks_like_regex" in w for w in res["warnings"])


def test_ac_rx_3_clean_literal_no_hint(tmp_path):
    """AC-RX-3: pattern literal sạch 'ma_ct' → không warning, không regex_hint."""
    root = tmp_path / "rx_proj3"
    root.mkdir(parents=True, exist_ok=True)
    (root / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (root / "a.txt").write_text("ma_ct = 'SO'\n", encoding="utf-8")

    res = search_files(root=str(root), pattern="ma_ct")
    assert res["success"] is True
    assert res["total_matches"] == 1
    assert "regex_hint" not in res
    assert not any("pattern_looks_like_regex" in w for w in res["warnings"])


def test_ac_rx_4_literal_paren_still_works(tmp_path):
    """AC-RX-4: pattern 'foo(bar' (literal hợp lệ) → search literal đúng,
    warning vẫn nổ (heuristic chấp nhận false-positive ở warn level)."""
    root = tmp_path / "rx_proj4"
    root.mkdir(parents=True, exist_ok=True)
    (root / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (root / "a.js").write_text("x = foo(bar, 1);\ny = fooBaz(2);\n", encoding="utf-8")

    res = search_files(root=str(root), pattern="foo(bar")
    assert res["success"] is True
    # literal 'foo(bar' chỉ match dòng 1, không match 'fooBaz(2)'
    assert res["total_matches"] == 1
    assert res["matches"][0]["line"] == 1
    assert res.get("regex_hint") is True
    assert any("pattern_looks_like_regex" in w for w in res["warnings"])

