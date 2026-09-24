"""Unit tests for spec GEMINI-mcp-snippet-plain-dbsearch-refs-batch.md.

Covers:
- AC-MRG-* : suggest_edit gộp vào read_local_file read_option=4 (bỏ tool riêng)
- AC-PLAIN-*: snippet symbol trên file thường (.js/.aspx) + minified
- AC-DBS-* : query_database mode='search' (mock execute_query, không cần DB thật)
- AC-REF-* : search_files mode='references'
- AC-BATCH-*: edits[] batch trong read_option=4
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest
from pathlib import Path

from suggest_edit import suggest_edit
from search_files import search_files
from xml_fbograph.mcp_tools import mcp_read_local_file
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


# ---------------------------------------------------------------------------
# AC-MRG-* — suggest_edit gộp vào read_option=4
# ---------------------------------------------------------------------------


def test_ac_mrg_1_read_option_4_full_contract(grid_project):
    """AC-MRG-1: read_option=4 + symbol + new_string -> đủ field spec(9) + mode='suggest_edit'."""
    _, xml_file, _ = grid_project
    res = json.loads(
        mcp_read_local_file(
            str(xml_file),
            read_option=4,
            symbol="open$CreateVoucher",
            new_string="function open$CreateVoucher(g) {\n\treturn false;\n}",
        )
    )
    assert res["success"] is True
    assert res["mode"] == "suggest_edit"
    for k in (
        "physical_file", "display_file", "origin", "encoding", "target",
        "raw_line_start", "raw_line_end", "old_string", "match_count",
        "expanded_for_uniqueness", "new_string", "diff_preview",
        "post_edit_check", "instructions", "warnings",
    ):
        assert k in res, k
    assert res["target"]["kind"] == "js_function"
    assert res["post_edit_check"]["js_parse"] == "ok"


def test_ac_mrg_2_tool_list_no_standalone():
    """AC-MRG-2: tool list không còn suggest_edit riêng — đủ tool core."""
    mcp_app = pytest.importorskip("fastbusiness_mcp.mcp_app")
    tools = asyncio.run(mcp_app.server.list_tools())
    names = [t.name for t in tools]
    assert "suggest_edit" not in names
    for expected in ("query_database", "read_local_file", "search_files",
                     "clone_things", "compare_things"):
        assert expected in names


def test_ac_mrg_3_edge_cases_preserved(grid_project, tmp_path):
    """AC-MRG-3: entity origin / not_unique / not_found / .f giữ nguyên qua read_option=4."""
    _, xml_file, ent_file = grid_project

    # origin=entity -> physical_file trỏ .ent
    res = json.loads(
        mcp_read_local_file(str(xml_file), read_option=4, symbol="helperFromEntity")
    )
    assert res["success"] is True
    assert res["origin"].startswith("entity")
    assert Path(res["physical_file"]).resolve() == ent_file.resolve()

    # old_string_not_unique + occurrences
    dup = tmp_path / "dup.js"
    dup.write_text("var x = 1;\nvar x = 1;\n", encoding="utf-8")
    res2 = json.loads(
        mcp_read_local_file(str(dup), read_option=4, old_string="var x = 1;", max_expand=0)
    )
    assert res2["success"] is False
    assert res2["error_code"] == "old_string_not_unique"
    assert res2["occurrences"]

    # old_string_not_found
    res3 = json.loads(
        mcp_read_local_file(str(xml_file), read_option=4, old_string="khongCoDau123")
    )
    assert res3["success"] is False
    assert res3["error_code"] == "old_string_not_found"

    # new_string parse fail -> báo trước ghi
    ok_js = tmp_path / "ok.js"
    ok_js.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    res4 = json.loads(
        mcp_read_local_file(
            str(ok_js), read_option=4, symbol="ok",
            new_string="function ok( { broken",
        )
    )
    assert res4["success"] is True
    assert res4["post_edit_check"]["js_parse"] != "ok"

    # .f -> encrypted_file
    f_file = tmp_path / "enc.f"
    f_file.write_bytes(b"\x00\x01 encrypted")
    res5 = json.loads(mcp_read_local_file(str(f_file), read_option=4, symbol="x"))
    assert res5["success"] is False
    assert res5["error_code"] == "encrypted_file"


def test_ac_mrg_4_options_no_regress_and_no_write(grid_project):
    """AC-MRG-4: read_option 1/2/3 không regress; option=4 không ghi file."""
    _, xml_file, _ = grid_project
    raw = mcp_read_local_file(str(xml_file), read_option=1)
    assert "<grid" in raw
    flat = mcp_read_local_file(str(xml_file), read_option=2)
    assert "helperFromEntity" in flat
    summary = mcp_read_local_file(str(xml_file), read_option=3)
    assert "{" in summary

    before = _mtime(xml_file)
    mcp_read_local_file(
        str(xml_file), read_option=4, symbol="open$CreateVoucher",
        new_string="function open$CreateVoucher(g) { return false; }",
    )
    assert _mtime(xml_file) == before


# ---------------------------------------------------------------------------
# AC-PLAIN-* — snippet symbol trên file thường
# ---------------------------------------------------------------------------


@pytest.fixture
def plain_project(tmp_path):
    proj = tmp_path / "PLAIN_PROJ"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")

    main = proj / "Main"
    main.mkdir(parents=True, exist_ok=True)
    aspx = main / "cactpt1.aspx"
    aspx.write_text(
        "\n".join(
            [
                '<%@ Page Language="C#" %>',
                "<html><body>",
                '<script src="js/jquery.js"></script>',
                "<script>",
                "function load$Form() {",
                "\tvar x = 1;",
                "\treturn x;",
                "}",
                "</script>",
                "<div>html between</div>",
                "<script>",
                "var helper = function() {",
                "\treturn 2;",
                "};",
                "window.sendMail = function(ids) {",
                "\treturn ids;",
                "};",
                "</script>",
                "</body></html>",
            ]
        ),
        encoding="utf-8",
    )

    cs = proj / "ClientScript"
    cs.mkdir(parents=True, exist_ok=True)
    js = cs / "j5.js"
    js.write_text(
        "\n".join(
            [
                "// header",
                "function sendMail(ids) {",
                "\tvar t = 1;",
                "\treturn t;",
                "}",
                "var calc = function(a) {",
                "\treturn a + 1;",
                "};",
            ]
        ),
        encoding="utf-8",
    )
    return proj, aspx, js


def test_ac_plain_1_symbol_on_aspx(plain_project):
    """AC-PLAIN-1: symbol trên .aspx có <script> -> đúng hàm, view=raw, line=raw file."""
    _, aspx, _ = plain_project
    res = json.loads(mcp_read_local_file(str(aspx), symbol="load$Form"))
    assert res["success"] is True
    assert res["view"] == "raw"
    snip = res["snippets"][0]
    assert snip["kind"] == "js_function"
    assert snip["name"] == "load$Form"
    # function load$Form ở dòng 5 raw file
    assert snip["line_start"] == 5
    assert "return x;" in snip["text"]
    # không lấn sang block script thứ 2
    assert "helper" not in snip["text"]


def test_ac_plain_2_js_variants(plain_project):
    """AC-PLAIN-2: .js thường — function foo / var foo = function đều locate được."""
    _, _, js = plain_project
    res = json.loads(mcp_read_local_file(str(js), symbol="sendMail"))
    assert res["success"] is True
    assert res["snippets"][0]["line_start"] == 2
    assert "return t;" in res["snippets"][0]["text"]

    res2 = json.loads(mcp_read_local_file(str(js), symbol="calc"))
    assert res2["success"] is True
    assert "a + 1" in res2["snippets"][0]["text"]


def test_ac_plain_2b_dotted_and_member(tmp_path):
    """window.foo = function / foo.bar = function (suffix match 'bar')."""
    f = tmp_path / "w.js"
    f.write_text(
        "window.sendMail = function(ids) {\n\treturn ids;\n};\n"
        "my.ns.deep = function() {\n\treturn 9;\n};\n",
        encoding="utf-8",
    )
    res = json.loads(mcp_read_local_file(str(f), symbol="sendMail"))
    assert res["success"] is True
    assert "return ids;" in res["snippets"][0]["text"]

    # suffix match: gõ 'deep' khớp 'my.ns.deep'
    res2 = json.loads(mcp_read_local_file(str(f), symbol="deep"))
    assert res2["success"] is True
    assert "return 9;" in res2["snippets"][0]["text"]


def test_ac_plain_3_minified_window(tmp_path):
    """AC-PLAIN-3: .js minified (dòng > max_line_chars) -> cửa sổ ký tự, line_truncated."""
    f = tmp_path / "min.js"
    long_line = "var i=function(){return 1};" + "x" * 300 + "function sendMail(){var a=1;return a}"
    f.write_text(long_line + "\n", encoding="utf-8")
    res = json.loads(
        mcp_read_local_file(str(f), symbol="sendMail", max_line_chars=100)
    )
    assert res["success"] is True
    snip = res["snippets"][0]
    assert snip["line_truncated"] is True
    assert snip["line_total_chars"] >= len(long_line)  # có thể +\r trên Windows
    assert snip["line_start"] == snip["line_end"] == 1
    # cửa sổ quanh match, không phải cả dòng
    assert "function sendMail" in snip["text"]
    assert len(snip["text"]) <= 1200


def test_ac_plain_4_symbol_not_found_available(plain_project, tmp_path):
    """AC-PLAIN-4: symbol không có -> symbol_not_found + available_functions."""
    _, aspx, _ = plain_project
    res = json.loads(mcp_read_local_file(str(aspx), symbol="khongCoHamNay"))
    assert res["success"] is False
    assert res["error_code"] == "symbol_not_found"
    names = res["available_functions"]
    assert "load$Form" in names
    assert "helper" in names
    assert len(names) <= 50

    # file minified -> kèm note
    f = tmp_path / "m.js"
    f.write_text("var a=function(){}" + "y" * 300 + "\n", encoding="utf-8")
    res2 = json.loads(
        mcp_read_local_file(str(f), symbol="zzz", max_line_chars=100)
    )
    assert res2["success"] is False
    assert res2["error_code"] == "symbol_not_found"
    assert "minified" in res2.get("note", "")


def test_ac_plain_5_multiple_script_blocks(plain_project):
    """AC-PLAIN-5: .aspx nhiều <script> -> tìm đúng khối, line đúng raw."""
    _, aspx, _ = plain_project
    res = json.loads(mcp_read_local_file(str(aspx), symbol="helper"))
    assert res["success"] is True
    snip = res["snippets"][0]
    # var helper = function ở dòng 12 raw file
    assert snip["line_start"] == 12
    assert "return 2;" in snip["text"]
    assert "sendMail" not in snip["text"]

    res2 = json.loads(mcp_read_local_file(str(aspx), symbol="sendMail"))
    assert res2["success"] is True
    assert res2["snippets"][0]["line_start"] == 15


def test_ac_plain_6_block_on_plain_file(plain_project):
    """AC-PLAIN-6: block= trên file thường -> block_not_supported_for_plain_file."""
    _, aspx, js = plain_project
    res = json.loads(mcp_read_local_file(str(aspx), block="action:X"))
    assert res["success"] is False
    assert res["error_code"] == "block_not_supported_for_plain_file"
    res2 = json.loads(mcp_read_local_file(str(js), block="action:X"))
    assert res2["error_code"] == "block_not_supported_for_plain_file"


def test_ac_plain_7_controller_no_regress(grid_project):
    """AC-PLAIN-7: symbol trên controller XML -> y nguyên spec(8), không regress."""
    _, xml_file, _ = grid_project
    res = json.loads(mcp_read_local_file(str(xml_file), symbol="open$CreateVoucher"))
    assert res["success"] is True
    assert res["view"] == "flat"
    assert res["snippets"][0]["kind"] == "js_function"


# ---------------------------------------------------------------------------
# AC-DBS-* — query_database mode='search' (mock DB layer)
# ---------------------------------------------------------------------------


def _fake_conn_result(file_path, db_type="app"):
    return {
        "success": True,
        "parsed": {"server": "fake", "database": "fake_db", "user": "", "password": ""},
        "project_root": "P",
        "web_config_path": "W",
    }


class _FakeExec:
    """execute_query giả — query 1 trả object rows, query 2 trả definitions."""

    OBJ_COLS = [
        "object_id", "name", "schema_name", "type", "type_desc",
        "create_date", "modify_date", "has_definition",
    ]

    def __init__(self, obj_rows, def_rows=None):
        self.obj_rows = obj_rows
        self.def_rows = def_rows or []
        self.calls = []

    def __call__(self, parsed=None, query="", max_rows=20000, params=None, **kw):
        self.calls.append({"query": query, "params": params, "max_rows": max_rows})
        if "FROM sys.objects" in query:
            rows = self.obj_rows[:max_rows]
            return {
                "success": True,
                "result_sets": [
                    {"columns": self.OBJ_COLS, "rows": rows, "row_count": len(rows)}
                ],
            }
        return {
            "success": True,
            "result_sets": [
                {
                    "columns": ["object_id", "definition"],
                    "rows": self.def_rows,
                    "row_count": len(self.def_rows),
                }
            ],
        }


@pytest.fixture
def patched_db(monkeypatch):
    import query_database.service as svc

    monkeypatch.setattr(svc, "get_connection_config", _fake_conn_result)
    return svc


def _obj_row(oid, name, typ="P", has_def=1):
    return [oid, name, "dbo", typ, "SQL_STORED_PROCEDURE", "2024-01-01", "2024-06-01", has_def]


def test_ac_dbs_1_references_matched_lines(patched_db, monkeypatch):
    """AC-DBS-1: references=<bảng> -> list object + matched_lines đúng dòng."""
    import query_database.service as svc

    defs = [
        (1, "CREATE PROC p1\nAS\n  insert fsdSttRecRef (stt_rec)\n  select 1\n"),
        (2, "CREATE PROC p2\nAS\n  -- no match\n"),
    ]
    fake = _FakeExec([_obj_row(1, "p1"), _obj_row(2, "p2")], defs)
    monkeypatch.setattr(svc, "execute_query", fake)

    res = svc.query_database(
        file_path="x.xml", query="", mode="search", references="fsdSttRecRef"
    )
    assert res["success"] is True
    assert res["mode"] == "search"
    assert res["object_count"] == 2
    p1 = next(o for o in res["objects"] if o["name"] == "p1")
    assert p1["matched_lines"] == [
        {"line": 3, "text": "insert fsdSttRecRef (stt_rec)"}
    ]
    # references truyền qua params, không nối chuỗi
    q1 = fake.calls[0]
    assert "fsdSttRecRef" not in q1["query"]
    assert "fsdSttRecRef" in q1["params"]


def test_ac_dbs_2_object_name_like(patched_db, monkeypatch):
    """AC-DBS-2: object_name LIKE pattern -> truyền thẳng qua params."""
    import query_database.service as svc

    fake = _FakeExec([_obj_row(9, "zc_CreatePT1FromSO")])
    monkeypatch.setattr(svc, "execute_query", fake)
    res = svc.query_database(
        file_path="x.xml", query="", mode="search", object_name="zc_Create%SO"
    )
    assert res["success"] is True
    assert res["objects"][0]["name"] == "zc_CreatePT1FromSO"
    assert "zc_Create%SO" in fake.calls[0]["params"]
    assert "LIKE ?" in fake.calls[0]["query"]


def test_ac_dbs_3_injection_safe(patched_db, monkeypatch):
    """AC-DBS-3: references chứa % / ' / -- -> parameterized, SQL không chứa payload."""
    import query_database.service as svc

    payload = "x'; DROP TABLE sys.objects--%"
    fake = _FakeExec([])
    monkeypatch.setattr(svc, "execute_query", fake)
    res = svc.query_database(
        file_path="x.xml", query="", mode="search", references=payload
    )
    assert res["success"] is True
    q = fake.calls[0]["query"]
    assert "DROP TABLE" not in q
    assert payload in fake.calls[0]["params"]


