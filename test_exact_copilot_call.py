"""Test exact same way as Copilot calls the tool"""

import asyncio
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastbusiness_mcp.tools.generate_field_from_lmdb import GenerateFieldFromLMDBTool


async def test_exact_copilot_call():
    """
    Test EXACTLY how Copilot calls the tool
    """
    
    print("=" * 80)
    print("TEST EXACT COPILOT CALL")
    print("=" * 80)
    
    # Initialize tool
    db_path = "data/fields_lmdb"
    tool = GenerateFieldFromLMDBTool(db_path=db_path)
    
    print(f"\n📁 Database: {db_path}")
    print(f"\n🔧 Calling tool with EXACT Copilot arguments...")
    
    # EXACT arguments from Copilot
    arguments = {
        "field_name": "dept_id",
        "file_path": "\\\\172.168.5.14\\CustomerPro\\HRM\\LIKSIN\\FBISP23\\App_Data\\Controllers\\Dir\\BISATran.xml",
        "lookup_type": "autocomplete"
    }
    
    print(f"\n📋 Arguments:")
    print(json.dumps(arguments, indent=2))
    
    print(f"\n{'─' * 80}")
    print("EXECUTING...")
    print('─' * 80)
    
    # Call tool EXACTLY as Copilot does
    result = await tool.execute(arguments)
    
    # Display result
    print(f"\n📊 RESULT:")
    print('─' * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print('─' * 80)
    
    # Analyze result
    print(f"\n🔍 ANALYSIS:")
    print('─' * 80)
    
    if result['success']:
        print("✅ SUCCESS!")
        print(f"\n  Field Name: {result.get('field_name')}")
        print(f"  Header: {result.get('header')}")
        print(f"  Source: {result.get('source')}")
        
        if 'xml' in result:
            print(f"\n  📄 Generated XML:")
            print("  " + "─" * 76)
            for line in result['xml'].split('\n'):
                print(f"  {line}")
            print("  " + "─" * 76)
    else:
        print("❌ FAILED!")
        print(f"\n  Error: {result.get('error')}")
        
        if 'hint' in result:
            print(f"\n  💡 Hint: {result['hint']}")
        
        if 'suggestions' in result:
            print(f"\n  💡 Suggestions:")
            for suggestion in result['suggestions']:
                print(f"    - {suggestion}")
        
        if 'similar_fields' in result:
            print(f"\n  📋 Similar fields found:")
            for field in result['similar_fields'][:5]:
                print(f"    - {field['field_name']}: {field['header']}")
        
        if 'did_you_mean' in result:
            print(f"\n  ❓ Did you mean: {result['did_you_mean']}")
    
    # Close tool
    tool.close()
    
    print("\n" + "=" * 80)
    print("✓ Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    print("\n🚀 Testing EXACT Copilot Call Pattern...\n")
    asyncio.run(test_exact_copilot_call())