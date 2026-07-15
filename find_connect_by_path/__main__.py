"""CLI: truyền file path → in connection string.

Usage:
    python -m find_connect_by_path "E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml"
    python -m find_connect_by_path "E:\\FBO\\...\\AITran.xml" app
    python -m find_connect_by_path "E:\\FBO\\...\\AITran.xml" all
"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m find_connect_by_path <file_path> [app|sys|all]")
        print()
        print("Example:")
        print('  python -m find_connect_by_path "E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml"')
        return 1

    file_path = sys.argv[1]
    db_type = sys.argv[2] if len(sys.argv) > 2 else "app"

    from find_connect_by_path import find_connection_by_path

    result = find_connection_by_path(file_path, db_type)

    print(f"File path    : {file_path}")
    print(f"DB type      : {db_type}")
    print()

    if not result.get("success"):
        print(f"[ERROR] {result.get('error')}")
        if result.get("project_root"):
            print(f"Project root : {result['project_root']}")
        if result.get("available_db_types"):
            print(f"Available    : {', '.join(result['available_db_types'])}")
        return 1

    print(f"Project root : {result['project_root']}")
    print(f"Web.config   : {result['web_config_path']}")
    print(f"Available    : {', '.join(result.get('available_db_types', []))}")
    print()

    if "connections" in result:
        for name, info in result["connections"].items():
            parsed = info["parsed"]
            print(f"=== {name.upper()} ===")
            print(info["connection_string"])
            print(f"  Server   : {parsed.get('server', '')}")
            print(f"  Database : {parsed.get('database', '')}")
            print(f"  User     : {parsed.get('user', '')}")
            print()
    else:
        parsed = result["parsed"]
        print("Connection string:")
        print(result["connection_string"])
        print()
        print(f"Server   : {parsed.get('server', '')}")
        print(f"Database : {parsed.get('database', '')}")
        print(f"User     : {parsed.get('user', '')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
