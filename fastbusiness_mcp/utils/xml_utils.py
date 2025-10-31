"""XML parsing and manipulation utilities with robust entity handling."""

import re
from typing import Optional, Union
from lxml import etree
import xml.etree.ElementTree as ET


def extract_cdata_content(xml_content: str) -> list[tuple[str, str, int]]:
    """
    Extract CDATA sections from XML content.

    Args:
        xml_content: XML string

    Returns:
        List of tuples (parent_tag, cdata_content, line_number)
    """
    cdata_blocks = []
    lines = xml_content.split("\n")

    current_tag = None
    in_cdata = False
    cdata_content = []
    cdata_start_line = 0

    for line_num, line in enumerate(lines, 1):
        # Detect parent tag before CDATA
        tag_match = re.search(r"<(command|script|action|query|text)\b", line)
        if tag_match:
            current_tag = tag_match.group(1)

        # Detect CDATA start
        if "<![CDATA[" in line:
            in_cdata = True
            cdata_start_line = line_num
            # Extract content after CDATA start on same line
            after_cdata = line.split("<![CDATA[", 1)[1]
            if "]]>" not in after_cdata:
                cdata_content.append(after_cdata)
            else:
                # CDATA ends on same line
                content = after_cdata.split("]]>", 1)[0]
                cdata_blocks.append((current_tag or "unknown", content, cdata_start_line))
                in_cdata = False
            continue

        # Collect CDATA content
        if in_cdata:
            if "]]>" in line:
                # CDATA ends
                content = line.split("]]>", 1)[0]
                cdata_content.append(content)
                full_content = "\n".join(cdata_content)
                cdata_blocks.append((current_tag or "unknown", full_content, cdata_start_line))
                cdata_content = []
                in_cdata = False
            else:
                cdata_content.append(line)

    return cdata_blocks


def parse_xml_safe(xml_content: str, remove_entities: bool = True) -> Optional[etree._Element]:
    """
    Safely parse XML content with multiple fallback strategies.

    This handles FastBusiness XML files with many ENTITY declarations.

    Args:
        xml_content: XML string
        remove_entities: Whether to remove ENTITY declarations before parsing

    Returns:
        Parsed XML element or None if parsing fails
    """
    # Strategy 1: Try with entity removal (fastest for FastBusiness files)
    if remove_entities:
        try:
            cleaned_xml = remove_entity_declarations(xml_content)
            parser = etree.XMLParser(
                recover=True,
                remove_blank_text=True,
                resolve_entities=False,
                no_network=True
            )
            root = etree.fromstring(cleaned_xml.encode("utf-8"), parser)
            return root
        except Exception:
            pass

    # Strategy 2: Try lxml with recovery mode
    try:
        parser = etree.XMLParser(
            recover=True,
            remove_blank_text=True,
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
            dtd_validation=False
        )
        root = etree.fromstring(xml_content.encode("utf-8"), parser)
        return root
    except Exception:
        pass

    # Strategy 3: Try built-in ElementTree (more lenient)
    try:
        # Remove DOCTYPE and ENTITY for ElementTree
        cleaned = remove_doctype_and_entities(xml_content)
        root = ET.fromstring(cleaned)
        # Convert to lxml element for compatibility
        return etree.fromstring(ET.tostring(root, encoding="unicode").encode("utf-8"))
    except Exception:
        pass

    # Strategy 4: Parse only the main element without DOCTYPE
    try:
        # Extract main element (skip DOCTYPE)
        main_element = extract_main_element(xml_content)
        if main_element:
            parser = etree.XMLParser(recover=True, resolve_entities=False)
            root = etree.fromstring(main_element.encode("utf-8"), parser)
            return root
    except Exception:
        pass

    return None


def remove_entity_declarations(xml_content: str) -> str:
    """
    Remove ENTITY declarations from XML but keep the main content.

    Args:
        xml_content: XML string with ENTITY declarations

    Returns:
        XML string without ENTITY declarations
    """
    # Remove entire DOCTYPE declaration including ENTITY declarations
    pattern = r'<!DOCTYPE\s+\w+\s*\[.*?\]>'
    cleaned = re.sub(pattern, '', xml_content, flags=re.DOTALL)

    # Also remove standalone ENTITY declarations
    entity_pattern = r'<!ENTITY\s+\w+\s+.*?>'
    cleaned = re.sub(entity_pattern, '', cleaned, flags=re.DOTALL)

    return cleaned


def remove_doctype_and_entities(xml_content: str) -> str:
    """
    Remove DOCTYPE and all ENTITY declarations completely.

    Args:
        xml_content: XML string

    Returns:
        Clean XML without DOCTYPE/ENTITY
    """
    # Remove XML declaration
    cleaned = re.sub(r'<\?xml[^>]*\?>', '', xml_content)

    # Remove DOCTYPE with all its content
    cleaned = re.sub(r'<!DOCTYPE[^>]*(?:\[.*?\])?>', '', cleaned, flags=re.DOTALL)

    # Remove comments with ENTITY references
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)

    return cleaned.strip()


def extract_main_element(xml_content: str) -> Optional[str]:
    """
    Extract the main XML element, skipping DOCTYPE and declarations.

    Args:
        xml_content: Full XML content

    Returns:
        Main element XML or None
    """
    # Find the main element start (dir, grid, report, etc.)
    match = re.search(r'<(dir|grid|report|form)\b[^>]*>.*?</\1>', xml_content, re.DOTALL)
    if match:
        return match.group(0)

    return None


