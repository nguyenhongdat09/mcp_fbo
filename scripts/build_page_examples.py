"""Trích tiêu đề `v` (+ `e`) của các dòng <page> theo từng template Page.0xx để
làm ví dụ cho Jev (tool_help/classify_page/page_examples.json).

Chạy:  python -X utf8 scripts/build_page_examples.py [<project SP30+>] [--max 50]
Mặc định project = DIVN/FBISP30. Chạy lại khi muốn làm mới ví dụ.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

DEFAULT_ROOT = r"\\172.168.5.14\CustomerPro\FBI\DIVN\FBISP30"
OUT = Path(__file__).resolve().parents[1] / "tool_help" / "classify_page" / "page_examples.json"

_PAGE = re.compile(r"^\s*<page\s", re.IGNORECASE)
_ATTR = {k: re.compile(r'\b' + k + r'\s*=\s*"([^"]*)"') for k in ("v", "e", "template", "id")}


def _files(root: Path) -> list[Path]:
    meta = root / "App_Data" / "Metadata"
    files = sorted(meta.glob("Page*.xml"))
    files.append(root / "App_Data" / "PageMetadata.xml")   # page inline (023/024, named...)
    return [f for f in files if f.exists()]


def collect(root: Path) -> dict[str, list[dict]]:
    by_tpl: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for f in _files(root):
        for line in f.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            if not _PAGE.match(line):
                continue
            a = {k: (m.group(1) if (m := rx.search(line)) else "") for k, rx in _ATTR.items()}
            tpl, v = a["template"], html.unescape(a["v"]).strip()
            if not tpl or not v or (tpl, v.lower()) in seen:
                continue
            seen.add((tpl, v.lower()))
            by_tpl.setdefault(tpl, []).append({"v": v, "e": html.unescape(a["e"]).strip()})
    return by_tpl


def pick(items: list[dict], limit: int) -> list[dict]:
    """Tối đa `limit` mục, rải đều theo thứ tự file để đa dạng, ưu tiên có `e`."""
    items = [i for i in items if i["e"]] + [i for i in items if not i["e"]] \
        if len(items) > limit else items
    if len(items) <= limit:
        return items
    step = len(items) / limit
    return [items[int(i * step)] for i in range(limit)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=DEFAULT_ROOT)
    ap.add_argument("--max", type=int, default=50)
    args = ap.parse_args()
    by_tpl = collect(Path(args.root))
    out = {}
    for tpl in sorted(by_tpl):
        items = by_tpl[tpl]
        out[tpl] = {
            "total": len(items),
            "examples": [f'"{i["v"]}" e="{i["e"]}"' if i["e"] else f'"{i["v"]}"'
                         for i in pick(items, args.max)],
        }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT}: {len(out)} template, "
          + ", ".join(f"{k}={v['total']}" for k, v in out.items()))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