def test_ac_dbs_4_object_types_whitelist(patched_db, monkeypatch):
    """AC-DBS-4: object_types='V' -> chỉ view trong IN-list; giá trị lạ bị drop."""
    import query_database.service as svc

    fake = _FakeExec([_obj_row(1, "v1", typ="V")])
    monkeypatch.setattr(svc, "execute_query", fake)
    res = svc.query_database(
        file_path="x.xml", query="", mode="search",
        object_name="%v%", object_types="V",
    )
    assert res["success"] is True
    assert "IN ('V')" in fake.calls[0]["query"]

    res2 = svc.query_database(
        file_path="x.xml", query="", mode="search",
        object_name="%x%", object_types="V,';DROP--",
    )
    assert res2["success"] is True
    assert "IN ('V')" in fake.calls[-1]["query"]
    assert "DROP" not in fake.calls[-1]["query"]


def test_ac_dbs_5_criteria_required_and_truncated(patched_db, monkeypatch):
    """AC-DBS-5: không criteria -> search_criteria_required; quá max_results -> truncated."""
    import query_database.service as svc

    res = svc.query_database(file_path="x.xml", query="", mode="search")
    assert res["success"] is False
    assert res["error_code"] == "search_criteria_required"

    fake = _FakeExec([_obj_row(i, f"p{i}") for i in range(4)])
    monkeypatch.setattr(svc, "execute_query", fake)
    res2 = svc.query_database(
        file_path="x.xml", query="", mode="search",
        object_name="p%", max_results=3,
    )
    assert res2["success"] is True
    assert res2["object_count"] == 3
    assert res2["truncated"] is True


