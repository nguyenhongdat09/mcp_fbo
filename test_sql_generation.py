#!/usr/bin/env python3
"""Test SQL Generation Tool"""

import asyncio
import sys
sys.path.insert(0, '.')

from fastbusiness_mcp.tools.generate_sql_for_fields import GenerateSQLForFieldsTool


async def test_sql_generation():
    """Test SQL generation with various scenarios"""
    tool = GenerateSQLForFieldsTool()

    print("=" * 80)
    print("TEST 1: Partitioned table with lookup fields")
    print("=" * 80)

    result1 = await tool.execute({
        'field_names': ['ma_bo_phant', 'ten_bo_phan%l'],
        'tables': ['d91$000000'],
        'create_master_table': False
    })

    print(f"Success: {result1['success']}")
    print(f"\nSQL Script:\n{result1['sql_script']}")

    print("\n" + "=" * 80)
    print("TEST 2: Non-partitioned table")
    print("=" * 80)

    result2 = await tool.execute({
        'field_names': ['ma_vt', 'ten_vt', 'so_luong'],
        'tables': ['dmvt'],
        'create_master_table': False
    })

    print(f"Success: {result2['success']}")
    print(f"\nSQL Script:\n{result2['sql_script']}")

    print("\n" + "=" * 80)
    print("TEST 3: Multiple tables with numeric fields")
    print("=" * 80)

    result3 = await tool.execute({
        'field_names': ['tien_nt', 'so_luong', 'ngay_ct'],
        'tables': ['d91$000000', 'm91$000000'],
        'create_master_table': False
    })

    print(f"Success: {result3['success']}")
    print(f"\nSQL Script:\n{result3['sql_script']}")

    print("\n" + "=" * 80)
    print("TEST 4: Lookup field with master table creation")
    print("=" * 80)

    result4 = await tool.execute({
        'field_names': ['ma_khlk', 'ten_kh%l'],
        'tables': ['d91$000000'],
        'create_master_table': True
    })

    print(f"Success: {result4['success']}")
    print(f"\nSQL Script:\n{result4['sql_script']}")

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(test_sql_generation())
