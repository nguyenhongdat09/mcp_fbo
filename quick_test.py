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
            print("  ❌ No database backend installed")
            print("  ⚠️  You cannot use LevelDB features without a backend\n")
            print("Solutions:")
            print("  1. pip install python-rocksdb  (works on Windows Python 3.13)")
            print("  2. pip install plyvel-wheels   (for Linux/Mac or Python 3.11)")
            print("  3. See requirements-leveldb.txt for details\n")
            return

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
        paths = config.get_db_paths()

        found_db = False
        for path in paths:
            exists = Path(path).exists()
            if exists:
                print(f"  ✅ Found: {path}")
                found_db = True
            else:
                print(f"  ❌ Not found: {path}")

        if not found_db:
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
