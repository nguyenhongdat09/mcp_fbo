"""Test file type detector manually."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector
from fastbusiness_mcp.utils.file_utils import read_file


def test_file_detector():
    """Test file type detection."""
    detector = FileTypeDetector()

    print("=" * 70)
    print("Testing File Type Detector")
    print("=" * 70)

    # Test 1: Sample DIR file
    print("\n✅ Test 1: Sample DIR File")
    print("-" * 70)
    sample_xml = read_file("tests/fixtures/sample_dir.xml")

    if sample_xml:
        context = detector.detect(sample_xml)

        print(f"File Type: {context.file_type.value}")
        print(f"Table Name: {context.table_name}")
        print(f"Has Partition: {context.has_partition}")
        print(f"Partition Field: {context.partition_field or 'N/A'}")
        print(f"Events: {', '.join([e.value for e in context.events])}")
    else:
        print("❌ Error: Could not read sample file")

    # Test 2: Grid View
    print("\n\n✅ Test 2: Grid View XML")
    print("-" * 70)
    grid_xml = '''<?xml version="1.0"?>
    <grid table="m91$000000" type="Voucher">
        <queries>
            <query event="Loading"></query>
            <query event="Finding"></query>
        </queries>
        <toolbar>
            <button command="Insert"></button>
        </toolbar>
    </grid>'''

    context = detector.detect(grid_xml)
    print(f"File Type: {context.file_type.value}")
    print(f"Table Name: {context.table_name}")
    print(f"Events: {', '.join([e.value for e in context.events])}")

    # Test 3: Grid Detail
    print("\n\n✅ Test 3: Grid Detail XML")
    print("-" * 70)
    detail_xml = '''<?xml version="1.0"?>
    <grid type="Detail">
        <fields>
            <field name="ma_vt"></field>
        </fields>
    </grid>'''

    context = detector.detect(detail_xml)
    print(f"File Type: {context.file_type.value}")
    print(f"Controller: {context.controller_name or 'N/A'}")

    # Test 4: Filter
    print("\n\n✅ Test 4: Filter XML")
    print("-" * 70)
    filter_xml = '''<?xml version="1.0"?>
    <!DOCTYPE dir [
        <!ENTITY XMLWhenFilterLoading SYSTEM "test.xml">
    ]>
    <dir type="Report" cache="true">
        <commands>
            <command event="Processing"></command>
        </commands>
    </dir>'''

    context = detector.detect(filter_xml)
    print(f"File Type: {context.file_type.value}")
    print(f"Events: {', '.join([e.value for e in context.events])}")

    print("\n" + "=" * 70)
    print("All Tests Complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_file_detector()
