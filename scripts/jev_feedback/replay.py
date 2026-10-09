"""Replay tool_help cũ (log trước khi ghi routing) qua Jev để có routing.

Kết quả cache vào ``scratch/jev_feedback_replay.jsonl`` (key = hash
steps + task_requirement) — chạy lại không tốn thêm Jev. Chi phí ~3–5k
token input/call × $0.042/M ≈ $0.0002/call.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "scratch" / "jev_feedback_replay.jsonl"


def replay_key(steps: list, task_requirement: str = "") -> str:
    raw = json.dumps([[str(s).strip() for s in steps], task_requirement or ""],
                     ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_cache() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if CACHE.is_file():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                out[d["key"]] = d
            except (json.JSONDecodeError, KeyError):
                pass
    return out


def replay(records: list[dict], cfg: dict, limit: int | None = None,
           verbose: bool = True) -> dict[str, dict]:
    """Replay mọi tool_help chưa có routing & chưa có trong cache."""
    from tool_help.service import _RESULT_CACHE, tool_help_with_meta

    cache = load_cache()
    todo = []
    for r in records:
        if r.get("tool") != "tool_help" or r.get("routing"):
            continue
        inp = r.get("input") or {}
        steps = inp.get("steps") or []
        req = (inp.get("context") or {}).get("task_requirement", "")
        k = replay_key(steps, req)
        if steps and k not in cache and k not in {t[0] for t in todo}:
            todo.append((k, steps, req))
    if limit is not None:
        todo = todo[:limit]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "a", encoding="utf-8") as fh:
        for n, (k, steps, req) in enumerate(todo, 1):
            _RESULT_CACHE.clear()
            ctx = {"task_requirement": req} if req else None
            _, meta = tool_help_with_meta(*steps, context=ctx,
                                          jev_config=cfg)
            if meta.get("router") != "jev":
                if verbose:
                    print(f"  replay {n}/{len(todo)}: Jev lỗi — bỏ qua")
                continue
            d = {"key": k, **meta}
            cache[k] = d
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            if verbose:
                print(f"  replay {n}/{len(todo)} ok")
            time.sleep(0.1)
    return cache
