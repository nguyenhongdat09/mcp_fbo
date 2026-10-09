"""Tests recovery tầng wrapper (tool_help/recovery.py).

Response lỗi lấy nguyên dạng từ log thật E:\\fastbusiness_mcp\\logs.
"""
from __future__ import annotations

import json

from tool_help.recovery import attach_recovery, build_recovery

_CTR = "\\\\172.168.5.14\\CustomerPro\\FBI\\HAOHOA\\FBISP2421\\App_Data\\Controllers"


def _resp(**kw) -> str:
    return json.dumps({"success": False, **kw}, ensure_ascii=False)


def test_old_string_not_found_points_to_option4():
    args = {"file_path": _CTR + "\\Dir\\X.xml", "old_string": "INTO functions",
            "read_option": 4}
    rec = build_recovery("read_local_file", args, _resp(
        error_code="old_string_not_found", closest_match=[],
        hint="old_string không khớp file vật lý"))
    assert rec["rule"] == "old_string_not_found"
    assert rec["next"]["call"]["read_option"] == 4
    assert rec["next"]["call"]["file_path"] == args["file_path"]
    # tool đã có closest_match → không lặp
    assert build_recovery("read_local_file", args, _resp(
        error_code="old_string_not_found", closest_match=["x"])) is None


def test_symbol_not_found_switches_to_search():
    args = {"file_path": "ClientScript\\j5.js", "symbol": "registerClass"}
    rec = build_recovery("read_local_file", args, _resp(
        error_code="symbol_not_found", symbol="registerClass",
        available_functions=["getDays"]))
    assert rec["kind"] == "switch_tool"
    assert rec["next"] == {"tool": "search_files", "call": {
        "root": "ClientScript", "mode": "content",
        "pattern": "registerClass"}}


def test_block_not_found_did_you_mean():
    rec = build_recovery("read_local_file",
                         {"block": "command:Inserted2"}, _resp(
                             error_code="block_not_found",
                             block="command:Inserted2",
                             available={"commands": ["Inserting", "Inserted",
                                                     "Updating"],
                                        "actions": ["Reading"]}))
    assert rec["did_you_mean"][0] == "command:Inserted"


def test_path_not_found_only_when_no_hint():
    fp = _CTR + "\\Dir\\zcdmxn.xml"
    assert build_recovery("read_local_file", {"file_path": fp}, _resp(
        error_code="path_not_found", input=fp,
        hint="Gần giống: zcdmsanh.xml")) is None
    rec = build_recovery("read_local_file", {"file_path": fp}, _resp(
        error_code="path_not_found", input=fp))
    assert rec["next"]["call"] == {"root": _CTR + "\\Dir",
                                   "mode": "files_only",
                                   "include_glob": "*zcdmxn*"}


def test_missing_param_names_wrong_key():
    # log thật: agent truyền search_query thay vì pattern
    args = {"glob_pattern": "zc*.xml", "root": _CTR + "\\Dir",
            "search_query": "titleV"}
    rec = build_recovery("search_files", args, _resp(
        error_code="invalid_pattern", message="pattern is required"))
    assert rec["rule"] == "invalid_pattern"
    assert "Thiếu param 'pattern'" in rec["hint"]
    assert "glob_pattern" in rec["hint"] or "search_query" in rec["hint"]


def test_generic_required_message_without_known_code():
    rec = build_recovery("query_database", {"file_path": "x"}, _resp(
        error="query is required"))
    assert rec["rule"] == "missing_param"


def test_no_recovery_for_success_or_text_or_existing():
    assert build_recovery("x", {}, '{"success": true}') is None
    assert build_recovery("x", {}, "[ERROR] Invalid column name 'a'") is None
    assert build_recovery("x", {}, _resp(error_code="path_not_found",
                                         recovery={"rule": "r"})) is None
    assert build_recovery("x", {}, "not json {") is None


def test_attach_keeps_valid_json_and_call_log_reads_rule(tmp_path):
    from mcp.types import CallToolResult, TextContent

    from fastbusiness_mcp.utils import call_log

    text = _resp(error_code="symbol_not_found", symbol="f")
    result = CallToolResult(content=[TextContent(type="text", text=text)])
    rec = build_recovery("read_local_file", {"symbol": "f",
                                             "file_path": "a\\b.xml"}, text)
    new_result, new_text = attach_recovery(result, text, rec)
    data = json.loads(new_result.content[0].text)        # vẫn là JSON
    assert data["recovery"]["rule"] == "symbol_not_found"
    assert data["error_code"] == "symbol_not_found"      # lỗi gốc giữ nguyên

    call_log.set_log_dir(tmp_path)
    try:
        call_log.log_tool_call("read_local_file", {}, 1.0,
                               response_text=new_text)
    finally:
        call_log.set_log_dir(None)
    line = next(tmp_path.glob("mcp-*.jsonl")).read_text(
        encoding="utf-8").splitlines()[-1]
    r = json.loads(line)
    assert r["ok"] is False and r["recovery_rule"] == "symbol_not_found"
