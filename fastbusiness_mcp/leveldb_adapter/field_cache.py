"""Field cache and lookup logic with smart fallback"""

from typing import Optional, Dict, Tuple, List
from .leveldb_manager import LevelDBManager
import logging

logger = logging.getLogger(__name__)

class FieldCache:
    """Cache and smart lookup for field definitions"""

    # Common field templates mapping
    COMMON_TEMPLATES = {
        # Quantity fields
        "quantity": ["so_luong", "sl_nhap", "sl_xuat", "sl_ton"],

        # Date fields
        "date": ["ngay_ct", "ngay_lct", "ngay_hd", "ngay_ht"],

        # Amount/money fields
        "amount": ["tien", "tien_nt", "t_tien", "t_tien_nt"],

        # Customer fields
        "customer": ["ma_kh", "ma_khat", "ma_ncc"],

        # Item/product fields
        "item": ["ma_vt", "ma_vtat", "ma_hh"],

        # Generic code fields
        "code": ["ma_bp", "ma_dvcs", "ma_kho"],

        # Generic name fields
        "name": ["ten_kh", "ten_vt", "ten_bp"],

        # Description fields
        "description": ["dien_giai", "ghi_chu"],
    }

    def __init__(self, leveldb_manager: LevelDBManager):
        self.leveldb = leveldb_manager

    def get_field_with_fallback(
        self,
        field_name: str,
        db_type: str
    ) -> Tuple[Optional[Dict], str, Optional[str]]:
        """
        Get field definition with intelligent fallback

        Args:
            field_name: Requested field name (e.g., "sl_du_kien", "ma_khat")
            db_type: Database type

        Returns:
            Tuple of (field_definition, source, template_field_name)
            source can be: "exact_match", "template_match", "not_found"
            template_field_name: Name of field used as template (if applicable)
        """

        # Step 1: Try exact match
        logger.info(f"Searching for exact match: {field_name} in {db_type}")
        field_def = self.leveldb.get_field(field_name, db_type)

        if field_def:
            logger.info(f"Found exact match for {field_name}")
            return (field_def, "exact_match", None)

        # Step 2: Try to find template based on naming convention
        logger.info(f"Exact match not found, searching for template...")
        template_def, template_name = self._find_template(field_name, db_type)

        if template_def:
            logger.info(f"Found template: {template_name}")
            # Clone and modify
            modified = template_def.copy()
            # Note: Don't modify field_name in definition, let generator handle it
            return (modified, "template_match", template_name)

        logger.warning(f"No match found for {field_name}")
        return (None, "not_found", None)

    def _find_template(
        self,
        field_name: str,
        db_type: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Find suitable template for field based on naming convention

        Returns:
            Tuple of (template_definition, template_field_name)
        """

        field_lower = field_name.lower()

        # Strategy 1: Check naming patterns

        # Quantity fields (sl_*, so_luong*)
        if field_lower.startswith('sl_') or 'so_luong' in field_lower:
            template = self._get_common_template("quantity", db_type)
            if template:
                return template

        # Date fields (ngay_*, date_*, thang_*, nam_*)
        if any(field_lower.startswith(prefix) for prefix in ['ngay_', 'date_', 'thang_', 'nam_']):
            template = self._get_common_template("date", db_type)
            if template:
                return template

        # Amount/money fields (tien*, t_*, amount*, gia*)
        if any(term in field_lower for term in ['tien', 'amount', 'gia']) or field_lower.startswith('t_'):
            template = self._get_common_template("amount", db_type)
            if template:
                return template

        # Strategy 2: Check lookup suffix
        lookup_type = self.detect_lookup_type(field_name)

        if lookup_type == "autocomplete":  # Ends with 'at'
            # Try to find similar autocomplete field
            base_name = field_name[:-2]  # Remove 'at' suffix

            # First try: exact base match with 'at'
            similar = self.leveldb.search_fields(base_name + "at", db_type, limit=1, exact_match=True)
            if similar:
                return (similar[0]['definition'], similar[0]['field_name'])

            # Second try: any autocomplete field as template
            similar = self.leveldb.search_fields("at", db_type, limit=5)
            for item in similar:
                if item['field_name'].endswith('at'):
                    return (item['definition'], item['field_name'])

        elif lookup_type == "lookup":  # Ends with 'lk'
            # Try to find similar lookup field
            base_name = field_name[:-2]  # Remove 'lk' suffix

            # First try: exact base match with 'lk'
            similar = self.leveldb.search_fields(base_name + "lk", db_type, limit=1, exact_match=True)
            if similar:
                return (similar[0]['definition'], similar[0]['field_name'])

            # Second try: any lookup field as template
            similar = self.leveldb.search_fields("lk", db_type, limit=5)
            for item in similar:
                if item['field_name'].endswith('lk'):
                    return (item['definition'], item['field_name'])

        # Strategy 3: Check generic prefixes

        # Code fields (ma_*)
        if field_lower.startswith('ma_'):
            template = self._get_common_template("code", db_type)
            if template:
                return template

        # Name fields (ten_*)
        if field_lower.startswith('ten_'):
            template = self._get_common_template("name", db_type)
            if template:
                return template

        # Description fields (dien_giai*, ghi_chu*)
        if field_lower.startswith('dien_giai') or field_lower.startswith('ghi_chu'):
            template = self._get_common_template("description", db_type)
            if template:
                return template

        return (None, None)

    def _get_common_template(
        self,
        template_type: str,
        db_type: str
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Get common field template by type"""

        if template_type not in self.COMMON_TEMPLATES:
            return (None, None)

        # Try each common field name in order
        for field_name in self.COMMON_TEMPLATES[template_type]:
            field_def = self.leveldb.get_field(field_name, db_type)
            if field_def:
                logger.info(f"Using {field_name} as template for {template_type}")
                return (field_def, field_name)

        return (None, None)

    def detect_lookup_type(self, field_name: str) -> Optional[str]:
        """
        Detect lookup type from field name suffix

        Returns:
            "autocomplete" for fields ending with 'at' (chọn 1)
            "lookup" for fields ending with 'lk' (chọn nhiều)
            None for non-lookup fields
        """
        if field_name.endswith('at'):
            return "autocomplete"
        elif field_name.endswith('lk'):
            return "lookup"
        return None

    def suggest_similar_fields(
        self,
        field_name: str,
        db_type: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Suggest similar fields when exact match not found

        Returns:
            List of similar field definitions
        """

        # Try partial match on base name
        if len(field_name) >= 3:
            base_pattern = field_name[:5]  # First 5 chars
            results = self.leveldb.search_fields(base_pattern, db_type, limit=limit)
            if results:
                return results

        # Try pattern-based suggestions
        field_lower = field_name.lower()

        if field_lower.startswith('sl_'):
            return self.leveldb.search_fields('sl_', db_type, limit=limit)

        if field_lower.startswith('ngay_'):
            return self.leveldb.search_fields('ngay_', db_type, limit=limit)

        if field_lower.startswith('ma_'):
            return self.leveldb.search_fields('ma_', db_type, limit=limit)

        return []
