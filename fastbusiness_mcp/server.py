"""FastBusiness MCP Server - LMDB Field Generation Only."""

import asyncio
import yaml
import re
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

from .tools.generate_field_from_lmdb import GenerateFieldFromLMDBTool
from .tools.generate_sql_for_fields import GenerateSQLForFieldsTool
from .tools.code_assistant_tool import CodeAssistantTool
from .tools.xml_snippet_tool import XMLSnippetTool
from .utils.logger import setup_logger 
from .utils.file_utils import read_file
  
logger = setup_logger(__name__) 


class FastBusinessMCPServer:
    """FastBusiness MCP Server - LMDB Field Generation + AI Code Assistant."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize MCP server."""
        self.config = self._load_config(config_path)
        self.server = Server("fastbusiness-mcp-server")

        from pathlib import Path
        import os

        # ============================================
        # LMDB DATABASE PATH RESOLUTION (Priority Order)
        # ============================================
        # 1. Environment variable (highest priority)
        # 2. Config file
        # 3. Default relative path

        lmdb_path = None

        # Priority 1: Check environment variable
        env_db_path = os.environ.get('FASTBUSINESS_VSCODE_DB_PATH')
        if env_db_path:
            lmdb_path = env_db_path
            logger.info(f"[OK] Using LMDB path from environment variable: {lmdb_path}")

        # Priority 2: Check config file
        if not lmdb_path:
            lmdb_path = self.config.get("database", {}).get("lmdb_path", "data/fields_lmdb")
            logger.info(f"[OK] Using LMDB path from config: {lmdb_path}")

        # Convert to absolute path if relative
        if not Path(lmdb_path).is_absolute():
            # Use current working directory as base
            lmdb_path = str(Path.cwd() / lmdb_path)
            logger.info(f"[OK] Converted to absolute path: {lmdb_path}")

        logger.info(f"[DB] Final LMDB database path: {lmdb_path}")

        # Initialize LMDB field tool
        self.lmdb_field_tool = GenerateFieldFromLMDBTool(db_path=lmdb_path)

        # Initialize SQL generation tool
        self.sql_gen_tool = GenerateSQLForFieldsTool()

        # ============================================
        # KNOWLEDGE BASE PATH RESOLUTION
        # ============================================
        # 1. Environment variable (highest priority)
        # 2. Config file
        # 3. Default relative path

        kb_path = os.environ.get('FASTBUSINESS_KNOWLEDGE_BASE_PATH')
        if not kb_path:
            kb_path = self.config.get("paths", {}).get("knowledge_base", "knowledge_base")

        # Convert to absolute path if relative
        if not Path(kb_path).is_absolute():
            kb_path = str(Path.cwd() / kb_path)

        logger.info(f"[KB] Knowledge base path: {kb_path}")

        # Initialize Code Assistant (Knowledge Base System)
        self.code_assistant = CodeAssistantTool(knowledge_base_dir=kb_path)

        # Initialize XML Snippet Tool (Cách 2: Generate precise snippets)
        self.xml_snippet = XMLSnippetTool()

        # Register handlers
        self._register_resources()
        self._register_tools()

        logger.info("FastBusiness MCP Server (LMDB Field Generation + AI Code Assistant) initialized")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
            return {
                "data": {
                    "quick_reference": "data/quick_reference.txt",
                    "xml_summary": "data/xml_meaning_summary.txt",
                }
            }

    def _register_resources(self) -> None:
        """Register MCP resources."""

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="fastbusiness://docs/quick-reference",
                    name="FastBusiness Quick Reference",
                    mimeType="text/plain",
                    description="Complete quick reference for FastBusiness XML development",
                ),
                Resource(
                    uri="fastbusiness://docs/xml-summary",
                    name="XML Meaning Summary",
                    mimeType="text/plain",
                    description="Summary of XML structures and their meanings",
                ),
                Resource(
                    uri="fastbusiness://instructions/xml-handler-workflow",
                    name="CRITICAL: XML Handler Workflow - MUST READ FIRST",
                    mimeType="text/markdown",
                    description="[REQUIRED] How to add JavaScript handlers to XML files - READ THIS BEFORE adding onChange/onFocus handlers!",
                ),
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read resource content."""
            try:
                if uri == "fastbusiness://docs/quick-reference":
                    return read_file(self.config["data"]["quick_reference"])
                elif uri == "fastbusiness://docs/xml-summary":
                    return read_file(self.config["data"]["xml_summary"])
                elif uri == "fastbusiness://instructions/xml-handler-workflow":
                    return """# CRITICAL: XML Handler Workflow

## ⚠️ IMPORTANT: When user asks to add JavaScript handlers, you MUST use the snippet tools!

DO NOT write XML manually! DO NOT use code assistant to generate XML!
The MCP server provides PRECISE tools that ensure 100% correct XML structure.

## When to Use These Tools:

User says ANY of these:
- "Thêm xử lý khi nhập X" / "Add handler when entering X"
- "Khi nhập X thì Y" / "When X is entered then Y"
- "Thêm onChange cho X" / "Add onChange to X"
- "Thêm onFocus cho X" / "Add onFocus to X"
- "Khi focus X thì Y" / "When X is focused then Y"