def test_ac_dbs_6_encrypted_object_listed(patched_db, monkeypatch):
    """AC-DBS-6: object encrypted (has_definition=0) -> vẫn list, matched_lines rỗng."""
    import query_database.service as svc

    fake = _FakeExec([_obj_row(1, "encProc", has_def=0)])
    monkeypatch.setattr(svc, "execute_query", fake)
    res = svc.query_database(
        file_path="x.xml", query="", mode="search", references="abc"
    )
    assert res["success"] is True
    obj = res["objects"][0]
    assert obj["has_definition"] == 0
    assert obj["matched_lines"] == []
    # không gọi query definition cho object không có definition
    assert len(fake.calls) == 1


# ---------------------------------------------------------------------------
# AC-REF-* — search_files mode='references'
# ---------------------------------------------------------------------------


@pytest.fixture
def ref_project(tmp_path):
    root = tmp_path / "ref_proj"
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
        "function send() {\n\tBase64.encode(data);\n}\n",
        encoding="utf-8",
    )
    main = root / "Main"
    main.mkdir(parents=True, exist_ok=True)
    (main / "login.aspx").write_text(
        "<script>\nBase64.encode(token);\n</script>\n", encoding="utf-8"
    )
    return root


def test_ac_ref_1_usages_listed(ref_project):
    """AC-REF-1: mode=references -> usages[] đủ path/line/preview + usage_count."""
    res = search_files(
        root=str(ref_project), mode="references", symbol="Base64",
        include_glob="*.{js,aspx}",
    )
    assert res["success"] is True
    assert res["mode"] == "references"
    assert res["usage_count"] == len(res["usages"]) == 3
    for u in res["usages"]:
        assert {"path", "line", "preview", "is_definition"} <= set(u)
    paths = [u["path"] for u in res["usages"]]
    assert any("jAjax.js" in p for p in paths)
    assert any("login.aspx" in p for p in paths)


