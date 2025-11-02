"""Test XML Handler Tool"""

import os
import sys
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastbusiness_mcp.tools.xml_handler_tool import XMLHandlerTool


# Sample XML files for testing
DIR_XML = """<?xml version="1.0" encoding="utf-8"?>
<dir table="dmkhachhang">
    <field name="ma_kh" header="Mã khách hàng" width="120" />
    <field name="ten_kh" header="Tên khách hàng" width="200" />
    <field name="so_luong" header="Số lượng" width="100" />
    <field name="gia" header="Giá" width="100" />
    <field name="tien" header="Tiền" width="120" />
</dir>
"""

GRID_DETAIL_XML = """<?xml version="1.0" encoding="utf-8"?>
<grid table="d31$000000" type="Detail">
    <field name="ma_vt" header="Mã vật tư" width="120" />
    <field name="so_luong" header="Số lượng" width="100" />
    <field name="gia" header="Giá" width="100" />
    <field name="tien" header="Tiền" width="120" />
</grid>
"""


def test_add_onchange_handler_to_dir():
    """Test adding onChange handler to Dir file"""
    print("\n" + "="*60)
    print("TEST 1: Add onChange handler to Dir file")
    print("="*60)

    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(DIR_XML)
        temp_file = f.name

    try:
        tool = XMLHandlerTool("knowledge_base")

        # Test 1: Add simple console.log handler
        print("\n1. Adding onChange handler to 'ma_kh' field with console.log(1)...")
        result = tool.add_onchange_handler(
            temp_file,
            'ma_kh',
            'console.log(1);'
        )

        if result.get('success'):
            print(f"   ✅ Success!")
            print(f"   Function name: {result.get('function_name', '')}")
            print(f"   Generated code (first 200 chars):")
            print("   " + result.get('generated_code', '')[:200] + "...")

            # Read file to verify
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if clientScript was added
            if '<clientScript>' in content:
                print("   ✅ clientScript added to field")
            else:
                print("   ❌ clientScript NOT added to field")

            # Check if function was added
            if 'function onChange' in content:
                print("   ✅ Function added to <script> section")
            else:
                print("   ❌ Function NOT added to <script> section")

            # Check if using correct API
            if 'sender.parentForm' in content:
                print("   ✅ Uses correct API: sender.parentForm")
            else:
                print("   ❌ Does NOT use correct API")

        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

        # Test 2: Add calculation handler
        print("\n2. Adding onChange handler to 'so_luong' field with calculation...")
        result = tool.add_onchange_handler(
            temp_file,
            'so_luong',
            '''var sl = f.getItemValue('so_luong');
var gia = f.getItemValue('gia');
f.setItemValue('tien', sl * gia);'''
        )

        if result.get('success'):
            print(f"   ✅ Success!")
            print(f"   Function name: {result.get('function_name', '')}")
            # Verify calculation code is in function
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if "sl * gia" in content:
                print("   ✅ Calculation code added correctly")
        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

        print("\n   Final XML (first 1000 chars):")
        with open(temp_file, 'r', encoding='utf-8') as f:
            print("   " + f.read()[:1000] + "...")

    finally:
        # Cleanup
        os.unlink(temp_file)

    print("\n✅ Test 1 completed!\n")


def test_add_onchange_handler_to_grid_detail():
    """Test adding onChange handler to Grid Detail file"""
    print("\n" + "="*60)
    print("TEST 2: Add onChange handler to Grid Detail file")
    print("="*60)

    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(GRID_DETAIL_XML)
        temp_file = f.name

    try:
        tool = XMLHandlerTool("knowledge_base")

        print("\n1. Adding onChange handler to 'so_luong' field in Grid Detail...")
        result = tool.add_onchange_handler(
            temp_file,
            'so_luong',
            '''var row = g._activeRow;
var colGia = g._getColumnOrder('gia');
var gia = g._getItemValue(row, colGia);
var colTien = g._getColumnOrder('tien');
g._setItemValue(row, colTien, value * gia);'''
        )

        if result.get('success'):
            print(f"   ✅ Success!")
            print(f"   Function name: {result.get('function_name', '')}")

            # Read file to verify
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check critical Grid Detail requirements
            if 'g.get_element().parentForm' in content:
                print("   ✅ CRITICAL: Gets parent form with g.get_element().parentForm")
            else:
                print("   ❌ CRITICAL MISSING: Does NOT get parent form!")

            if 'sender.grid' in content:
                print("   ✅ Uses sender.grid to get grid object")

            if '_getItemValue' in content or '_setItemValue' in content:
                print("   ✅ Uses Grid API (_getItemValue, _setItemValue)")

        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

        print("\n   Final XML (first 1000 chars):")
        with open(temp_file, 'r', encoding='utf-8') as f:
            print("   " + f.read()[:1000] + "...")

    finally:
        # Cleanup
        os.unlink(temp_file)

    print("\n✅ Test 2 completed!\n")


def test_add_form_lifecycle_handler():
    """Test adding form lifecycle handler"""
    print("\n" + "="*60)
    print("TEST 3: Add form lifecycle handler")
    print("="*60)

    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(DIR_XML)
        temp_file = f.name

    try:
        tool = XMLHandlerTool("knowledge_base")

        print("\n1. Adding active$Form$ lifecycle handler...")
        result = tool.add_form_lifecycle_handler(
            temp_file,
            'active',
            '''if (f._action === 'New') {
    f.setItemValue('ma_kh', 'KH001');
    f.setItemValue('ten_kh', 'Test Customer');
}'''
        )

        if result.get('success'):
            print(f"   ✅ Success!")
            print(f"   Function name: {result.get('function_name', '')}")

            # Read file to verify
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if 'function active$Form$' in content:
                print("   ✅ Function name is correct: active$Form$")

            if "f._action === 'New'" in content:
                print("   ✅ Handler code added correctly")

        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

    finally:
        # Cleanup
        os.unlink(temp_file)

    print("\n✅ Test 3 completed!\n")


def test_add_onfocus_handler():
    """Test adding onFocus handler"""
    print("\n" + "="*60)
    print("TEST 4: Add onFocus handler")
    print("="*60)

    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(DIR_XML)
        temp_file = f.name

    try:
        tool = XMLHandlerTool("knowledge_base")

        print("\n1. Adding onFocus handler to 'ma_kh' field...")
        result = tool.add_onfocus_handler(
            temp_file,
            'ma_kh',
            'console.log("Focus on ma_kh");'
        )

        if result.get('success'):
            print(f"   ✅ Success!")
            print(f"   Function name: {result.get('function_name', '')}")

            # Read file to verify
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if 'onfocus=' in content.lower():
                print("   ✅ onFocus clientScript added")

            if 'function onFocus' in content:
                print("   ✅ onFocus function added")

        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")

    finally:
        # Cleanup
        os.unlink(temp_file)

    print("\n✅ Test 4 completed!\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("XML HANDLER TOOL - TEST SUITE")
    print("="*60)

    try:
        test_add_onchange_handler_to_dir()
        test_add_onchange_handler_to_grid_detail()
        test_add_form_lifecycle_handler()
        test_add_onfocus_handler()

        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