→ YOU MUST USE: `add_clientscript_to_field` + `add_function_to_script` tools!

## REQUIRED Workflow:

### Step 1: Get field XML
```
Call: get_field_info
  field_name: 'so_ct_hd'
  file_path: '...'

Result: You get field_xml
```

### Step 2: Add clientScript to field
```
Call: add_clientscript_to_field
  field_xml: '<field name="so_ct_hd">...</field>' (from Step 1)
  handler_type: 'onchange' or 'onfocus'
  function_name: 'onChange$Voucher$so_ct_hd'

Result: Server returns modified_field XML with clientScript
```

**YOU MUST**: Replace the original field in file with modified_field

### Step 3: Add function to script section
```
Call: add_function_to_script
  function_code: '''
function onChange$Voucher$so_ct_hd(sender) {
    var f = sender.parentForm;
    if (f._action === 'View') return;

    // User's logic here
    f.setItemValue("so_seri_hd", "123455");
}
'''

Result: Server returns function_snippet and search_pattern
```

**YOU MUST**:
1. Find the pattern `    </text>\n</script>` in file
2. Replace it with function_snippet

## Function Naming Rules:

**DIR files** (form):
- onChange: `onChange$Voucher$field_name`
- onFocus: `onFocus$Voucher$field_name`

**GRID files** (grid):
- onChange: `onChange$Grid$field_name` (GridView)
- onChange: `onChange$Voucher$GridName$field_name` (GridDetail)

**FILTER files**:
- onChange: `onChange$Filter$field_name`

## Complete Example:

User: "Thêm xử lý nhập so_ct_hd gán so_seri_hd = '123455'"

**Step 1**: Call `get_field_info` with field_name='so_ct_hd', file_path='...'
→ Get field_xml

**Step 2**: Call `add_clientscript_to_field`:
```
field_xml: (result from step 1)
handler_type: 'onchange'
function_name: 'onChange$Voucher$so_ct_hd'
```
→ Replace field in file with modified_field

**Step 3**: Call `add_function_to_script`:
```
function_code: '''
function onChange$Voucher$so_ct_hd(sender) {
    var f = sender.parentForm;
    if (f._action === 'View') return;
    f.setItemValue("so_seri_hd", "123455");
}
'''
```
→ Find `    </text>\n</script>` and replace with function_snippet

**DONE!** ✓ clientScript in correct position ✓ Function inside CDATA

## Why Use These Tools?

❌ **DO NOT** manually write XML:
- clientScript might be in wrong position
- Function might be outside CDATA
- Multiple functions might overlap

✅ **USE TOOLS**:
- Server controls 100% of XML structure
- Always correct position
- Always inside CDATA
- Zero errors

## Remember:

1. **ALWAYS** use `add_clientscript_to_field` for adding handlers
2. **ALWAYS** use `add_function_to_script` for adding functions
3. **NEVER** write XML manually
4. **NEVER** use code assistant for XML structure

The tools exist specifically to ensure precision. USE THEM!
"""
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")

            return "Resource not found"

    def _register_tools(self) -> None:
        """Register MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="generate_field_from_lmdb",
                    description="""[*] Generate field from LMDB database - USE THIS when user asks to add fields!

AUTOMATIC CONTEXT DETECTION:
- Provide file_path (current file path) for most accurate detection (RECOMMENDED)
- Or provide xml_content (current file content) as fallback
- Or manually specify context_type if known

LOOKUP TYPE PARSING (from Vietnamese):
- "thêm trường X" / "add field X" → lookup_type='default'
- "thêm trường X dạng lookup" / "dạng chọn lookup" → lookup_type='autocomplete' (default for lookup)
- "thêm trường X lookup chọn nhiều" / "chọn nhiều" → lookup_type='lookup'
- "thêm trường X autocomplete" → lookup_type='autocomplete'

EXAMPLES:
User: "Thêm trường mã khách hàng dạng lookup"
→ field_name='ma_kh', lookup_type='autocomplete', file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml'

User: "Thêm trường mã kh dạng lookup chọn nhiều"
→ field_name='ma_kh', lookup_type='lookup', file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Grid\\zcdmbtqt.xml'

User: "Thêm số lượng"
→ field_name='so_luong', lookup_type='default', file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Filter\\Report.xml'

The tool will:
1. Auto-detect context from file_path (DIR/FILTER_VOUCHER/FILTER_NORMAL/GRID_VIEW/GRID_INPUT)
2. Query LMDB for field with lookup suffix
3. Return field XML ready to insert
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "field_name": {
                                "type": "string",
                                "description": "Field name without suffix (e.g., 'ma_kh', 'so_luong', 'ngay_ct')",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Current file path for auto-detecting context type (most accurate, recommended)",
                            },
                            "xml_content": {
                                "type": "string",
                                "description": "Current XML file content for auto-detecting context type (fallback if file_path not available)",
                            },
                            "context_type": {
                                "type": "string",
                                "description": "Manual context type if file_path/xml_content not provided: DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT",
                            },
                            "lookup_type": {
                                "type": "string",
                                "description": "Lookup type: 'default' (no lookup), 'autocomplete' (single select), 'lookup' (multi-select)",
                            },
                            "show_similar": {
                                "type": "boolean",
                                "description": "Show similar fields if not found (default: true)",
                            },
                        },
                        "required": ["field_name"],
                    },
                ),
                Tool(
                    name="search_lmdb_fields",
                    description="Search for fields in LMDB database by pattern",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "string",
                                "description": "Search pattern (substring match)",
                            },
                            "context_type": {
                                "type": "string",
                                "description": "Context type: DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT",
                            },
                            "limit": {
                                "type": "number",
                                "description": "Maximum results (default: 20)",
                            },
                        },
                        "required": ["pattern", "context_type"],
                    },
                ),
                Tool(
                    name="lmdb_database_stats",
                    description="Get statistics about the LMDB field database",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="generate_sql_for_fields",
                    description="""[*] Generate SQL commands for adding fields to database tables