def test_ac_ref_2_definition_not_in_usages(ref_project):
    """AC-REF-2: dòng definition không đếm vào usages; definitions[] kèm kind."""
    res = search_files(
        root=str(ref_project), mode="references", symbol="Base64",
        include_glob="*.js",
    )
    assert res["definition_count"] == 1
    assert res["definitions"][0]["kind"] == "var"
    assert all(u["is_definition"] is False for u in res["usages"])
    assert not any(
        u["path"].endswith("hwcrypto.js") and u["line"] == 1 for u in res["usages"]
    )

    res_no_def = search_files(
        root=str(ref_project), mode="references", symbol="Base64",
        include_glob="*.js", include_definitions=False,
    )
    assert "definitions" not in res_no_def
    assert res_no_def["definition_count"] == 1  # vẫn đếm, chỉ ẩn list


def test_ac_ref_3_truncated_warning(tmp_path):
    """AC-REF-3: truncated -> warning cấm kết luận ít usage."""
    root = tmp_path / "many_proj"
    root.mkdir(parents=True, exist_ok=True)
    for i in range(6):
        (root / f"f{i}.js").write_text("Target.call();\n", encoding="utf-8")
    res = search_files(
        root=str(root), mode="references", symbol="Target",
        include_glob="*.js", max_files=2, prefer_name_match=False,
    )
    assert res["success"] is True
    assert res["truncated"] is True
    assert any("candidates not opened" in w for w in res["warnings"])


