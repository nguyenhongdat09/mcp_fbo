"""XML parsing and manipulation utilities using REGEX only (NO XML libraries)."""

import re
from typing import Optional, Dict, List, Tuple


def extract_cdata_content(xml_content: str) -> List[Tuple[str, str, int]]:
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
    match = re.search(r'<(dir|grid|report|form)\b[^>]*>.*?</\1>', xml_content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0)

    return None


def extract_entity_mappings(xml_content: str) -> Dict[str, str]:
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


def extract_tag_content(xml_content: str, tag_name: str) -> List[str]:
    """
    Extract content of all tags with given name using regex.

    Args:
        xml_content: XML string
        tag_name: Tag name to find

    Returns:
        List of tag contents (including the tag itself)
    """
    pattern = rf'<{tag_name}\b[^>]*>.*?</{tag_name}>'
    matches = re.findall(pattern, xml_content, re.DOTALL | re.IGNORECASE)
    return matches


def extract_tag_attribute(tag_content: str, attr_name: str) -> Optional[str]:
    """
    Extract attribute value from a tag string.

    Args:
        tag_content: Tag string (e.g., '<field name="ma_kh" header="Mã KH"/>')
        attr_name: Attribute name

    Returns:
        Attribute value or None
    """
    # Pattern: attr_name="value" or attr_name='value'
    pattern = rf'{attr_name}\s*=\s*["\']([^"\']*)["\']'
    match = re.search(pattern, tag_content)
    if match:
        return match.group(1)
    return None


def extract_all_tag_attributes(tag_content: str) -> Dict[str, str]:
    """
    Extract all attributes from a tag string.

    Args:
        tag_content: Tag string

    Returns:
        Dictionary of attribute name -> value
    """
    attributes = {}

    # Pattern: name="value" or name='value'
    pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']'

    for match in re.finditer(pattern, tag_content):
        attr_name = match.group(1)
        attr_value = match.group(2)
        attributes[attr_name] = attr_value

    return attributes


def find_elements_by_regex(xml_content: str, pattern: str) -> List[str]:
    """
    Find all XML elements matching a regex pattern.

    Args:
        xml_content: XML string
        pattern: Regex pattern

    Returns:
        List of matching element strings
    """
    matches = re.findall(pattern, xml_content, re.DOTALL | re.IGNORECASE)
    return matches


def find_hardcoded_partitions(sql: str) -> List[Tuple[str, int]]:
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


def is_valid_xml_structure(xml_content: str) -> Tuple[bool, str]:
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
    if not re.search(r'<(dir|grid|report|form)\b', xml_content, re.IGNORECASE):
        return False, "No main element found (dir, grid, report, form)"

    # Try to count opening/closing tags roughly
    opening_tags = len(re.findall(r'<(\w+)[^/>]*(?<!/)>', xml_content))
    closing_tags = len(re.findall(r'</\w+>', xml_content))

    # Allow some mismatch due to ENTITY references and comments
    if abs(opening_tags - closing_tags) > 10:
        return False, f"Tag mismatch: {opening_tags} opening vs {closing_tags} closing"

    return True, "Structure appears valid"


def replace_tag_attribute(xml_content: str, tag_pattern: str, attr_name: str, new_value: str) -> str:
    """
    Replace attribute value in matching tags.

    Args:
        xml_content: XML string
        tag_pattern: Regex pattern to match tags
        attr_name: Attribute name to replace
        new_value: New attribute value

    Returns:
        XML string with replaced attributes
    """
    def replace_attr(match):
        tag_content = match.group(0)
        # Replace attribute value
        attr_pattern = rf'{attr_name}\s*=\s*["\']([^"\']*)["\']'
        replaced = re.sub(attr_pattern, f'{attr_name}="{new_value}"', tag_content)
        return replaced

    return re.sub(tag_pattern, replace_attr, xml_content, flags=re.DOTALL | re.IGNORECASE)
