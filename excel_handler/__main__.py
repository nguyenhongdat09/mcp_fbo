"""CLI: python -m excel_handler <grid.xml> [--row ...] [--column ...] [--value ...] [--output ...]

--defaults-only: chỉ in JSON defaults (mode + row/column/value hoặc headers) rồi thoát —
agent xem gợi ý trước khi truyền override.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .grid_parser import build_pivot_defaults, has_pivot_tag, parse_header_fields
from .service import excel_handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="excel_handler",
        description="Xuất mẫu Excel (.xlsx) từ file Grid XML FBO (tự nhận diện pivot).",
    )
    parser.add_argument("grid_file", help="Path file Grid\\*.xml (local hoặc UNC)")
    parser.add_argument("--row", dest="row_fields", default=None, help="Row fields csv (pivot)")
    parser.add_argument("--column", dest="column_fields", default=None, help="Column fields csv (pivot)")
    parser.add_argument("--value", dest="value_fields", default=None, help="Value fields csv (pivot)")
    parser.add_argument("--output", dest="output_path", default=None, help="Path .xlsx đích (kèm thư mục)")
    parser.add_argument(
        "--name",
        dest="excel_name",
        default=None,
        help="Tên file .xlsx muốn xuất (vd zcbccashflow_01.xlsx) — đặt trong Templates\\Excel",
    )
    parser.add_argument(
        "--defaults-only",
        action="store_true",
        help="Chỉ in JSON defaults (không xuất file)",
    )
    args = parser.parse_args(argv)

    grid_path = Path(args.grid_file)
    if not grid_path.exists():
        print(json.dumps({"error": f"Không tìm thấy file: {args.grid_file}"}, ensure_ascii=False))
        return 1

    if args.defaults_only:
        xml = grid_path.read_text(encoding="utf-8-sig")
        if has_pivot_tag(xml):
            payload = {"mode": "pivot", **build_pivot_defaults(xml)}
        else:
            payload = {
                "mode": "normal",
                "headers": [[h, t, f] for h, t, f in parse_header_fields(xml)],
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        result = excel_handler(
            grid_file=args.grid_file,
            row_fields=args.row_fields,
            column_fields=args.column_fields,
            value_fields=args.value_fields,
            output_path=args.output_path,
            excel_name=args.excel_name,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1

    print(f"Đã xuất mẫu Excel ({result.mode}): {result.output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
