"""FastBusiness XML Parser for Field Definitions using REGEX ONLY

This module parses FastBusiness XML files to extract field definitions
for storage in LMDB database - using PURE REGEX, NO XML libraries.

Simple logic:
1. Extract ALL <field> tags using regex (don't care about sections)
2. Classify by folder path + attribute checks
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FastBusinessXMLParser:
    """Parser for FastBusiness XML files to extract field definitions using REGEX"""

    # Context types to extract from XML
    CONTEXT_TYPES = ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']

    def __init__(self):
        """Initialize XML parser"""
        self.stats = {
            'files_parsed': 0,
            'fields_extracted': 0,
            'errors': 0
        }

    def parse_file(self, xml_path: str) -> Dict[str, List[Dict]]:
        """
        Parse XML file and extract field definitions using REGEX

        Args:
            xml_path: Path to XML file

        Returns:
            Dict mapping context_type → list of field definitions
        """
        xml_path = Path(xml_path)
        if not xml_path.exists():
            logger.error(f"File not found: {xml_path}")
            self.stats['errors'] += 1
            return {}

        try:
            # Read file content
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            # Clean XML (remove DOCTYPE, ENTITY, XInclude, Comments)
            xml_content = self._clean_xml(xml_content)

            # Determine context type by folder path
            context_type = self._determine_context_type(str(xml_path), xml_content)

            if context_type == 'UNKNOWN':
                logger.warning(f"Cannot determine context type for {xml_path.name}")
                return {}

            # Extract ALL <field> tags using regex (simple!)
            fields = self._extract_all_field_tags(xml_content)

            if not fields:
                logger.info(f"✓ Parsed {xml_path.name}: 0 fields")
                return {}

            # Return results
            results = {context_type: fields}

            self.stats['files_parsed'] += 1
            self.stats['fields_extracted'] += len(fields)

            logger.info(f"✓ Parsed {xml_path.name}: {len(fields)} fields")
            logger.info(f"  {context_type}: {len(fields)} fields")

            return results

        except Exception as e:
            logger.error(f"Error parsing {xml_path}: {e}")
            self.stats['errors'] += 1
            return {}

    def _clean_xml(self, xml_content: str) -> str:
        """
        Clean XML content by removing problematic parts

        Args:
            xml_content: Raw XML content

        Returns:
            Cleaned XML content
        """
        # Remove XML declaration
        cleaned = re.sub(r'<\?xml[^>]*\?>', '', xml_content)

        # Remove DOCTYPE with all its content (including ENTITY declarations)
        cleaned = re.sub(r'<!DOCTYPE[^>]*(?:\[.*?\])?>', '', cleaned, flags=re.DOTALL)

        # Remove ENTITY declarations
        cleaned = re.sub(r'<!ENTITY\s+\w+\s+.*?>', '', cleaned, flags=re.DOTALL)

        # Remove XInclude tags (these cause errors)
        cleaned = re.sub(r'<xi:include[^>]*/?>', '', cleaned, flags=re.IGNORECASE)

        # Remove comments
        cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)

        return cleaned

    def _determine_context_type(self, file_path: str, xml_content: str) -> str:
        """
        Determine context type by folder path + content attributes

        Args:
            file_path: Full file path
            xml_content: XML content

        Returns:
            Context type string
        """
        # Normalize path
        normalized_path = file_path.replace('/', '\\')

        # Extract folder name from path
        if '\\Dir\\' in normalized_path or '\\dir\\' in normalized_path:
            return 'DIR'

        elif '\\Filter\\' in normalized_path or '\\filter\\' in normalized_path:
            # Check if any field has 'operation' attribute
            has_operation = bool(re.search(r'<field[^>]*\boperation\s*=', xml_content, re.IGNORECASE))
            return 'FILTER_VOUCHER' if has_operation else 'FILTER_NORMAL'

        elif '\\Grid\\' in normalized_path or '\\grid\\' in normalized_path:
            # Check if any field has 'allowSorting' or 'allowFilter'
            has_sorting = bool(re.search(r'<field[^>]*\ballowSorting\s*=', xml_content, re.IGNORECASE))
            has_filter = bool(re.search(r'<field[^>]*\ballowFilter\s*=', xml_content, re.IGNORECASE))
            return 'GRID_VIEW' if (has_sorting or has_filter) else 'GRID_INPUT'

        return 'UNKNOWN'

    def _extract_all_field_tags(self, xml_content: str) -> List[Dict]:
        """
        Extract ALL <field> tags from entire XML content using regex

        Simple approach: Find all <field ...>...</field> tags, extract attributes

        Args:
            xml_content: Cleaned XML content

        Returns:
            List of field definitions
        """
        fields = []

        # Pattern to match field tags: <field ...>...</field> or <field ... />
        # Use non-greedy match to avoid matching across multiple fields
        field_pattern = r'<field\b([^>]*?)>(.*?)</field>|<field\b([^>]*?)/>'

        for match in re.finditer(field_pattern, xml_content, re.DOTALL | re.IGNORECASE):
            # Group 1 & 2 = <field ...>...</field>
            # Group 3 = <field ... />
            if match.group(1):  # Non-self-closing tag
                attributes_str = match.group(1)
                field_content = match.group(2)
                full_tag = match.group(0)
            else:  # Self-closing tag
                attributes_str = match.group(3)
                field_content = ""
                full_tag = match.group(0)

            # Extract attributes
            attributes = self._extract_attributes(attributes_str)

            # Get base field name from 'name' or 'field' attribute
            base_field_name = attributes.get('name') or attributes.get('field')

            if not base_field_name:
                continue  # Skip if no field name

            # Detect lookup type from <items style="...">
            lookup_suffix = self._detect_lookup_suffix(field_content)

            # Add suffix to field name based on lookup type
            field_name = base_field_name + lookup_suffix

            # Clean XML: remove unwanted attributes and tags
            cleaned_xml = self._clean_field_xml(full_tag)

            # Build field definition
            definition = {
                'field_name': field_name,
                'attributes': attributes,
                'xml': cleaned_xml
            }

            # Extract header (from attribute or child tag)
            if 'header' in attributes:
                definition['header'] = attributes['header']
            else:
                # Try to extract from <header v="..."> child tag (Grid format)
                header_match = re.search(r'<header[^>]*\bv\s*=\s*["\']([^"\']*)["\']', field_content, re.IGNORECASE)
                if header_match:
                    definition['header'] = header_match.group(1)

            # Extract other common attributes
            if 'type' in attributes:
                definition['type'] = attributes['type']
            if 'width' in attributes:
                definition['width'] = attributes['width']

            fields.append({
                'field_name': field_name,
                'definition': definition
            })

        return fields

    def _detect_lookup_suffix(self, field_content: str) -> str:
        """
        Detect lookup type from <items style="..."> tag and return appropriate suffix

        Args:
            field_content: Content inside <field>...</field>

        Returns:
            Suffix string: 't' for AutoComplete, 'lk' for Lookup, '' for others
        """
        # Check for <items style="AutoComplete">
        if re.search(r'<items[^>]*\bstyle\s*=\s*["\']AutoComplete["\']', field_content, re.IGNORECASE):
            return 't'

        # Check for <items style="Lookup">
        if re.search(r'<items[^>]*\bstyle\s*=\s*["\']Lookup["\']', field_content, re.IGNORECASE):
            return 'lk'

        # No lookup or other style
        return ''

    def _clean_field_xml(self, xml_str: str) -> str:
        """
        Clean field XML by removing unwanted attributes and tags

        Removes:
        - Attributes: allowNulls, isPrimaryKey, hidden, categoryIndex, allowContain, onDemand, aliasName, operation
        - Tags: <clientScript>, <query>

        Args:
            xml_str: Original field XML string

        Returns:
            Cleaned XML string
        """
        cleaned = xml_str

        # Remove unwanted attributes
        unwanted_attrs = [
            'allowNulls', 'isPrimaryKey', 'hidden', 'categoryIndex',
            'allowContain', 'onDemand', 'aliasName', 'operation'
        ]

        for attr in unwanted_attrs:
            # Pattern: attr="value" or attr='value'
            pattern = rf'\s+{attr}\s*=\s*["\'][^"\']*["\']'
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove <clientScript>...</clientScript> tags
        cleaned = re.sub(r'<clientScript\b[^>]*>.*?</clientScript>\s*', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

        # Remove <query>...</query> tags
        cleaned = re.sub(r'<query\b[^>]*>.*?</query>\s*', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

        return cleaned

    def _extract_attributes(self, attributes_str: str) -> Dict[str, str]:
        """
        Extract all attributes from an attributes string

        Args:
            attributes_str: String containing attributes

        Returns:
            Dictionary of attribute name → value
        """
        attributes = {}

        # Pattern: name="value" or name='value'
        pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']'

        for match in re.finditer(pattern, attributes_str):
            attr_name = match.group(1)
            attr_value = match.group(2)
            attributes[attr_name] = attr_value

        return attributes

    def parse_directory(self, dir_path: str, pattern: str = "*.xml") -> Dict[str, List[Dict]]:
        """
        Parse all XML files in a directory

        Args:
            dir_path: Directory path
            pattern: File pattern (default: *.xml)

        Returns:
            Dict mapping context_type → list of ALL field definitions from all files
        """
        dir_path = Path(dir_path)
        if not dir_path.exists():
            logger.error(f"Directory not found: {dir_path}")
            return {}

        # Find all XML files
        xml_files = list(dir_path.glob(pattern))
        if not xml_files:
            logger.warning(f"No XML files found in {dir_path}")
            return {}

        logger.info(f"Found {len(xml_files)} XML files in {dir_path}")

        # Aggregate results across all files
        aggregated = {context: [] for context in self.CONTEXT_TYPES}

        for xml_file in xml_files:
            file_results = self.parse_file(str(xml_file))

            # Merge results
            for context_type, fields in file_results.items():
                aggregated[context_type].extend(fields)

        # Log summary
        logger.info("\n" + "="*60)
        logger.info("Parsing Summary:")
        logger.info(f"  Files processed: {self.stats['files_parsed']}")
        logger.info(f"  Total fields: {self.stats['fields_extracted']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info("="*60)

        for context_type, fields in aggregated.items():
            if fields:
                logger.info(f"  {context_type}: {len(fields)} fields")

        return aggregated

    def get_stats(self) -> Dict:
        """Get parsing statistics"""
        return self.stats.copy()

    def reset_stats(self):
        """Reset parsing statistics"""
        self.stats = {
            'files_parsed': 0,
            'fields_extracted': 0,
            'errors': 0
        }
