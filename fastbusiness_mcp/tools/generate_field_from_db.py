"""Tool: Generate field from LevelDB with intelligent fallback"""

from typing import Dict, Any, Optional
from ..core.base_tool import BaseTool
from ..leveldb_adapter.leveldb_manager import LevelDBManager
from ..leveldb_adapter.field_cache import FieldCache
from ..leveldb_adapter.config import LevelDBConfig


class GenerateFieldFromDBTool(BaseTool):
    """Generate field definition from LevelDB database"""

    def __init__(self, use_vscode_extension: bool = True):
        """
        Initialize tool

        Args:
            use_vscode_extension: If True, try to use VS Code extension database first
        """
        self.leveldb = LevelDBManager(use_vscode_extension=use_vscode_extension)
        self.cache = FieldCache(self.leveldb)

    @property
    def name(self) -> str:
        return "generate_field_from_db"

    @property
    def description(self) -> str:
        return """Generate field XML definition from LevelDB database.

        Workflow:
        1. Search for exact field name match in LevelDB
        2. If not found, search for template based on naming pattern:
           - sl_*, so_luong* → quantity template
           - ngay_*, date_* → date template
           - ma_*at → autocomplete lookup template
           - ma_*lk → multiple lookup template
           - tien*, t_* → amount template
        3. Return field XML with source information

        Examples:
        - "sl_du_kien" → Uses "so_luong" as template
        - "ma_vtat" → Uses "ma_khat" as template (autocomplete)
        - "ngay_lct" → Uses "ngay_ct" as template
        """

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "description": "Field name (e.g., 'sl_du_kien', 'ma_vtat', 'ngay_lct')"
                },
                "context_type": {
                    "type": "string",
                    "enum": ["DIR", "FILTER_VOUCHER", "FILTER_NORMAL", "GRID_VIEW", "GRID_INPUT"],
                    "description": "Where the field will be used"
                },
                "display_name_vi": {
                    "type": "string",
                    "description": "Vietnamese display name (optional, updates template)"
                },
                "display_name_en": {
                    "type": "string",
                    "description": "English display name (optional, updates template)"
                }
            },
            "required": ["field_name", "context_type"]
        }

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute field generation from DB"""

        field_name = arguments["field_name"]
        context_type = arguments["context_type"]
        display_name_vi = arguments.get("display_name_vi")
        display_name_en = arguments.get("display_name_en")

        # Get field with fallback
        field_def, source, template_name = self.cache.get_field_with_fallback(
            field_name,
            context_type
        )

        if not field_def:
            # Provide suggestions
            suggestions = self.cache.suggest_similar_fields(field_name, context_type, limit=5)

            return {
                "success": False,
                "source": "not_found",
                "field_name": field_name,
                "message": f"Cannot find field or template for '{field_name}' in {context_type} database",
                "suggestions": {
                    "similar_fields": [s['field_name'] for s in suggestions],
                    "action": "Please provide one of these similar fields to use as template, or specify the field type manually"
                }
            }

        # Build XML from field definition
        xml = await self._build_field_xml(
            field_def,
            field_name,
            display_name_vi,
            display_name_en,
            context_type
        )

        # Check if need companion field (lookup)
        companion_xml = None
        lookup_type = self.cache.detect_lookup_type(field_name)

        if lookup_type or ('items' in field_def and field_def['items'].get('style') in ['AutoComplete', 'Lookup']):
            companion_xml = await self._build_companion_field(field_name, context_type, field_def)

        return {
            "success": True,
            "source": source,
            "field_name": field_name,
            "template_used": template_name if source == "template_match" else None,
            "lookup_type": lookup_type,
            "xml": xml,
            "companion_xml": companion_xml,
            "message": self._build_success_message(source, template_name, lookup_type)
        }

    async def _build_field_xml(
        self,
        field_def: Dict,
        new_field_name: str,
        display_vi: Optional[str],
        display_en: Optional[str],
        context_type: str
    ) -> str:
        """Build XML from field definition"""

        xml_parts = [f'<field name="{new_field_name}"']

        # Add attributes from template
        if field_def.get('type') and field_def['type'] != 'String':
            xml_parts.append(f' type="{field_def["type"]}"')

        if context_type in ["GRID_VIEW", "GRID_INPUT"] and field_def.get('width'):
            xml_parts.append(f' width="{field_def["width"]}"')

        if field_def.get('align'):
            xml_parts.append(f' align="{field_def["align"]}"')

        if field_def.get('allowNulls') == False or field_def.get('allowNulls') == 'false':
            xml_parts.append(' allowNulls="false"')

        if field_def.get('dataFormatString'):
            xml_parts.append(f' dataFormatString="{field_def["dataFormatString"]}"')

        # GridView specific attributes
        if context_type == "GRID_VIEW":
            if field_def.get('allowSorting'):
                xml_parts.append(' allowSorting="true"')
            if field_def.get('allowFilter'):
                xml_parts.append(' allowFilter="true"')

        xml_parts.append('>\n')

        # Header
        vi_name = display_vi or field_def.get('header_vi', '[Vietnamese]')
        en_name = display_en or field_def.get('header_en', '[English]')
        xml_parts.append(f'  <header v="{vi_name}" e="{en_name}"/>\n')

        # Items (lookup) if exists in template
        if 'items' in field_def:
            items = field_def['items']
            style = items.get('style', 'AutoComplete')

            xml_parts.append(f'  <items style="{style}"')

            if items.get('controller'):
                xml_parts.append(f'\n         controller="{items["controller"]}"')

            # Update reference to match new field name
            if items.get('reference'):
                # Generate new reference based on new field name
                if new_field_name.endswith('at') or new_field_name.endswith('lk'):
                    base_name = new_field_name[:-2]
                    new_ref = f"ten_{base_name}%l"
                else:
                    # Keep original reference pattern
                    new_ref = items['reference']

                xml_parts.append(f'\n         reference="{new_ref}"')

            if items.get('key'):
                xml_parts.append(f'\n         key="{items["key"]}"')

            if items.get('check'):
                xml_parts.append(f'\n         check="{items["check"]}"')

            xml_parts.append('/>\n')

        xml_parts.append('</field>')

        return ''.join(xml_parts)

    async def _build_companion_field(
        self,
        field_name: str,
        context_type: str,
        field_def: Dict
    ) -> str:
        """Build companion field for lookup"""

        # Extract base name
        if field_name.endswith('at') or field_name.endswith('lk'):
            base_name = field_name[:-2]
        else:
            # Extract from items reference if available
            if 'items' in field_def and 'reference' in field_def['items']:
                ref = field_def['items']['reference']
                # Reference format: ten_kh%l
                if '%l' in ref:
                    companion_name = ref
                else:
                    companion_name = f"ten_{field_name}%l"
            else:
                companion_name = f"ten_{field_name}%l"

        if field_name.endswith('at') or field_name.endswith('lk'):
            companion_name = f"ten_{base_name}%l"

        xml_parts = [f'<field name="{companion_name}" external="true" readOnly="true"']

        if context_type in ["GRID_VIEW", "GRID_INPUT"]:
            # Try to get width from template or default
            width = field_def.get('companion_width', 200)
            xml_parts.append(f' width="{width}"')

        xml_parts.append('>\n')
        xml_parts.append('  <header v="" e=""/>\n')
        xml_parts.append('</field>')

        return ''.join(xml_parts)

    def _build_success_message(
        self,
        source: str,
        template_name: Optional[str],
        lookup_type: Optional[str]
    ) -> str:
        """Build success message"""

        if source == "exact_match":
            msg = "Found exact field definition in database"
        elif source == "template_match":
            msg = f"Used '{template_name}' as template (exact match not found)"
        else:
            msg = "Generated field"

        if lookup_type:
            lookup_desc = "single selection (AutoComplete)" if lookup_type == "autocomplete" else "multiple selection (Lookup)"
            msg += f". Detected as lookup field ({lookup_desc}), companion field generated"

        return msg
