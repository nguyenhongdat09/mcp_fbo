"""Universal field search script"""

import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastbusiness_mcp.tools.generate_field_from_lmdb import GenerateFieldFromLMDBTool


async def search_field(field_name: str, context_type: str = 'DIR'):
    """
    Search for a field
    
    Args:
        field_name: Field name to search (e.g., 'ma_bp', 'ma_kh')
        context_type: Context type (DIR, FILTER_VOUCHER, GRID_VIEW, etc.)
    """
    
    db_path = "data/fields_lmdb"
    tool = GenerateFieldFromLMDBTool(db_path=db_path)
    
    print("=" * 70)
    print(f"Search Field: '{field_name}' in {context_type}")
    print("=" * 70)
    
    # Step 1: Quick search
    print(f"\n🔍 Step 1: Quick search for '{field_name}'...")
    
    search_result = tool.search_fields(
        context_type=context_type,
        pattern=field_name,
        limit=5
    )
    
    if search_result['success'] and search_result['count'] > 0:
        print(f"✓ Found {search_result['count']} matching field(s):")
        
        for field in search_result['results']:
            print(f"\n  • {field['field_name']}")
            print(f"    Header: {field['header']}")
            print(f"    Type: {field['type']}")
    else:
        print(f"✗ No exact matches found")
        
        # Try partial match
        print(f"\n🔍 Trying partial match with prefix...")
        prefix = field_name[:3] if len(field_name) >= 3 else field_name
        
        search_result = tool.search_fields(
            context_type=context_type,
            pattern=prefix,
            limit=10
        )
        
        if search_result['success'] and search_result['count'] > 0:
            print(f"✓ Found {search_result['count']} fields starting with '{prefix}':")
            for field in search_result['results']:
                print(f"  - {field['field_name']}: {field['header']}")
    
    # Step 2: Get full definition
    print(f"\n" + "=" * 70)
    print(f"Step 2: Get full definition for '{field_name}'")
    print("=" * 70)
    
    result = await tool.execute({
        'field_name': field_name,
        'context_type': context_type,
        'lookup_type': 'autocomplete',
        'show_similar': True
    })
    
    if result['success']:
        print(f"\n✓ Field found!")
        print(f"\n📋 Basic Info:")
        print(f"  Name: {result['field_name']}")
        print(f"  Header: {result['header']}")
        print(f"  Source: {result['source']}")
        
        # Show definition
        if 'definition' in result:
            print(f"\n📄 Full Definition:")
            print(json.dumps(result['definition'], indent=2, ensure_ascii=False))
        
        # Show XML
        if 'xml' in result:
            print(f"\n📄 Generated XML:")
            print("─" * 70)
            print(result['xml'])
            print("─" * 70)
            
            # Save to file
            xml_file = f"{field_name}_{context_type}.xml"
            with open(xml_file, 'w', encoding='utf-8') as f:
                f.write(result['xml'])
            print(f"\n💾 XML saved to: {xml_file}")
    
    else:
        print(f"\n✗ Field not found: {result['error']}")
        
        if 'similar_fields' in result:
            print(f"\n💡 Did you mean one of these?")
            for field in result['similar_fields'][:10]:
                print(f"  - {field['field_name']}: {field['header']}")
    
    tool.close()
    
    print("\n" + "=" * 70)
    print("✓ Search completed!")
    print("=" * 70)


if __name__ == "__main__":
    # Get field name from command line or use default
    if len(sys.argv) > 1:
        field_name = sys.argv[1]
        context_type = sys.argv[2] if len(sys.argv) > 2 else 'DIR'
    else:
        field_name = 'ma_bp'  # Default
        context_type = 'DIR'
    
    print(f"\n🚀 Searching for: {field_name} in {context_type}\n")
    
    asyncio.run(search_field(field_name, context_type))