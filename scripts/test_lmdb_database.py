#!/usr/bin/env python3
"""Test and inspect LMDB Field Database

This script allows you to inspect the contents of the LMDB field database
and test field queries with pattern matching.

Usage:
    # Show database statistics
    python scripts/test_lmdb_database.py --stats

    # List all fields in a context
    python scripts/test_lmdb_database.py --list DIR

    # List fields with limit
    python scripts/test_lmdb_database.py --list DIR --limit 20

    # Search for fields by pattern
    python scripts/test_lmdb_database.py --search "ma_" --context DIR

    # Test field lookup with pattern matching
    python scripts/test_lmdb_database.py --test "sl_nhap_hang" --context GRID_INPUT

    # Test lookup types
    python scripts/test_lmdb_database.py --test "ma_kh" --context DIR --lookup autocomplete
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastbusiness_mcp.lmdb_adapter import LMDBManager, FieldPatternMatcher


def show_stats(lmdb: LMDBManager):
    """Show database statistics"""
    print("\n" + "="*70)
    print("📊 LMDB FIELD DATABASE STATISTICS")
    print("="*70)

    total_fields = 0
    for context_type in ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']:
        count = lmdb.count_fields(context_type)
        if count > 0:
            print(f"  {context_type:20} : {count:,} fields")
            total_fields += count

    print(f"\n  {'TOTAL':20} : {total_fields:,} fields")
    print("="*70)


def list_fields(lmdb: LMDBManager, context_type: str, limit: int = None):
    """List all fields in a context"""
    print(f"\n📋 Fields in {context_type}:")
    print("-"*70)

    fields = lmdb.get_all_fields(context_type)

    if not fields:
        print(f"  ⚠️  No fields found in {context_type}")
        return

    display_limit = limit if limit else len(fields)

    for i, field_data in enumerate(fields[:display_limit], 1):
        field_name = field_data.get('field_name', '?')
        definition = field_data.get('definition', {})
        header = definition.get('header', 'N/A')
        field_type = definition.get('type', 'N/A')
        width = definition.get('width', 'N/A')

        print(f"{i:3}. {field_name:25} | {header:35} | {field_type:10} | W:{width}")

    if len(fields) > display_limit:
        print(f"\n... and {len(fields) - display_limit} more fields")

    print(f"\nTotal: {len(fields)} fields")


def search_fields(lmdb: LMDBManager, pattern: str, context_type: str, limit: int = 50):
    """Search for fields matching pattern"""
    print(f"\n🔍 Searching for '{pattern}' in {context_type}:")
    print("-"*70)

    results = lmdb.search_fields(context_type, pattern, limit=limit)

    if not results:
        print(f"  ⚠️  No fields matching '{pattern}' found in {context_type}")
        return

    for i, result in enumerate(results, 1):
        field_name = result.get('field_name', '?')
        definition = result.get('definition', {})
        header = definition.get('header', 'N/A')
        field_type = definition.get('type', 'N/A')

        print(f"{i:3}. {field_name:25} | {header:35} | {field_type:10}")

    print(f"\nFound: {len(results)} fields")


def test_field_lookup(lmdb: LMDBManager, field_name: str, context_type: str,
                     lookup_type: str = 'default'):
    """Test field lookup with pattern matching"""
    print(f"\n🧪 Testing field lookup:")
    print("-"*70)
    print(f"  Field name    : {field_name}")
    print(f"  Context type  : {context_type}")
    print(f"  Lookup type   : {lookup_type}")
    print("-"*70)

    matcher = FieldPatternMatcher(lmdb)
    result = matcher.get_field_with_fallback(context_type, field_name, lookup_type)

    if result:
        print(f"\n✅ SUCCESS - Field found/generated")
        print(f"\n  Final field name: {result.get('field_name', '?')}")
        print(f"  Header          : {result.get('header', '?')}")
        print(f"  Type            : {result.get('type', '?')}")

        # Detect source
        actual_name = result.get('field_name', '')
        if actual_name == matcher.add_lookup_suffix(field_name, lookup_type):
            source = "✓ Exact match in database"
        else:
            source = "✓ Generated from template (pattern matching)"

        print(f"  Source          : {source}")

        # Show XML snippet
        xml = result.get('xml', '')
        if xml:
            xml_lines = xml.strip().split('\n')
            print(f"\n  XML Definition (first 5 lines):")
            for line in xml_lines[:5]:
                print(f"    {line}")
            if len(xml_lines) > 5:
                print(f"    ... ({len(xml_lines) - 5} more lines)")
    else:
        print(f"\n❌ FAILED - Field not found")

        # Show similar fields
        similar = matcher.search_similar_fields(context_type, field_name, limit=10)
        if similar:
            print(f"\n💡 Similar fields found:")
            for i, sim in enumerate(similar[:5], 1):
                print(f"  {i}. {sim['field_name']:25} | {sim['definition'].get('header', 'N/A')}")


def get_field_details(lmdb: LMDBManager, field_name: str, context_type: str):
    """Get detailed information about a specific field"""
    print(f"\n🔎 Field Details:")
    print("-"*70)

    field = lmdb.get_field(context_type, field_name)

    if not field:
        print(f"  ⚠️  Field '{field_name}' not found in {context_type}")
        return

    definition = field.get('definition', {})

    print(f"  Field Name: {field.get('field_name', '?')}")
    print(f"  Header    : {definition.get('header', 'N/A')}")
    print(f"  Type      : {definition.get('type', 'N/A')}")
    print(f"  Width     : {definition.get('width', 'N/A')}")

    # Show attributes
    attributes = definition.get('attributes', {})
    if attributes:
        print(f"\n  Attributes:")
        for key, value in attributes.items():
            print(f"    {key:20} = {value}")

    # Show XML
    xml = definition.get('xml', '')
    if xml:
        print(f"\n  Full XML Definition:")
        for line in xml.strip().split('\n'):
            print(f"    {line}")


def main():
    parser = argparse.ArgumentParser(
        description='Test and inspect LMDB field database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--db-path',
        default='data/fields_lmdb',
        help='LMDB database path (default: data/fields_lmdb)'
    )

    # Actions (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group(required=True)

    action_group.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )

    action_group.add_argument(
        '--list',
        metavar='CONTEXT',
        help='List all fields in context (DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT)'
    )

    action_group.add_argument(
        '--search',
        metavar='PATTERN',
        help='Search for fields matching pattern'
    )

    action_group.add_argument(
        '--test',
        metavar='FIELD_NAME',
        help='Test field lookup with pattern matching'
    )

    action_group.add_argument(
        '--get',
        metavar='FIELD_NAME',
        help='Get detailed information about a specific field'
    )

    # Optional arguments
    parser.add_argument(
        '--context',
        default='DIR',
        help='Context type for search/test/get (default: DIR)'
    )

    parser.add_argument(
        '--lookup',
        choices=['default', 'autocomplete', 'lookup'],
        default='default',
        help='Lookup type for test (default: default)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of results'
    )

    args = parser.parse_args()

    # Initialize LMDB
    print(f"Opening LMDB database at: {args.db_path}")
    lmdb = LMDBManager(db_path=args.db_path)

    try:
        if args.stats:
            show_stats(lmdb)

        elif args.list:
            list_fields(lmdb, args.list, args.limit)

        elif args.search:
            search_fields(lmdb, args.search, args.context, args.limit or 50)

        elif args.test:
            test_field_lookup(lmdb, args.test, args.context, args.lookup)

        elif args.get:
            get_field_details(lmdb, args.get, args.context)

    finally:
        lmdb.close()


if __name__ == '__main__':
    main()
