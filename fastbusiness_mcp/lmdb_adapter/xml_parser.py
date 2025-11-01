"""FastBusiness XML Parser for Field Definitions using REGEX ONLY

This module parses FastBusiness XML files to extract field definitions
for storage in LMDB database - using PURE REGEX, NO XML libraries.
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
            {
                'DIR': [{'field_name': 'ma_kh', 'definition': {...}}, ...],
                'FILTER_VOUCHER': [...],
                ...
            }
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

            # Clean XML (remove DOCTYPE, ENTITY, XInclude)
            xml_content = self._clean_xml(xml_content)

            # Extract fields by context type
            results = {}
            total_fields = 0

            for context_type in self.CONTEXT_TYPES:
                fields = self._extract_fields_regex(xml_content, context_type)
                if fields:
                    results[context_type] = fields
                    total_fields += len(fields)
                    logger.info(f"  {context_type}: {len(fields)} fields")

            self.stats['files_parsed'] += 1
            self.stats['fields_extracted'] += total_fields

            logger.info(f"✓ Parsed {xml_path.name}: {total_fields} fields")
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

    def _extract_fields_regex(self, xml_content: str, context_type: str) -> List[Dict]:
        """
        Extract field definitions from specific context type using REGEX

        Args:
            xml_content: Cleaned XML content
            context_type: Context type (DIR, FILTER_VOUCHER, etc.)

        Returns:
            List of field definitions
        """
        fields = []

        # Define regex patterns for each context type
        if context_type == 'DIR':
            # Find <DIR>...</DIR> section
            dir_match = re.search(r'<DIR\b[^>]*>(.*?)</DIR>', xml_content, re.DOTALL | re.IGNORECASE)
            if dir_match:
                section_content = dir_match.group(1)
                fields = self._extract_field_elements(section_content)

        elif context_type == 'FILTER_VOUCHER':
            # Find <FILTER type="VOUCHER">...</FILTER> section
            filter_match = re.search(r'<FILTER\s+type\s*=\s*["\']VOUCHER["\'][^>]*>(.*?)</FILTER>', xml_content, re.DOTALL | re.IGNORECASE)
            if filter_match:
                section_content = filter_match.group(1)
                fields = self._extract_field_elements(section_content)

        elif context_type == 'FILTER_NORMAL':
            # Find <FILTER type="NORMAL">...</FILTER> section
            filter_match = re.search(r'<FILTER\s+type\s*=\s*["\']NORMAL["\'][^>]*>(.*?)</FILTER>', xml_content, re.DOTALL | re.IGNORECASE)
            if filter_match:
                section_content = filter_match.group(1)
                fields = self._extract_field_elements(section_content)

        elif context_type == 'GRID_VIEW':
            # Find <GRID_VIEW>...</GRID_VIEW> section
            grid_match = re.search(r'<GRID_VIEW\b[^>]*>(.*?)</GRID_VIEW>', xml_content, re.DOTALL | re.IGNORECASE)
            if grid_match:
                section_content = grid_match.group(1)
                fields = self._extract_field_elements(section_content)

        elif context_type == 'GRID_INPUT':
            # Find <GRID_INPUT>...</GRID_INPUT> section
            grid_match = re.search(r'<GRID_INPUT\b[^>]*>(.*?)</GRID_INPUT>', xml_content, re.DOTALL | re.IGNORECASE)
            if grid_match:
                section_content = grid_match.group(1)
                fields = self._extract_field_elements(section_content)

        return fields

    def _extract_field_elements(self, section_content: str) -> List[Dict]:
        """
        Extract individual field elements from a section

        Args:
            section_content: Content of a section (DIR, FILTER, GRID, etc.)

        Returns:
            List of field definitions
        """
        fields = []

        # Pattern to match field tags (self-closing or with closing tag)
        # Matches: <field .../>  or  <field ...>...</field>
        # Also matches variations: <Field>, <FIELD>, <column>, <item>
        field_patterns = [
            r'<field\b([^>]*?)/>',  # Self-closing <field ... />
            r'<field\b([^>]*?)>(.*?)</field>',  # With closing tag <field>...</field>
            r'<column\b([^>]*?)/>',  # Alternative: <column />
            r'<column\b([^>]*?)>(.*?)</column>',  # <column>...</column>
            r'<item\b([^>]*?)/>',  # Alternative: <item />
            r'<item\b([^>]*?)>(.*?)</item>',  # <item>...</item>
        ]

        for pattern in field_patterns:
            for match in re.finditer(pattern, section_content, re.DOTALL | re.IGNORECASE):
                attributes_str = match.group(1)

                # Extract attributes from the attributes string
                attributes = self._extract_attributes(attributes_str)

                # Get field name from 'field' or 'name' attribute
                field_name = attributes.get('field') or attributes.get('name')

                if not field_name:
                    continue  # Skip if no field name

                # Get the full tag content (for XML storage)
                full_tag = match.group(0)

                # Build field definition
                definition = {
                    'field_name': field_name,
                    'attributes': attributes,
                    'xml': full_tag
                }

                # Extract common attributes to top level
                if 'header' in attributes:
                    definition['header'] = attributes['header']
                if 'type' in attributes:
                    definition['type'] = attributes['type']
                if 'width' in attributes:
                    definition['width'] = attributes['width']

                fields.append({
                    'field_name': field_name,
                    'definition': definition
                })

        return fields

    def _extract_attributes(self, attributes_str: str) -> Dict[str, str]:
        """
        Extract all attributes from an attributes string

        Args:
            attributes_str: String containing attributes (e.g., 'field="ma_kh" header="Mã KH"')

        Returns:
            Dictionary of attribute name -> value
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
            {
                'DIR': [field1, field2, ...],
                'FILTER_VOUCHER': [...],
                ...
            }
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
