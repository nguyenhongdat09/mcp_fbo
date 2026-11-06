"""Tests: nguồn (file gốc / entity) của hàm JS trong summary_xml."""

from __future__ import annotations

import os
import time
from pathlib import Path

from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
from xml_controller_summary.origins import (
    ORIGINAL_FILE_LABEL,
    build_function_origins,
    entity_label,
)


def _record(raw: str, source_file: str = r"E:\P\App_Data\Controllers\Include\A.ent", line: int = 5) -> dict:
    return {"source_file": source_file, "declared_in_file": source_file, "line": line, "raw": raw}


# ---------------------------------------------------------------------------
# Unit: build_function_origins
# ---------------------------------------------------------------------------

def test_function_in_entity_and_in_file():
    trace = {"ScriptA": _record("function in_entity(f) { return 1; }")}
    out = build_function_origins(["in_entity", "in_file"], trace)
    assert out[ORIGINAL_FILE_LABEL] == ["in_file"]
    label = entity_label("ScriptA", trace["ScriptA"])
    assert out[label] == ["in_entity"]
    assert label == "&ScriptA; (Include/A.ent:5)"


def test_original_file_label_is_first():
    trace = {"ScriptA": _record("function in_entity(f) {}")}
    out = build_function_origins(["in_entity", "in_file"], trace)
    assert list(out)[0] == ORIGINAL_FILE_LABEL


def test_call_only_is_not_a_definition():
    trace = {"ScriptA": _record("function other(f) { helper(f); }")}
    out = build_function_origins(["helper"], trace)
    assert out == {ORIGINAL_FILE_LABEL: ["helper"]}


def test_object_literal_and_assign_function_forms():
    trace = {
        "ScriptA": _record("var o = { create: function(f) {}, other: 1 };\nhandler = function(x) {};"),
    }
    out = build_function_origins(["create", "handler"], trace)
    assert out == {"&ScriptA; (Include/A.ent:5)": ["create", "handler"]}


def test_name_assembled_from_fragment_entity():
    # function set$]]>&Identity;<![CDATA[Name(...) với Identity = "PVTranImport"
    trace = {
        "ImportXmlScript": _record("function set$]]>&Identity;<![CDATA[Name(id) {}\nfunction plain(f) {}"),
        "Identity": _record("PVTranImport", line=3),
    }
    out = build_function_origins(["setPVTranImportName".replace("set", "set$"), "plain"], trace)
    label = entity_label("ImportXmlScript", trace["ImportXmlScript"])
    assert out == {label: ["set$PVTranImportName", "plain"]}


def test_nested_entity_function_goes_to_inner_entity_only():
    trace = {
        "Outer": _record("function outer_fn(f) {}\n&Inner;"),
        "Inner": _record("function inner_fn(f) {}\n" + "x" * 200, line=9),
    }
    out = build_function_origins(["outer_fn", "inner_fn"], trace)
    assert out[entity_label("Outer", trace["Outer"])] == ["outer_fn"]
    assert out[entity_label("Inner", trace["Inner"])] == ["inner_fn"]


def test_code_entity_is_not_collapsed_into_parent():
    # Inner ngắn nhưng chứa "function" nên không được coi là mảnh tên.
    trace = {
        "Outer": _record("function outer_fn(f) {}\n&Inner;"),
        "Inner": _record("function inner_fn(f) {}"),
    }
    out = build_function_origins(["outer_fn", "inner_fn"], trace)
    assert out[entity_label("Outer", trace["Outer"])] == ["outer_fn"]
    assert out[entity_label("Inner", trace["Inner"])] == ["inner_fn"]


def test_name_built_in_main_file_stays_original_file():
    # Tên ghép nằm trong chính file chính (không có trong trace) -> Original File.
    trace = {"Identity": _record("PVTranImport")}
    out = build_function_origins(["insert$PVTranImportForm$Retrieve$Data"], trace)
    assert out == {ORIGINAL_FILE_LABEL: ["insert$PVTranImportForm$Retrieve$Data"]}


def test_empty_inputs():
    assert build_function_origins([], {"A": _record("function a() {}")}) == {}
    assert build_function_origins(["a"], None) == {ORIGINAL_FILE_LABEL: ["a"]}


