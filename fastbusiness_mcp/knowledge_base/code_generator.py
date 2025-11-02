"""Code Generator - Generate JavaScript code from patterns"""

import re
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generate JavaScript code from patterns and templates

    Features:
    - Template variable substitution ({{variable}} syntax)
    - Generate code from patterns
    - Code formatting and validation
    - Context-aware code generation
    """

    def __init__(self, knowledge_engine=None):
        """Initialize Code Generator

        Args:
            knowledge_engine: KnowledgeEngine instance (optional)
        """
        self.knowledge_engine = knowledge_engine

    def generate_from_pattern(
        self,
        pattern_name: str,
        variables: Dict[str, str] = None,
        context: Dict = None
    ) -> Dict:
        """Generate code from a pattern

        Args:
            pattern_name: Name of pattern (e.g., 'form_init_new')
            variables: Dict of variable substitutions
            context: Optional context dict for validation

        Returns:
            Dict with 'success', 'code', 'description', 'warnings'
        """
        if not self.knowledge_engine:
            return {
                'success': False,
                'error': 'No knowledge engine available'
            }

        # Get pattern from knowledge engine
        pattern = self.knowledge_engine.get_pattern(pattern_name)
        if not pattern:
            return {
                'success': False,
                'error': f'Pattern not found: {pattern_name}'
            }

        # Get template
        template = pattern.get('template', '')
        if not template:
            return {
                'success': False,
                'error': f'Pattern has no template: {pattern_name}'
            }

        # Substitute variables
        variables = variables or {}
        code = self._substitute_variables(template, variables)

        # Validate context compatibility
        warnings = []
        if context:
            pattern_context = pattern.get('context', '')
            warnings.extend(self._validate_context(pattern_context, context))

        return {
            'success': True,
            'code': code,
            'pattern_name': pattern_name,
            'description': pattern.get('description', ''),
            'context': pattern.get('context', ''),
            'location': pattern.get('location', ''),
            'warnings': warnings
        }

    def generate_from_snippet(
        self,
        snippet_name: str,
        variables: Dict[str, str] = None
    ) -> Dict:
        """Generate code from a snippet

        Args:
            snippet_name: Name of snippet (e.g., 'get_parent_form_from_grid')
            variables: Dict of variable substitutions

        Returns:
            Dict with 'success', 'code', 'description'
        """
        if not self.knowledge_engine:
            return {
                'success': False,
                'error': 'No knowledge engine available'
            }

        # Get snippet from knowledge engine
        snippet = self.knowledge_engine.get_snippet(snippet_name)
        if not snippet:
            return {
                'success': False,
                'error': f'Snippet not found: {snippet_name}'
            }

        # Get code
        code = snippet.get('code', '')
        if not code:
            return {
                'success': False,
                'error': f'Snippet has no code: {snippet_name}'
            }

        # Substitute variables
        variables = variables or {}
        code = self._substitute_variables(code, variables)

        return {
            'success': True,
            'code': code,
            'snippet_name': snippet_name,
            'description': snippet.get('description', ''),
            'critical': snippet.get('critical', False)
        }

    def generate_function_skeleton(
        self,
        function_type: str,
        function_name: str,
        context: Dict = None
    ) -> Dict:
        """Generate function skeleton based on type

        Args:
            function_type: Type of function (e.g., 'active_form', 'onchange_field', 'load_grid')
            function_name: Full function name (e.g., 'active$Form$', 'onChange$Voucher$ma_kh')
            context: Context dict from ContextDetector

        Returns:
            Dict with 'success', 'code', 'description'
        """
        if not context:
            return {
                'success': False,
                'error': 'Context required for function generation'
            }

        file_type = context.get('file_type')
        grid_subtype = context.get('grid_subtype')

        # Determine skeleton based on function type and context
        if function_type == 'active_form':
            if file_type == 'Dir':
                code = self._generate_active_form_skeleton(context)
            else:
                return {
                    'success': False,
                    'error': f'active$Form$ only valid for Dir files, not {file_type}'
                }

        elif function_type == 'onchange_field':
            if file_type == 'Dir':
                code = self._generate_onchange_field_skeleton(function_name, context)
            else:
                return {
                    'success': False,
                    'error': f'onChange field handler only valid for Dir files, not {file_type}'
                }

        elif function_type == 'onchange_grid_cell':
            if grid_subtype == 'GridDetail':
                code = self._generate_onchange_grid_cell_skeleton(function_name, context)
            else:
                return {
                    'success': False,
                    'error': f'Grid cell onChange only valid for Grid Detail, not {grid_subtype}'
                }

        elif function_type == 'load_grid':
            if file_type == 'Grid':
                code = self._generate_load_grid_skeleton(function_name, context)
            else:
                return {
                    'success': False,
                    'error': f'load$Grid$ only valid for Grid files, not {file_type}'
                }

        elif function_type == 'response_complete':
            if file_type in ['Dir', 'Filter']:
                code = self._generate_response_complete_skeleton(context)
            else:
                return {
                    'success': False,
                    'error': f'ResponseComplete only valid for Dir/Filter, not {file_type}'
                }

        else:
            return {
                'success': False,
                'error': f'Unknown function type: {function_type}'
            }

        return {
            'success': True,
            'code': code,
            'function_name': function_name,
            'function_type': function_type,
            'context': context
        }

    def _substitute_variables(self, template: str, variables: Dict[str, str]) -> str:
        """Substitute {{variable}} placeholders in template

        Args:
            template: Template string with {{variable}} placeholders
            variables: Dict of variable values

        Returns:
            Template with variables substituted
        """
        result = template

        # Find all {{variable}} patterns
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, result)

        # Substitute each variable
        for var_name in matches:
            if var_name in variables:
                placeholder = f'{{{{{var_name}}}}}'
                result = result.replace(placeholder, variables[var_name])

        return result

    def _validate_context(self, pattern_context: str, actual_context: Dict) -> List[str]:
        """Validate pattern context against actual context

        Args:
            pattern_context: Required context from pattern (e.g., "Form (Dir)")
            actual_context: Actual context dict

        Returns:
            List of warning messages
        """
        warnings = []
        file_type = actual_context.get('file_type')
        grid_subtype = actual_context.get('grid_subtype')

        # Check context compatibility
        if 'Form' in pattern_context or 'Dir' in pattern_context:
            if file_type != 'Dir':
                warnings.append(f'⚠️  Pattern is for Form (Dir) but file type is {file_type}')

        if 'Grid Detail' in pattern_context:
            if grid_subtype != 'GridDetail':
                warnings.append(f'⚠️  Pattern is for Grid Detail but grid subtype is {grid_subtype}')

        if 'Grid View' in pattern_context:
            if grid_subtype != 'GridView':
                warnings.append(f'⚠️  Pattern is for Grid View but grid subtype is {grid_subtype}')

        return warnings

    def _generate_active_form_skeleton(self, context: Dict) -> str:
        """Generate active$Form$ skeleton"""
        has_grid_detail = context.get('has_grid_detail', False)

        code = "function active$Form$(f) {\n"
        code += "    // Form initialization\n"
        code += "    \n"
        code += "    if (f._action === 'New') {\n"
        code += "        // Set default values\n"
        code += "        f.setItemValue('ngay_ct', new Date());\n"
        code += "        f.setItemValue('status', 1);\n"
        code += "        \n"
        code += "        // Focus to first field\n"
        code += "        f.getItem('ma_kh').focus();\n"

        if has_grid_detail:
            code += "        \n"
            code += "        // Add empty row to grid detail\n"
            code += "        var g = f.grid;\n"
            code += "        g._appendRow(null, true);\n"

        code += "    }\n"
        code += "}"

        return code

    def _generate_onchange_field_skeleton(self, function_name: str, context: Dict) -> str:
        """Generate onChange field handler skeleton"""
        # Extract field name from function name
        # onChange$Voucher$ma_kh → ma_kh
        match = re.search(r'\$(\w+)$', function_name)
        field_name = match.group(1) if match else 'field_name'

        code = f"function {function_name}(sender) {{\n"
        code += "    var f = sender.parentForm;\n"
        code += "    \n"
        code += "    // Skip in view mode\n"
        code += "    if (f._action === 'View') {\n"
        code += "        return;\n"
        code += "    }\n"
        code += "    \n"
        code += f"    var value = f.getItemValue('{field_name}');\n"
        code += "    \n"
        code += "    // Your logic here\n"
        code += "}"

        return code

    def _generate_onchange_grid_cell_skeleton(self, function_name: str, context: Dict) -> str:
        """Generate onChange grid cell handler skeleton"""
        # Extract grid and field name
        # onChange$Voucher$APDetail$so_luong → APDetail, so_luong
        parts = function_name.split('$')
        grid_name = parts[2] if len(parts) > 2 else 'GridName'
        field_name = parts[3] if len(parts) > 3 else 'field_name'

        code = f"function {function_name}(sender) {{\n"
        code += "    var g = sender.grid;\n"
        code += "    var f = g.get_element().parentForm;  // CRITICAL: Get parent form\n"
        code += "    \n"
        code += "    var row = g._activeRow;\n"
        code += "    \n"
        code += f"    // Get column indexes\n"
        code += f"    var col{field_name.capitalize()} = g._getColumnOrder('{field_name}');\n"
        code += "    \n"
        code += f"    // Get value\n"
        code += f"    var {field_name} = g._getItemValue(row, col{field_name.capitalize()});\n"
        code += "    \n"
        code += "    // Your calculation logic here\n"
        code += "    \n"
        code += "    // Set result\n"
        code += "    // g._setItemValue(row, colResult, result);\n"
        code += "}"

        return code

    def _generate_load_grid_skeleton(self, function_name: str, context: Dict) -> str:
        """Generate load$Grid$ skeleton"""
        grid_subtype = context.get('grid_subtype')

        if grid_subtype == 'GridDetail':
            code = f"function {function_name}(g) {{\n"
            code += "    // CRITICAL: Get parent form first!\n"
            code += "    var f = g.get_element().parentForm;\n"
            code += "    \n"
            code += "    // Setup calculations\n"
            code += "    g.$a = {\n"
            code += "        // Calculate within grid\n"
            code += "        tien: '[tien]:=[so_luong]*[gia]',\n"
            code += "        \n"
            code += "        // Use parent form field ($ prefix!)\n"
            code += "        gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]',\n"
            code += "        \n"
            code += "        // Aggregate to parent form\n"
            code += "        t_tien: ['t_tien', 'tien']\n"
            code += "    };\n"
            code += "    \n"
            code += "    // Setup header fields for AJAX (if needed)\n"
            code += "    g.$h = {\n"
            code += "        ty_gia: '[$ty_gia]',\n"
            code += "        ngay_ct: '[$ngay_ct]'\n"
            code += "    };\n"
            code += "}"

        else:  # GridView
            code = f"function {function_name}(g) {{\n"
            code += "    // Grid View initialization\n"
            code += "    // Only use g.xxx API - NO parent form!\n"
            code += "    \n"
            code += "    // Your grid view logic here\n"
            code += "}"

        return code

    def _generate_response_complete_skeleton(self, context: Dict) -> str:
        """Generate on$Form$ResponseComplete skeleton"""
        code = "function on$Form$ResponseComplete(sender, e) {\n"
        code += "    var f = e.object;\n"
        code += "    \n"
        code += "    if (e.type.Context === 'YourContext') {\n"
        code += "        var result = e.type.Result;\n"
        code += "        \n"
        code += "        if (result && result.length > 0) {\n"
        code += "            // CRITICAL: Access by INDEX!\n"
        code += "            // SQL: select col1, col2, col3\n"
        code += "            var value1 = result[0].Value;  // Index 0 = col1\n"
        code += "            var value2 = result[1].Value;  // Index 1 = col2\n"
        code += "            var value3 = result[2].Value;  // Index 2 = col3\n"
        code += "            \n"
        code += "            // Set values to form\n"
        code += "            f.setItemValue('field1', value1);\n"
        code += "            f.setItemValue('field2', value2);\n"
        code += "        } else {\n"
        code += "            alert('Data not found');\n"
        code += "        }\n"
        code += "    }\n"
        code += "}"

        return code

    def format_code(self, code: str, indent: int = 4) -> str:
        """Format JavaScript code with proper indentation

        Args:
            code: JavaScript code string
            indent: Number of spaces per indent level

        Returns:
            Formatted code
        """
        # Simple formatting - preserve existing indentation
        lines = code.split('\n')
        formatted_lines = []

        for line in lines:
            # Preserve existing indentation
            formatted_lines.append(line)

        return '\n'.join(formatted_lines)

    def get_context_appropriate_patterns(self, context: Dict) -> List[Dict]:
        """Get patterns appropriate for given context

        Args:
            context: Context dict from ContextDetector

        Returns:
            List of pattern dicts with name, description, context
        """
        if not self.knowledge_engine:
            return []

        # Construct context string from file_type and grid_subtype
        file_type = context.get('file_type')
        grid_subtype = context.get('grid_subtype')

        # Map to pattern context strings
        if file_type == 'Dir':
            context_str = 'Form (Dir)'
        elif file_type == 'Grid':
            if grid_subtype == 'GridDetail':
                context_str = 'Grid Detail'
            elif grid_subtype == 'GridView':
                context_str = 'Grid View'
            else:
                context_str = 'Grid'
        elif file_type == 'Filter':
            context_str = 'Form (Dir)'  # Filter uses same API as Form
        else:
            return []

        patterns = self.knowledge_engine.get_patterns_for_context(context_str)

        return patterns
