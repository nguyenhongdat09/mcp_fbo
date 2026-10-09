"""Gán nhãn step ↔ call: agent có làm theo khuyến nghị tool_help không.

Với mỗi call ``tool_help`` có routing (log mới ghi sẵn; log cũ lấy từ
replay), cửa sổ = các call sau nó tới tool_help kế tiếp (tối đa
``WINDOW_CALLS`` call / ``WINDOW_MINUTES`` phút). Mỗi step gióng đơn điệu
với call đầu tiên (từ con trỏ, tìm trong ``LOOKAHEAD`` call) có:
- task_type == top-1        → FOLLOWED
- task_type ∈ alternatives  → ALT
- cùng tool, mode khác      → SWITCHED (agent đổi mode)
Không thấy → SKIPPED (step no_match → SKIPPED_OK).

Kết quả call: ok → *_OK; lỗi rồi call kế cùng tool OK → *_FAIL_FIXED; lỗi
→ *_FAILED. ``actual`` = task_type của call thành công cuối cùng cho step.
``high_trust`` = khớp ngay call đầu cửa sổ còn lại (khoảng cách 0–1).
"""
from __future__ import annotations

from datetime import timedelta

from tool_help.cards import task_type_for_call

WINDOW_CALLS = 10
WINDOW_MINUTES = 15
LOOKAHEAD = 4
FIX_LOOKAHEAD = 3


def _window(calls: list[dict], start: int) -> list[dict]:
    t0 = calls[start].get("_ts")
    out = []
    for c in calls[start + 1:]:
        if c.get("tool") == "tool_help" or len(out) >= WINDOW_CALLS:
            break
        if t0 and c.get("_ts") and c["_ts"] - t0 > timedelta(
                minutes=WINDOW_MINUTES):
            break
        out.append(c)
    return out


def _tt(call: dict) -> str | None:
    return task_type_for_call(call.get("tool"), call.get("input") or {})


def label_help_call(help_rec: dict, routing: list[dict],
                    window: list[dict]) -> list[dict]:
    rows = []
    ptr = 0
    for r in routing:
        routed = r.get("task_type")
        alts = set(r.get("alts") or [])
        row = {"help_id": help_rec.get("help_id"), "ts": help_rec.get("ts"),
               "session": help_rec.get("_session"), "step": r.get("step"),
               "routed": routed, "tool": r.get("tool"),
               "confidence": r.get("confidence"),
               "decision": r.get("decision"), "alts": sorted(alts),
               "actual": None, "label": "SKIPPED", "high_trust": False}
        if routed == "no_match" or not r.get("tool"):
            row["label"] = "SKIPPED_OK"
            rows.append(row)
            continue
        match, kind = None, None
        for j in range(ptr, min(ptr + LOOKAHEAD, len(window))):
            tt = _tt(window[j])
            if tt == routed:
                match, kind = j, "FOLLOWED"
            elif tt in alts:
                match, kind = j, "ALT"
            elif window[j].get("tool") == r.get("tool"):
                match, kind = j, "SWITCHED"
            if match is not None:
                break
        if match is None:
            rows.append(row)
            continue
        call = window[match]
        row["high_trust"] = match - ptr <= 1
        end = match
        if call.get("ok"):
            row["label"], row["actual"] = f"{kind}_OK", _tt(call)
        else:
            row["error_code"] = call.get("error_code")
            if call.get("recovery_rule"):
                row["recovery_rule"] = call["recovery_rule"]
            fix = next((k for k in range(match + 1, min(
                match + 1 + FIX_LOOKAHEAD, len(window)))
                if window[k].get("tool") == call.get("tool")
                and window[k].get("ok")), None)
            if fix is not None:
                row["label"] = f"{kind}_FAIL_FIXED"
                row["actual"] = _tt(window[fix])
                end = fix
            else:
                row["label"] = f"{kind}_FAILED"
        ptr = end + 1
        rows.append(row)
    return rows


def label_sessions(sess: dict[str, list[dict]],
                   replay: dict[str, dict] | None = None) -> list[dict]:
    """Nhãn cho mọi tool_help trong mọi phiên. ``replay`` = routing replay
    cho log cũ, key = replay_key(steps, task_requirement)."""
    from .replay import replay_key

    replay = replay or {}
    rows: list[dict] = []
    for key, calls in sess.items():
        for i, c in enumerate(calls):
            if c.get("tool") != "tool_help":
                continue
            c["_session"] = key
            routing = c.get("routing")
            if not routing:
                inp = c.get("input") or {}
                rp = replay.get(replay_key(
                    inp.get("steps") or [],
                    (inp.get("context") or {}).get("task_requirement", "")))
                if not rp:
                    continue
                routing = rp.get("routing") or []
                c.setdefault("help_id", rp.get("help_id"))
            rows += label_help_call(c, routing, _window(calls, i))
    return rows
