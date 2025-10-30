"""Scan FastBusiness project and populate field registry."""

import asyncio
import sys
from pathlib import Path
from lxml import etree

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastbusiness_mcp.database.db_manager import DatabaseManager
from fastbusiness_mcp.database.field_repository import FieldRepository
from fastbusiness_mcp.core.models import FieldDefinition
from fastbusiness_mcp.utils.file_utils import find_xml_files, read_file
from fastbusiness_mcp.utils.xml_utils import parse_xml_safe, get_attribute
from fastbusiness_mcp.utils.logger import setup_logger

logger = setup_logger(__name__)


async def scan_project(project_path: str, db_path: str = "data/fields.db"):
    """
    Scan project directory and extract field definitions.

    Args:
        project_path: Path to FastBusiness project
        db_path: Path to database
    """
    db = DatabaseManager(db_path)

    try:
        await db.connect()
        await db.initialize_schema()
        repo = FieldRepository(db)

        # Find all XML files
        xml_files = find_xml_files(project_path)
        logger.info(f"Found {len(xml_files)} XML files")

        total_fields = 0

        for xml_file in xml_files:
            try:
                content = read_file(xml_file)
                if not content:
                    continue

                # Parse XML
                root = parse_xml_safe(content)
                if root is None:
                    continue

                # Extract controller name from file path
                file_name = Path(xml_file).stem
                controller = file_name

                # Find all fields
                for field_elem in root.findall(".//field"):
                    field_name = get_attribute(field_elem, "name")
                    if not field_name:
                        continue

                    # Extract field attributes
                    field = FieldDefinition(
                        name=field_name,
                        type=get_attribute(field_elem, "type", "String"),
                        width=int(w) if (w := get_attribute(field_elem, "width")) else None,
                        align=get_attribute(field_elem, "align"),
                        allow_nulls=get_attribute(field_elem, "allowNulls") != "false",
                        read_only=get_attribute(field_elem, "readOnly") == "true",
                        hidden=get_attribute(field_elem, "hidden") == "true",
                        external=get_attribute(field_elem, "external") == "true",
                    )

                    # Check for header
                    header_elem = field_elem.find("header")
                    if header_elem is not None:
                        field.header_vi = get_attribute(header_elem, "v", "")
                        field.header_en = get_attribute(header_elem, "e", "")

                    # Check for lookup
                    items_elem = field_elem.find("items")
                    if items_elem is not None:
                        style = get_attribute(items_elem, "style")
                        if style == "AutoComplete":
                            field.is_lookup = True
                            field.lookup_controller = get_attribute(items_elem, "controller")
                            field.lookup_reference = get_attribute(items_elem, "reference")

                    # Add to database
                    await repo.add_field(field, xml_file, controller)
                    total_fields += 1

                logger.info(f"Processed: {xml_file}")

            except Exception as e:
                logger.error(f"Error processing {xml_file}: {e}")

        logger.info(f"✅ Scan complete: {total_fields} fields extracted")

    except Exception as e:
        logger.error(f"❌ Scan failed: {e}")
        sys.exit(1)
    finally:
        await db.disconnect()


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scan_project.py <project_path>")
        sys.exit(1)

    project_path = sys.argv[1]

    if not Path(project_path).exists():
        logger.error(f"Project path not found: {project_path}")
        sys.exit(1)

    await scan_project(project_path)


if __name__ == "__main__":
    asyncio.run(main())
