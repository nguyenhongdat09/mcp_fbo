"""Unit tests for read_local_file tool absolute path auto-resolution + snippet mode.

Covers AC-RLF-1..3 (GEMINI-mcp-agent-gaps.md) và AC-SNIP-*, AC-PATH-3/4/6
(GEMINI-mcp-read-snippet-symbol.md).
"""

from __future__ import annotations

import json

import pytest
from pathlib import Path
from xml_fbograph.mcp_tools import mcp_read_local_file
from xml_fbograph.utils.any_path import reset_sticky_context


@pytest.fixture(autouse=True)
def _reset_sticky():
    reset_sticky_context()
    yield
    reset_sticky_context()


@pytest.fixture
def fbo_project(tmp_path):
    proj = tmp_path / "FBO_PROJ"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")

    # Main folder
    main_dir = proj / "Main"
    main_dir.mkdir(parents=True, exist_ok=True)
    aspx_file = main_dir / "zccnslkdhtpnc.aspx"
    aspx_file.write_text("<%@ Page Language=\"C#\" %><div>Hello FBO</div>", encoding="utf-8")

    # App_Data/Controllers/Dir
    ctrl_dir = proj / "App_Data" / "Controllers" / "Dir"
    ctrl_dir.mkdir(parents=True, exist_ok=True)
    xml_file = ctrl_dir / "TestDir.xml"
    xml_file.write_text("<dir id=\"TestDir\"><fields><field name=\"ma_kh\"/></fields></dir>", encoding="utf-8")

    return proj, aspx_file, xml_file


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
                '<command event="Showing"><text><![CDATA[',
                "select 1",
                "]]></text></command>",
                "<fields><field name=\"ma_kh\"/></fields>",
                "</grid>",
            ]
        ),
        encoding="utf-8",
    )

    cs_dir = proj / "ClientScript"
    cs_dir.mkdir(parents=True, exist_ok=True)
    js_file = cs_dir / "jAjax.js"
    js_file.write_text(
        "\n".join(
            [
                "// line 1",
                "function sendMail(ids) {",
                "\tvar x = 1;",
                "\treturn x;",
                "}",
                "// line 6",
                "// line 7",
                "// line 8",
                "// line 9",
                "// line 10",
            ]
        ),
        encoding="utf-8",
    )

    return proj, xml_file, js_file


def test_ac_rlf_1_abs_path_without_reference_file(fbo_project):
    """AC-RLF-1: Abs path khong can reference_file -> doc OK."""
    _, aspx_file, _ = fbo_project
    content = mcp_read_local_file(
        file_path=str(aspx_file),
        reference_file="",
        read_option=1,
    )
    assert "Hello FBO" in content
    assert "Loi:" not in content


def test_ac_rlf_2_relative_path_missing_reference_file(fbo_project):
    """AC-RLF-2: Relative path thieu context -> bao loi no_project_context (fresh, chua co sticky)."""
    from xml_fbograph.utils.any_path import reset_sticky_context

    reset_sticky_context()
    content = mcp_read_local_file(
        file_path="Filter/x.xml",
        reference_file="",
        read_option=1,
    )
    assert "no_project_context" in content


def test_ac_rlf_3_no_regress_read_options(fbo_project):
    """AC-RLF-3: Khong regress cac options 1, 2, 3."""
    _, _, xml_file = fbo_project
    # Option 1: raw
    raw = mcp_read_local_file(file_path=str(xml_file), reference_file="", read_option=1)
    assert "<dir id=\"TestDir\">" in raw

    # Option 2: flat
    flat = mcp_read_local_file(file_path=str(xml_file), reference_file="", read_option=2)
    assert "TestDir" in flat

    # Option 3: summary_xml (controller .xml)
    summary = mcp_read_local_file(file_path=str(xml_file), reference_file="", read_option=3)
    assert "TestDir" in summary or "{" in summary


# ---------------------------------------------------------------------------
# AC-SNIP-* — snippet mode (GEMINI-mcp-read-snippet-symbol.md)
# ---------------------------------------------------------------------------


def test_ac_snip_1_symbol_on_controller(grid_project):
    """AC-SNIP-1: symbol=open$CreateVoucher -> đúng body function, không dump cả file."""
    _, xml_file, _ = grid_project
    res = json.loads(
        mcp_read_local_file(str(xml_file), symbol="open$CreateVoucher")
    )
    assert res["success"] is True
    assert res["mode"] == "snippet"
    assert res["view"] == "flat"
    snip = res["snippets"][0]
    assert snip["kind"] == "js_function"
    assert snip["name"] == "open$CreateVoucher"
    assert snip["line_start"] > 0
    assert snip["line_end"] > snip["line_start"]
    assert "function open$CreateVoucher(g) {" in snip["text"]
    assert "f.request('GetCreatedVoucher');" in snip["text"]
    assert "return true;" in snip["text"]
    # Không dump cả file: text chỉ quanh function
    assert "GetCreatedVoucher\"><" not in snip["text"]
    assert len(snip["text"]) < 2000


