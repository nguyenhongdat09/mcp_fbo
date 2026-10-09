"""Tests router tự học (scripts/jev_feedback) trên fixture JSONL nhỏ."""
from __future__ import annotations

import json

from scripts.jev_feedback import label as lb
from scripts.jev_feedback import load, reports


def _write_log(tmp_path, records, day="20261009"):
    d = tmp_path / "logs"
    d.mkdir(exist_ok=True)
    with open(d / f"mcp-{day}.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return d


def _help(sid, seq, routing, ts="2026-10-09T10:00:00"):
    return {"session_id": sid, "seq": seq, "ts": ts, "tool": "tool_help",
            "ok": True, "input": {"steps": [r["step"] for r in routing]},
            "help_id": f"h{seq}", "routing": routing}


def _call(sid, seq, tool, inp, ok=True, ts="2026-10-09T10:00:05", **kw):
    return {"session_id": sid, "seq": seq, "ts": ts, "tool": tool,
            "input": inp, "ok": ok, **kw}


def _r(i, step, tt, tool, conf=0.95, alts=()):
    return {"i": i, "step": step, "task_type": tt, "tool": tool,
            "confidence": conf, "decision": "act", "alts": list(alts)}


def _rows(tmp_path, records):
    d = _write_log(tmp_path, records)
    sess = load.sessions(list(load.iter_records(d)))
    return lb.label_sessions(sess), sess


def test_followed_alt_switched_and_fixed(tmp_path):
    routing = [
        _r(1, "Đọc summary Dir/A.xml", "read_summary", "read_local_file"),
        _r(2, "Tìm file chứa dmku", "grep_content", "search_files",
           alts=["match_filename"]),
        _r(3, "Query dmvt", "db_run_sql", "query_database"),
        _r(4, "Đăng ký menu web", "no_match", None),
    ]
    rows, _ = _rows(tmp_path, [
        _help("s1", 1, routing),
        _call("s1", 2, "read_local_file", {"read_option": 3}),
        _call("s1", 3, "search_files", {"mode": "files_only"}),
        _call("s1", 4, "query_database", {"query": "select x"}, ok=False,
              error_code="error_response", recovery_rule="invalid_column"),
        _call("s1", 5, "query_database", {"query": "select y"}),
    ])
    by = {r["step"]: r for r in rows}
    assert by["Đọc summary Dir/A.xml"]["label"] == "FOLLOWED_OK"
    assert by["Đọc summary Dir/A.xml"]["high_trust"] is True
    assert by["Tìm file chứa dmku"]["label"] == "ALT_OK"
    assert by["Tìm file chứa dmku"]["actual"] == "match_filename"
    q = by["Query dmvt"]
    assert q["label"] == "FOLLOWED_FAIL_FIXED"
    assert q["recovery_rule"] == "invalid_column"
    assert by["Đăng ký menu web"]["label"] == "SKIPPED_OK"


def test_sessions_do_not_mix(tmp_path):
    # 2 phiên ghi xen kẽ cùng file — chỉ ghép call cùng session_id
    rows, _ = _rows(tmp_path, [
        _help("A", 1, [_r(1, "Đọc summary X.xml", "read_summary",
                          "read_local_file")]),
        _call("B", 1, "query_database", {"query": "select 1"}),
        _call("A", 2, "read_local_file", {"read_option": 3}),
    ])
    (r,) = rows
    assert r["label"] == "FOLLOWED_OK" and r["high_trust"]


def test_switched_mode_and_skipped(tmp_path):
    rows, _ = _rows(tmp_path, [
        _help("s", 1, [
            _r(1, "Đọc A.xml", "read_flat", "read_local_file"),
            _r(2, "Check syntax a.sql", "db_check_syntax", "query_database"),
        ]),
        _call("s", 2, "read_local_file", {"read_option": 3}),
    ])
    a, b = rows
    assert a["label"] == "SWITCHED_OK" and a["actual"] == "read_summary"
    assert b["label"] == "SKIPPED"


def test_window_stops_at_next_tool_help(tmp_path):
    rows, _ = _rows(tmp_path, [
        _help("s", 1, [_r(1, "Query", "db_run_sql", "query_database")]),
        _help("s", 2, [_r(1, "Đọc", "read_raw", "read_local_file")]),
        _call("s", 3, "query_database", {"query": "select 1"}),
    ])
    assert rows[0]["label"] == "SKIPPED"


def test_legacy_log_split_by_server_start(tmp_path):
    rec = [{"event": "server_start", "ts": "2026-09-20T08:00:00"},
           {"ts": "2026-09-20T08:00:01", "tool": "query_database",
            "input": {}, "ok": True},
           {"event": "server_start", "ts": "2026-09-20T09:00:00"},
           {"ts": "2026-09-20T09:00:01", "tool": "search_files",
            "input": {}, "ok": True}]
    d = _write_log(tmp_path, rec, day="20260920")
    sess = load.sessions(list(load.iter_records(d)))
    assert len(sess) == 2


def _trusted_rows(spec):
    """spec: list (step, routed, actual, conf)."""
    return [{"step": s, "routed": r, "actual": a, "confidence": c,
             "high_trust": True, "label": "FOLLOWED_OK" if r == a
             else "SWITCHED_OK", "session": "s", "ts": "t"}
            for s, r, a, c in spec]


def test_calibrate_suggests_thresholds():
    spec = ([(f"s{i}", "x", "x", 0.95) for i in range(10)]
            + [(f"m{i}", "x", "x" if i < 7 else "y", 0.75)
               for i in range(10)]
            + [(f"l{i}", "x", "y", 0.35) for i in range(10)])
    cal = reports.calibrate(_trusted_rows(spec))
    assert cal["n"] == 30
    assert cal["suggest_confidence_act"] == 0.8      # chỉ bucket 0.9+ ≥ 90%
    # >= 0.4 gộp nhóm 0.75 + 0.95: 17/20 = 85% ≥ 70%; nhóm 0.35 nằm ngoài
    assert cal["suggest_confidence_review"] == 0.4


def test_harvest_dedup_and_load_approved(tmp_path):
    path = tmp_path / "auto.jsonl"
    rows = _trusted_rows([("a", "read_flat", "read_summary", 0.6),
                          ("a", "read_flat", "read_summary", 0.6),
                          ("b", "grep_content", "grep_content", 0.9)])
    assert reports.harvest(rows, path) == 2
    assert reports.harvest(rows, path) == 0
    lines = [json.loads(x) for x in path.read_text(
        encoding="utf-8").splitlines()]
    assert lines[0]["jev_wrong"] is True and lines[0]["status"] == "pending"
    lines[0]["status"] = "approved"
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False)
                              for x in lines), encoding="utf-8")
    (case,) = reports.load_approved(path)
    assert case["step"] == "a" and case["ok"] == ["read_summary"]


