"""Smart Pattern Matching for Field Names

This module provides intelligent field name pattern detection and template-based
field generation with automatic substitution of field names and headers.

Uses REGEX ONLY - NO XML libraries.
"""

import re
import logging
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


class FieldPatternMatcher:
    """Smart pattern matching for field names with template substitution"""

    # Pattern definitions: (pattern, template_key, description)
    PATTERNS = [
        (r'^sl_', 'so_luong', 'quantity'),           # sl_* → so_luong
        (r'^ngay_', 'ngay_ct', 'date'),              # ngay_* → ngay_ct
        (r'_nt$', 'tien_nt', 'foreign_currency'),    # *_nt → tien_nt
        (r'^tien', 'tien', 'currency'),              # tien* → tien
    ]

    # Default templates for unknown fields
    DEFAULT_TEMPLATES = ['ghi_chu', 'dien_giai']

    # Lookup type suffixes
    LOOKUP_SUFFIXES = {
        'autocomplete': 't',   # ma_kh + t = ma_khat
        'lookup': 'lk',        # ma_kh + lk = ma_khlk
        'default': ''          # ma_kh (no suffix)
    }

    def __init__(self, lmdb_manager):
        """
        Initialize pattern matcher

        Args:
            lmdb_manager: LMDBManager instance for querying database
        """
        self.lmdb = lmdb_manager

    def detect_pattern(self, field_name: str) -> Optional[Tuple[str, str]]:
        """
        Detect field name pattern and return matching template key

        Args:
            field_name: Field name to analyze (e.g., 'sl_nhap_hang')

        Returns:
            Tuple of (pattern_type, template_key) or None if no pattern matches
            Example: ('quantity', 'so_luong')
        """
        for pattern, template_key, pattern_type in self.PATTERNS:
            if re.search(pattern, field_name):
                logger.info(f"Field '{field_name}' matches pattern '{pattern_type}' → template '{template_key}'")
                return (pattern_type, template_key)

        logger.debug(f"No pattern match for '{field_name}'")
        return None

    def add_lookup_suffix(self, field_name: str, lookup_type: str) -> str:
        """
        Add appropriate suffix for lookup type

        Args:
            field_name: Base field name (e.g., 'ma_kh')
            lookup_type: 'autocomplete', 'lookup', or 'default'

        Returns:
            Field name with suffix (e.g., 'ma_khat', 'ma_khlk', 'ma_kh')
        """
        suffix = self.LOOKUP_SUFFIXES.get(lookup_type, '')
        if suffix:
            logger.info(f"Adding {lookup_type} suffix: {field_name} → {field_name}{suffix}")
            return f"{field_name}{suffix}"
        return field_name

    def get_field_with_fallback(self, context_type: str, field_name: str,
                                lookup_type: str = 'default') -> Optional[Dict]:
        """
        Get field definition with smart fallback to pattern-based templates

        Search strategy:
        1. Try exact match with lookup suffix (if specified)
        2. Try pattern-based template lookup
        3. Try default text templates (ghi_chu, dien_giai)

        Args:
            context_type: Context type (DIR, FILTER_VOUCHER, etc.)
            field_name: Field name to search
            lookup_type: 'autocomplete', 'lookup', or 'default'

        Returns:
            Field definition dict with substituted field name and header
        """
        # Step 1: Try exact match with lookup suffix
        full_field_name = self.add_lookup_suffix(field_name, lookup_type)
        logger.info(f"🔍 Searching for field: {full_field_name} in context={context_type}, lookup={lookup_type}")
        field_def = self.lmdb.get_field(context_type, full_field_name)

        if field_def:
            logger.info(f"✓ Found exact match: {full_field_name}")
            return field_def
        else:
            logger.debug(f"✗ Exact match not found: {full_field_name}")

        # Step 2: Try pattern-based template
        pattern_match = self.detect_pattern(field_name)
        if pattern_match:
            pattern_type, template_key = pattern_match
            template_field_name = self.add_lookup_suffix(template_key, lookup_type)
            template = self.lmdb.get_field(context_type, template_field_name)

            if template:
                logger.info(f"✓ Using {pattern_type} template: {template_field_name}")
                return self.substitute_field(template, full_field_name, field_name)

        # Step 3: Try default text templates
        for default_template in self.DEFAULT_TEMPLATES:
            template_field_name = self.add_lookup_suffix(default_template, lookup_type)
            template = self.lmdb.get_field(context_type, template_field_name)

            if template:
                logger.info(f"✓ Using default template: {template_field_name}")
                return self.substitute_field(template, full_field_name, field_name)

        logger.warning(f"✗ No template found for '{field_name}' in {context_type}")
        return None

    def substitute_field(self, template: Dict, new_field_name: str,
                        base_field_name: str) -> Dict:
        """
        Substitute field name and header in template

        Args:
            template: Template field definition dict
            new_field_name: New field name with suffix (e.g., 'sl_nhap_hang')
            base_field_name: Base field name for header generation (e.g., 'sl_nhap_hang')

        Returns:
            New field definition with substituted values
        """
        # Deep copy template
        import copy
        new_field = copy.deepcopy(template)

        # Generate new header from field name
        new_header = self._generate_header(base_field_name)

        logger.info(f"Substituting: {template.get('field_name', '?')} → {new_field_name}")
        logger.info(f"Header: {template.get('header', '?')} → {new_header}")

        # Substitute in dict
        if 'field_name' in new_field:
            new_field['field_name'] = new_field_name
        if 'header' in new_field:
            new_field['header'] = new_header

        # If template has XML string, substitute there too
        if 'xml' in new_field and isinstance(new_field['xml'], str):
            new_field['xml'] = self._substitute_in_xml(
                new_field['xml'],
                template.get('field_name', ''),
                new_field_name,
                template.get('header', ''),
                new_header
            )

        return new_field

    def _generate_header(self, field_name: str) -> str:
        """
        Generate human-readable header from field name

        Args:
            field_name: Field name (e.g., 'sl_nhap_hang', 'ngay_lap_phieu')

        Returns:
            Generated header (e.g., 'Số lượng nhập hàng', 'Ngày lập phiếu')
        """
        # Common Vietnamese field name prefixes
        PREFIXES = {
            'ma_': 'Mã',
            'ten_': 'Tên',
            'sl_': 'Số lượng',
            'so_': 'Số',
            'ngay_': 'Ngày',
            'gio_': 'Giờ',
            'tien_': 'Tiền',
            'gia_': 'Giá',
            'ty_': 'Tỷ',
            'don_': 'Đơn',
            'ghi_': 'Ghi',
            'dien_': 'Diễn',
        }

        parts = field_name.split('_')
        header_parts = []

        i = 0
        while i < len(parts):
            part = parts[i]
            prefix = f"{part}_"

            # Check if this is a known prefix
            if prefix in PREFIXES:
                header_parts.append(PREFIXES[prefix])
                # Capitalize remaining parts
                remaining = parts[i+1:]
                header_parts.extend([p.capitalize() for p in remaining])
                break
            else:
                # Capitalize this part
                header_parts.append(part.capitalize())

            i += 1

        header = ' '.join(header_parts)

        # Special handling for common suffixes
        if field_name.endswith('_nt'):
            header += ' (ngoại tệ)'

        return header

    def _substitute_in_xml(self, xml_str: str, old_field: str, new_field: str,
                          old_header: str, new_header: str) -> str:
        """
        Substitute field name and header in XML string using REGEX

        Args:
            xml_str: XML string
            old_field: Original field name
            new_field: New field name
            old_header: Original header
            new_header: New header

        Returns:
            XML string with substitutions
        """
        result = xml_str

        # Substitute field attribute (handles both single and double quotes)
        if old_field:
            # Pattern: field="old_field" or field='old_field'
            result = re.sub(
                rf'field\s*=\s*["\']({re.escape(old_field)})["\']',
                f'field="{new_field}"',
                result,
                flags=re.IGNORECASE
            )

        # Substitute header attribute (handles both single and double quotes)
        if old_header:
            # Pattern: header="old_header" or header='old_header'
            result = re.sub(
                rf'header\s*=\s*["\']({re.escape(old_header)})["\']',
                f'header="{new_header}"',
                result,
                flags=re.IGNORECASE
            )

        return result

    def search_similar_fields(self, context_type: str, field_name: str,
                             limit: int = 10) -> List[Dict]:
        """
        Search for fields similar to the given field name

        Args:
            context_type: Context type
            field_name: Field name to search
            limit: Maximum results

        Returns:
            List of similar field definitions
        """
        # Extract base name (remove common suffixes)
        base_name = re.sub(r'(t|lk)$', '', field_name)

        # Search for fields containing the base name
        results = self.lmdb.search_fields(context_type, base_name, limit=limit)

        logger.info(f"Found {len(results)} similar fields for '{field_name}'")
        return results
