"""4 đầu ra từ nhãn step↔call.

- ``harvest``   : case eval mới (pending — user duyệt → approved).
- ``calibrate`` : bảng reliability theo confidence → đề xuất act/review.
- ``card_health``/``recovery_stats`` → báo cáo markdown.
- ``distill``   : đề xuất regex cho keywords.py (KHÔNG tự sửa file).

"Đúng" của 1 step = task_type agent dùng thành công (``actual``) trùng
task_type tool_help khuyên (``routed``). Chỉ tính hàng ``high_trust``.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTO_CASES = ROOT / "scratch" / "jev_eval_cases_auto.jsonl"

_BUCKETS = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]


def _trusted(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("high_trust") and r.get("actual")]


# ------------------------------------------------------------------ harvest
def harvest(rows: list[dict], path: Path = AUTO_CASES) -> int:
    """Ghi case mới vào jsonl (bỏ trùng step). Trả số case thêm."""
    existing: set[str] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line)["step"])
            except (json.JSONDecodeError, KeyError):
                pass
    added = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in _trusted(rows):
            if r["step"] in existing:
                continue
            existing.add(r["step"])
            fh.write(json.dumps({
                "step": r["step"], "ok": [r["actual"]],
                "routed": r["routed"], "jev_wrong": r["routed"] != r["actual"],
                "label": r["label"], "status": "pending",
                "source": f"{r.get('session')}@{r.get('ts')}",
            }, ensure_ascii=False) + "\n")
            added += 1
    return added


def load_approved(path: Path = AUTO_CASES) -> list[dict]:
    """Case auto đã duyệt — jev_eval.py --steps-set đọc thêm."""
    out = []
    if path.is_file():
        for n, line in enumerate(path.read_text(
                encoding="utf-8").splitlines()):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("status") == "approved":
                out.append({"id": f"A{n:04d}", "step": d["step"],
                            "ok": d["ok"]})
    return out


# ---------------------------------------------------------------- calibrate
def calibrate(rows: list[dict], target_act: float = 0.9,
              target_review: float = 0.7, min_n: int = 5) -> dict:
    data = [(float(r["confidence"]), r["routed"] == r["actual"])
            for r in _trusted(rows) if r.get("confidence") is not None]
    table = []
    for lo, hi in zip(_BUCKETS, _BUCKETS[1:]):
        b = [ok for c, ok in data if lo <= c < hi]
        table.append({"range": f"{lo:.1f}-{min(hi, 1.0):.1f}", "n": len(b),
                      "acc": round(sum(b) / len(b), 3) if b else None})

    def _threshold(target: float) -> float | None:
        # ngưỡng thấp nhất t mà mọi confidence >= t đạt accuracy >= target
        for lo in _BUCKETS[:-1]:
            above = [ok for c, ok in data if c >= lo]
            if len(above) >= min_n and sum(above) / len(above) >= target:
                return lo
        return None

    return {"n": len(data), "table": table,
            "suggest_confidence_act": _threshold(target_act),
            "suggest_confidence_review": _threshold(target_review)}


# ------------------------------------------------------------- card health
def card_health(rows: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("routed") and r["routed"] != "no_match":
            by[r["routed"]].append(r)
    out = []
    for tt, rs in by.items():
        n = len(rs)
        follow = sum(r["label"].startswith(("FOLLOWED", "ALT")) for r in rs)
        failed = sum("FAIL" in r["label"] for r in rs)
        switched = Counter(r["actual"] for r in rs
                           if r["label"].startswith("SWITCHED")
                           and r.get("actual"))
        errs = Counter(r["error_code"] for r in rs if r.get("error_code"))
        out.append({"task_type": tt, "n": n,
                    "follow_rate": round(follow / n, 2),
                    "fail_rate": round(failed / n, 2),
                    "skipped": sum(r["label"] == "SKIPPED" for r in rs),
                    "switched_to": switched.most_common(3),
                    "top_errors": errs.most_common(3)})
    out.sort(key=lambda x: (-x["n"]))
    return out


def recovery_stats(sess: dict[str, list[dict]]) -> list[dict]:
    """Mỗi luật recovery: số lần fire + % call kế tiếp cùng tool thành công."""
    fired: Counter = Counter()
    fixed: Counter = Counter()
    for calls in sess.values():
        for i, c in enumerate(calls):
            rule = c.get("recovery_rule")
            if not rule:
                continue
            fired[rule] += 1
            nxt = next((x for x in calls[i + 1:i + 4]
                        if x.get("tool") == c.get("tool")), None)
            if nxt is not None and nxt.get("ok"):
                fixed[rule] += 1
    return [{"rule": k, "fired": v, "next_ok_rate": round(fixed[k] / v, 2)}
            for k, v in fired.most_common()]


# ------------------------------------------------------------------ distill
_WORD_RE = re.compile(r"[\w$.]+", re.UNICODE)


def _ngrams(text: str, n_max: int = 3) -> set[str]:
    words = [w for w in _WORD_RE.findall(text.lower()) if len(w) > 1]
    out = set()
    for n in range(1, n_max + 1):
        for i in range(len(words) - n + 1):
            out.add(" ".join(words[i:i + n]))
    return out


def distill(rows: list[dict], min_conf: float = 0.9,
            min_precision: float = 0.9, min_support: int = 3) -> list[dict]:
    """Step Jev chắc + agent làm đúng mà keyword_route đoán sai → n-gram
    đặc trưng (precision cao) → đề xuất regex cho keywords.py."""
    from tool_help.keywords import keyword_route

    gold = [(r["step"], r["routed"]) for r in _trusted(rows)
            if r["routed"] == r["actual"]
            and float(r.get("confidence") or 0) >= min_conf]
    if not gold:
        return []
    gram_types: dict[str, Counter] = defaultdict(Counter)
    for step, tt in gold:
        for g in _ngrams(step):
            gram_types[g][tt] += 1
    missed = [(s, tt) for s, tt in gold if keyword_route(s) != tt]
    out, seen = [], set()
    for step, tt in missed:
        best = None
        for g in _ngrams(step):
            c = gram_types[g]
            support, total = c[tt], sum(c.values())
            if support < min_support or support / total < min_precision:
                continue
            if best is None or (len(g), support) > (len(best[0]), best[1]):
                best = (g, support, support / total)
        if best and (best[0], tt) not in seen:
            seen.add((best[0], tt))
            out.append({"task_type": tt, "ngram": best[0],
                        "support": best[1],
                        "precision": round(best[2], 2),
                        "regex": re.escape(best[0]).replace(r"\ ", r"\s+"),
                        "example": step,
                        "keyword_said": keyword_route(step)})
    return out


# ------------------------------------------------------------------ report
def to_markdown(rows: list[dict], cal: dict, health: list[dict],
                rec: list[dict], dist: list[dict], meta: dict) -> str:
    labels = Counter(r["label"] for r in rows)
    lines = [f"# Jev feedback — {meta.get('date')}", "",
             f"Log: `{meta.get('log_dir')}` since {meta.get('since') or '-'} · "
             f"{meta.get('n_help')} tool_help · {len(rows)} step nhãn · "
             f"{sum(r['high_trust'] for r in rows)} high_trust", "",
             "## Nhãn", ""]
    lines += [f"- {k}: {v}" for k, v in labels.most_common()]
    lines += ["", "## Hiệu chỉnh ngưỡng confidence", "",
              f"n={cal['n']} · đề xuất confidence_act="
              f"{cal['suggest_confidence_act']} · confidence_review="
              f"{cal['suggest_confidence_review']} (chỉ đề xuất — tự sửa "
              "config)", "",
              "> \"đồng ý\" = agent dùng đúng task_type tool_help khuyên — "
              "KHÔNG phải Jev đúng (agent có thể tự chọn khác mà vẫn xong "
              "việc). Log cũ (trước session_id) còn lẫn phiên → chỉ tin bảng "
              "này khi đủ log mới.", "",
              "| confidence | n | đồng ý |", "|---|---|---|"]
    lines += [f"| {b['range']} | {b['n']} | {b['acc']} |"
              for b in cal["table"]]
    lines += ["", "## Sức khỏe card", "",
              "| task_type | n | follow | fail | skipped | đổi sang | lỗi |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {h['task_type']} | {h['n']} | {h['follow_rate']} | "
              f"{h['fail_rate']} | {h['skipped']} | "
              f"{', '.join(f'{k}({v})' for k, v in h['switched_to'])} | "
              f"{', '.join(f'{k}({v})' for k, v in h['top_errors'])} |"
              for h in health]
    lines += ["", "## Luật recovery", "", "| rule | fired | call kế OK |",
              "|---|---|---|"]
    lines += [f"| {r['rule']} | {r['fired']} | {r['next_ok_rate']} |"
              for r in rec] or ["| (chưa có) | | |"]
    lines += ["", "## Đề xuất keyword (chưng cất Jev → keywords.py)", ""]
    if dist:
        lines += [f"- `{d['regex']}` → **{d['task_type']}** (support "
                  f"{d['support']}, precision {d['precision']}; keyword cũ: "
                  f"{d['keyword_said']}) — vd: {d['example'][:90]}"
                  for d in dist]
    else:
        lines.append("(chưa đủ dữ liệu)")
    return "\n".join(lines) + "\n"
