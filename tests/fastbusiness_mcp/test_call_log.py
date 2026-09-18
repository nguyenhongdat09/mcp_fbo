"""AC-LOG-* — JSONL tool call logging.

Spec: docs/doc/gemini/GEMINI-mcp-call-logging.md
"""

from __future__ import annotations

import asyncio
import json
import re
import threading

import pytest

from fastbusiness_mcp.utils import call_log


@pytest.fixture
def log_dir(tmp_path):
    d = tmp_path / "logs"
    call_log.set_log_dir(d)
    yield d
    call_log.set_log_dir(None)


def _today_file(d):
    files = list(d.glob("mcp-*.jsonl"))
    assert len(files) == 1, f"expected 1 daily file, got {files}"
    return files[0]


def _call_records(d):
    """Parse JSONL, bỏ dòng event (server_start) — chỉ giữ tool call."""
    f = _today_file(d)
    return [
        json.loads(line)
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and '"tool"' in line
    ]


# ---------------------------------------------------------------------------
# AC-LOG-1: mỗi call → đúng 1 dòng JSONL đủ field
# ---------------------------------------------------------------------------
def test_ac_log_1_one_jsonl_line_per_call(log_dir):
    call_log.log_tool_call(
        "read_local_file",
        {"file_path": "Grid/SOTran.xml", "symbol": "load$Form", "read_option": 1},
        42.4,
        response_text=json.dumps(
            {"success": True, "mode": "snippet", "snippets": [{"a": 1}, {"a": 2}]}
        ),
    )
    recs = _call_records(log_dir)
    assert len(recs) == 1
    r = recs[0]
    assert r["tool"] == "read_local_file"
    assert r["ok"] is True
    assert r["ms"] == 42.4
    assert r["input"]["file_path"] == "Grid/SOTran.xml"
    assert r["input"]["read_option"] == 1
    assert r["result_summary"]["mode"] == "snippet"
    assert r["result_summary"]["snippets_n"] == 2
    assert "error_code" not in r
    assert "result_full" not in r  # call OK → không nhúng full response


# ---------------------------------------------------------------------------
# AC-LOG-2: fail → result_full + error_code; exception → exc_type
# ---------------------------------------------------------------------------
def test_ac_log_2_failed_call_has_result_full(log_dir):
    call_log.log_tool_call(
        "read_local_file",
        {"file_path": "Grid/X.xml", "symbol": "nope"},
        10,
        response_text=json.dumps(
            {
                "success": False,
                "error_code": "symbol_not_found",
                "message": "không thấy symbol",
                "available_functions_n": 0,
            }
        ),
    )
    (r,) = _call_records(log_dir)
    assert r["ok"] is False
    assert r["error_code"] == "symbol_not_found"
    assert r["message"] == "không thấy symbol"
    assert "symbol_not_found" in r["result_full"]


def test_ac_log_2_exception_logged(log_dir):
    call_log.log_tool_call("tool_x", {"a": 1}, 5, exc=ValueError("boom"))
    (r,) = _call_records(log_dir)
    assert r["ok"] is False
    assert r["error_code"] == "exception"
    assert r["exc_type"] == "ValueError"
    assert r["message"] == "boom"


def test_ac_log_2_text_error_detected(log_dir):
    """Response text non-JSON bắt đầu [LỖI → ok=false, error_response."""
    call_log.log_tool_call(
        "query_radar", {"cypher_query": "MATCH..."}, 99,
        response_text="\n[LỖI CÚ PHÁP CYPHER KUZUDB]\nchi tiết...",
    )
    (r,) = _call_records(log_dir)
    assert r["ok"] is False
    assert r["error_code"] == "error_response"
    assert "[LỖI" in r["result_full"]


# ---------------------------------------------------------------------------
# AC-LOG-3: warnings/truncated/project_root/resolved_via copy đủ
# ---------------------------------------------------------------------------
def test_ac_log_3_context_fields_copied(log_dir):
    call_log.log_tool_call(
        "search_files",
        {"root": "Grid"},
        7,
        response_text=json.dumps(
            {
                "success": True,
                "project_root": "\\\\172.168.5.14\\p\\FBISP2422",
                "resolved_via": "sticky_context",
                "warnings": ["project_root switched: A → B"],
                "truncated": False,
                "matches": [],
            }
        ),
    )
    (r,) = _call_records(log_dir)
    assert r["ok"] is True
    assert r["project_root"].endswith("FBISP2422")
    assert r["resolved_via"] == "sticky_context"
    assert r["warnings"] == ["project_root switched: A → B"]
    assert r["truncated"] is False
    assert r["result_summary"]["matches_n"] == 0


# ---------------------------------------------------------------------------
# AC-LOG-4: redact pass|secret|token|key; field >4000 chars cắt kèm marker
# ---------------------------------------------------------------------------
def test_ac_log_4_redact_sensitive_and_cap(log_dir):
    long_sql = "x" * 5000
    call_log.log_tool_call(
        "query_database",
        {
            "query": long_sql,
            "password": "s3cret",
            "api_key": "abc123",
            "nested": {"access_token": "tok", "safe": "v"},
        },
        1,
        response_text='{"success": true}',
    )
    (r,) = _call_records(log_dir)
    assert r["input"]["password"] == "***"
    assert r["input"]["api_key"] == "***"
    assert r["input"]["nested"]["access_token"] == "***"
    assert r["input"]["nested"]["safe"] == "v"
    q = r["input"]["query"]
    assert len(q) < 5000
    assert q.endswith("... [truncated 1000 chars]")