Generates `fsd_addfields` SQL commands with automatic table extraction and SQL type detection.

✨ NEW: AUTOMATIC TABLE EXTRACTION - Python does everything!
- Provide file_path (current file path) - RECOMMENDED
- Or provide xml_content (current file content) - fallback
- Python auto-extracts table from <grid table="..."> or <dir table="...">
- Works for GRID_INPUT and DIR contexts only
- NO NEED to pass tables parameter!

EXTRACTION RULES:
- <grid table="d31$000000"> → Extracts d31$ (has $ → keep up to $)
- <dir table="m31$000000"> → Extracts m31$ (has $ → keep up to $)
- <dir table="dmvt"> → Extracts dmvt (no $ → take all)

CRITICAL RULES:
- If XML table has $ (e.g., d91$000000) → Preserve $ in SQL: exec fsd_addfields 'd91$', ...
- If XML table has NO $ (e.g., dmvt) → Don't add $: exec fsd_addfields 'dmvt', ...

SQL TYPE AUTO-DETECTION:
- ma_* → varchar(33)
- ten_*, ghi_chu → nvarchar(256)
- ngay_* → smalldatetime
- tien*, *_nt → numeric(19,4)
- so_luong, sl_*, *_sl → numeric(19,4)  (INCLUDES sl_nhap, sl_xuat!)
- thang, nam → int
- status → tinyint
- *%l → nvarchar(256)

EXAMPLES:
1. Using file_path (RECOMMENDED):
   field_names=['sl_nhap', 'sl_xuat']
   file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Grid\\Detail.xml'
   →
   Python reads file → Finds <grid table="d31$000000"> → Extracts d31$
   exec fsd_addfields 'd31$', 'sl_nhap', 'numeric(19,4)'
   exec fsd_addfields 'd31$', 'sl_xuat', 'numeric(19,4)'

2. Using xml_content (fallback):
   field_names=['ma_kh']
   xml_content='<dir table="m31$000000">...</dir>'
   →
   Python parses XML → Finds <dir table="m31$000000"> → Extracts m31$
   exec fsd_addfields 'm31$', 'ma_kh', 'varchar(33)'