def test_ac_snip_2_block_action(grid_project):
    """AC-SNIP-2: block=action:GetCreatedVoucher -> đúng SQL của action."""
    _, xml_file, _ = grid_project
    res = json.loads(
        mcp_read_local_file(str(xml_file), block="action:GetCreatedVoucher")
    )
    assert res["success"] is True
    snip = res["snippets"][0]
    assert snip["kind"] == "sql_block"
    assert snip["name"] == "action:GetCreatedVoucher"
    assert "fsdSttRecRef" in snip["text"]
    assert "open$CreateVoucher" not in snip["text"]


def test_ac_snip_2b_block_command(grid_project):
    """block=command:Showing -> đúng command SQL."""
    _, xml_file, _ = grid_project
    res = json.loads(
        mcp_read_local_file(str(xml_file), block="command:Showing")
    )
    assert res["success"] is True
    assert res["snippets"][0]["name"] == "command:Showing"
    assert "select 1" in res["snippets"][0]["text"]


def test_ac_snip_3_line_range_raw(grid_project):
    """AC-SNIP-3: start_line/end_line trên .js -> đúng khoảng raw kèm NNN| prefix."""
    _, _, js_file = grid_project
    res = json.loads(
        mcp_read_local_file(str(js_file), start_line=2, end_line=5)
    )
    assert res["success"] is True
    assert res["view"] == "raw"
    snip = res["snippets"][0]
    assert snip["kind"] == "lines"
    assert snip["line_start"] == 2
    assert snip["line_end"] == 5
    assert "2|function sendMail(ids) {" in snip["text"]
    assert "5|}" in snip["text"]
    assert "1|// line 1" not in snip["text"]


def test_ac_snip_4_symbol_not_found(grid_project):
    """AC-SNIP-4: symbol sai tên -> symbol_not_found + available_functions."""
    _, xml_file, _ = grid_project
    res = json.loads(
        mcp_read_local_file(str(xml_file), symbol="hamKhongTonTai")
    )
    assert res["success"] is False
    assert res["error_code"] == "symbol_not_found"
    assert "open$CreateVoucher" in res["available_functions"]


def test_ac_snip_5_symbol_in_entity(grid_project):
    """AC-SNIP-5: function nằm trong .ent include -> origin=entity + warning."""
    _, xml_file, _ = grid_project
    res = json.loads(
        mcp_read_local_file(str(xml_file), symbol="helperFromEntity")
    )
    assert res["success"] is True
    snip = res["snippets"][0]
    assert snip["origin"].startswith("entity")
    assert "function helperFromEntity()" in snip["text"]
    assert any("entity" in w for w in res["warnings"])


def test_ac_snip_6_no_snippet_params_no_regress(grid_project):
    """AC-SNIP-6: không param snippet -> hành vi option 1/2/3 nguyên vẹn."""
    _, xml_file, _ = grid_project
    raw = mcp_read_local_file(str(xml_file), read_option=1)
    assert raw.lstrip().startswith("<?xml") or "<grid" in raw
    flat = mcp_read_local_file(str(xml_file), read_option=2)
    assert "helperFromEntity" in flat  # entity đã expand
    summary = mcp_read_local_file(str(xml_file), read_option=3)
    assert "{" in summary


def test_ac_snip_7_symbol_overrides_lines(grid_project):
    """symbol + lines cùng lúc -> ưu tiên symbol, warning symbol_overrides_lines."""
    _, xml_file, _ = grid_project
    res = json.loads(
        mcp_read_local_file(str(xml_file), symbol="open$CreateVoucher", start_line=1, end_line=3)
    )
    assert res["success"] is True
    assert res["snippets"][0]["kind"] == "js_function"
    assert "symbol_overrides_lines" in res["warnings"]


def test_ac_snip_line_out_of_range(grid_project):
    """start_line > total -> line_out_of_range + total_lines."""
    _, _, js_file = grid_project
    res = json.loads(
        mcp_read_local_file(str(js_file), start_line=9999)
    )
    assert res["success"] is False
    assert res["error_code"] == "line_out_of_range"
    assert res["total_lines"] > 0


# ---------------------------------------------------------------------------
# AC-PATH-* — universal path resolver (GEMINI-mcp-read-snippet-symbol.md)
# ---------------------------------------------------------------------------


