"""CLI router tự học.

  python -X utf8 -m scripts.jev_feedback all [--since YYYY-MM-DD]
         [--log-dir DIR] [--replay] [--replay-limit N]

Lệnh: all | label | report (all = label + harvest + report markdown).
``--replay`` gọi Jev cho tool_help log cũ chưa có routing (cache lại).
Report ghi vào docs/doc/tool_help/feedback/<ngày>.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.jev_feedback import label as lb  # noqa: E402
from scripts.jev_feedback import load, replay, reports  # noqa: E402

DEFAULT_LOG_DIR = Path("E:/fastbusiness_mcp/logs")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jev_feedback")
    ap.add_argument("cmd", choices=["all", "label", "report"])
    ap.add_argument("--since")
    ap.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--replay-limit", type=int)
    ap.add_argument("--out-dir",
                    default=str(ROOT / "docs" / "doc" / "tool_help" /
                                "feedback"))
    args = ap.parse_args(argv)

    records = list(load.iter_records(Path(args.log_dir), args.since))
    sess = load.sessions(records)
    n_help = sum(1 for r in records if r.get("tool") == "tool_help")

    rp = replay.load_cache()
    if args.replay:
        from jev import load_jev_config

        cfg = load_jev_config()
        if not cfg:
            print("Không có config Jev — bỏ replay")
        else:
            rp = replay.replay(records, cfg, limit=args.replay_limit)

    rows = lb.label_sessions(sess, rp)
    print(f"{n_help} tool_help · {len(rows)} step nhãn · "
          f"{sum(r['high_trust'] for r in rows)} high_trust")
    if args.cmd == "label":
        for r in rows:
            print(json.dumps(r, ensure_ascii=False, default=str))
        return 0

    added = reports.harvest(rows) if args.cmd == "all" else 0
    md = reports.to_markdown(
        rows, reports.calibrate(rows), reports.card_health(rows),
        reports.recovery_stats(sess), reports.distill(rows),
        {"date": f"{date.today():%Y-%m-%d}", "log_dir": args.log_dir,
         "since": args.since, "n_help": n_help})
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{date.today():%Y-%m-%d}.md"
    out.write_text(md, encoding="utf-8")
    print(f"harvest +{added} case → {reports.AUTO_CASES.name}; report → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
