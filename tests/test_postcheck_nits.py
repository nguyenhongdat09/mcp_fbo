"""AC-CHK-*/AC-EXP-*/AC-SUB-*/AC-RNG-*/AC-AST-* —
docs/doc/gemini/GEMINI-mcp-postcheck-and-nits.md.

- post_edit_check parse JS THẬT qua js_engine (không "ok" giả).
- expanded_for_uniqueness/expanded_lines phản ánh thật.
- Subfolder của project đã biết không tính project root mới.
- start_line > end_line -> invalid_range.
- symbol extractor ưu tiên AST, fallback regex.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from suggest_edit import suggest_edit
from xml_controller_summary import snippet as snippet_mod
from xml_controller_summary.snippet import (
    find_js_function_in_text,
    list_js_function_names,
)
from xml_fbograph.mcp_tools import mcp_read_local_file
from xml_fbograph.utils.any_path import (
    known_projects,
    reset_sticky_context,
    resolve_any_path,
)


@pytest.fixture(autouse=True)
def _reset_sticky():
    reset_sticky_context()
    yield
    reset_sticky_context()


@pytest.fixture
def js_project(tmp_path):
    """Project tối thiểu: Web.config + App_Data/Controllers + ClientScript."""
    proj = tmp_path / "PROJ"
    ctrl = proj / "App_Data" / "Controllers" / "Dir"
    ctrl.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (ctrl / "SOTran.xml").write_text("<dir/>", encoding="utf-8")
    cs = proj / "ClientScript"
    cs.mkdir(parents=True, exist_ok=True)
    return proj


def _grid_xml(proj: Path) -> Path:
    grid_dir = proj / "App_Data" / "Controllers" / "Grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    xml = grid_dir / "SOTran.xml"
    xml.write_text(
        "\n".join(
            [
                '<?xml version="1.0"?>',
                '<grid id="SOTran">',
                "<script><text><![CDATA[",
                "function open$CreateVoucher(g) {",
                "\tvar f = g.parentForm;",
                "\treturn true;",
                "}",
                "]]></text></script>",
                '<action id="GetOne"><text><![CDATA[',
                "select 1",
                "]]></text></action>",
                "</grid>",
            ]
        ),
        encoding="utf-8",
    )
    return xml


# ---------------------------------------------------------------------------
# AC-CHK-* — post_edit_check parse JS thật
# ---------------------------------------------------------------------------


def test_ac_chk_1_bad_syntax_failed_js_file(tmp_path):
    """AC-CHK-1 (.js): new_string '{{{ ;' -> js_parse=failed + errors có line/column."""
    f = tmp_path / "ok.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    res = suggest_edit(
        str(f), symbol="ok", new_string="function f(){ var x = {{{ ;"
    )
    assert res["success"] is True
    chk = res["post_edit_check"]
    assert chk["js_parse"] == "failed"
    assert chk["errors"]
    assert any(e.get("line") for e in chk["errors"])
    assert any("column" in e for e in chk["errors"])


def test_ac_chk_1_bad_syntax_failed_controller_xml(js_project):
    """AC-CHK-1 (.xml controller): '{{{' trong CDATA -> failed, không còn 'ok' giả."""
    xml = _grid_xml(js_project)
    res = suggest_edit(
        str(xml),
        symbol="open$CreateVoucher",
        new_string="function open$CreateVoucher(g) { var x = {{{ ;",
    )
    assert res["success"] is True
    chk = res["post_edit_check"]
    assert chk["js_parse"] == "failed"
    assert chk["errors"]
    assert any(e.get("line") for e in chk["errors"])


def test_ac_chk_2_valid_js_ok(tmp_path):
    """AC-CHK-2: new_string hợp lệ -> js_parse='ok' (không false-positive)."""
    f = tmp_path / "ok.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    res = suggest_edit(
        str(f), symbol="ok", new_string="function ok() {\n\treturn 2;\n}"
    )
    assert res["post_edit_check"]["js_parse"] == "ok"


def test_ac_chk_3_brace_in_string_comment_ok(tmp_path):
    """AC-CHK-3: '{' trong string/comment và @@var@@/&Entity; -> không fail giả."""
    f = tmp_path / "ok.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    res = suggest_edit(
        str(f),
        symbol="ok",
        new_string=(
            'function ok() {\n\tvar s = "a{b}"; // }\n'
            "\tvar u = @@userID@@;\n\tvar e = &extFunc;; // }\n\treturn u;\n}"
        ),
    )
    assert res["post_edit_check"]["js_parse"] == "ok"


def test_ac_chk_4_failed_still_success_with_warning(tmp_path):
    """AC-CHK-4: js_parse=failed -> success=true, instructions cảnh báo không nên ghi."""
    f = tmp_path / "ok.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    res = suggest_edit(str(f), symbol="ok", new_string="function ok( { broken")
    assert res["success"] is True
    assert res["post_edit_check"]["js_parse"] == "failed"
    assert "không nên ghi" in res["instructions"]


def test_ac_chk_5_batch_checks_final_buffer(tmp_path):
    """AC-CHK-5: edits[] batch -> post_edit_check trên buffer sau mọi edit."""
    f = tmp_path / "ok.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    res = suggest_edit(
        str(f),
        edits=[
            {"old_string": "return 1;", "new_string": "return 2;"},
            {"old_string": "return 2;", "new_string": "return {{{ ;"},
        ],
    )
    assert res["edits_applied"] == 2
    assert res["post_edit_check"]["js_parse"] == "failed"
    assert "không nên ghi" in res["instructions"]


def test_ac_chk_6_parser_unavailable_unchecked(tmp_path, monkeypatch):
    """AC-CHK-6: parser không chạy được -> 'unchecked', tuyệt đối không 'ok' giả."""
    f = tmp_path / "ok.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "js_engine.generated.JavaScriptParser", None)
    res = suggest_edit(str(f), symbol="ok", new_string="function ok() { return 2; }")
    assert res["success"] is True
    chk = res["post_edit_check"]
    assert chk["js_parse"] == "unchecked"
    assert "parser unavailable" in chk["errors"][0]["message"]


# ---------------------------------------------------------------------------
# AC-EXP-* — expanded_for_uniqueness phản ánh thật
# ---------------------------------------------------------------------------


def test_ac_exp_1_fragment_expanded_flag_true(tmp_path):
    """AC-EXP-1: old_string fragment match nhiều chỗ -> expanded_for_uniqueness=true."""
    f = tmp_path / "dup.js"
    f.write_text(
        "function a() {\n\tvar x = 1;\n\treturn x;\n}\n"
        "function b() {\n\tvar y = 2;\n\treturn y;\n}\n",
        encoding="utf-8",
    )
    res = suggest_edit(str(f), old_string="var")
    assert res["success"] is True
    assert res["expanded_for_uniqueness"] is True
    assert res["expanded_lines"] >= 1
    assert "var" in res["old_string"]


def test_ac_exp_2_unique_no_expand(tmp_path):
    """AC-EXP-2: old_string unique sẵn -> expanded_for_uniqueness=false."""
    f = tmp_path / "one.js"
    f.write_text("function a() {\n\tvar x = 1;\n\treturn x;\n}\n", encoding="utf-8")
    res = suggest_edit(str(f), old_string="return x;")
    assert res["success"] is True
    assert res["expanded_for_uniqueness"] is False


# ---------------------------------------------------------------------------
# AC-SUB-* — subfolder không tính project root mới
# ---------------------------------------------------------------------------


def test_ac_sub_1_subfolder_echo_parent_root(js_project):
    """AC-SUB-1: file trong ClientScript/ (có Web.config riêng) -> project_root cha."""
    proj = js_project
    cs = proj / "ClientScript"
    (cs / "Web.config").write_text("<configuration/>", encoding="utf-8")
    js = cs / "lib.js"
    js.write_text("var a = 1;", encoding="utf-8")

    xml = proj / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"
    seed = resolve_any_path(str(xml))  # sticky = PROJ
    assert Path(seed.project_root).resolve() == proj.resolve()

    res = resolve_any_path(str(js))
    assert res.ok is True
    assert Path(res.project_root).resolve() == proj.resolve()  # không phải ...\ClientScript
    assert res.switched_from is None
    assert all("ClientScript" not in r for r in known_projects())


def test_ac_sub_3_real_switch_still_warns(tmp_path):
    """AC-SUB-3: call sang project thật khác -> vẫn warn switched đúng."""
    projs = []
    for name in ("PA", "PB"):
        proj = tmp_path / name
        (proj / "App_Data" / "Controllers" / "Dir").mkdir(parents=True, exist_ok=True)
        (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
        (proj / "App_Data" / "Controllers" / "Dir" / "SOTran.xml").write_text(
            "<dir/>", encoding="utf-8"
        )
        cs = proj / "ClientScript"
        cs.mkdir(parents=True, exist_ok=True)
        (cs / "Web.config").write_text("<configuration/>", encoding="utf-8")
        (cs / "lib.js").write_text(f"// {name}", encoding="utf-8")
        projs.append(proj)
    pa, pb = projs

    resolve_any_path(str(pa / "App_Data" / "Controllers" / "Dir" / "SOTran.xml"))
    res = resolve_any_path(str(pb / "ClientScript" / "lib.js"))
    assert res.ok is True
    assert Path(res.project_root).resolve() == pb.resolve()
    assert res.switched_from is not None
    assert "PA" in res.switched_from


# ---------------------------------------------------------------------------
# AC-RNG-* — start_line > end_line -> invalid_range
# ---------------------------------------------------------------------------


def test_ac_rng_1_reversed_range_invalid(tmp_path):
    """AC-RNG-1: start_line=50, end_line=10 -> error_code invalid_range."""
    f = tmp_path / "big.js"
    f.write_text("\n".join(f"// line {i}" for i in range(1, 101)), encoding="utf-8")
    res = json.loads(
        mcp_read_local_file(str(f), start_line=50, end_line=10)
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_range"
    assert "50" in res["message"] and "10" in res["message"]


def test_ac_rng_2_end_line_zero_to_eof(tmp_path):
    """AC-RNG-2: start_line hợp lệ + end_line=0 -> đọc tới cuối (giữ)."""
    f = tmp_path / "big.js"
    f.write_text("\n".join(f"// line {i}" for i in range(1, 21)), encoding="utf-8")
    res = json.loads(mcp_read_local_file(str(f), start_line=15, end_line=0))
    assert res["success"] is True
    snip = res["snippets"][0]
    assert snip["line_start"] == 15
    assert snip["line_end"] == 20


def test_ac_rng_suggest_edit_reversed_invalid(tmp_path):
    """Cùng rule cho selector lines của suggest_edit (read_option=4)."""
    f = tmp_path / "big.js"
    f.write_text("\n".join(f"// line {i}" for i in range(1, 101)), encoding="utf-8")
    res = suggest_edit(str(f), start_line=50, end_line=10)
    assert res["success"] is False
    assert res["error_code"] == "invalid_range"


# ---------------------------------------------------------------------------
# AC-AST-* — symbol extractor ưu tiên AST, fallback regex
# ---------------------------------------------------------------------------


def test_ac_ast_1_method_shorthand_via_ast(tmp_path):
    """AC-AST-1: method shorthand `open(){}` — regex không bắt được, AST resolve."""
    f = tmp_path / "obj.js"
    f.write_text(
        'var obj = {\n\topen() {\n\t\treturn "a{b}";\n\t},\n'
        '\tclose: function() {\n\t\treturn 2; // }\n\t}\n};\n',
        encoding="utf-8",
    )
    res = suggest_edit(str(f), symbol="open")
    assert res["success"] is True
    assert res["target"]["kind"] == "js_function"
    assert "open()" in res["old_string"]
    # range đúng — không dính phần close
    assert "close" not in res["old_string"]


def test_ac_ast_2_regex_fallback_when_no_ast(tmp_path, monkeypatch):
    """AC-AST-2: AST không ra tree -> regex+brace-match vẫn cứu được (không regress)."""
    text = "function keep() {\n\treturn 1;\n}\nvar x = {{{\n"
    monkeypatch.setattr(snippet_mod, "_ast_function_spans", lambda _t: None)
    matches = find_js_function_in_text(text, "keep")
    assert matches
    assert matches[0].name == "keep"


def test_ac_ast_3_available_functions_full(tmp_path):
    """AC-AST-3: available_functions đầy đủ — kể cả `X: function`, method shorthand."""
    text = (
        "var obj = {\n\topen() { return 1; },\n\tclose: function() { return 2; }\n};\n"
        "function plain() { return 3; }\n"
        "ns.deep = function() { return 4; };\n"
    )
    names = list_js_function_names(text)
    for expected in ("open", "close", "plain", "ns.deep"):
        assert expected in names


def test_ac_ast_symbol_not_found_lists_available(js_project):
    """symbol_not_found trên controller flat vẫn trả available_functions."""
    xml = _grid_xml(js_project)
    res = suggest_edit(str(xml), symbol="khongCoDau")
    assert res["success"] is False
    assert res["error_code"] == "symbol_not_found"
    assert "open$CreateVoucher" in res["available_functions"]
