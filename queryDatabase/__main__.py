"""CLI test: python -m queryDatabase <file_path> "<query>" [app|sys]"""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print('Usage: python -m queryDatabase "<file_path>" "<query>" [app|sys]')
        print()
        print('Example:')
        print('  python -m queryDatabase "E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml" "SELECT TOP 5 * FROM dmvt"')
        return 1

    file_path = sys.argv[1]
    query = sys.argv[2]
    db_type = sys.argv[3] if len(sys.argv) > 3 else "app"

    from queryDatabase import query_database

    result = query_database(file_path, query, db_type)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
