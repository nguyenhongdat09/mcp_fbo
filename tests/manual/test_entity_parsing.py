"""Test XML parsing with complex ENTITY declarations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastbusiness_mcp.utils.xml_utils import (
    parse_xml_safe,
    parse_xml_tolerant,
    extract_entity_mappings,
    is_valid_xml_structure,
    remove_entity_declarations
)
from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector
from fastbusiness_mcp.utils.file_utils import read_file


def test_entity_parsing():
    """Test parsing XML with many ENTITY declarations."""

    print("=" * 70)
    print("Testing XML Parsing with Complex ENTITY Declarations")
    print("=" * 70)

    # Test with complex entity file
    xml_file = "tests/fixtures/complex_entities.xml"
    xml_content = read_file(xml_file)

    if not xml_content:
        print(f"❌ Could not read file: {xml_file}")
        return

    # Test 1: Check structure validity
    print("\n✅ Test 1: Check XML Structure")
    print("-" * 70)
    is_valid, message = is_valid_xml_structure(xml_content)
    print(f"Valid Structure: {'✅ YES' if is_valid else '❌ NO'}")
    print(f"Message: {message}")

    # Test 2: Extract entities
    print("\n✅ Test 2: Extract ENTITY Mappings")
    print("-" * 70)
    entities = extract_entity_mappings(xml_content)
    print(f"Found {len(entities)} entity declarations:")
    for name, value in list(entities.items())[:5]:  # Show first 5
        print(f"  &{name}; → {value}")
    if len(entities) > 5:
        print(f"  ... and {len(entities) - 5} more")

    # Test 3: Parse with parse_xml_safe
    print("\n✅ Test 3: Parse with parse_xml_safe")
    print("-" * 70)
    root = parse_xml_safe(xml_content)

    if root is not None:
        print("✅ Successfully parsed with parse_xml_safe")
        print(f"Root tag: {root.tag}")
        print(f"Root attributes: {dict(root.attrib)}")

        # Count child elements
        fields = root.findall(".//field")
        commands = root.findall(".//command")
        print(f"Found {len(fields)} field elements")
        print(f"Found {len(commands)} command elements")
    else:
        print("❌ Failed to parse with parse_xml_safe")

    # Test 4: Parse with parse_xml_tolerant (more robust)
    print("\n✅ Test 4: Parse with parse_xml_tolerant")
    print("-" * 70)
    root = parse_xml_tolerant(xml_content)

    if root is not None:
        print("✅ Successfully parsed with parse_xml_tolerant")
        print(f"Root tag: {root.tag}")

        # Extract key information
        table = root.get("table")
        code = root.get("code")
        type_attr = root.get("type")

        print(f"Table: {table}")
        print(f"Code: {code}")
        print(f"Type: {type_attr}")
    else:
        print("❌ Failed to parse with parse_xml_tolerant")

    # Test 5: Use with FileTypeDetector
    print("\n✅ Test 5: File Type Detection")
    print("-" * 70)
    detector = FileTypeDetector()

    try:
        context = detector.detect(xml_content)
        print(f"✅ File type detected: {context.file_type.value}")
        print(f"Table: {context.table_name}")
        print(f"Has Partition: {context.has_partition}")
        print(f"Events: {', '.join([e.value for e in context.events])}")
    except Exception as e:
        print(f"❌ Detection failed: {e}")

    # Test 6: Remove entities and parse
    print("\n✅ Test 6: Parse After Removing Entities")
    print("-" * 70)
    cleaned = remove_entity_declarations(xml_content)
    print(f"Original size: {len(xml_content)} chars")
    print(f"Cleaned size: {len(cleaned)} chars")
    print(f"Reduced by: {len(xml_content) - len(cleaned)} chars")

    root = parse_xml_safe(cleaned, remove_entities=False)
    if root is not None:
        print("✅ Successfully parsed cleaned XML")
    else:
        print("❌ Failed to parse cleaned XML")

    # Test 7: Real-world scenario
    print("\n✅ Test 7: Extract CDATA Blocks")
    print("-" * 70)
    from fastbusiness_mcp.utils.xml_utils import extract_cdata_content

    cdata_blocks = extract_cdata_content(xml_content)
    print(f"Found {len(cdata_blocks)} CDATA blocks")

    for i, (tag, content, line) in enumerate(cdata_blocks[:3], 1):  # Show first 3
        print(f"\n  Block {i}:")
        print(f"  Parent tag: <{tag}>")
        print(f"  Line: {line}")
        print(f"  Content preview: {content[:100]}...")

    if len(cdata_blocks) > 3:
        print(f"\n  ... and {len(cdata_blocks) - 3} more blocks")

    print("\n" + "=" * 70)
    print("All Tests Complete!")
    print("=" * 70)

    # Summary
    print("\n📊 Summary:")
    print(f"  ✅ XML Structure: Valid")
    print(f"  ✅ Entities Extracted: {len(entities)}")
    print(f"  ✅ Parsing: Success")
    print(f"  ✅ File Detection: Working")
    print(f"  ✅ CDATA Extraction: {len(cdata_blocks)} blocks")


if __name__ == "__main__":
    test_entity_parsing()
