"""Test Generate Field from LMDB - FastBusiness MCP"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import tool
from fastbusiness_mcp.tools.generate_field_from_lmdb import GenerateFieldFromLMDBTool


async def test_generate_field():
    """Test generating fields from LMDB"""
    
    # Path to LMDB database
    db_path = os.path.join(project_root, "data", "fields_lmdb")
    
    print("=" * 70)
    print("FastBusiness Field Generator - Test Suite")
    print("=" * 70)
    print(f"\n📁 Database path: {db_path}")
    
    # Check if database exists
    if not os.path.exists(db_path):
        print("\n❌ LMDB database not found!")
        print("\nNext steps:")
        print("1. Create the database directory:")
        print(f"   mkdir {db_path}")
        print("\n2. Run the database builder (need to create):")
        print("   python build_lmdb.py")
        print("\n" + "=" * 70)
        return
    
    # Initialize tool
    print("\n🔧 Initializing tool...")
    tool = GenerateFieldFromLMDBTool(db_path=db_path)
    
    # TEST 1: Database Statistics
    print("\n" + "=" * 70)
    print("TEST 1: Database Statistics")
    print("=" * 70)
    
    try:
        stats = tool.get_database_stats()
        
        if stats['success']:
            print(f"\n✓ Database loaded successfully!")
            print(f"\n📊 Statistics:")
            
            for context, count in stats['statistics'].items():
                if context != 'total':
                    print(f"  {context:20s}: {count:5d} fields")
            
            print(f"  {'─' * 30}")
            print(f"  {'TOTAL':20s}: {stats['statistics']['total']:5d} fields")
        else:
            print(f"\n✗ Failed to get stats")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nDatabase might be empty or corrupted.")
        tool.close()
        return
    
    # TEST 2: Generate ma_kh (common field)
    print("\n" + "=" * 70)
    print("TEST 2: Generate 'ma_kh' field (Dir context)")
    print("=" * 70)
    
    try:
        result = await tool.execute({
            'field_name': 'ma_kh',
            'context_type': 'DIR',
            'lookup_type': 'autocomplete',
            'show_similar': True
        })
        
        print(f"\n✓ Success: {result['success']}")
        
        if result['success']:
            print(f"✓ Field Name: {result['field_name']}")
            print(f"✓ Header: {result['header']}")
            print(f"✓ Source: {result['source']}")
            
            if 'xml' in result:
                print(f"\n📄 Generated XML:")
                print("─" * 70)
                print(result['xml'])
                print("─" * 70)
        else:
            print(f"✗ Error: {result['error']}")
            
            if 'similar_fields' in result:
                print(f"\n💡 Similar fields found:")
                for field in result['similar_fields'][:5]:
                    print(f"  - {field['field_name']}: {field['header']}")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    # TEST 3: Generate so_luong (quantity field)
    print("\n" + "=" * 70)
    print("TEST 3: Generate 'so_luong' field")
    print("=" * 70)
    
    try:
        result = await tool.execute({
            'field_name': 'so_luong',
            'context_type': 'DIR',
            'lookup_type': 'default',
            'show_similar': True
        })
        
        print(f"\n✓ Success: {result['success']}")
        
        if result['success']:
            print(f"✓ Field Name: {result['field_name']}")
            print(f"✓ Header: {result['header']}")
            print(f"✓ Source: {result['source']}")
            
            if 'xml' in result:
                print(f"\n📄 Generated XML:")
                print("─" * 70)
                print(result['xml'])
                print("─" * 70)
        else:
            print(f"✗ Error: {result['error']}")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    # TEST 4: Search fields
    print("\n" + "=" * 70)
    print("TEST 4: Search fields with pattern 'ma_'")
    print("=" * 70)
    
    try:
        search_result = tool.search_fields(
            context_type='DIR',
            pattern='ma_',
            limit=10
        )
        
        if search_result['success']:
            print(f"\n🔍 Pattern: '{search_result['pattern']}'")
            print(f"✓ Found {search_result['count']} fields:\n")
            
            for field in search_result['results']:
                print(f"  • {field['field_name']:20s} | {field['header']}")
        else:
            print(f"\n✗ Search failed")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    # TEST 5: Test non-existent field
    print("\n" + "=" * 70)
    print("TEST 5: Generate non-existent field (test fallback)")
    print("=" * 70)
    
    try:
        result = await tool.execute({
            'field_name': 'xyz_field_not_exist',
            'context_type': 'DIR',
            'lookup_type': 'default',
            'show_similar': True
        })
        
        print(f"\n✓ Success: {result['success']}")
        
        if result['success']:
            print(f"✓ Field generated from template")
            print(f"✓ Source: {result['source']}")
        else:
            print(f"✗ Field not found: {result['error']}")
            
            if 'suggestion' in result:
                print(f"\n💡 {result['suggestion']}")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    # Close connection
    print("\n" + "=" * 70)
    print("Closing database connection...")
    tool.close()
    
    print("\n✓ All tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    print("\n🚀 Starting FastBusiness Field Generator Tests...\n")
    asyncio.run(test_generate_field())