def test_ac_ref_4_other_modes_no_regress(ref_project):
    """AC-REF-4: content/definition/files_only không regress."""
    r1 = search_files(root=str(ref_project), pattern="Base64")
    assert r1["success"] is True and r1["total_matches"] >= 3
    r2 = search_files(root=str(ref_project), mode="definition", symbol="Base64")
    assert r2["definition_found"] is True
    r3 = search_files(root=str(ref_project), mode="files_only")
    assert r3["files_scanned"] == 0
    r_bad = search_files(root=str(ref_project), mode="references", symbol="")
    assert r_bad["success"] is False
    assert r_bad["error_code"] == "invalid_symbol"


# ---------------------------------------------------------------------------
# AC-BATCH-* — edits[] trong read_option=4
# ---------------------------------------------------------------------------


def test_ac_batch_1_multi_edit_one_diff(tmp_path):
    """AC-BATCH-1: 3 edits -> 1 diff_preview tổng + 1 post_edit_check, edits_applied=3."""
    f = tmp_path / "b.js"
    before = _mtime(f) if f.exists() else None
    f.write_text(
        "var link_url = getLink();\n"
        "open(link_url);\n"
        "log(link_url);\n",
        encoding="utf-8",
    )
    before = _mtime(f)
    res = suggest_edit(
        str(f),
        edits=[
            {"old_string": "var link_url = getLink();",
             "new_string": "var voucher_url = getLink();"},
            {"old_string": "open(link_url);", "new_string": "open(voucher_url);"},
            {"old_string": "log(link_url);", "new_string": "log(voucher_url);"},
        ],
    )
    assert res["success"] is True
    assert res["edits_applied"] == 3
    assert len(res["edits"]) == 3
    assert res["diff_preview"] and "voucher_url" in res["diff_preview"]
    assert res["post_edit_check"]["js_parse"] == "ok"
    assert _mtime(f) == before
    # file gốc không đổi
    assert "link_url" in f.read_text(encoding="utf-8")


