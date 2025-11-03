"""XML Handler Tool - Add JavaScript handlers to FastBusiness XML files"""

import re
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

from ..knowledge_base.engine import KnowledgeEngine
from ..knowledge_base.context_detector import ContextDetector
from ..knowledge_base.code_generator import CodeGenerator

logger = logging.getLogger(__name__)


class XMLHandlerTool:
    """Tool for adding JavaScript handlers to FastBusiness XML files

    Features:
    - Add onChange handlers to fields
    - Add onFocus handlers to fields
    - Add form lifecycle handlers (active$Form$, etc.)
    - Auto-detect context and generate correct code
    - Handle all XML manipulation
    """

    def __init__(self, knowledge_base_dir: str = "knowledge_base"):
        """Initialize XML Handler Tool

        Args:
            knowledge_base_dir: Path to knowledge base directory
        """
        self.knowledge_engine = KnowledgeEngine(knowledge_base_dir)
        self.context_detector = ContextDetector()
        self.code_generator = CodeGenerator(self.knowledge_engine)

    def add_onchange_handler(
        self,
        file_path: str,
        field_name: str,
        handler_code: str = None
    ) -> Dict:
        """Add onChange handler to a field

        Args:
            file_path: Path to XML file
            field_name: Field name to add handler to
            handler_code: JavaScript code for handler body (optional)

        Returns:
            Dict with success, message, function_name, generated_code
        """
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            # Detect context
            context = self.context_detector.detect_from_content(xml_content, file_path)
            if not context.get('success', True):
                return {
                    'success': False,
                    'error': f"Failed to detect context: {context.get('error', 'Unknown error')}"
                }

            file_type = context.get('file_type')
            grid_subtype = context.get('grid_subtype')

            # Generate function name based on context
            function_name = self._generate_function_name(
                'onchange',
                field_name,
                file_type,
                grid_subtype
            )

            # Generate handler code
            if handler_code:
                # User provided custom code
                generated_code = self._generate_onchange_function(
                    function_name,
                    field_name,
                    handler_code,
                    context
                )
            else:
                # Generate skeleton only
                result = self.code_generator.generate_function_skeleton(
                    'onchange_field' if file_type == 'Dir' else 'onchange_grid_cell',
                    function_name,
                    context
                )
                if not result.get('success'):
                    return result
                generated_code = result.get('code', '')

            # Add clientScript to field
            xml_content, field_found = self._add_client_script_to_field(
                xml_content,
                field_name,
                f'onchange="{function_name}(this);"'
            )

            if not field_found:
                return {
                    'success': False,
                    'error': f"Field '{field_name}' not found in XML"
                }

            # Add function to script section
            xml_content = self._add_function_to_script(
                xml_content,
                generated_code
            )

            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)

            return {
                'success': True,
                'message': f"Added onChange handler for field '{field_name}'",
                'function_name': function_name,
                'generated_code': generated_code,
                'file_path': file_path
            }

        except Exception as e:
            logger.error(f"Error adding onChange handler: {e}")
            return {
                'success': False,
                'error': f"Error adding onChange handler: {str(e)}"
            }

    def add_onfocus_handler(
        self,
        file_path: str,
        field_name: str,
        handler_code: str = None
    ) -> Dict:
        """Add onFocus handler to a field

        Args:
            file_path: Path to XML file
            field_name: Field name to add handler to
            handler_code: JavaScript code for handler body (optional)

        Returns:
            Dict with success, message, function_name, generated_code
        """
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            # Detect context
            context = self.context_detector.detect_from_content(xml_content, file_path)
            if not context.get('success', True):
                return {
                    'success': False,
                    'error': f"Failed to detect context: {context.get('error', 'Unknown error')}"
                }

            file_type = context.get('file_type')
            grid_subtype = context.get('grid_subtype')

            # Generate function name
            function_name = self._generate_function_name(
                'onfocus',
                field_name,
                file_type,
                grid_subtype
            )

            # Generate handler code
            if handler_code:
                generated_code = self._generate_onfocus_function(
                    function_name,
                    field_name,
                    handler_code,
                    context
                )
            else:
                # Generate skeleton
                generated_code = self._generate_onfocus_function(
                    function_name,
                    field_name,
                    '// Your code here',
                    context
                )

            # Add clientScript to field
            xml_content, field_found = self._add_client_script_to_field(
                xml_content,
                field_name,
                f'onfocus="{function_name}(this);"'
            )

            if not field_found:
                return {
                    'success': False,
                    'error': f"Field '{field_name}' not found in XML"
                }

            # Add function to script section
            xml_content = self._add_function_to_script(
                xml_content,
                generated_code
            )

            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)

            return {
                'success': True,
                'message': f"Added onFocus handler for field '{field_name}'",
                'function_name': function_name,
                'generated_code': generated_code,
                'file_path': file_path
            }

        except Exception as e:
            logger.error(f"Error adding onFocus handler: {e}")
            return {
                'success': False,
                'error': f"Error adding onFocus handler: {str(e)}"
            }

    def add_form_lifecycle_handler(
        self,
        file_path: str,
        lifecycle: str,
        handler_code: str
    ) -> Dict:
        """Add form lifecycle handler (active$Form$, etc.)

        Args:
            file_path: Path to XML file
            lifecycle: Lifecycle event ('active', 'beforeSave', etc.)
            handler_code: JavaScript code for handler body

        Returns:
            Dict with success, message, function_name, generated_code
        """
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            # Detect context
            context = self.context_detector.detect_from_content(xml_content, file_path)
            if not context.get('success', True):
                return {
                    'success': False,
                    'error': f"Failed to detect context: {context.get('error', 'Unknown error')}"
                }

            file_type = context.get('file_type')

            if file_type != 'Dir':
                return {
                    'success': False,
                    'error': f"Form lifecycle handlers only supported for Dir files, not {file_type}"
                }

            # Generate function name
            function_name = f"{lifecycle}$Form$"

            # Generate handler code
            generated_code = self._generate_lifecycle_function(
                function_name,
                handler_code,
                context
            )

            # Add function to script section
            xml_content = self._add_function_to_script(
                xml_content,
                generated_code
            )

            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)

            return {
                'success': True,
                'message': f"Added {lifecycle} lifecycle handler",
                'function_name': function_name,
                'generated_code': generated_code,
                'file_path': file_path
            }

        except Exception as e:
            logger.error(f"Error adding lifecycle handler: {e}")
            return {
                'success': False,
                'error': f"Error adding lifecycle handler: {str(e)}"
            }

    def _generate_function_name(
        self,
        event_type: str,
        field_name: str,
        file_type: str,
        grid_subtype: Optional[str] = None
    ) -> str:
        """Generate function name based on context

        Args:
            event_type: 'onchange' or 'onfocus'
            field_name: Field name
            file_type: Dir, Grid, or Filter
            grid_subtype: GridDetail or GridView (if Grid)

        Returns:
            Function name (e.g., 'onChange$Voucher$ma_kh')
        """
        # Format event type with proper camelCase
        # "onchange" -> "onChange", "onfocus" -> "onFocus"
        if event_type.lower() == 'onchange':
            event_name = 'onChange'
        elif event_type.lower() == 'onfocus':
            event_name = 'onFocus'
        else:
            # Fallback to capitalize for other events
            event_name = event_type.capitalize()

        # Determine middle part
        if file_type == 'Dir':
            middle = 'Voucher'
        elif file_type == 'Filter':
            middle = 'Filter'
        elif file_type == 'Grid':
            if grid_subtype == 'GridDetail':
                # For Grid Detail, need grid name - use placeholder
                middle = 'Voucher$GridName'
            else:
                middle = 'Grid'
        else:
            middle = 'Voucher'

        return f"{event_name}${middle}${field_name}"

    def _generate_onchange_function(
        self,
        function_name: str,
        field_name: str,
        handler_code: str,
        context: Dict
    ) -> str:
        """Generate onChange function code

        Args:
            function_name: Function name
            field_name: Field name
            handler_code: Custom handler code
            context: Context dict

        Returns:
            Complete function code
        """
        file_type = context.get('file_type')
        grid_subtype = context.get('grid_subtype')

        if file_type == 'Dir' or file_type == 'Filter':
            # Form onChange
            code = f"""function {function_name}(sender) {{
    var f = sender.parentForm;

    // Skip in view mode
    if (f._action === 'View') {{
        return;
    }}

    var value = f.getItemValue('{field_name}');

    {handler_code}
}}"""

        elif file_type == 'Grid':
            if grid_subtype == 'GridDetail':
                # Grid Detail onChange
                code = f"""function {function_name}(sender) {{
    var g = sender.grid;
    var f = g.get_element().parentForm;  // CRITICAL: Get parent form

    var row = g._activeRow;
    var col = g._getColumnOrder('{field_name}');
    var value = g._getItemValue(row, col);

    {handler_code}
}}"""
            else:
                # Grid View onChange
                code = f"""function {function_name}(sender) {{
    var g = sender.grid;

    var row = g._activeRow;
    var col = g._getColumnOrder('{field_name}');
    var value = g._getItemValue(row, col);

    {handler_code}
}}"""
        else:
            # Fallback
            code = f"""function {function_name}(sender) {{
    {handler_code}
}}"""

        return code

    def _generate_onfocus_function(
        self,
        function_name: str,
        field_name: str,
        handler_code: str,
        context: Dict
    ) -> str:
        """Generate onFocus function code"""
        file_type = context.get('file_type')

        if file_type == 'Dir' or file_type == 'Filter':
            code = f"""function {function_name}(sender) {{
    var f = sender.parentForm;

    {handler_code}
}}"""
        else:
            code = f"""function {function_name}(sender) {{
    {handler_code}
}}"""

        return code

    def _generate_lifecycle_function(
        self,
        function_name: str,
        handler_code: str,
        context: Dict
    ) -> str:
        """Generate lifecycle function code"""
        code = f"""function {function_name}(f) {{
    {handler_code}
}}"""
        return code

    def _add_client_script_to_field(
        self,
        xml_content: str,
        field_name: str,
        script_content: str
    ) -> Tuple[str, bool]:
        """Add clientScript to field definition BEFORE closing </field> tag

        Args:
            xml_content: XML content
            field_name: Field name
            script_content: Script content (e.g., 'onchange="func(this);"')

        Returns:
            (modified_xml, field_found)
        """
        # Find field definition with its closing tag
        # Pattern: <field name="field_name" ...> ... </field>
        pattern = rf'<field\b[^>]*\bname\s*=\s*["\']?{re.escape(field_name)}["\']?[^>]*(?:/>|>.*?</field>)'

        match = re.search(pattern, xml_content, re.DOTALL | re.IGNORECASE)
        if not match:
            return xml_content, False

        field_content = match.group(0)

        # Check if field is self-closing
        if field_content.strip().endswith('/>'):
            # Self-closing: <field name="xxx" />
            # Convert to: <field name="xxx">\n  <clientScript>...</clientScript>\n</field>
            field_without_slash = field_content.rstrip('/> \t\n')
            new_field = f'{field_without_slash}>\n        <clientScript><![CDATA[{script_content}]]></clientScript>\n    </field>'
            xml_content = xml_content[:match.start()] + new_field + xml_content[match.end():]
        else:
            # Has closing tag: <field ...>...</field>
            # Add clientScript BEFORE </field>

            # Check if clientScript already exists
            if '<clientScript>' in field_content:
                # Replace existing clientScript
                field_content = re.sub(
                    r'<clientScript>.*?</clientScript>',
                    f'<clientScript><![CDATA[{script_content}]]></clientScript>',
                    field_content,
                    flags=re.DOTALL
                )
                xml_content = xml_content[:match.start()] + field_content + xml_content[match.end():]
            else:
                # Insert clientScript BEFORE </field>
                closing_tag_pos = field_content.rfind('</field>')
                if closing_tag_pos > 0:
                    new_field = (
                        field_content[:closing_tag_pos] +
                        f'<clientScript><![CDATA[{script_content}]]></clientScript>\n    ' +
                        field_content[closing_tag_pos:]
                    )
                    xml_content = xml_content[:match.start()] + new_field + xml_content[match.end():]

        return xml_content, True

    def _add_function_to_script(
        self,
        xml_content: str,
        function_code: str
    ) -> str:
        """Add function to <script> section INSIDE CDATA

        Args:
            xml_content: XML content
            function_code: Function code to add

        Returns:
            Modified XML content
        """
        # Find <script> section
        script_match = re.search(r'<script[^>]*>(.*?)</script>', xml_content, re.DOTALL | re.IGNORECASE)

        if script_match:
            # Script section exists - add function to it
            script_content = script_match.group(1)

            # Check if function already exists (by function name)
            function_name_match = re.search(r'function\s+(\w+\$\w+(?:\$\w+)?)\s*\(', function_code)
            if function_name_match:
                function_name = function_name_match.group(1)
                # Remove existing function with same name (inside CDATA)
                script_content = re.sub(
                    rf'function\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{.*?\}}',
                    '',
                    script_content,
                    flags=re.DOTALL
                )

            # Insert function INSIDE CDATA (before ]]>)
            # Find CDATA section
            cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', script_content, re.DOTALL)

            if cdata_match:
                # CDATA exists - insert function BEFORE ]]>
                cdata_content = cdata_match.group(1)

                # Add function to CDATA content
                new_cdata_content = cdata_content.rstrip() + '\n\n' + function_code + '\n'

                # Replace CDATA content
                new_script_content = script_content[:cdata_match.start(1)] + new_cdata_content + script_content[cdata_match.end(1):]
            else:
                # No CDATA - create one and wrap existing content + new function
                # Check if there's any content
                content_before_entities = script_content.split('&')[0].strip()
                entities_part = '&' + script_content.split('&', 1)[1] if '&' in script_content else ''

                if content_before_entities:
                    # Wrap existing content + new function in CDATA
                    new_script_content = f'<![CDATA[\n{content_before_entities}\n\n{function_code}\n]]>\n{entities_part}'
                else:
                    # Just add CDATA with function
                    new_script_content = f'<![CDATA[\n{function_code}\n]]>\n{entities_part.lstrip()}'

            xml_content = (
                xml_content[:script_match.start(1)] +
                new_script_content +
                xml_content[script_match.end(1):]
            )
        else:
            # No script section - create one with CDATA
            # Find where to insert (before </dir> or </grid> or </filter>)
            closing_tag_match = re.search(r'(</(?:dir|grid|filter)>)', xml_content, re.IGNORECASE)
            if closing_tag_match:
                new_script = f'\n    <script><![CDATA[\n{function_code}\n    ]]></script>\n'
                xml_content = (
                    xml_content[:closing_tag_match.start()] +
                    new_script +
                    xml_content[closing_tag_match.start():]
                )
            else:
                # Can't find closing tag - append at end
                xml_content += f'\n<script><![CDATA[\n{function_code}\n]]></script>\n'

        return xml_content
