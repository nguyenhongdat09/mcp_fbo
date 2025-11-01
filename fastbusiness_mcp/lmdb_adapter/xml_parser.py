"""FastBusiness XML Parser for Field Definitions

This module parses FastBusiness XML files to extract field definitions
for storage in LMDB database.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from lxml import etree

logger = logging.getLogger(__name__)


class FastBusinessXMLParser:
    """Parser for FastBusiness XML files to extract field definitions"""

    # Context types to extract from XML
    CONTEXT_TYPES = ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']

    # XPath patterns for finding fields in different contexts
    FIELD_XPATHS = {
        'DIR': './/DIR//field',
        'FILTER_VOUCHER': './/FILTER[@type="VOUCHER"]//field',
        'FILTER_NORMAL': './/FILTER[@type="NORMAL"]//field',
        'GRID_VIEW': './/GRID_VIEW//field',
        'GRID_INPUT': './/GRID_INPUT//field',
    }

    def __init__(self):
        """Initialize XML parser"""
        self.stats = {
            'files_parsed': 0,
            'fields_extracted': 0,
            'errors': 0
        }

    def parse_file(self, xml_path: str) -> Dict[str, List[Dict]]:
        """
        Parse XML file and extract field definitions

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
            # Parse XML file with XInclude disabled to avoid external file errors
            parser = etree.XMLParser(
                load_dtd=False,
                no_network=True,
                resolve_entities=False,
                remove_blank_text=True
            )
            tree = etree.parse(str(xml_path), parser)
            root = tree.getroot()

            # Extract fields by context type
            results = {}
            total_fields = 0

            for context_type in self.CONTEXT_TYPES:
                fields = self._extract_fields(root, context_type)
                if fields:
                    results[context_type] = fields
                    total_fields += len(fields)
                    logger.info(f"  {context_type}: {len(fields)} fields")

            self.stats['files_parsed'] += 1
            self.stats['fields_extracted'] += total_fields

            logger.info(f"✓ Parsed {xml_path.name}: {total_fields} fields")
            return results

        except etree.XMLSyntaxError as e:
            logger.error(f"XML syntax error in {xml_path}: {e}")
            self.stats['errors'] += 1
            return {}
        except Exception as e:
            logger.error(f"Error parsing {xml_path}: {e}")
            self.stats['errors'] += 1
            return {}

    def _extract_fields(self, root: etree.Element, context_type: str) -> List[Dict]:
        """
        Extract field definitions from specific context type

        Args:
            root: XML root element
            context_type: Context type (DIR, FILTER_VOUCHER, etc.)

        Returns:
            List of field definitions
        """
        xpath = self.FIELD_XPATHS.get(context_type)
        if not xpath:
            return []

        fields = []
        field_elements = root.xpath(xpath)

        for field_elem in field_elements:
            field_def = self._parse_field_element(field_elem)
            if field_def:
                fields.append(field_def)

        return fields

    def _parse_field_element(self, elem: etree.Element) -> Optional[Dict]:
        """
        Parse a single field element into a field definition

        Args:
            elem: Field XML element

        Returns:
            Field definition dict with 'field_name' and 'definition' keys
        """
        # Get field name from 'field' attribute
        field_name = elem.get('field')
        if not field_name:
            logger.warning(f"Field element missing 'field' attribute: {etree.tostring(elem, encoding='unicode')[:100]}")
            return None

        # Extract all attributes
        attributes = dict(elem.attrib)

        # Extract child elements
        children = {}
        for child in elem:
            tag = child.tag
            # Handle multiple children with same tag
            if tag in children:
                if not isinstance(children[tag], list):
                    children[tag] = [children[tag]]
                children[tag].append(self._element_to_dict(child))
            else:
                children[tag] = self._element_to_dict(child)

        # Build field definition
        definition = {
            'field_name': field_name,
            'attributes': attributes,
            'children': children if children else None,
            'xml': etree.tostring(elem, encoding='unicode', pretty_print=True)
        }

        # Extract common attributes to top level for easier access
        if 'header' in attributes:
            definition['header'] = attributes['header']
        if 'type' in attributes:
            definition['type'] = attributes['type']
        if 'width' in attributes:
            definition['width'] = attributes['width']

        return {
            'field_name': field_name,
            'definition': definition
        }

    def _element_to_dict(self, elem: etree.Element) -> Dict:
        """
        Convert XML element to dictionary

        Args:
            elem: XML element

        Returns:
            Dictionary representation
        """
        result = {}

        # Add attributes
        if elem.attrib:
            result['@attributes'] = dict(elem.attrib)

        # Add text content
        if elem.text and elem.text.strip():
            result['@text'] = elem.text.strip()

        # Add children
        for child in elem:
            tag = child.tag
            child_dict = self._element_to_dict(child)

            if tag in result:
                # Multiple children with same tag → make it a list
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_dict)
            else:
                result[tag] = child_dict

        return result

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