def parse_xml_tolerant(xml_content: str) -> Optional[etree._Element]:
    """
    Parse XML with maximum tolerance for FastBusiness files.

    This is specifically designed for FastBusiness XML with:
    - Multiple ENTITY declarations
    - SYSTEM references
    - Complex DOCTYPE
    - Nested structures

    Args:
        xml_content: XML string

    Returns:
        Parsed XML element or None
    """
    # First, try to extract entity mappings for later reference
    entities = extract_entity_mappings(xml_content)

    # Clean and parse
    cleaned = remove_entity_declarations(xml_content)

    # Try parsing with various strategies
    for strategy in [
        # Strategy 1: lxml with full recovery
        lambda: _parse_lxml_full_recovery(cleaned),
        # Strategy 2: lxml without DOCTYPE
        lambda: _parse_lxml_no_doctype(xml_content),
        # Strategy 3: Standard library
        lambda: _parse_stdlib(cleaned),
        # Strategy 4: Main element only
        lambda: _parse_main_element_only(xml_content),
    ]:
        try:
            result = strategy()
            if result is not None:
                return result
        except Exception:
            continue

    return None


def _parse_lxml_full_recovery(xml_content: str) -> Optional[etree._Element]:
    """Parse with lxml full recovery mode."""
    parser = etree.XMLParser(
        recover=True,
        remove_blank_text=True,
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=True
    )
    return etree.fromstring(xml_content.encode("utf-8"), parser)


def _parse_lxml_no_doctype(xml_content: str) -> Optional[etree._Element]:
    """Parse after removing DOCTYPE."""
    cleaned = remove_doctype_and_entities(xml_content)
    parser = etree.XMLParser(recover=True, resolve_entities=False)
    return etree.fromstring(cleaned.encode("utf-8"), parser)


def _parse_stdlib(xml_content: str) -> Optional[etree._Element]:
    """Parse with standard library then convert to lxml."""
    root = ET.fromstring(xml_content)
    xml_str = ET.tostring(root, encoding="unicode")
    return etree.fromstring(xml_str.encode("utf-8"))


def _parse_main_element_only(xml_content: str) -> Optional[etree._Element]:
    """Parse only main element."""
    main = extract_main_element(xml_content)
    if main:
        parser = etree.XMLParser(recover=True, resolve_entities=False)
        return etree.fromstring(main.encode("utf-8"), parser)
    return None


def extract_entity_mappings(xml_content: str) -> dict[str, str]:
    """
    Extract ENTITY declarations for reference.

    Args:
        xml_content: XML string

    Returns:
        Dictionary of entity name -> value/path
    """
    entities = {}

    # Pattern: <!ENTITY name "value"> or <!ENTITY name SYSTEM "path">
    pattern = r'<!ENTITY\s+(\w+)\s+(?:SYSTEM\s+)?["\']([^"\']+)["\']'

    for match in re.finditer(pattern, xml_content):
        entity_name = match.group(1)
        entity_value = match.group(2)
        entities[entity_name] = entity_value

    return entities


def get_element_text(element: Union[etree._Element, ET.Element], xpath: str, default: str = "") -> str:
    """
    Safely get text content from XML element using XPath.

    Compatible with both lxml and standard library elements.

    Args:
        element: XML element (lxml or stdlib)
        xpath: XPath expression
        default: Default value if not found

    Returns:
        Text content or default
    """
    try:
        if isinstance(element, etree._Element):
            # lxml element
            result = element.xpath(xpath)
            if result and isinstance(result[0], str):
                return result[0]
            elif result and hasattr(result[0], "text"):
                return result[0].text or default
        else:
            # Standard library element - use find
            elem = element.find(xpath.replace('//', './').replace('/', './'))
            if elem is not None and elem.text:
                return elem.text
        return default
    except Exception:
        return default


def get_attribute(element: Union[etree._Element, ET.Element], attr: str, default: str = "") -> str:
    """
    Safely get attribute value from XML element.

    Compatible with both lxml and standard library elements.

    Args:
        element: XML element
        attr: Attribute name
        default: Default value if not found

    Returns:
        Attribute value or default
    """
    try:
        return element.get(attr, default)
    except Exception:
        return default


def find_hardcoded_partitions(sql: str) -> list[tuple[str, int]]:
    """
    Find hardcoded partition tables in SQL.

    Args:
        sql: SQL string

    Returns:
        List of (table_name, line_number) tuples
    """
    pattern = re.compile(r"\b([a-z]\d{2})\$(\d{6})\b", re.IGNORECASE)
    findings = []

    for line_num, line in enumerate(sql.split("\n"), 1):
        matches = pattern.finditer(line)
        for match in matches:
            findings.append((match.group(0), line_num))

    return findings


def is_valid_xml_structure(xml_content: str) -> tuple[bool, str]:
    """
    Check if XML has valid basic structure.

    Args:
        xml_content: XML string

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for basic XML structure
    if not xml_content.strip():
        return False, "Empty XML content"

    # Check for main element
    if not re.search(r'<(dir|grid|report|form)\b', xml_content):
        return False, "No main element found (dir, grid, report, form)"

    # Try to count opening/closing tags roughly
    opening_tags = len(re.findall(r'<(\w+)[^/>]*(?<!/)>', xml_content))
    closing_tags = len(re.findall(r'</\w+>', xml_content))

    # Allow some mismatch due to ENTITY references and comments
    if abs(opening_tags - closing_tags) > 10:
        return False, f"Tag mismatch: {opening_tags} opening vs {closing_tags} closing"

    return True, "Structure appears valid"
