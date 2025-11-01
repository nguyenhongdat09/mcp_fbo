#!/usr/bin/env python3
"""Test script for generate_field_from_db tool"""

import asyncio
import sys
from pathlib import Path


async def test_leveldb_availability():
    """Test if LevelDB backend is available"""
    print("=" * 80)
    print("TEST 1: Checking LevelDB backend availability")
    print("=" * 80)

    backend = None
    try:
        import plyvel
        backend = "plyvel"
        print("✅ plyvel is installed")
        print(f"   Version: {plyvel.__version__ if hasattr(plyvel, '__version__') else 'unknown'}")
        return True
    except ImportError:
        pass

    try:
        import rocksdb
        backend = "rocksdb"
        print("✅ python-rocksdb is installed")
        version = rocksdb.__version__ if hasattr(rocksdb, '__version__') else 'unknown'
        print(f"   Version: {version}")
        print("   Note: RocksDB can read LevelDB databases")
        return True
    except ImportError:
        pass

    print("❌ No database backend installed")
    print("\n⚠️  LevelDB features will be DISABLED")
    print("\nTo enable LevelDB features, install ONE of:")
    print("  Option 1: pip install python-rocksdb  (works on Windows Python 3.13)")
    print("  Option 2: pip install plyvel-wheels   (for Linux/Mac or Python 3.11)")
    print("  Option 3: See requirements-leveldb.txt for details")
    return False


async def test_leveldb_manager():
    """Test LevelDB Manager initialization"""
    print("\n" + "=" * 80)
    print("TEST 2: Testing LevelDB Manager")
    print("=" * 80)

    try:
        from fastbusiness_mcp.leveldb_adapter.leveldb_manager import LevelDBManager, DB_BACKEND

        print(f"Database backend: {DB_BACKEND}")

        if not DB_BACKEND:
            print("⚠️  LevelDB Manager will run in DISABLED mode")
            return False

        manager = LevelDBManager(use_vscode_extension=True)
        print(f"✅ LevelDB Manager initialized (using {DB_BACKEND})")
        print(f"   Config paths checked:")

        # Check paths
        from fastbusiness_mcp.leveldb_adapter.config import LevelDBConfig
        config = LevelDBConfig()

        for path in config.get_db_paths():
            exists = Path(path).exists()
            status = "✅" if exists else "❌"
            print(f"   {status} {path}")

        return True

    except Exception as e:
        print(f"❌ Error initializing LevelDB Manager: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_generate_field_tool():
    """Test the generate_field_from_db tool"""
    print("\n" + "=" * 80)
    print("TEST 3: Testing generate_field_from_db tool")
    print("=" * 80)

    try:
        from fastbusiness_mcp.tools.generate_field_from_db import GenerateFieldFromDBTool

        print("✅ GenerateFieldFromDBTool imported successfully")

        # Initialize tool
        tool = GenerateFieldFromDBTool(use_vscode_extension=True)
        print("✅ Tool initialized")

        # Test tool properties
        print(f"\nTool name: {tool.name}")
        print(f"Tool description: {tool.description[:100]}...")

        # Test with a common field
        print("\n" + "-" * 80)
        print("Testing field generation: 'so_luong' for DIR context")
        print("-" * 80)

        result = await tool.execute({
            "field_name": "so_luong",
            "context_type": "DIR"
        })

        if result["success"]:
            print(f"✅ SUCCESS: {result['message']}")
            print(f"\nSource: {result['source']}")
            print(f"Field Name: {result['field_name']}")

            if result.get('template_used'):
                print(f"Template Used: {result['template_used']}")

            print(f"\nGenerated XML:")
            print(result['xml'])

            if result.get('companion_xml'):
                print(f"\nCompanion Field:")
                print(result['companion_xml'])
        else:
            print(f"❌ FAILED: {result['message']}")
            if result.get('suggestions'):
                print(f"\nSuggestions:")
                for field in result['suggestions'].get('similar_fields', []):
                    print(f"  - {field}")

        return result["success"]

    except Exception as e:
        print(f"❌ Error testing tool: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_specific_fields():
    """Test specific field patterns"""
    print("\n" + "=" * 80)
    print("TEST 4: Testing specific field patterns")
    print("=" * 80)

    from fastbusiness_mcp.tools.generate_field_from_db import GenerateFieldFromDBTool

    tool = GenerateFieldFromDBTool(use_vscode_extension=True)

    test_cases = [
        ("sl_du_kien", "DIR", "Quantity field with sl_ pattern"),
        ("ma_vtat", "FILTER_NORMAL", "Code field with ma_ pattern and lookup"),
        ("ngay_ct", "DIR", "Date field with ngay_ pattern"),
        ("tien_nt", "GRID_VIEW", "Currency field with tien_ pattern"),
        ("tk_no", "GRID_INPUT", "Account field with tk_ pattern"),
    ]

    results = []

    for field_name, context, description in test_cases:
        print(f"\n{'-' * 80}")
        print(f"Test: {description}")
        print(f"Field: {field_name}, Context: {context}")
        print(f"{'-' * 80}")

        try:
            result = await tool.execute({
                "field_name": field_name,
                "context_type": context
            })

            if result["success"]:
                print(f"✅ {result['message']}")
                results.append((field_name, True))
            else:
                print(f"❌ {result['message']}")
                results.append((field_name, False))

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append((field_name, False))

    # Summary
    print(f"\n{'=' * 80}")
    print("TEST SUMMARY")
    print(f"{'=' * 80}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for field_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {field_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


async def main():
    """Run all tests"""
    print("\n")
    print("*" * 80)
    print("FASTBUSINESS MCP - LEVELDB TOOL TEST SUITE")
    print("*" * 80)

    # Test 1: Check database backend
    has_backend = await test_leveldb_availability()

    if not has_backend:
        print("\n" + "=" * 80)
        print("⚠️  CANNOT CONTINUE - no database backend installed")
        print("=" * 80)
        print("\nLevelDB tool requires plyvel or python-rocksdb package.")
        print("Please install one of them first.")
        sys.exit(1)

    # Test 2: Check LevelDB Manager
    has_leveldb = await test_leveldb_manager()

    if not has_leveldb:
        print("\n" + "=" * 80)
        print("⚠️  LevelDB database not found or cannot be opened")
        print("=" * 80)
        print("\nPossible reasons:")
        print("1. LevelDB database path not configured correctly")
        print("2. Database files don't exist at expected locations")
        print("3. Permission issues accessing the database")
        sys.exit(1)

    # Test 3: Test basic tool functionality
    tool_works = await test_generate_field_tool()

    if not tool_works:
        print("\n⚠️  Basic tool test failed, skipping pattern tests")
        sys.exit(1)

    # Test 4: Test specific patterns
    await test_specific_fields()

    print("\n" + "*" * 80)
    print("ALL TESTS COMPLETED")
    print("*" * 80)


if __name__ == "__main__":
    asyncio.run(main())
