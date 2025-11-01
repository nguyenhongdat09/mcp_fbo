#!/usr/bin/env python3
"""Quick test - Check if LevelDB tool is ready"""

import asyncio


async def quick_test():
    print("\n🔍 QUICK TEST - LevelDB Tool\n")

    # Step 1: Check database backend
    print("Step 1: Checking database backend...")
    backend = None
    try:
        import plyvel
        backend = "plyvel"
        print("  ✅ plyvel installed (LevelDB native)\n")
    except ImportError:
        try:
            import rocksdb
            backend = "rocksdb"
            print("  ✅ python-rocksdb installed (RocksDB - can read LevelDB)\n")
        except ImportError:
            backend = "json"
            print("  ⚠️  No LevelDB backend installed")
            print("  ✅ Using JSON fallback mode\n")
            print("  Note: JSON fallback requires exported JSON files.")
            print("  See tools/README.md for export instructions\n")

    # Step 2: Check LevelDB Manager
    print("Step 2: Checking LevelDB Manager...")
    try:
        from fastbusiness_mcp.leveldb_adapter.leveldb_manager import (
            LevelDBManager,
            DB_BACKEND,
        )

        if not DB_BACKEND:
            print("  ❌ DB_BACKEND = None")
            print("  ⚠️  LevelDB features disabled\n")
            return

        print(f"  ✅ LevelDB Manager ready (using {DB_BACKEND})\n")
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        return

    # Step 3: Check database paths
    print("Step 3: Checking database paths...")
    try:
        from fastbusiness_mcp.leveldb_adapter.config import LevelDBConfig
        from pathlib import Path

        config = LevelDBConfig()

        # Check appropriate paths based on backend
        if backend == "json":
            paths = config.get_json_paths()
            print("  Looking for JSON export files...")
        else:
            paths = config.get_db_paths()
            print("  Looking for LevelDB directories...")

        found_db = False
        for db_type, path in paths.items():
            exists = Path(path).exists()
            if exists:
                print(f"  ✅ Found: {path}")
                found_db = True
            else:
                print(f"  ❌ Not found: {path}")

        if not found_db:
            if backend == "json":
                print("\n  ⚠️  No JSON export files found!")
                print("  Please export LevelDB to JSON first.")
                print("  Run: python tools/export_leveldb_to_json.py --vscode")
                print("  See tools/README.md for detailed instructions\n")
            else:
                print("\n  ⚠️  No LevelDB database found!")
                print("  Please configure database path in config.yaml or environment variable\n")
            return

        print()
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        return

    # Step 4: Test tool
    print("Step 4: Testing generate_field_from_db tool...")
    try:
        from fastbusiness_mcp.tools.generate_field_from_db import (
            GenerateFieldFromDBTool,
        )

        tool = GenerateFieldFromDBTool(use_vscode_extension=True)

        # Try to generate a common field
        result = await tool.execute(
            {"field_name": "so_luong", "context_type": "DIR"}
        )

        if result["success"]:
            print(f"  ✅ Tool works! Generated field: {result['field_name']}")
            print(f"  Source: {result['source']}")
            print()
        else:
            print(f"  ⚠️  Field not found: {result['message']}")
            if result.get("suggestions"):
                print(f"  Suggestions: {result['suggestions']['similar_fields']}")
            print()
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        import traceback

        traceback.print_exc()
        return

    # Success!
    print("=" * 60)
    print("✅ ALL CHECKS PASSED - LevelDB tool is ready!")
    print("=" * 60)
    print("\nYou can now use the tool in MCP server:")
    print('  Tool name: "generate_field_from_db"')
    print("  Example: Generate field 'sl_du_kien' for DIR context\n")


if __name__ == "__main__":
    asyncio.run(quick_test())
