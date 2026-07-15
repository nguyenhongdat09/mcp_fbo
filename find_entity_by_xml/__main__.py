"""CLI: python -m find_entity_by_xml <file_path> [entity ...] [--list-all] [--force-reload] [--mode content|path]"""

from __future__ import annotations

import argparse
import sys

from .formatter import format_entity_result
from .service import get_xml_entities


def main() -> int:
    parser = argparse.ArgumentParser(description="Đọc XML entity từ file FBO")
    parser.add_argument("file_path", help="Đường dẫn file XML")
    parser.add_argument("entities", nargs="*", help="Tên entity (có thể nhiều)")
    parser.add_argument(
        "--mode",
        choices=["content", "path"],
        action="append",
        default=["content"],
        help="content=mode 0, path=mode 1 (có thể lặp để lấy cả hai)",
    )
    parser.add_argument("--list-all", action="store_true", help="Liệt kê tất cả entity (mode content)")
    parser.add_argument("--force-reload", action="store_true", help="Bỏ cache parse và đọc lại file")
    args = parser.parse_args()

    result = get_xml_entities(
        args.file_path,
        args.entities or None,
        mode=args.mode,
        force_reload=args.force_reload,
        list_all=args.list_all,
    )
    print(format_entity_result(result))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