The tool will:
1. Read file (if file_path provided) or use xml_content
2. Auto-extract table from <grid table="..."> or <dir table="...">
3. Auto-detect SQL type from field name pattern
4. Preserve $ suffix if table is partitioned
5. Strip lookup suffixes (t, lk) from field names
6. Optionally generate master table creation for lookup fields
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "field_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of field names to add (e.g., ['ma_kh', 'ten_kh%l', 'sl_nhap'])",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "File path to read XML and extract table (recommended)",
                            },
                            "xml_content": {
                                "type": "string",
                                "description": "XML content to extract table (fallback if file_path not available)",
                            },
                            "create_master_table": {
                                "type": "boolean",
                                "description": "Generate master table creation for lookup fields (default: false)",
                            },
                        },
                        "required": ["field_names"],
                    },
                ),
                # ============================================
                # KNOWLEDGE BASE SYSTEM TOOLS
                # ============================================
                Tool(
                    name="detect_context_from_file",
                    description="""[SEARCH] Detect context from FastBusiness XML file

Detects:
- File type (Dir, Grid, Filter)
- Grid subtype (GridDetail vs GridView)
- Which API to use (form_api, grid_api, or both)
- Critical rules to follow
- Context-specific recommendations

EXAMPLES:
User: "What context is this file?"
→ file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml'
→ Returns: DIR, use Form API (f.xxx)

User: "What API should I use in this grid?"
→ file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Grid\\Detail.xml'
→ Returns: GridDetail, use both Grid API (g.xxx) and Form API (f.xxx), MUST get parent form

The tool will:
1. Analyze file type from path and content
2. Detect grid subtype if applicable
3. Return which API(s) to use
4. List critical rules to follow
5. Provide context-specific recommendations
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to XML file (recommended)",
                            },
                            "xml_content": {
                                "type": "string",
                                "description": "XML content (fallback if file_path not available)",
                            },
                        },
                    },
                ),
                Tool(
                    name="get_api_help",
                    description="""[KB] Get FastBusiness API reference

Get detailed API reference for Form API (f.xxx) or Grid API (g.xxx).

EXAMPLES:
User: "How do I get a field value?"
→ api_type='form', category='value_operations', operation='get_item_value'
→ Returns: f.getItemValue(name) with examples and anti-patterns

User: "Show me Grid API for getting cell values"
→ api_type='grid', category='cell_operations', operation='get_item_value'
→ Returns: g._getItemValue(row, col) with examples

User: "Show all Form API"
→ api_type='form'
→ Returns: Complete Form API reference

The tool will:
1. Return API syntax, description, parameters
2. Show usage examples
3. Highlight anti-patterns to avoid
4. Provide context-specific notes
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "api_type": {
                                "type": "string",
                                "description": "'form' or 'grid'",
                            },
                            "category": {
                                "type": "string",
                                "description": "API category (e.g., 'value_operations', 'cell_operations') - optional",
                            },
                            "operation": {
                                "type": "string",
                                "description": "Specific operation name (e.g., 'get_item_value') - optional",
                            },
                        },
                        "required": ["api_type"],
                    },
                ),
                Tool(
                    name="generate_code_from_pattern",
                    description="""⚡ Generate JavaScript code from pattern

Generate code from common patterns with variable substitution.

AVAILABLE PATTERNS:
- form_init_new: Initialize form with default values
- form_field_onchange: Field onChange handler
- form_load_data_onchange: Load data from server on field change
- form_calculate_field: Calculate field value
- grid_detail_init: Initialize Grid Detail with calculations
- grid_detail_cell_onchange: Grid Detail cell onChange
- grid_detail_add_row_from_form: Add grid row from form
- grid_view_load: Grid View load handler
- lookup_reload_on_filter_change: Reload lookup when filter changes

EXAMPLES:
User: "Generate onChange handler for ma_kh field"
→ pattern_name='form_field_onchange'
→ variables={'field_name': 'ma_kh', 'logic': '// Load customer data'}
→ file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml'

User: "Generate Grid Detail initialization"
→ pattern_name='grid_detail_init'
→ variables={'grid_name': 'GridAPDetail', 'calculations': 'tien: "[tien]:=[so_luong]*[gia]"'}

The tool will:
1. Load pattern template from knowledge base
2. Substitute variables in template
3. Validate context compatibility
4. Return ready-to-use JavaScript code
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern_name": {
                                "type": "string",
                                "description": "Pattern name (e.g., 'form_init_new', 'grid_detail_init')",
                            },
                            "variables": {
                                "type": "object",
                                "description": "Variables for template substitution (e.g., {'field_name': 'ma_kh'})",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Current file path for context detection (optional)",
                            },
                            "xml_content": {
                                "type": "string",
                                "description": "XML content for context detection (optional)",
                            },
                        },
                        "required": ["pattern_name"],
                    },
                ),
                Tool(
                    name="search_patterns",
                    description="""🔎 Search code patterns

Search for patterns by query, context, or get patterns appropriate for current file.

EXAMPLES:
User: "Show me patterns for this file"
→ file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml'
→ Returns: Form patterns (init, onchange, calculate, etc.)

User: "Show me grid patterns"
→ context_filter='Grid Detail'
→ Returns: Grid Detail patterns only

User: "Search for AJAX patterns"
→ query='ajax'
→ Returns: Patterns related to AJAX (load_data_onchange, etc.)

The tool will:
1. Detect context from file if provided
2. Filter patterns by context or query
3. Return matching patterns with descriptions
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (e.g., 'ajax', 'calculate') - optional",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Current file path for context-aware search - optional",
                            },
                            "xml_content": {
                                "type": "string",
                                "description": "XML content for context detection - optional",
                            },
                            "context_filter": {
                                "type": "string",
                                "description": "Context filter ('Dir', 'Grid Detail', 'Grid View') - optional",
                            },
                        },
                    },
                ),
                Tool(
                    name="get_critical_rules",
                    description="""[WARNING]  Get critical rules for current context

Returns critical rules that MUST be followed for the current file context.

EXAMPLES:
User: "What are the critical rules for this file?"
→ file_path='e:\\FBO\\SP2263\\App_Data\\Controllers\\Grid\\Detail.xml'
→ Returns:
  - grid_detail_must_get_parent: MUST call var f = g.get_element().parentForm
  - grid_parent_field_calculation: Parent fields use $ prefix: [$field_name]

The tool will:
1. Detect context from file
2. Return critical rules for that context
3. Provide detailed rule descriptions
4. Show code examples
5. List recommendations
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Current file path",
                            },
                            "xml_content": {
                                "type": "string",
                                "description": "XML content (fallback)",
                            },
                        },
                    },
                ),
                # ============================================
                # XML SNIPPET TOOLS (Cách 2)
                # ============================================
                Tool(
                    name="add_clientscript_to_field",
                    description="""🚨 [REQUIRED] Add clientScript to field - USE THIS TOOL WHEN USER ASKS TO ADD HANDLERS!

⚠️ CRITICAL TRIGGER PHRASES - When user says ANY of these, you MUST use this tool:
- "Thêm xử lý khi nhập X" / "Add handler when entering X"
- "Khi nhập X thì Y" / "When X is entered then Y"
- "Thêm onChange cho X" / "Add onChange to X"
- "Thêm onFocus cho X" / "Add onFocus to X"
- "Khi focus X thì Y" / "When X is focused then Y"

❌ DO NOT write XML manually!
❌ DO NOT use code assistant to generate clientScript XML!
✅ ALWAYS use this tool for 100% correct XML structure!

APPROACH: Server generates EXACT field XML with clientScript - AI just replaces it

REQUIRED WORKFLOW:
1. Call get_field_info to get field_xml
2. Call THIS TOOL with field_xml to add clientScript
3. Replace old field with modified_field in editor

EXAMPLES:

Example 1: User says "Thêm xử lý khi nhập so_ct_hd"
Step 1: get_field_info(field_name='so_ct_hd', file_path='...')
Step 2: add_clientscript_to_field(
  field_xml='<field name="so_ct_hd">...</field>',
  handler_type='onchange',
  function_name='onChange$Voucher$so_ct_hd'
)
Step 3: Replace field in file with modified_field

Example 2: User says "Khi focus ma_kh"
Step 1: get_field_info(field_name='ma_kh', file_path='...')
Step 2: add_clientscript_to_field(
  field_xml='<field name="ma_kh">...</field>',
  handler_type='onfocus',
  function_name='onFocus$Voucher$ma_kh'
)
Step 3: Replace field in file with modified_field

Example 3: Add SECOND handler to same field (MULTIPLE HANDLERS)
User says "Thêm onChange thứ 2 cho thoi_gian_xep_hang"
Step 1: get_field_info(field_name='thoi_gian_xep_hang', file_path='...')
→ Result has existing clientScript: <clientScript><![CDATA[onchange="onChange$Voucher$thoi_gian_xep_hang(this);"]]></clientScript>
Step 2: add_clientscript_to_field(
  field_xml='<field name="thoi_gian_xep_hang">...<clientScript>...</clientScript></field>',
  handler_type='onchange',
  function_name='onChange$Voucher$thoi_gian_xep_hang2'
)
→ Server APPENDS function with semicolon:
  <clientScript><![CDATA[onchange="onChange$Voucher$thoi_gian_xep_hang(this);onChange$Voucher$thoi_gian_xep_hang2(this);"]]></clientScript>
Step 3: Replace field in file with modified_field

Example 4: Add DIFFERENT handler type (onFocus to field with onChange)
User says "Thêm onFocus cho field đã có onChange"
→ Server adds new attribute: onchange="func1(this);" onfocus="func2(this);"

MULTIPLE HANDLERS SUPPORT:
✅ Same handler type (onChange + onChange) → Appends with semicolon
✅ Different handler type (onChange + onFocus) → Adds new attribute
✅ Always preserves existing handlers

FUNCTION NAMING:
- DIR file onChange: onChange$Voucher$field_name
- DIR file onFocus: onFocus$Voucher$field_name
- GRID onChange: onChange$Grid$field_name
- FILTER onChange: onChange$Filter$field_name
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "field_xml": {
                                "type": "string",
                                "description": "Original field XML (from get_field_info tool)",
                            },
                            "handler_type": {
                                "type": "string",
                                "description": "Handler type: 'onchange' or 'onfocus'",
                            },
                            "function_name": {
                                "type": "string",
                                "description": "Function name (e.g., 'onChange$Voucher$so_ct_hd')",
                            },
                        },
                        "required": ["field_xml", "handler_type", "function_name"],
                    },
                ),
                Tool(
                    name="add_function_to_script",
                    description="""🚨 [REQUIRED] Add JavaScript function to script section - MUST USE after add_clientscript_to_field!

⚠️ CRITICAL: After using add_clientscript_to_field, you MUST use this tool to add the JavaScript function!

❌ DO NOT write function code manually in XML!
❌ DO NOT insert function outside CDATA!
✅ ALWAYS use this tool to ensure function goes INSIDE CDATA!

APPROACH: Server generates EXACT CDATA snippet with function - AI finds and replaces pattern

REQUIRED WORKFLOW (Step 2 of adding handlers):
1. You already called add_clientscript_to_field (Step 1)
2. Now generate the JavaScript function code
3. Call THIS TOOL with function_code
4. Find pattern "    </text>\\n</script>" in file
5. Replace it with function_snippet from tool result

WHY THIS TOOL IS CRITICAL:
- Ensures function is INSIDE CDATA (not outside)
- Ensures function is BEFORE </text> closing tag
- Server wraps function correctly with CDATA tags
- 100% correct XML structure guaranteed

EXAMPLE:

User: "Khi nhập so_ct_hd thì gán so_seri_hd = '123455'"

After Step 1 (add_clientscript_to_field), now Step 2:

1. Generate function code:
```javascript
function onChange$Voucher$so_ct_hd(sender) {
    var f = sender.parentForm;
    if (f._action === 'View') return;
    f.setItemValue("so_seri_hd", "123455");
}
```

2. Call add_function_to_script(function_code=...)

3. Server returns function_snippet:
```xml
<![CDATA[
function onChange$Voucher$so_ct_hd(sender) {
    var f = sender.parentForm;
    if (f._action === 'View') return;
    f.setItemValue("so_seri_hd", "123455");
}
]]>
    </text>
</script>
```

4. Find "    </text>\\n</script>" in file

5. Replace with function_snippet

RESULT: ✓ Function INSIDE CDATA ✓ BEFORE </text> ✓ Zero errors

IMPORTANT:
- Always call this AFTER add_clientscript_to_field
- Search pattern: "    </text>\\n</script>" (4 spaces before </text>)
- Server automatically wraps function in CDATA
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "function_code": {
                                "type": "string",
                                "description": "Complete JavaScript function code",
                            },
                        },
                        "required": ["function_code"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "generate_field_from_lmdb":
                    # Auto-detect context type from file_path (preferred) or xml_content
                    file_path = arguments.get('file_path', '')
                    xml_content = arguments.get('xml_content', '')

                    # Always ensure context_type is set (default to DIR)
                    if 'context_type' not in arguments:
                        arguments['context_type'] = 'DIR'

                    if file_path or xml_content:
                        # Priority 1: Use file_path for path-based detection (most accurate)
                        if file_path:
                            detected_context = self._detect_context_type_from_path(file_path, xml_content)
                        # Priority 2: Use xml_content for content-based detection (fallback)
                        else:
                            detected_context = self._detect_context_type_from_xml(xml_content)

                        # Override context_type with detected value
                        if detected_context != 'UNKNOWN':
                            arguments['context_type'] = detected_context
                            logger.info(f"Auto-detected context type: {detected_context} from file_path: {file_path}")
                        else:
                            # Keep existing context_type (already defaulted to DIR above)
                            logger.warning(f"Cannot detect context from path, using: {arguments['context_type']}")

                    # Remove file_path and xml_content from arguments (not needed by execute)
                    arguments.pop('file_path', None)
                    arguments.pop('xml_content', None)
                    
                    # Log database info for debugging
                    db_path = str(self.lmdb_field_tool.lmdb.db_path.absolute()) if self.lmdb_field_tool.lmdb else "N/A"
                    db_fields = self.lmdb_field_tool.lmdb.count_fields(arguments.get('context_type', 'DIR')) if self.lmdb_field_tool.lmdb else 0
                    logger.info(f"[SEARCH] Database: {db_path} ({db_fields} fields in {arguments.get('context_type', 'DIR')})")

                    # Log final arguments for debugging
                    logger.info(f"Calling tool.execute() with arguments: field_name={arguments.get('field_name')}, context_type={arguments.get('context_type')}, lookup_type={arguments.get('lookup_type')}")
                    result = await self.lmdb_field_tool.execute(arguments)
                    
                    if result['success']:
                        # Format success response
                        response = f"""[OK] Field generated from {result['source']}

Field Name: {result['field_name']}
Header: {result['header']}
Context: {arguments.get('context_type', 'N/A')}

XML Definition:
{result['xml']}

[DB] Database: {result.get('database_path', db_path)}"""
                    else:
                        # Format error response
                        response = f"[ERROR] {result['error']}"

                        # Add database diagnostics if database is empty
                        if result.get('database_empty'):
                            response += f"\n\n[DB] Database path: {result['database_path']}"
                            response += f"\n\n[INFO] To fix this issue:"
                            response += f"\n   1. Run: python scripts/import_fields_to_lmdb.py --xml-dir <path_to_xml_dir>"
                            response += f"\n   2. Or specify absolute database path in config.yaml"
                            response += f"\n   3. Make sure both VS Code and Cursor use same working directory"

                        # Show similar fields if available
                        if 'similar_fields' in result:
                            similar = '\n'.join([f"  - {f['field_name']}: {f['header']}" for f in result['similar_fields'][:5]])
                            response += f"\n\n[INFO] Similar fields found:\n{similar}"
                        if 'suggestion' in result:
                            response += f"\n\n{result['suggestion']}"

                        # Show database stats if not empty
                        if 'database_fields_count' in result:
                            response += f"\n\n[STATS] Database has {result['database_fields_count']} fields in {result['context_type']}"

                        # Always show database path for debugging (even if not empty)
                        response += f"\n\n[DB] Database: {result.get('database_path', db_path)}"

                    return [TextContent(type="text", text=response)]

                elif name == "search_lmdb_fields":
                    pattern = arguments["pattern"]
                    context_type = arguments["context_type"]
                    limit = arguments.get("limit", 20)

                    result = self.lmdb_field_tool.search_fields(context_type, pattern, limit)

                    if result['success']:
                        if result['count'] == 0:
                            response = f"No fields found matching '{pattern}' in {context_type}"
                        else:
                            fields_list = '\n'.join([
                                f"  {i+1}. {f['field_name']:30} | {f['header']:40} | {f['type']}"
                                for i, f in enumerate(result['results'])
                            ])
                            response = f"""Found {result['count']} fields matching '{pattern}' in {context_type}:

{fields_list}"""
                    else:
                        response = f"[ERROR] Search failed: {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "lmdb_database_stats":
                    result = self.lmdb_field_tool.get_database_stats()

                    if result['success']:
                        stats = result['statistics']
                        stats_text = '\n'.join([
                            f"  {context:20} : {count:,} fields"
                            for context, count in stats.items() if context != 'total' and count > 0
                        ])
                        response = f"""[STATS] LMDB Field Database Statistics

Database Path: {result['database_path']}

{stats_text}

Total: {stats['total']:,} fields"""
                    else:
                        response = "[ERROR] Failed to get database statistics"

                    return [TextContent(type="text", text=response)]

                elif name == "generate_sql_for_fields":
                    result = await self.sql_gen_tool.execute(arguments)

                    if result['success']:
                        # Format success response
                        field_list = ', '.join(result['field_names'])
                        table_list = ', '.join(result['tables'])

                        response = f"""[OK] SQL generated for fields: {field_list}

📋 Target tables: {table_list}
[STATS] Commands generated: {result['command_count']}

SQL Script:
```sql
{result['sql_script']}
```

[WARNING]  IMPORTANT:
1. Copy và chạy SQL trong SQL Server Management Studio
2. Chạy SQL trước khi deploy XML file lên server
3. Kiểm tra partition suffix ($) trong table names"""

                        if result.get('master_tables'):
                            response += f"\n\n🗂️  Master tables: {', '.join(result['master_tables'])}"

                    else:
                        response = f"[ERROR] {result['error']}"

                    return [TextContent(type="text", text=response)]

                # ============================================
                # KNOWLEDGE BASE SYSTEM TOOLS HANDLERS
                # ============================================
                elif name == "detect_context_from_file":
                    file_path = arguments.get('file_path')
                    xml_content = arguments.get('xml_content')

                    result = self.code_assistant.detect_context(file_path, xml_content)

                    if result.get('success'):
                        response = result.get('summary', '')
                    else:
                        response = f"[ERROR] {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "get_api_help":
                    api_type = arguments.get('api_type')
                    category = arguments.get('category')
                    operation = arguments.get('operation')

                    result = self.code_assistant.get_api_help(api_type, operation, category)

                    if result.get('success'):
                        if 'formatted' in result:
                            response = result['formatted']
                        else:
                            # Return full API structure
                            import json
                            response = f"[KB] {api_type.upper()} API Reference:\n\n```json\n{json.dumps(result['api'], indent=2)}\n```"
                    else:
                        response = f"[ERROR] {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "generate_code_from_pattern":
                    pattern_name = arguments.get('pattern_name')
                    variables = arguments.get('variables', {})
                    file_path = arguments.get('file_path')
                    xml_content = arguments.get('xml_content')

                    result = self.code_assistant.generate_code(pattern_name, variables, file_path, xml_content)

                    if result.get('success'):
                        response = f"""[OK] Code generated from pattern: {pattern_name}

Pattern: {result.get('description', '')}
Context: {result.get('context', '')}
Location: {result.get('location', '')}

Generated Code:
```javascript
{result.get('code', '')}
```"""

                        if result.get('warnings'):
                            warnings_text = '\n'.join(result['warnings'])
                            response += f"\n\n[WARNING]  Warnings:\n{warnings_text}"
                    else:
                        response = f"[ERROR] {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "search_patterns":
                    query = arguments.get('query')
                    file_path = arguments.get('file_path')
                    xml_content = arguments.get('xml_content')
                    context_filter = arguments.get('context_filter')

                    result = self.code_assistant.search_patterns(query, file_path, xml_content, context_filter)

                    if result.get('success'):
                        patterns = result.get('patterns', [])

                        if len(patterns) == 0:
                            response = "No patterns found matching criteria"
                        else:
                            pattern_list = []
                            for i, pattern in enumerate(patterns, 1):
                                pattern_list.append(f"{i}. **{pattern['name']}**")
                                pattern_list.append(f"   Description: {pattern.get('description', '')}")
                                pattern_list.append(f"   Context: {pattern.get('context', '')}")
                                pattern_list.append(f"   Location: {pattern.get('location', '')}")
                                pattern_list.append("")

                            header = f"Found {len(patterns)} patterns"
                            if result.get('context'):
                                header += f" for {result['context']}"
                            if result.get('filter'):
                                header += f" (filter: {result['filter']})"
                            if result.get('query'):
                                header += f" (query: '{result['query']}')"

                            response = f"🔎 {header}\n\n" + '\n'.join(pattern_list)
                    else:
                        response = f"[ERROR] {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "get_critical_rules":
                    file_path = arguments.get('file_path')
                    xml_content = arguments.get('xml_content')

                    result = self.code_assistant.get_critical_rules(file_path, xml_content)

                    if result.get('success'):
                        file_type = result.get('file_type', 'UNKNOWN')
                        grid_subtype = result.get('grid_subtype')
                        critical_rules = result.get('critical_rules', [])
                        rule_details = result.get('rule_details', [])
                        recommendations = result.get('recommendations', [])

                        response = f"[WARNING]  **Critical Rules for {file_type}"
                        if grid_subtype:
                            response += f" ({grid_subtype})"
                        response += ":**\n\n"

                        if not critical_rules:
                            response += "No critical rules for this context.\n"
                        else:
                            for rule in rule_details:
                                rule_id = rule.get('rule_id', '')
                                priority = rule.get('priority', '')
                                context = rule.get('context', '')

                                response += f"🔴 **{rule_id}** (Priority: {priority})\n"
                                response += f"Context: {context}\n\n"

                                if rule.get('must_do'):
                                    response += "Must do:\n"
                                    for step in rule['must_do']:
                                        response += f"  {step.get('step', '')}. {step.get('code', '')}\n"
                                        response += f"     Reason: {step.get('reason', '')}\n"
                                    response += "\n"

                                if rule.get('example'):
                                    response += f"Example:\n```javascript\n{rule['example']}\n```\n\n"

                        if recommendations:
                            response += "\n[INFO] **Recommendations:**\n"
                            for rec in recommendations:
                                response += f"  {rec}\n"
                    else:
                        response = f"[ERROR] {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                # ============================================
                # XML SNIPPET TOOLS HANDLERS (Cách 2)
                # ============================================
                elif name == "add_clientscript_to_field":
                    field_xml = arguments.get('field_xml')
                    handler_type = arguments.get('handler_type')
                    function_name = arguments.get('function_name')

                    if not field_xml or not handler_type or not function_name:
                        return [TextContent(type="text", text="[ERROR] field_xml, handler_type, and function_name are required")]

                    result = self.xml_snippet.add_clientscript_to_field(field_xml, handler_type, function_name)

                    if result.get('success'):
                        response = f"""[OK] Generated field XML with clientScript

[ORIGINAL FIELD]
```xml
{result.get('original_field', '')}
```

[MODIFIED FIELD]
```xml
{result.get('modified_field', '')}
```

[INSTRUCTIONS]
{result.get('instructions', '')}
"""
                    else:
                        response = f"[ERROR] {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "add_function_to_script":
                    function_code = arguments.get('function_code')

                    if not function_code:
                        return [TextContent(type="text", text="[ERROR] function_code is required")]

                    result = self.xml_snippet.add_function_to_script(function_code)

                    if result.get('success'):
                        response = f"""[OK] Generated function snippet

[FUNCTION SNIPPET]
```xml
{result.get('function_snippet', '')}
```

[SEARCH PATTERN]
```
{result.get('search_pattern', '')}
```

[INSTRUCTIONS]
{result.get('instructions', '')}
"""
                    else:
                        response = f"[ERROR] {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    def _detect_context_type_from_path(self, file_path: str, xml_content: str = '') -> str:
        """
        Detect context type from file path - SIMPLE LOGIC per user requirement:
        - Path contains \\Dir\\ → DIR
        - Path contains \\Filter\\ → FILTER (then check operation attribute)
        - Path contains \\Grid\\ → GRID (then check allowSorting/allowFilter)

        Args:
            file_path: File path
            xml_content: Optional XML content for subtype detection

        Returns:
            Context type: DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT, or UNKNOWN
        """
        # Normalize path separators
        normalized_path = file_path.replace('/', '\\')

        # Simple folder name check (case-insensitive)
        if '\\Dir\\' in normalized_path or '\\dir\\' in normalized_path:
            return 'DIR'

        elif '\\Filter\\' in normalized_path or '\\filter\\' in normalized_path:
            # Check if any field has 'operation' attribute
            if xml_content:
                has_operation = bool(re.search(r'<field[^>]*\boperation\s*=', xml_content, re.IGNORECASE))
                return 'FILTER_VOUCHER' if has_operation else 'FILTER_NORMAL'
            else:
                return 'FILTER_NORMAL'  # Default to FILTER_NORMAL if no content

        elif '\\Grid\\' in normalized_path or '\\grid\\' in normalized_path:
            # Check if any field has 'allowSorting' or 'allowFilter'
            if xml_content:
                has_sorting = bool(re.search(r'<field[^>]*\ballowSorting\s*=', xml_content, re.IGNORECASE))
                has_filter = bool(re.search(r'<field[^>]*\ballowFilter\s*=', xml_content, re.IGNORECASE))
                return 'GRID_VIEW' if (has_sorting or has_filter) else 'GRID_INPUT'
            else:
                return 'GRID_INPUT'  # Default to GRID_INPUT if no content

        return 'UNKNOWN'

    def _detect_context_type_from_xml(self, xml_content: str) -> str:
        """
        Detect context type from XML content using regex (fallback method)

        Args:
            xml_content: XML file content

        Returns:
            Context type: DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT, or UNKNOWN
        """
        # Check for Dir (has <dir> tag)
        if re.search(r'<dir\b', xml_content, re.IGNORECASE):
            # Check if it's a filter (has XMLWhenFilterLoading)
            if 'XMLWhenFilterLoading' in xml_content:
                # Check if any field has 'operation' attribute
                has_operation = bool(re.search(r'<field[^>]*\boperation\s*=', xml_content, re.IGNORECASE))
                return 'FILTER_VOUCHER' if has_operation else 'FILTER_NORMAL'
            else:
                return 'DIR'

        # Check for Grid (has <grid> tag)
        elif re.search(r'<grid\b', xml_content, re.IGNORECASE):
            # Check if any field has 'allowSorting' or 'allowFilter'
            has_sorting = bool(re.search(r'<field[^>]*\ballowSorting\s*=', xml_content, re.IGNORECASE))
            has_filter = bool(re.search(r'<field[^>]*\ballowFilter\s*=', xml_content, re.IGNORECASE))
            return 'GRID_VIEW' if (has_sorting or has_filter) else 'GRID_INPUT'

        return 'UNKNOWN'

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting FastBusiness MCP Server (LMDB Field Generation + AI Code Assistant)...")

        # Run server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    server = FastBusinessMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
