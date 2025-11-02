#!/usr/bin/env python3
"""Test SQL Generation with file_path parameter"""

import asyncio
import sys
sys.path.insert(0, '.')

from fastbusiness_mcp.tools.generate_sql_for_fields import GenerateSQLForFieldsTool


async def test_file_path_extraction():
    """Test SQL generation with file_path parameter"""
    tool = GenerateSQLForFieldsTool()

    print("=" * 80)
    print("TEST 1: file_path with GRID (partitioned table)")
    print("=" * 80)

    result1 = await tool.execute({
        'field_names': ['sl_nhap', 'sl_xuat'],
        'file_path': 'test_data/test_grid.xml',
    })

    print(f"Success: {result1['success']}")
    if result1['success']:
        print(f"Extracted table: {result1['tables']}")
        print(f"\nSQL Script:\n{result1['sql_script']}")

        # Verify
        assert result1['tables'] == ['d31$'], f"❌ Expected ['d31$'], got {result1['tables']}"
        assert 'numeric(19,4)' in result1['sql_script'], "❌ sl_nhap should be numeric!"
        assert 'd31$' in result1['sql_script'], "❌ Should contain d31$!"
        print("\n✅ PASS: Extracted d31$ from file, sl_* is numeric(19,4)")
    else:
        print(f"❌ FAILED: {result1['error']}")
        return

    print("\n" + "=" * 80)
    print("TEST 2: file_path with DIR (partitioned table)")
    print("=" * 80)

    result2 = await tool.execute({
        'field_names': ['ma_kh', 'ten_kh%l', 'ngay_ct'],
        'file_path': 'test_data/test_dir.xml',
    })

    print(f"Success: {result2['success']}")
    if result2['success']:
        print(f"Extracted table: {result2['tables']}")
        print(f"\nSQL Script:\n{result2['sql_script']}")

        # Verify
        assert result2['tables'] == ['m91$'], f"❌ Expected ['m91$'], got {result2['tables']}"
        assert "exec fsd_addfields 'm91$', 'ma_kh', 'varchar(33)'" in result2['sql_script']
        assert "exec fsd_addfields 'm91$', 'ten_kh%l', 'nvarchar(256)'" in result2['sql_script']
        assert "exec fsd_addfields 'm91$', 'ngay_ct', 'smalldatetime'" in result2['sql_script']
        print("\n✅ PASS: Extracted m91$ from file, correct SQL types")
    else:
        print(f"❌ FAILED: {result2['error']}")
        return

    print("\n" + "=" * 80)
    print("TEST 3: file_path with non-partitioned table")
    print("=" * 80)

    result3 = await tool.execute({
        'field_names': ['ma_vt', 'ten_vt', 'don_gia'],
        'file_path': 'test_data/test_dmvt.xml',
    })

    print(f"Success: {result3['success']}")
    if result3['success']:
        print(f"Extracted table: {result3['tables']}")
        print(f"\nSQL Script:\n{result3['sql_script']}")

        # Verify
        assert result3['tables'] == ['dmvt'], f"❌ Expected ['dmvt'], got {result3['tables']}"
        assert 'dmvt' in result3['sql_script'], "❌ Should contain dmvt!"
        assert '$' not in result3['sql_script'], "❌ Should NOT contain $ for non-partitioned!"
        print("\n✅ PASS: Extracted dmvt from file, no $ added")
    else:
        print(f"❌ FAILED: {result3['error']}")
        return

    print("\n" + "=" * 80)
    print("TEST 4: Error handling - missing file_path and xml_content")
    print("=" * 80)

    result4 = await tool.execute({
        'field_names': ['ma_kh'],
        # No file_path, no xml_content
    })

    print(f"Success: {result4['success']}")
    if not result4['success']:
        print(f"Error (expected): {result4['error']}")
        assert 'Either file_path or xml_content must be provided' in result4['error']
        print("\n✅ PASS: Correctly rejects when both file_path and xml_content are missing")
    else:
        print("❌ FAILED: Should have returned error!")
        return

    print("\n" + "=" * 80)
    print("TEST 5: Error handling - file not found")
    print("=" * 80)

    result5 = await tool.execute({
        'field_names': ['ma_kh'],
        'file_path': 'nonexistent.xml',
    })

    print(f"Success: {result5['success']}")
    if not result5['success']:
        print(f"Error (expected): {result5['error']}")
        assert 'Failed to read file' in result5['error']
        print("\n✅ PASS: Correctly handles file not found")
    else:
        print("❌ FAILED: Should have returned error!")
        return

    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 80)
    print("\nSummary:")
    print("✅ file_path with GRID → Extracts d31$")
    print("✅ file_path with DIR → Extracts m91$")
    print("✅ file_path with non-partitioned → Extracts dmvt (no $)")
    print("✅ Error handling when file_path/xml_content missing")
    print("✅ Error handling when file not found")
    print("\n✨ NEW: Python reads file and extracts table automatically!")


if __name__ == '__main__':
    asyncio.run(test_file_path_extraction())
