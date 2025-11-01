#!/usr/bin/env python3
"""Quick test - Check if LevelDB tool is ready"""

import asyncio


async def quick_test():
    print("\n🔍 QUICK TEST - LevelDB Tool\n")

    # Step 1: Check plyvel
    print("Step 1: Checking plyvel package...")
    try:
        import plyvel
        print("  ✅ plyvel installed\n")
    except ImportError:
        print("  ❌ plyvel NOT installed")
        print("  ⚠️  You cannot use LevelDB features without plyvel\n")
        print("Solutions:")
        print("  1. Install Python 3.11 instead of 3.13")
        print("  2. pip install plyvel (requires LevelDB dev headers)")
        print("  3. Use the tool in MCP server (if configured properly)\n")
        return

    # Step 2: Check LevelDB Manager
    print("Step 2: Checking LevelDB Manager...")
    try:
        from fastbusiness_mcp.leveldb_adapter.leveldb_manager import (
            LevelDBManager,
            PLYVEL_AVAILABLE,
        )

        if not PLYVEL_AVAILABLE:
            print("  ❌ PLYVEL_AVAILABLE = False")
            print("  ⚠️  LevelDB features disabled\n")
            return

        print("  ✅ LevelDB Manager ready\n")
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
