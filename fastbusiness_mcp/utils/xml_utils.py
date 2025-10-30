"""XML parsing and manipulation utilities."""

import re
from typing import Optional
from lxml import etree


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


def parse_xml_safe(xml_content: str) -> Optional[etree._Element]:
    """
    Safely parse XML content, handling common issues.

    Args:
        xml_content: XML string

    Returns:
        Parsed XML element or None if parsing fails
    """
    try:
        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(xml_content.encode("utf-8"), parser)
        return root
    except Exception:
        return None


def get_element_text(element: etree._Element, xpath: str, default: str = "") -> str:
    """
    Safely get text content from XML element using XPath.

    Args:
        element: XML element
        xpath: XPath expression
        default: Default value if not found

    Returns:
        Text content or default
    """
    try:
        result = element.xpath(xpath)
        if result and isinstance(result[0], str):
            return result[0]
        elif result and hasattr(result[0], "text"):
            return result[0].text or default
        return default
    except Exception:
        return default


def get_attribute(element: etree._Element, attr: str, default: str = "") -> str:
    """
    Safely get attribute value from XML element.

    Args:
        element: XML element
        attr: Attribute name
        default: Default value if not found

    Returns:
        Attribute value or default
    """
    return element.get(attr, default)


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
