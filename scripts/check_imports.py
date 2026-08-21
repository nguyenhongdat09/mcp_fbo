"""Check architectural layer dependency rules across packages.

Rule: Dependency goes strictly one-way downwards:
fastbusiness_mcp -> queryDatabase -> sql_object_summary -> tsql_engine -> antlr4
"""

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_imports_from_file(file_path: Path) -> list[str]:
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"[WARN] Cannot parse {file_path}: {e}")
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def check_directory(dir_path: Path, forbidden_prefixes: list[str]) -> list[str]:
    violations = []
    if not dir_path.exists():
        return violations

    for py_file in dir_path.rglob("*.py"):
        if "generated" in py_file.parts or ".venv" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        imports = get_imports_from_file(py_file)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                if imp == forbidden or imp.startswith(f"{forbidden}."):
                    rel_path = py_file.relative_to(ROOT)
                    violations.append(f"{rel_path}: imports forbidden '{imp}'")
    return violations


def main() -> int:
    all_violations = []

    # Layer 1: tsql_engine must not import higher layers or DB
    v1 = check_directory(
        ROOT / "tsql_engine",
        ["queryDatabase", "sql_object_summary", "fastbusiness_mcp", "pyodbc", "find_connect_by_path"],
    )
    all_violations.extend(v1)

    # Layer 2: sql_object_summary must not import DB, pyodbc, or MCP
    v2 = check_directory(
        ROOT / "sql_object_summary",
        ["queryDatabase", "fastbusiness_mcp", "pyodbc", "find_connect_by_path"],
    )
    all_violations.extend(v2)

    # Layer 4: fastbusiness_mcp/mcp_app.py must not import tsql_engine or visitors directly
    mcp_app = ROOT / "fastbusiness_mcp" / "mcp_app.py"
    if mcp_app.exists():
        for imp in get_imports_from_file(mcp_app):
            if imp.startswith("tsql_engine") or imp.startswith("sql_object_summary.visitors"):
                all_violations.append(f"fastbusiness_mcp/mcp_app.py: imports forbidden '{imp}'")

    if all_violations:
        print("[FAIL] Architectural import violations detected:")
        for v in all_violations:
            print(f"  - {v}")
        return 1

    print("[OK] All architectural layer dependency rules passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
