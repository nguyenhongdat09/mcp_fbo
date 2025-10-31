"""Test result access validator manually."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastbusiness_mcp.validators.result_access_validator import ResultAccessValidator


async def test_result_access():
    """Test result access validation."""
    validator = ResultAccessValidator()

    print("=" * 70)
    print("Testing Result Access Validator")
    print("=" * 70)

    # Test 1: Wrong property access
    print("\n✅ Test 1: Wrong Property Access (Should Fail)")
    print("-" * 70)
    js_bad = """
    var maKH = result[0].ma_kh;
    var tenKH = result[1].ten_kh;
    """

    sql = "select ma_kh, ten_kh from dmkh"

    print(f"SQL Query: {sql}")
    print(f"JavaScript:\n{js_bad}")

    result = validator.validate(js_bad, sql)

    print(f"\nResult: {'❌ INVALID' if not result.is_valid else '✅ VALID'}")
    if not result.is_valid:
        print(f"Found {len(result.errors)} error(s):")
        for i, error in enumerate(result.errors, 1):
            print(f"\n  {i}. {error.message}")
            print(f"     Code: {error.code}")
            print(f"     Suggestion: {error.suggestion}")

    # Test 2: Correct access
    print("\n\n✅ Test 2: Correct Value Access (Should Pass)")
    print("-" * 70)
    js_good = """
    var maKH = result[0].Value;  // ma_kh
    var tenKH = result[1].Value; // ten_kh
    """

    print(f"JavaScript:\n{js_good}")

    result = validator.validate(js_good, sql)

    print(f"\nResult: {'❌ INVALID' if not result.is_valid else '✅ VALID'}")

    # Test 3: Column mapping
    print("\n\n✅ Test 3: Generate Column Mapping")
    print("-" * 70)
    sql_query = "select ma_kh, ten_kh, dia_chi, dien_thoai from dmkh"
    print(f"SQL Query: {sql_query}")

    mapping = validator.generate_column_mapping(sql_query)
    print(f"\nGenerated Mapping:\n{mapping}")

    # Test 4: Complex SQL
    print("\n\n✅ Test 4: Wrong Access with Column Mapping")
    print("-" * 70)
    js_complex = "var diaChi = result[2].dia_chi;"
    sql_complex = "select ma_kh, ten_kh, dia_chi from dmkh"

    print(f"SQL: {sql_complex}")
    print(f"JavaScript: {js_complex}")

    result = validator.validate(js_complex, sql_complex)

    print(f"\nResult: {'❌ INVALID' if not result.is_valid else '✅ VALID'}")
    if not result.is_valid:
        for error in result.errors:
            print(f"\n  Error: {error.message}")
            print(f"  Suggestion: {error.suggestion}")

    print("\n" + "=" * 70)
    print("All Tests Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_result_access())