def test_distill_proposes_ngram_keyword_misses():
    steps = [f"Tra cứu tồn đầu kỳ kho K{i}" for i in range(4)]
    rows = _trusted_rows([(s, "db_balance", "db_balance", 0.95)
                          for s in steps])
    out = reports.distill(rows)
    from tool_help.keywords import keyword_route
    if all(keyword_route(s) == "db_balance" for s in steps):
        assert out == []          # keyword đã đúng → không đề xuất
    else:
        assert out and out[0]["task_type"] == "db_balance"
        assert out[0]["precision"] >= 0.9


def test_recovery_stats(tmp_path):
    _, sess = _rows(tmp_path, [
        _call("s", 1, "query_database", {}, ok=False,
              recovery_rule="invalid_column"),
        _call("s", 2, "query_database", {}),
        _call("s", 3, "read_local_file", {}, ok=False,
              recovery_rule="old_string_not_found"),
        _call("s", 4, "read_local_file", {}, ok=False),
    ])
    stats = {r["rule"]: r for r in reports.recovery_stats(sess)}
    assert stats["invalid_column"]["next_ok_rate"] == 1.0
    assert stats["old_string_not_found"]["next_ok_rate"] == 0.0


def test_markdown_renders(tmp_path):
    rows = _trusted_rows([("a", "x", "x", 0.9)])
    md = reports.to_markdown(rows, reports.calibrate(rows),
                             reports.card_health(rows), [], [],
                             {"date": "2026-10-09", "n_help": 1})
    assert "# Jev feedback — 2026-10-09" in md
    assert "## Sức khỏe card" in md