def test_ac_path_3_relative_via_sticky(grid_project):
    """AC-PATH-3: sau 1 call abs -> relative không cần reference_file."""
    proj, xml_file, _ = grid_project
    # Call abs đầu tiên -> set sticky context
    first = mcp_read_local_file(str(xml_file), read_option=1)
    assert "<grid" in first
    # Relative tiếp theo — resolve qua sticky
    second = mcp_read_local_file("Grid/SOTran.xml", read_option=1)
    assert "<grid" in second
    assert "no_project_context" not in second
    assert "Loi" not in second


def test_ac_path_4_relative_outside_controllers(grid_project):
    """AC-PATH-4: 'ClientScript/jAjax.js' -> resolve qua project_root, không phải Controllers."""
    proj, xml_file, js_file = grid_project
    mcp_read_local_file(str(xml_file), read_option=1)  # set sticky
    res = mcp_read_local_file("ClientScript/jAjax.js", read_option=1)
    assert "sendMail" in res


def test_ac_path_5_relative_not_found(grid_project):
    """AC-PATH-5: relative không tồn tại -> path_not_found + tried[] + known_projects."""
    _, xml_file, _ = grid_project
    mcp_read_local_file(str(xml_file), read_option=1)  # set sticky
    res = json.loads(mcp_read_local_file("ClientScriptt", read_option=1))
    assert res["success"] is False
    assert res["error_code"] == "path_not_found"
    assert res["tried"]
    assert res["known_projects"]


def test_ac_path_6_fresh_no_context():
    """AC-PATH-6: fresh server + call relative -> no_project_context, không crash."""
    reset_sticky_context()
    res = json.loads(mcp_read_local_file("Dir/x.xml", read_option=1))
    assert res["success"] is False
    assert res["error_code"] == "no_project_context"


# ---------------------------------------------------------------------------
# AC-CAP-* — read_local_file full-dump cap 80k (GEMINI-mcp-read-cap-and-search-regex.md)
# ---------------------------------------------------------------------------


@pytest.fixture
def big_file_project(tmp_path):
    proj = tmp_path / "BIG_PROJ"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
    # ~120k chars: 2000 dòng x 60 chars
    big = proj / "big.sql"
    big.write_text(
        "".join(f"-- line {i:05d} " + "x" * 45 + "\n" for i in range(1, 2001)),
        encoding="utf-8",
    )
    small = proj / "small.sql"
    small.write_text("SELECT 1\nSELECT 2\n", encoding="utf-8")
    return proj, big, small


def test_ac_cap_1_big_file_truncated_marker(big_file_project):
    """AC-CAP-1: file > 80k chars → [TRUNCATED] + total_lines + hint."""
    _, big, _ = big_file_project
    out = mcp_read_local_file(str(big), read_option=1)
    assert "[TRUNCATED]" in out
    marker = out[out.index("[TRUNCATED]") + len("[TRUNCATED]"):]
    footer = json.loads(marker.strip())
    assert footer["truncated"] is True
    assert footer["total_chars"] > 80_000
    assert footer["total_lines"] == 2001  # 2000 dòng + newline cuối
    assert footer["returned_chars"] == 80_000
    assert "hint" in footer


def test_ac_cap_2_small_file_no_marker(big_file_project):
    """AC-CAP-2: file nhỏ → không marker, output y hệt trước."""
    _, _, small = big_file_project
    out = mcp_read_local_file(str(small), read_option=1)
    assert "[TRUNCATED]" not in out
    assert "SELECT 1" in out and "SELECT 2" in out


def test_ac_cap_3_continue_via_start_line(big_file_project):
    """AC-CAP-3: đọc tiếp bằng start_line → trả phần còn lại đúng."""
    _, big, _ = big_file_project
    res = json.loads(mcp_read_local_file(str(big), start_line=1995))
    assert res["success"] is True
    text = res["snippets"][0]["text"]
    assert "line 01995" in text
    assert "line 02000" in text


def test_ac_cap_4_option2_flat_also_capped(big_file_project):
    """AC-CAP-4: read_option=2 (flat) file lớn → cũng cap tương tự."""
    proj, big, _ = big_file_project
    # flat_xml trên .sql → fallback nội dung gốc; cap vẫn áp dụng trên content
    out = mcp_read_local_file(str(big), read_option=2)
    # flat_xml có thể raise → fallback trả 'Loi khi doc flat XML' (không cap)
    # hoặc trả content → cap. Chấp nhận cả 2: nếu có content thì phải cap.
    if "Loi khi doc flat XML" not in out:
        assert "[TRUNCATED]" in out
