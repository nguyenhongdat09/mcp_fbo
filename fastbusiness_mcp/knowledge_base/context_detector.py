"""Context Detector - Detect file context from XML content"""

import re
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextDetector:
    """Detect context from FastBusiness XML files

    Determines:
    - File type (Dir, Grid, Filter)
    - Grid subtype (GridDetail vs GridView)
    - Location context (script section, field definition)
    - Which API to use (form_api, grid_api, or both)
    """

    def __init__(self):
        """Initialize Context Detector"""
        pass

    def detect_from_file(self, file_path: str) -> Dict:
        """Detect context from XML file path

        Args:
            file_path: Path to XML file

        Returns:
            Context dict with file_type, grid_subtype, location, etc.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            return self.detect_from_content(xml_content, file_path)

        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {
                'success': False,
                'error': f'Failed to read file: {str(e)}'
            }

    def detect_from_content(self, xml_content: str, file_path: str = '') -> Dict:
        """Detect context from XML content

        Args:
            xml_content: XML file content
            file_path: Optional file path for path-based detection

        Returns:
            Context dict
        """
        context = {
            'success': True,
            'file_type': 'UNKNOWN',
            'grid_subtype': None,
            'primary_object': None,
            'secondary_object': None,
            'primary_api': None,
            'secondary_api': None,
            'has_parent_form': False,
            'critical_rules': [],
            'file_path': file_path
        }

        # Detect file type
        file_type = self._detect_file_type(xml_content, file_path)
        context['file_type'] = file_type

        # Detect based on file type
        if file_type == 'Dir':
            context.update(self._detect_dir_context(xml_content))

        elif file_type == 'Grid':
            context.update(self._detect_grid_context(xml_content))

        elif file_type == 'Filter':
            context.update(self._detect_filter_context(xml_content))

        # Add recommendations
        context['recommendations'] = self._generate_recommendations(context)

        return context

    def _detect_file_type(self, xml_content: str, file_path: str) -> str:
        """Detect file type from XML content and path

        Args:
            xml_content: XML content
            file_path: File path

        Returns:
            'Dir', 'Grid', or 'Filter'
        """
        # Check path first (most reliable)
        if file_path:
            normalized_path = file_path.replace('/', '\\')

            if '\\Dir\\' in normalized_path or '\\dir\\' in normalized_path:
                return 'Dir'

            elif '\\Grid\\' in normalized_path or '\\grid\\' in normalized_path:
                return 'Grid'

            elif '\\Filter\\' in normalized_path or '\\filter\\' in normalized_path:
                return 'Filter'

        # Fallback to content detection
        if re.search(r'<dir\b', xml_content, re.IGNORECASE):
            # Check if it's a filter
            if 'XMLWhenFilterLoading' in xml_content or 'type="Report"' in xml_content:
                return 'Filter'
            else:
                return 'Dir'

        elif re.search(r'<grid\b', xml_content, re.IGNORECASE):
            return 'Grid'

        return 'UNKNOWN'

    def _detect_dir_context(self, xml_content: str) -> Dict:
        """Detect Dir (Form) context

        Args:
            xml_content: XML content

        Returns:
            Context updates dict
        """
        context = {
            'primary_object': 'f',
            'primary_api': 'form_api',
            'has_parent_form': False
        }

        # Check if Dir has embedded Grid Detail
        has_grid_detail = bool(re.search(r'<grid\b[^>]*\btype\s*=\s*["\']Detail["\']', xml_content, re.IGNORECASE))

        if has_grid_detail:
            context['has_grid_detail'] = True
            context['grid_subtype'] = 'GridDetail'
            # Note: When in Grid Detail script, will need both APIs
            context['critical_rules'].append('grid_detail_must_get_parent')

        return context

    def _detect_grid_context(self, xml_content: str) -> Dict:
        """Detect Grid context and subtype

        Args:
            xml_content: XML content

        Returns:
            Context updates dict
        """
        # Determine grid subtype
        is_detail = bool(re.search(r'<grid\b[^>]*\btype\s*=\s*["\']Detail["\']', xml_content, re.IGNORECASE))
        has_queries = bool(re.search(r'<queries\b', xml_content, re.IGNORECASE))
        has_toolbar = bool(re.search(r'<toolbar\b', xml_content, re.IGNORECASE))

        if is_detail:
            # Grid Detail
            return {
                'grid_subtype': 'GridDetail',
                'primary_object': 'g',
                'secondary_object': 'f',
                'primary_api': 'grid_api',
                'secondary_api': 'form_api',
                'has_parent_form': True,
                'critical_rules': ['grid_detail_must_get_parent', 'grid_parent_field_calculation']
            }

        elif has_queries or has_toolbar:
            # Grid View
            return {
                'grid_subtype': 'GridView',
                'primary_object': 'g',
                'primary_api': 'grid_api',
                'has_parent_form': False,
                'critical_rules': ['grid_view_no_parent']
            }

        else:
            # Unknown grid type, assume GridView
            return {
                'grid_subtype': 'GridView',
                'primary_object': 'g',
                'primary_api': 'grid_api',
                'has_parent_form': False
            }

    def _detect_filter_context(self, xml_content: str) -> Dict:
        """Detect Filter context

        Args:
            xml_content: XML content

        Returns:
            Context updates dict
        """
        return {
            'primary_object': 'sender',
            'primary_api': 'form_api',
            'has_parent_form': False,
            'note': 'Filter uses form API (same as Dir)'
        }

    def _generate_recommendations(self, context: Dict) -> list:
        """Generate recommendations based on context

        Args:
            context: Context dict

        Returns:
            List of recommendation strings
        """
        recommendations = []

        file_type = context.get('file_type')
        grid_subtype = context.get('grid_subtype')

        # Recommendations based on file type
        if file_type == 'Dir':
            recommendations.append("✓ Use Form API: f.getItemValue(), f.setItemValue()")

            if context.get('has_grid_detail'):
                recommendations.append("⚠️  CRITICAL: If writing Grid Detail script, MUST get parent form first!")
                recommendations.append("   Code: var f = g.get_element().parentForm;")

        elif file_type == 'Grid':
            if grid_subtype == 'GridDetail':
                recommendations.append("🔴 CRITICAL: Grid Detail - MUST get parent form!")
                recommendations.append("   Step 1: var f = g.get_element().parentForm;")
                recommendations.append("   Step 2: Use both g.xxx (grid) and f.xxx (form)")
                recommendations.append("   Step 3: Parent fields in calculations use $ prefix: [$field_name]")

            elif grid_subtype == 'GridView':
                recommendations.append("✓ Grid View - Use grid API only: g._getItemValue(), g._setItemValue()")
                recommendations.append("❌ NO parent form access! Don't use f.xxx")

        elif file_type == 'Filter':
            recommendations.append("✓ Use Form API (same as Dir): f.getItemValue(), f.setItemValue()")

        # Response handler recommendation
        recommendations.append("📋 Response handlers: Access result by INDEX → result[0].Value, result[1].Value")

        return recommendations

    def get_context_summary(self, context: Dict) -> str:
        """Get human-readable context summary

        Args:
            context: Context dict from detect_from_content()

        Returns:
            Formatted summary string
        """
        if not context.get('success'):
            return f"❌ Error: {context.get('error', 'Unknown error')}"

        lines = []
        lines.append("📋 **File Context:**")
        lines.append(f"  - File Type: {context.get('file_type')}")

        if context.get('grid_subtype'):
            lines.append(f"  - Grid Subtype: {context.get('grid_subtype')}")

        lines.append(f"  - Primary Object: {context.get('primary_object')}")
        lines.append(f"  - Primary API: {context.get('primary_api')}")

        if context.get('secondary_object'):
            lines.append(f"  - Secondary Object: {context.get('secondary_object')}")
            lines.append(f"  - Secondary API: {context.get('secondary_api')}")

        if context.get('has_parent_form'):
            lines.append(f"  - Has Parent Form: YES (MUST access with get_element().parentForm)")

        # Critical rules
        if context.get('critical_rules'):
            lines.append("\n🔴 **Critical Rules:**")
            for rule_id in context['critical_rules']:
                lines.append(f"  - {rule_id}")

        # Recommendations
        if context.get('recommendations'):
            lines.append("\n💡 **Recommendations:**")
            for rec in context['recommendations']:
                lines.append(f"  {rec}")

        return '\n'.join(lines)
