"""Test partition validator manually."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastbusiness_mcp.validators.partition_validator import PartitionValidator


async def test_partition():
    """Test partition validation."""
    validator = PartitionValidator()

    print("=" * 70)
    print("Testing Partition Validator")
    print("=" * 70)

    # Test 1: Hardcoded partition (should fail)
    print("\n✅ Test 1: Hardcoded Partition (Should Fail)")
    print("-" * 70)
    sql_bad = "select * from d91$202501 where stt_rec = @stt_rec"
    print(f"SQL: {sql_bad}")
    result = validator.validate(sql_bad)

    print(f"\nResult: {'❌ INVALID' if not result.is_valid else '✅ VALID'}")
    if not result.is_valid:
        for error in result.errors:
            print(f"\n  Error: {error.message}")
            print(f"  Code: {error.code}")
            print(f"  Suggestion: {error.suggestion}")

    # Test 2: Correct partition (should pass)
    print("\n\n✅ Test 2: Correct Partition (Should Pass)")
    print("-" * 70)
    sql_good = "select * from @@prime$partition$current where stt_rec = @stt_rec"
    print(f"SQL: {sql_good}")
    result = validator.validate(sql_good)

    print(f"\nResult: {'❌ INVALID' if not result.is_valid else '✅ VALID'}")

    # Test 3: Multiple hardcoded partitions
    print("\n\n✅ Test 3: Multiple Hardcoded Partitions")
    print("-" * 70)
    sql_multiple = """
        select * from d91$202501
        union all
        select * from d91$202412
    """
    print(f"SQL: {sql_multiple.strip()}")
    result = validator.validate(sql_multiple)

    print(f"\nResult: {'❌ INVALID' if not result.is_valid else '✅ VALID'}")
    if not result.is_valid:
        print(f"Found {len(result.errors)} error(s):")
        for i, error in enumerate(result.errors, 1):
            print(f"\n  {i}. {error.message}")
            print(f"     Suggestion: {error.suggestion}")

    # Test 4: Master table hardcoded
    print("\n\n✅ Test 4: Master Table Hardcoded")
    print("-" * 70)
    sql_master = "select * from m91$202501"
    print(f"SQL: {sql_master}")
    result = validator.validate(sql_master)

    print(f"\nResult: {'❌ INVALID' if not result.is_valid else '✅ VALID'}")
    if not result.is_valid:
        for error in result.errors:
            print(f"\n  Error: {error.message}")
            print(f"  Suggestion: {error.suggestion}")

    print("\n" + "=" * 70)
    print("All Tests Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_partition())
