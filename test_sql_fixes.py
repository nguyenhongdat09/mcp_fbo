#!/usr/bin/env python3
"""Test SQL Generation Tool - Bug Fixes"""

import asyncio
import sys
sys.path.insert(0, '.')

from fastbusiness_mcp.tools.generate_sql_for_fields import GenerateSQLForFieldsTool


async def test_fixes():
    """Test SQL generation with bug fixes"""
    tool = GenerateSQLForFieldsTool()

    print("=" * 80)
    print("TEST 1: sl_nhap, sl_xuat pattern (should be numeric, not nvarchar)")
    print("=" * 80)

    result1 = await tool.execute({
        'field_names': ['sl_nhap', 'sl_xuat', 'sl_ton'],
        'tables': ['d31$000000'],
    })

    print(f"Success: {result1['success']}")
    print(f"\nSQL Script:\n{result1['sql_script']}")

    # Verify
    assert 'numeric(19,4)' in result1['sql_script'], "❌ FAILED: sl_nhap should be numeric(19,4)!"
    assert 'nvarchar' not in result1['sql_script'], "❌ FAILED: Should not contain nvarchar!"
    print("\n✅ PASS: sl_* fields correctly detected as numeric(19,4)")

    print("\n" + "=" * 80)
    print("TEST 2: Auto-extract table from GRID XML")
    print("=" * 80)

    grid_xml = '''<grid table="d31$000000" type="Detail">
        <fields>
            <field name="sl_nhap"/>
            <field name="sl_xuat"/>
        </fields>
    </grid>'''

    result2 = await tool.execute({
        'field_names': ['sl_nhap', 'sl_xuat'],
        'xml_content': grid_xml,
    })

    print(f"Success: {result2['success']}")
    print(f"Tables: {result2['tables']}")
    print(f"\nSQL Script:\n{result2['sql_script']}")

    # Verify
    assert result2['tables'] == ['d31$'], f"❌ FAILED: Expected ['d31$'], got {result2['tables']}"
    assert 'd31$' in result2['sql_script'], "❌ FAILED: Should contain d31$!"
    assert 'c31$' not in result2['sql_script'], "❌ FAILED: Should NOT suggest c31$!"
    assert 'i31$' not in result2['sql_script'], "❌ FAILED: Should NOT suggest i31$!"
    print("\n✅ PASS: Correctly extracted d31$ from grid XML, no other tables")

    print("\n" + "=" * 80)
    print("TEST 3: Auto-extract table from DIR XML")
    print("=" * 80)

    dir_xml = '''<dir table="m31$000000" type="Voucher">
        <fields>
            <field name="ma_kh"/>
            <field name="ten_kh%l"/>
        </fields>
    </dir>'''

    result3 = await tool.execute({
        'field_names': ['ma_kh', 'ten_kh%l'],
        'xml_content': dir_xml,
    })

    print(f"Success: {result3['success']}")
    print(f"Tables: {result3['tables']}")
    print(f"\nSQL Script:\n{result3['sql_script']}")

    # Verify
    assert result3['tables'] == ['m31$'], f"❌ FAILED: Expected ['m31$'], got {result3['tables']}"
    assert 'm31$' in result3['sql_script'], "❌ FAILED: Should contain m31$!"
    assert 'd31$' not in result3['sql_script'], "❌ FAILED: Should NOT suggest d31$!"
    assert 'c31$' not in result3['sql_script'], "❌ FAILED: Should NOT suggest c31$!"
    assert 'i31$' not in result3['sql_script'], "❌ FAILED: Should NOT suggest i31$!"
    print("\n✅ PASS: Correctly extracted m31$ from dir XML, no other tables")

    print("\n" + "=" * 80)
    print("TEST 4: Non-partitioned table extraction")
    print("=" * 80)

    non_partitioned_xml = '''<dir table="dmvt" type="Category">
        <fields>
            <field name="ma_vt"/>
        </fields>
    </dir>'''

    result4 = await tool.execute({
        'field_names': ['ma_vt'],
        'xml_content': non_partitioned_xml,
    })

    print(f"Success: {result4['success']}")
    print(f"Tables: {result4['tables']}")
    print(f"\nSQL Script:\n{result4['sql_script']}")

    # Verify
    assert result4['tables'] == ['dmvt'], f"❌ FAILED: Expected ['dmvt'], got {result4['tables']}"
    assert 'dmvt' in result4['sql_script'], "❌ FAILED: Should contain dmvt!"
    assert '$' not in result4['sql_script'], "❌ FAILED: Should NOT contain $ for non-partitioned!"
    print("\n✅ PASS: Correctly extracted dmvt (non-partitioned), no $ added")

    print("\n" + "=" * 80)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 80)
    print("\nSummary:")
    print("✅ sl_* pattern now detects as numeric(19,4)")
    print("✅ Auto-extract table from <grid table=\"...\">")
    print("✅ Auto-extract table from <dir table=\"...\">")
    print("✅ No extra table suggestions (c31$, i31$)")
    print("✅ Non-partitioned tables handled correctly")


if __name__ == '__main__':
    asyncio.run(test_fixes())