def test_ac_batch_2_chained_rename(tmp_path):
    """AC-BATCH-2: edit sau khớp text do edit trước tạo (rename dây chuyền)."""
    f = tmp_path / "c.js"
    f.write_text("var link_url = 'a';\ncall(link_url);\n", encoding="utf-8")
    res = suggest_edit(
        str(f),
        edits=[
            {"old_string": "link_url = 'a'", "new_string": "voucher_url = 'a'"},
            # 'voucher_url' chỉ tồn tại sau edit 1 — chứng minh apply tuần tự
            {"old_string": "voucher_url = 'a'", "new_string": "voucher_url = 'b'"},
        ],
    )
    assert res["success"] is True
    assert res["edits_applied"] == 2
    assert "voucher_url = 'b'" in res["diff_preview"]


def test_ac_batch_3_stop_on_fail(tmp_path):
    """AC-BATCH-3: edit giữa fail -> dừng chuỗi, edits_applied=số thành công, diff phần đã apply."""
    f = tmp_path / "d.js"
    f.write_text("aaa\nbbb\nccc\n", encoding="utf-8")
    res = suggest_edit(
        str(f),
        edits=[
            {"old_string": "aaa", "new_string": "AAA"},
            {"old_string": "khong_ton_tai", "new_string": "X"},
            {"old_string": "ccc", "new_string": "CCC"},
        ],
    )
    assert res["success"] is False
    assert res["edits_applied"] == 1
    assert res["edits"][0]["success"] is True
    assert res["edits"][1]["success"] is False
    assert res["edits"][1]["error_code"] == "old_string_not_found"
    # diff chỉ phần đã apply (AAA), không có CCC
    assert "AAA" in res["diff_preview"]
    assert "CCC" not in res["diff_preview"]
    assert f.read_text(encoding="utf-8") == "aaa\nbbb\nccc\n"


def test_ac_batch_4_overlap_detected(tmp_path):
    """AC-BATCH-4: vùng edit chồng lấn -> overlap_detected, buffer không corrupt."""
    f = tmp_path / "e.js"
    f.write_text("aaa\nbbb\nccc\n", encoding="utf-8")
    res = suggest_edit(
        str(f),
        edits=[
            {"old_string": "bbb", "new_string": "B\nB2\nB3"},
            # edit2 anchor 'B3\nccc' cắt ngang vùng edit1 vừa ghi
            {"old_string": "B3\nccc", "new_string": "X"},
        ],
    )
    assert res["success"] is False
    assert res["edits_applied"] == 1
    assert res["edits"][1]["error_code"] == "overlap_detected"
    assert f.read_text(encoding="utf-8") == "aaa\nbbb\nccc\n"


def test_ac_batch_5_no_write_and_ambiguous(tmp_path):
    """AC-BATCH-5: không file nào bị ghi; selector + edits -> ambiguous_target; single path không regress."""
    f = tmp_path / "f.js"
    f.write_text("function ok() {\n\treturn 1;\n}\n", encoding="utf-8")
    before = _mtime(f)
    res = suggest_edit(
        str(f),
        old_string="return 1;",
        edits=[{"old_string": "x", "new_string": "y"}],
    )
    assert res["success"] is False
    assert res["error_code"] == "ambiguous_target"
    assert _mtime(f) == before

    # edits rỗng -> missing_target
    res2 = suggest_edit(str(f), edits=[])
    assert res2["success"] is False
    assert res2["error_code"] == "missing_target"

    # single-edit path không regress
    res3 = suggest_edit(str(f), symbol="ok", new_string="function ok() { return 2; }")
    assert res3["success"] is True
    assert res3["mode"] == "suggest_edit"
    assert _mtime(f) == before