# ---------------------------------------------------------------------------
# Integration: summary_xml trên dự án tạm
# ---------------------------------------------------------------------------

MAIN_XML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
  <!ENTITY Identity "ZzTran">
  <!ENTITY ScriptInline "function inline_fn(f) { return 2; }">
  <!ENTITY ScriptInclude SYSTEM "..\\Include\\Javascript\\ScriptInclude.txt">
]>
<dir table="m00$000000" code="stt_rec" xmlns="urn:schemas-fast-com:data-dir">
  <fields>
    <field name="stt_rec"><header v="" e=""></header></field>
  </fields>
  <script>
    <text>
      <![CDATA[
function in_file(f) { return 1; }
function init$]]>&Identity;<![CDATA[Form$(f) { return 3; }
]]>
      &ScriptInline;
      &ScriptInclude;
    </text>
  </script>
</dir>
"""

INCLUDE_TXT = "function from_include(f) { return 4; }\n"


def _make_project(tmp_path: Path) -> Path:
    controllers = tmp_path / "App_Data" / "Controllers"
    (controllers / "Dir").mkdir(parents=True)
    (controllers / "Include" / "Javascript").mkdir(parents=True)
    main = controllers / "Dir" / "ZzTran.xml"
    main.write_text(MAIN_XML, encoding="utf-8")
    (controllers / "Include" / "Javascript" / "ScriptInclude.txt").write_text(INCLUDE_TXT, encoding="utf-8")
    return main


def test_summary_xml_function_origins_integration(tmp_path):
    main = _make_project(tmp_path)
    res = summary_xml(str(main), use_cache=False)
    assert res["success"] is True

    origins = res["js"]["function_origins"]
    assert list(origins)[0] == ORIGINAL_FILE_LABEL
    assert "in_file" in origins[ORIGINAL_FILE_LABEL]
    # Tên ghép từ &Identity; nằm trong file chính -> Original File (không bị gán nhầm entity).
    assert "init$ZzTranForm$" in origins[ORIGINAL_FILE_LABEL]

    inline_key = next(k for k in origins if k.startswith("&ScriptInline;"))
    assert origins[inline_key] == ["inline_fn"]
    assert "Dir/ZzTran.xml:" in inline_key

    include_key = next(k for k in origins if k.startswith("&ScriptInclude;"))
    assert origins[include_key] == ["from_include"]
    assert "Include/Javascript/ScriptInclude.txt" in include_key

    # js.functions vẫn là mảng chuỗi đầy đủ (không đổi kiểu).
    assert {"in_file", "inline_fn", "from_include", "init$ZzTranForm$"} <= set(res["js"]["functions"])


def test_summary_cache_invalidated_when_include_changes(tmp_path):
    main = _make_project(tmp_path)
    r1 = summary_xml(str(main), use_cache=True)
    assert "from_include" in r1["js"]["functions"]

    include = main.parent.parent / "Include" / "Javascript" / "ScriptInclude.txt"
    include.write_text(
        INCLUDE_TXT + "function added_later(f) { return 5; }\n", encoding="utf-8"
    )
    # Đảm bảo mtime đổi dù hệ thống file có độ phân giải thô.
    now = time.time() + 5
    os.utime(include, (now, now))

    r2 = summary_xml(str(main), use_cache=True)
    assert "added_later" in r2["js"]["functions"]
    include_key = next(k for k in r2["js"]["function_origins"] if k.startswith("&ScriptInclude;"))
    assert "added_later" in r2["js"]["function_origins"][include_key]


def test_summary_without_functions_has_no_origins_key(tmp_path):
    xml = tmp_path / "App_Data" / "Controllers" / "Dir" / "NoJs.xml"
    xml.parent.mkdir(parents=True)
    xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<dir table="dmx" code="ma" xmlns="urn:schemas-fast-com:data-dir">'
        '<fields><field name="ma"><header v="" e=""></header></field></fields></dir>',
        encoding="utf-8",
    )
    res = summary_xml(str(xml), use_cache=False)
    assert res["js"]["functions"] == []
    assert "function_origins" not in res["js"]