# ---------------------------------------------------------------------------
# AC-LOG-5: không byte nào ra stdout; UNC không bao giờ là log target
# ---------------------------------------------------------------------------
def test_ac_log_5_no_stdout(log_dir, capsys):
    call_log.log_tool_call("t", {"a": 1}, 1, response_text='{"success": true}')
    captured = capsys.readouterr()
    assert captured.out == ""


def test_ac_log_5_unc_dir_rejected():
    call_log.set_log_dir("\\\\server\\share\\logs")
    try:
        d = call_log.get_log_dir()
        assert not str(d).startswith("\\\\")
        assert d.name == "logs"
    finally:
        call_log.set_log_dir(None)


# ---------------------------------------------------------------------------
# AC-LOG-6: ghi log lỗi → tool vẫn bình thường, warn stderr 1 lần
# ---------------------------------------------------------------------------
def test_ac_log_6_log_write_failure_silent(tmp_path, capsys):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    call_log.set_log_dir(blocker)  # mkdir sẽ raise FileExistsError
    try:
        call_log.log_tool_call("t", {}, 1, response_text='{"success": true}')
        call_log.log_tool_call("t", {}, 1, response_text='{"success": true}')
        call_log.init_call_logging()
    finally:
        call_log.set_log_dir(None)
    err = capsys.readouterr().err
    assert "[call_log]" in err
    assert err.count("[call_log]") <= 2  # warn 1 lần, không spam mỗi call


# ---------------------------------------------------------------------------
# AC-LOG-7: file đổi theo ngày + retention 30 ngày
# ---------------------------------------------------------------------------
def test_ac_log_7_daily_filename(log_dir):
    call_log.log_tool_call("t", {}, 1)
    f = _today_file(log_dir)
    assert re.match(r"^mcp-\d{8}\.jsonl$", f.name)


def test_ac_log_7_retention_cleanup(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    old = d / "mcp-20200101.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    recent = d / "mcp-20990101.jsonl"
    recent.write_text("{}\n", encoding="utf-8")
    (d / "server.log").write_text("keep me", encoding="utf-8")
    call_log._cleanup_old_logs(d)
    assert not old.exists()
    assert recent.exists()
    assert (d / "server.log").exists()


# ---------------------------------------------------------------------------
# AC-LOG-8: 2 thread song song → 2 dòng hợp lệ, không xuyên dòng
# ---------------------------------------------------------------------------
def test_ac_log_8_thread_safe(log_dir):
    def worker(i):
        for j in range(5):
            call_log.log_tool_call(
                f"tool_{i}", {"i": i, "j": j}, 1,
                response_text='{"success": true}',
            )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    recs = _call_records(log_dir)
    assert len(recs) == 10
    assert {r["tool"] for r in recs} == {"tool_0", "tool_1"}
    assert all(r["input"]["i"] in (0, 1) for r in recs)


# ---------------------------------------------------------------------------
# Wrapper level (_logged_call_tool trong mcp_app)
# ---------------------------------------------------------------------------
class _FakeText:
    def __init__(self, text):
        self.text = text


class _FakeResult:
    def __init__(self, text, is_error=False):
        self.content = [_FakeText(text)]
        self.is_error = is_error


def test_wrapper_logs_and_returns_result(log_dir, monkeypatch):
    import fastbusiness_mcp.mcp_app as app

    expected = _FakeResult(json.dumps({"success": True, "mode": "x"}))

    async def fake(name, arguments, context=None):
        return expected

    monkeypatch.setattr(app, "_inner_call_tool", fake)
    out = asyncio.run(app._logged_call_tool("t", {"a": 1}))
    assert out is expected
    (r,) = _call_records(log_dir)
    assert r["tool"] == "t"
    assert r["ok"] is True
    assert r["result_summary"]["mode"] == "x"


def test_wrapper_exception_reraises_and_logs(log_dir, monkeypatch):
    import fastbusiness_mcp.mcp_app as app

    async def boom(name, arguments, context=None):
        raise RuntimeError("crash inside tool")

    monkeypatch.setattr(app, "_inner_call_tool", boom)
    with pytest.raises(RuntimeError, match="crash inside tool"):
        asyncio.run(app._logged_call_tool("t", {"a": 1}))
    (r,) = _call_records(log_dir)
    assert r["ok"] is False
    assert r["exc_type"] == "RuntimeError"


def test_wrapper_is_error_flag(log_dir, monkeypatch):
    import fastbusiness_mcp.mcp_app as app

    async def fake(name, arguments, context=None):
        return _FakeResult("something failed", is_error=True)

    monkeypatch.setattr(app, "_inner_call_tool", fake)
    asyncio.run(app._logged_call_tool("t", {}))
    (r,) = _call_records(log_dir)
    assert r["ok"] is False
    assert r["result_full"] == "something failed"


def test_extract_response_text_plain_str():
    text, is_error = call_log.extract_response_text('{"success": true}')
    assert text == '{"success": true}'
    assert is_error is False
    assert call_log.extract_response_text(None) == (None, False)


def test_call_log_extra_merged(log_dir):
    """extra dict được merge trực tiếp vào record JSONL."""
    call_log.log_tool_call(
        "search_files",
        {"root": "Grid"},
        12.5,
        response_text=json.dumps({"success": True, "files_n": 500}),
        extra={"oversized": True, "result_chars": 133469, "result_file": "C:\\logs\\overflow.json"},
    )
    (r,) = _call_records(log_dir)
    assert r["tool"] == "search_files"
    assert r["oversized"] is True
    assert r["result_chars"] == 133469
    assert r["result_file"] == "C:\\logs\\overflow.json"
    assert r["result_summary"]["files_n"] == 500

