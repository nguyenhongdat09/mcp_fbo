"""XML Snippet Tool - Generate XML snippets for AI client to insert

This tool provides PRECISE XML snippets that AI clients can directly replace into files.
Server handles ALL XML manipulation - client just replaces text.
"""

import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class XMLSnippetTool:
    """Tool for generating precise XML snippets

    NEW APPROACH (Cách 2):
    - Server generates EXACT XML snippets
    - AI client just replaces text
    - 100% accurate, no AI interpretation needed

    Tools:
    1. add_clientscript_to_field: Returns modified field XML with clientScript
    2. add_function_to_script: Returns CDATA snippet for function
    """

    def __init__(self):
        """Initialize XML Snippet Tool"""
        pass

    def add_clientscript_to_field(
        self,
        field_xml: str,
        handler_type: str,
        function_name: str
    ) -> Dict:
        """Add clientScript to field XML and return modified field

        Args:
            field_xml: Original field XML (e.g., from get_field_info)
            handler_type: "onchange" or "onfocus"
            function_name: Function name (e.g., "onChange$Voucher$so_ct_hd")

        Returns:
            {
                'success': True,
                'original_field': '<field name="so_ct_hd">...</field>',
                'modified_field': '<field name="so_ct_hd">...<clientScript>...</clientScript></field>',
                'instructions': 'Replace original_field with modified_field in your editor'
            }

        Example:
            Input field_xml:
                <field name="so_ct_hd" align="right">
                  <header v="Số hóa đơn"></header>
                  <items style="Mask"/>
                </field>

            Output modified_field:
                <field name="so_ct_hd" align="right">
                  <header v="Số hóa đơn"></header>
                  <items style="Mask"/>
                  <clientScript><![CDATA[onchange="onChange$Voucher$so_ct_hd(this);"]]></clientScript>
                </field>
        """
        try:
            # Validate handler type
            if handler_type.lower() not in ['onchange', 'onfocus']:
                return {
                    'success': False,
                    'error': f"Invalid handler_type: {handler_type}. Must be 'onchange' or 'onfocus'"
                }

            # Generate script content
            script_content = f'{handler_type.lower()}="{function_name}(this);"'

            # Store original
            original_field = field_xml.strip()

            # Check if clientScript already exists
            if '<clientScript>' in field_xml:
                # Replace existing clientScript
                modified_field = re.sub(
                    r'<clientScript>.*?</clientScript>',
                    f'<clientScript><![CDATA[{script_content}]]></clientScript>',
                    field_xml,
                    flags=re.DOTALL
                )
            else:
                # Add new clientScript BEFORE </field>
                # Check if self-closing
                if field_xml.strip().endswith('/>'):
                    # Convert self-closing to regular tag
                    field_without_slash = field_xml.rstrip('/> \t\n')
                    modified_field = f'{field_without_slash}>\n      <clientScript><![CDATA[{script_content}]]></clientScript>\n    </field>'
                else:
                    # Find </field> and insert before it
                    closing_pos = field_xml.rfind('</field>')
                    if closing_pos > 0:
                        modified_field = (
                            field_xml[:closing_pos] +
                            f'      <clientScript><![CDATA[{script_content}]]></clientScript>\n    ' +
                            field_xml[closing_pos:]
                        )
                    else:
                        return {
                            'success': False,
                            'error': 'Cannot find </field> closing tag'
                        }

            return {
                'success': True,
                'original_field': original_field,
                'modified_field': modified_field.strip(),
                'instructions': (
                    'In your editor:\n'
                    '1. Find the original_field XML\n'
                    '2. Replace it with modified_field\n'
                    '3. Save the file'
                )
            }

        except Exception as e:
            logger.error(f"Error adding clientScript: {e}")
            return {
                'success': False,
                'error': f"Error adding clientScript: {str(e)}"
            }

    def add_function_to_script(
        self,
        function_code: str
    ) -> Dict:
        """Generate CDATA snippet for function to insert before </text></script>

        Args:
            function_code: Complete JavaScript function

        Returns:
            {
                'success': True,
                'function_snippet': '<![CDATA[\nfunction...\n]]>\n    </text>\n</script>',
                'search_pattern': '</text>\\n</script>',
                'instructions': 'Find search_pattern and replace with function_snippet'
            }

        Example:
            Input function_code:
                function onChange$Voucher$so_ct_hd(sender) {
                    var f = sender.parentForm;
                    f.setItemValue("so_seri_hd", "123455");
                }

            Output function_snippet:
                <![CDATA[
                function onChange$Voucher$so_ct_hd(sender) {
                    var f = sender.parentForm;
                    f.setItemValue("so_seri_hd", "123455");
                }
                ]]>
                    </text>
                </script>

            Then AI client finds:
                    </text>
                </script>

            And replaces with function_snippet
        """
        try:
            # Clean function code
            function_code = function_code.strip()

            # Generate CDATA wrapped snippet
            function_snippet = f"""<![CDATA[
{function_code}
]]>
    </text>
</script>"""

            return {
                'success': True,
                'function_snippet': function_snippet,
                'search_pattern': '    </text>\n</script>',
                'instructions': (
                    'In your editor:\n'
                    '1. Find the pattern: "    </text>\\n</script>"\n'
                    '2. Replace it with function_snippet\n'
                    '3. This inserts the function INSIDE CDATA, BEFORE </text>\n'
                    '4. Save the file'
                )
            }

        except Exception as e:
            logger.error(f"Error generating function snippet: {e}")
            return {
                'success': False,
                'error': f"Error generating function snippet: {str(e)}"
            }
