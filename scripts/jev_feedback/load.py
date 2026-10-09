"""Đọc call log JSONL và tách phiên.

- Log mới: mỗi dòng có ``session_id`` + ``seq`` → nhóm chính xác.
- Log cũ (trước khi có session_id): tách theo ``server_start`` trong từng
  file ngày. Nhiều process ghi chung file → phiên có thể lẫn nhau; nhãn từ
  log cũ vì vậy chỉ ``high_trust`` khi gióng step↔call rất chặt.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator


def iter_records(log_dir: Path, since: str | None = None) -> Iterator[dict]:
    """Từng dòng log (giữ thứ tự file/ dòng), kèm ``_file``/``_line``."""
    since_key = (since or "").replace("-", "")
    for f in sorted(Path(log_dir).glob("mcp-*.jsonl")):
        day = f.stem.split("-", 1)[1]
        if since_key and day < since_key:
            continue
        with open(f, encoding="utf-8") as fh:
            for n, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rec["_file"], rec["_line"] = f.name, n
                yield rec


def _ts(rec: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(rec.get("ts")))
    except ValueError:
        return None


def sessions(records: list[dict]) -> dict[str, list[dict]]:
    """session key → list record tool call (đã sắp thứ tự)."""
    out: dict[str, list[dict]] = {}
    legacy_n: dict[str, int] = {}
    for rec in records:
        if rec.get("session_id"):
            key = rec["session_id"]
        else:
            f = rec["_file"]
            if rec.get("event") == "server_start":
                legacy_n[f] = legacy_n.get(f, 0) + 1
            key = f"legacy:{f}:{legacy_n.get(f, 0)}"
        if rec.get("tool"):
            rec["_ts"] = _ts(rec)
            out.setdefault(key, []).append(rec)
    for key, recs in out.items():
        if not key.startswith("legacy:"):
            recs.sort(key=lambda r: r.get("seq") or 0)
    return out
