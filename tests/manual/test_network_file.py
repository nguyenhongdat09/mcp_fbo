"""Test reading and parsing XML file from network share."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastbusiness_mcp.utils.xml_utils import (
    parse_xml_safe,
    parse_xml_tolerant,
    extract_entity_mappings,
    is_valid_xml_structure,
    extract_cdata_content
)
from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector
from fastbusiness_mcp.validators.partition_validator import PartitionValidator
from fastbusiness_mcp.validators.result_access_validator import ResultAccessValidator


def read_file_safe(file_path: str) -> tuple[bool, str, str]:
    """
    Safely read file with multiple encoding attempts.

    Returns:
        Tuple of (success, content, error_message)
    """
    encodings = ['utf-8', 'utf-16', 'utf-8-sig', 'latin-1', 'cp1252']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                return True, content, f"Successfully read with {encoding}"
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            return False, "", f"File not found: {file_path}"
        except PermissionError:
            return False, "", f"Permission denied: {file_path}"
        except Exception as e:
            return False, "", f"Error reading file: {e}"

    return False, "", "Could not read file with any encoding"


def test_network_xml_file(file_path: str):
    """
    Test reading and parsing XML file from network share.

    Args:
        file_path: Path to XML file (can be network UNC path)
    """
    print("=" * 80)
    print("FastBusiness XML File Analyzer")
    print("=" * 80)
    print(f"\nFile: {file_path}\n")

    # Step 1: Read file
    print("🔍 Step 1: Reading file...")
    print("-" * 80)

    success, xml_content, message = read_file_safe(file_path)

    if not success:
        print(f"❌ Failed to read file: {message}")
        return

    print(f"✅ {message}")
    print(f"File size: {len(xml_content):,} characters")
    print(f"Lines: {len(xml_content.splitlines()):,}")

    # Step 2: Validate structure
    print("\n🔍 Step 2: Validating XML structure...")
    print("-" * 80)

    is_valid, validation_msg = is_valid_xml_structure(xml_content)
    print(f"Structure: {'✅ Valid' if is_valid else '❌ Invalid'}")
    print(f"Message: {validation_msg}")

    # Step 3: Extract ENTITY declarations
    print("\n🔍 Step 3: Extracting ENTITY declarations...")
    print("-" * 80)

    entities = extract_entity_mappings(xml_content)
    print(f"Found {len(entities)} ENTITY declarations")

    if entities:
        print("\nEntity mappings:")
        for i, (name, value) in enumerate(list(entities.items())[:10], 1):
            print(f"  {i}. &{name}; → {value}")
        if len(entities) > 10:
            print(f"  ... and {len(entities) - 10} more")

    # Step 4: Parse XML
    print("\n🔍 Step 4: Parsing XML...")
    print("-" * 80)

    # Try parse_xml_safe first
    root = parse_xml_safe(xml_content)

    if root is None:
        print("⚠️  parse_xml_safe failed, trying parse_xml_tolerant...")
        root = parse_xml_tolerant(xml_content)

    if root is not None:
        print("✅ Successfully parsed XML!")
        print(f"Root tag: <{root.tag}>")
        print(f"Attributes: {dict(root.attrib)}")

        # Count elements
        fields = root.findall(".//field")
        commands = root.findall(".//command")
        actions = root.findall(".//action")

        print(f"\nElements found:")
        print(f"  - Fields: {len(fields)}")
        print(f"  - Commands: {len(commands)}")
        print(f"  - Actions: {len(actions)}")

    else:
        print("❌ Failed to parse XML with all strategies")
        print("   Please check the XML file for syntax errors")
        return

    # Step 5: Detect file type
    print("\n🔍 Step 5: Detecting file type...")
    print("-" * 80)

    try:
        detector = FileTypeDetector()
        context = detector.detect(xml_content)

        print(f"File type: {context.file_type.value}")
        print(f"Table: {context.table_name or 'N/A'}")
        print(f"Has partition: {context.has_partition}")
        print(f"Partition field: {context.partition_field or 'N/A'}")
        print(f"Events: {', '.join([e.value for e in context.events]) or 'None'}")

    except Exception as e:
        print(f"❌ File type detection failed: {e}")

    # Step 6: Extract and validate CDATA blocks
    print("\n🔍 Step 6: Extracting CDATA blocks...")
    print("-" * 80)

    cdata_blocks = extract_cdata_content(xml_content)
    print(f"Found {len(cdata_blocks)} CDATA blocks")

    if cdata_blocks:
        # Validate partition usage in SQL
        partition_validator = PartitionValidator()
        result_validator = ResultAccessValidator()

        partition_errors = 0
        result_errors = 0

        print("\nValidating CDATA content...")

        for i, (tag, content, line) in enumerate(cdata_blocks, 1):
            # Check if it's SQL (in command/action/query)
            if tag in ['command', 'action', 'query']:
                # Validate partition
                result = partition_validator.validate(content)
                if not result.is_valid:
                    partition_errors += len(result.errors)
                    print(f"\n  ⚠️  CDATA Block {i} (line {line}, <{tag}>):")
                    for error in result.errors[:3]:  # Show first 3 errors
                        print(f"     ❌ {error.message}")
                        print(f"        💡 {error.suggestion}")

            # Check if it's JavaScript (in script)
            elif tag in ['script', 'text']:
                # Check for result access issues
                result = result_validator.validate(content, None)
                if not result.is_valid:
                    result_errors += len(result.errors)
                    print(f"\n  ⚠️  CDATA Block {i} (line {line}, <{tag}>):")
                    for error in result.errors[:3]:  # Show first 3 errors
                        print(f"     ❌ {error.message}")
                        print(f"        💡 {error.suggestion}")

        print(f"\nValidation Summary:")
        print(f"  - Partition issues: {partition_errors}")
        print(f"  - Result access issues: {result_errors}")

        if partition_errors == 0 and result_errors == 0:
            print(f"  ✅ No critical issues found!")

    # Step 7: Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    print(f"""
File Information:
  ✅ Path: {file_path}
  ✅ Size: {len(xml_content):,} characters
  ✅ Lines: {len(xml_content.splitlines()):,}
  ✅ Encoding: Detected automatically

Structure:
  ✅ Valid XML: {is_valid}
  ✅ ENTITY declarations: {len(entities)}
  ✅ Parsed successfully: {'Yes' if root is not None else 'No'}

Content:
  ✅ File type: {context.file_type.value if root else 'Unknown'}
  ✅ Fields: {len(fields) if root else 0}
  ✅ Commands: {len(commands) if root else 0}
  ✅ CDATA blocks: {len(cdata_blocks)}

Validation:
  {'✅' if partition_errors == 0 else '⚠️ '} Partition issues: {partition_errors if cdata_blocks else 'N/A'}
  {'✅' if result_errors == 0 else '⚠️ '} Result access issues: {result_errors if cdata_blocks else 'N/A'}
    """)

    if root is not None and partition_errors == 0 and result_errors == 0:
        print("🎉 File is valid and ready to use!")
    elif root is not None:
        print("⚠️  File parsed successfully but has some validation warnings")
    else:
        print("❌ File has parsing errors that need to be fixed")

    print("=" * 80)


def main():
    """Main entry point."""
    # Default file path
    default_path = r"\\172.168.5.14\CustomerPro\FBI\TMSG\FBISP242\App_Data\Controllers\Dir\SATran.xml"

    # Get file path from command line or use default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = default_path
        print(f"Using default file path: {file_path}")
        print(f"(You can specify a different path: python {sys.argv[0]} <path>)\n")

    test_network_xml_file(file_path)


if __name__ == "__main__":
    main()
