"""Tests for MCP response oversize guard (AC-OVF-1..9).

Spec: docs/doc/gemini/GEMINI-mcp-response-oversize-guard.md
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp.types import CallToolResult, TextContent

from fastbusiness_mcp import mcp_app
from fastbusiness_mcp.utils import call_log, response_guard


@pytest.fixture
def log_dir(tmp_path):
    d = tmp_path / "logs"
    call_log.set_log_dir(d)
    response_guard._reset_warned()
    yield d
    call_log.set_log_dir(None)
    response_guard._reset_warned()


def _call_records(d):
    files = list(d.glob("mcp-*.jsonl"))
    if not files:
        return []
    f = files[0]
    return [
        json.loads(line)
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and '"tool"' in line
    ]


# ---------------------------------------------------------------------------
# AC-OVF-1: Response <= ngưỡng → trả y nguyên, guard_meta=None
# ---------------------------------------------------------------------------
def test_ac_ovf_1_under_cap_passthrough(log_dir):
    text = json.dumps({"success": True, "data": "small payload"})
    res, meta = response_guard.apply("tool_test", text, text, max_chars=1000)
    assert res == text
    assert meta is None
    # Không sinh file overflow nào
    assert len(list(log_dir.glob("overflow-*"))) == 0


# ---------------------------------------------------------------------------
# AC-OVF-2: Response > ngưỡng → spill file tồn tại với full content, compact JSON
# ---------------------------------------------------------------------------
def test_ac_ovf_2_oversized_spills_and_returns_compact(log_dir):
    raw_dict = {
        "success": True,
        "files": [f"file_{i}.txt" for i in range(2000)],
        "note": "large response",
    }
    raw_text = json.dumps(raw_dict, ensure_ascii=False)
    assert len(raw_text) > 1000

    compact_res, meta = response_guard.apply("search_files", raw_text, raw_text, max_chars=1000)

    # 1. File spill tồn tại
    spill_files = list(log_dir.glob("overflow-search_files-*.json"))
    assert len(spill_files) == 1
    spill_path = spill_files[0]
    assert spill_path.read_text(encoding="utf-8") == raw_text

    # 2. meta có đủ field
    assert meta is not None
    assert meta["oversized"] is True
    assert meta["result_chars"] == len(raw_text)
    assert meta["result_file"] == str(spill_path.resolve())

    # 3. Compact response có đủ các trường spec yêu cầu
    compact_dict = json.loads(compact_res)
    assert compact_dict["success"] is True
    assert compact_dict["oversized"] is True
    assert compact_dict["tool"] == "search_files"
    assert compact_dict["result_chars"] == len(raw_text)
    assert compact_dict["result_file"] == str(spill_path.resolve())
    assert "hint" in compact_dict
    assert "read_local_file" in compact_dict["hint"]
    assert "summary" in compact_dict


# ---------------------------------------------------------------------------
# AC-OVF-3: Compact JSON <= vài KB; summary giữ counts (_n), không nhúng mảng lớn
# ---------------------------------------------------------------------------
def test_ac_ovf_3_compact_payload_small_and_summary_counts(log_dir):
    raw_dict = {
        "success": True,
        "items": [{"id": i, "content": "x" * 100} for i in range(1000)],
    }
    raw_text = json.dumps(raw_dict)
    compact_res, _ = response_guard.apply("search_files", raw_text, raw_text, max_chars=500)

    assert len(compact_res.encode("utf-8")) < 2000  # < 2 KB
    compact_dict = json.loads(compact_res)
    summary = compact_dict["summary"]
    assert summary.get("items_n") == 1000
    assert "items" not in summary  # không nhúng cả mảng 1000 phần tử


# ---------------------------------------------------------------------------
# AC-OVF-4: Ghi file fail → trả response gốc y nguyên, warn stderr, tool call không hỏng
# ---------------------------------------------------------------------------
def test_ac_ovf_4_spill_write_fail_falls_back_to_original(tmp_path, capsys):
    # Đặt log_dir trỏ vào file để open() ghi file bị lỗi
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    call_log.set_log_dir(blocker)
    response_guard._reset_warned()

    try:
        raw_text = "x" * 2000
        res, meta = response_guard.apply("tool_err", raw_text, raw_text, max_chars=500)
        # Trả về kết quả gốc
        assert res == raw_text
        assert meta is None

        # Cảnh báo qua stderr
        err = capsys.readouterr().err
        assert "[response_guard]" in err
        assert "spill write failed" in err
    finally:
        call_log.set_log_dir(None)
        response_guard._reset_warned()


# ---------------------------------------------------------------------------
# AC-OVF-5: result dạng str lẫn CallToolResult / object .content đều replace đúng; kiểu lạ → passthrough
# ---------------------------------------------------------------------------
def test_ac_ovf_5_replace_result_types(log_dir):
    raw_text = json.dumps({"success": True, "data": "x" * 2000})

    # Case 1: result là str
    res_str, meta_str = response_guard.apply("tool1", raw_text, raw_text, max_chars=500)
    assert isinstance(res_str, str)
    assert json.loads(res_str)["oversized"] is True

    # Case 2: result là CallToolResult (pydantic object với .content)
    orig_ctr = CallToolResult(
        content=[TextContent(type="text", text=raw_text)],
        is_error=False,
    )
    res_ctr, meta_ctr = response_guard.apply("tool2", orig_ctr, raw_text, max_chars=500)
    assert isinstance(res_ctr, CallToolResult)
    assert len(res_ctr.content) == 1
    assert res_ctr.content[0].type == "text"
    parsed_ctr = json.loads(res_ctr.content[0].text)
    assert parsed_ctr["oversized"] is True
    assert res_ctr.is_error is False

    # Case 3: result là kiểu lạ không hỗ trợ (vd số int, dict lạ không có .content)
    strange_obj = 12345
    res_strange, meta_strange = response_guard.apply("tool3", strange_obj, raw_text, max_chars=500)
    assert res_strange == strange_obj
    assert meta_strange is None


# ---------------------------------------------------------------------------
# AC-OVF-6: Log JSONL của call oversize có oversized:true + result_chars + result_file,
#           result_summary vẫn từ payload gốc
# ---------------------------------------------------------------------------
def test_ac_ovf_6_logged_call_tool_integration(log_dir, monkeypatch):
    big_data = {
        "success": True,
        "files": [f"f_{i}.txt" for i in range(500)],
        "files_candidate": 500,
    }
    raw_text = json.dumps(big_data)

    async def fake_tool(name, arguments, context=None):
        return CallToolResult(content=[TextContent(type="text", text=raw_text)])

    monkeypatch.setattr(mcp_app, "_inner_call_tool", fake_tool)
    monkeypatch.setattr(mcp_app, "get_config", lambda: {"response_guard": {"max_chars": 500}})

    out = asyncio.run(mcp_app._logged_call_tool("search_files", {"root": "Dir"}))

    # Client nhận compact JSON
    compact_data = json.loads(out.content[0].text)
    assert compact_data["oversized"] is True
    assert "result_file" in compact_data

    # Log JSONL ghi nhận đúng
    recs = _call_records(log_dir)
    assert len(recs) == 1
    r = recs[0]
    assert r["tool"] == "search_files"
    assert r["oversized"] is True
    assert r["result_chars"] == len(raw_text)
    assert r["result_file"] == compact_data["result_file"]
    # result_summary vẫn được tính từ raw_text ban đầu!
    assert r["result_summary"]["files_n"] == 500
    assert r["result_summary"]["files_candidate"] == 500


# ---------------------------------------------------------------------------
# AC-OVF-7: Không byte nào ra stdout; spill file luôn local (không UNC)
# ---------------------------------------------------------------------------
def test_ac_ovf_7_no_stdout_and_local_file(log_dir, capsys):
    raw_text = "x" * 2000
    res, meta = response_guard.apply("tool_stdout", raw_text, raw_text, max_chars=500)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert meta is not None
    assert not meta["result_file"].startswith("\\\\")
    assert not meta["result_file"].startswith("//")


# ---------------------------------------------------------------------------
# AC-OVF-8: File overflow-* > 7 ngày bị dọn lúc server start; mcp-*.jsonl retention 30 ngày
# ---------------------------------------------------------------------------
def test_ac_ovf_8_cleanup_overflow_retention(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()

    # Tạo file overflow cũ 10 ngày
    old_ovf_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
    old_ovf = d / f"overflow-search_files-{old_ovf_date}-100000-000.json"
    old_ovf.write_text("{}", encoding="utf-8")

    # Tạo file overflow mới 2 ngày
    new_ovf_date = (datetime.now() - timedelta(days=2)).strftime("%Y%m%d")
    new_ovf = d / f"overflow-search_files-{new_ovf_date}-100000-000.json"
    new_ovf.write_text("{}", encoding="utf-8")

    # Tạo file mcp jsonl cũ 15 ngày (vẫn < 30 ngày -> giữ)
    mid_log_date = (datetime.now() - timedelta(days=15)).strftime("%Y%m%d")
    mid_log = d / f"mcp-{mid_log_date}.jsonl"
    mid_log.write_text("{}\n", encoding="utf-8")

    # Tạo file mcp jsonl cũ 35 ngày (> 30 ngày -> xóa)
    old_log_date = (datetime.now() - timedelta(days=35)).strftime("%Y%m%d")
    old_log = d / f"mcp-{old_log_date}.jsonl"
    old_log.write_text("{}\n", encoding="utf-8")

    call_log._cleanup_old_logs(d)

    # overflow cũ 10 ngày bị xóa, overflow mới 2 ngày còn
    assert not old_ovf.exists()
    assert new_ovf.exists()

    # jsonl cũ 35 ngày bị xóa, jsonl 15 ngày vẫn còn
    assert not old_log.exists()
    assert mid_log.exists()


# ---------------------------------------------------------------------------
# AC-OVF-9: Ngưỡng đổi được qua config.yaml response_guard.max_chars; thiếu key -> default 60000
# ---------------------------------------------------------------------------
def test_ac_ovf_9_config_max_chars(log_dir, monkeypatch):
    # Test fallback default 60000
    cfg_empty = {}
    guard_cfg = cfg_empty.get("response_guard") or {}
    val = guard_cfg.get("max_chars", response_guard._MAX_RESPONSE_CHARS)
    assert val == 60000

    # Test lấy từ config
    cfg_custom = {"response_guard": {"max_chars": 80000}}
    guard_cfg2 = cfg_custom.get("response_guard") or {}
    val2 = guard_cfg2.get("max_chars", response_guard._MAX_RESPONSE_CHARS)
    assert val2 == 80000
