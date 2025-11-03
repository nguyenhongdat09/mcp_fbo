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
from .tools.xml_handler_tool import XMLHandlerTool
from .utils.logger import setup_logger 
from .utils.file_utils import read_file
  
logger = setup_logger(__name__) 


class FastBusinessMCPServer:
    """FastBusiness MCP Server - LMDB Field Generation + AI Code Assistant."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize MCP server."""
        self.config = self._load_config(config_path)
        self.server = Server("fastbusiness-mcp-server")

        # Get LMDB database path from config (with fallback)
        lmdb_path = self.config.get("database", {}).get("lmdb_path", "data/fields_lmdb")

        # Convert to absolute path if relative
        from pathlib import Path
        import os
        if not Path(lmdb_path).is_absolute():
            # Use config file location as base directory
            config_dir = Path(config_path).parent if config_path != "config.yaml" else Path.cwd()
            lmdb_path = str(config_dir / lmdb_path)

        logger.info(f"Using LMDB database path: {lmdb_path}")

        # Initialize LMDB field tool
        self.lmdb_field_tool = GenerateFieldFromLMDBTool(db_path=lmdb_path)

        # Initialize SQL generation tool
        self.sql_gen_tool = GenerateSQLForFieldsTool()

        # Initialize Code Assistant (Knowledge Base System)
        self.code_assistant = CodeAssistantTool(knowledge_base_dir="knowledge_base")

        # Initialize XML Handler Tool
        self.xml_handler = XMLHandlerTool(knowledge_base_dir="knowledge_base")

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
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read resource content."""
            try:
                if uri == "fastbusiness://docs/quick-reference":
                    return read_file(self.config["data"]["quick_reference"])
                elif uri == "fastbusiness://docs/xml-summary":
                    return read_file(self.config["data"]["xml_summary"])
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
                    description="""⭐ Generate field from LMDB database - USE THIS when user asks to add fields!

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
                    description="""⭐ Generate SQL commands for adding fields to database tables

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
                    description="""🔍 Detect context from FastBusiness XML file

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
                    description="""📚 Get FastBusiness API reference

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
                    description="""⚠️  Get critical rules for current context

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
                # XML HANDLER TOOLS
                # ============================================
                Tool(
                    name="add_onchange_handler",
                    description="""✨ Add onChange handler to field in FastBusiness XML file

⚠️  CRITICAL: Use this tool when user asks to add onChange handler!
DON'T read file or write code manually - this tool does everything automatically.

What this tool does:
1. ✅ Auto-detects file type (Dir/Grid/Filter)
2. ✅ Finds field in XML
3. ✅ Adds <clientScript> to field definition
4. ✅ Generates correct function name (onChange$Voucher$field_name)
5. ✅ Uses correct API based on context (f.xxx or g.xxx)
6. ✅ Inserts function into <script> section

EXAMPLES:
User: "Thêm onchange cho ma_kh thì console.log(1)"
→ field_name='ma_kh', handler_code='console.log(1);'

User: "Khi nhập số lượng thì tính tiền = số lượng * giá"
→ field_name='so_luong'
→ handler_code='var sl = f.getItemValue("so_luong"); var gia = f.getItemValue("gia"); f.setItemValue("tien", sl * gia);'

Tool will:
1. Detect Dir/Grid context
2. Add: <clientScript><![CDATA[onchange="onChange$Voucher$ma_kh(this);"]]></clientScript>
3. Generate: function onChange$Voucher$ma_kh(sender) { var f = sender.parentForm; ... }
4. Insert into <script> section
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to XML file (REQUIRED)",
                            },
                            "field_name": {
                                "type": "string",
                                "description": "Field name to add handler to (e.g., 'ma_kh', 'so_luong')",
                            },
                            "handler_code": {
                                "type": "string",
                                "description": "JavaScript code for handler body (optional - will generate skeleton if not provided)",
                            },
                        },
                        "required": ["file_path", "field_name"],
                    },
                ),
                Tool(
                    name="add_onfocus_handler",
                    description="""✨ Add onFocus handler to field in FastBusiness XML file

⚠️  CRITICAL: Use this tool when user asks to add onFocus handler!
DON'T read file or write code manually - this tool does everything automatically.

EXAMPLES:
User: "Khi focus mã khách thì load dữ liệu"
→ field_name='ma_kh'
→ handler_code='f.request("GetCustomer", "GetCustomer", ["ma_kh"], sender);'

Tool will:
1. Detect context
2. Add clientScript to field
3. Generate correct function
4. Insert into script section
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to XML file (REQUIRED)",
                            },
                            "field_name": {
                                "type": "string",
                                "description": "Field name to add handler to",
                            },
                            "handler_code": {
                                "type": "string",
                                "description": "JavaScript code for handler body (optional)",
                            },
                        },
                        "required": ["file_path", "field_name"],
                    },
                ),
                Tool(
                    name="add_form_lifecycle_handler",
                    description="""✨ Add form lifecycle handler (active$Form$, etc.)

⚠️  CRITICAL: Use this tool when user asks to add form lifecycle handler!
DON'T read file or write code manually - this tool does everything automatically.

EXAMPLES:
User: "Khi load form mới thì gán ngày = hôm nay"
→ lifecycle='active'
→ handler_code='if (f._action === "New") { f.setItemValue("ngay_ct", new Date()); }'

Supported lifecycles:
- active: When form loads (active$Form$)
- beforeSave: Before form saves
- afterSave: After form saves

Tool will:
1. Generate lifecycle function
2. Insert into script section
""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to XML file (REQUIRED)",
                            },
                            "lifecycle": {
                                "type": "string",
                                "description": "Lifecycle event: 'active', 'beforeSave', 'afterSave'",
                            },
                            "handler_code": {
                                "type": "string",
                                "description": "JavaScript code for handler body",
                            },
                        },
                        "required": ["file_path", "lifecycle", "handler_code"],
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
                    
                    # Log final arguments for debugging
                    logger.info(f"Calling tool.execute() with arguments: field_name={arguments.get('field_name')}, context_type={arguments.get('context_type')}, lookup_type={arguments.get('lookup_type')}")
                    result = await self.lmdb_field_tool.execute(arguments)
                    
                    if result['success']:
                        # Format success response
                        response = f"""✅ Field generated from {result['source']}

Field Name: {result['field_name']}
Header: {result['header']}
Context: {arguments.get('context_type', 'N/A')}

XML Definition:
{result['xml']}"""
                    else:
                        # Format error response
                        response = f"❌ {result['error']}"

                        # Add database diagnostics if database is empty
                        if result.get('database_empty'):
                            response += f"\n\n📂 Database path: {result['database_path']}"
                            response += f"\n\n💡 To fix this issue:"
                            response += f"\n   1. Run: python scripts/import_fields_to_lmdb.py --xml-dir <path_to_xml_dir>"
                            response += f"\n   2. Or specify absolute database path in config.yaml"
                            response += f"\n   3. Make sure both VS Code and Cursor use same working directory"

                        # Show similar fields if available
                        if 'similar_fields' in result:
                            similar = '\n'.join([f"  - {f['field_name']}: {f['header']}" for f in result['similar_fields'][:5]])
                            response += f"\n\n💡 Similar fields found:\n{similar}"
                        if 'suggestion' in result:
                            response += f"\n\n{result['suggestion']}"

                        # Show database stats if not empty
                        if 'database_fields_count' in result:
                            response += f"\n\n📊 Database has {result['database_fields_count']} fields in {result['context_type']}"

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
                        response = f"❌ Search failed: {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "lmdb_database_stats":
                    result = self.lmdb_field_tool.get_database_stats()

                    if result['success']:
                        stats = result['statistics']
                        stats_text = '\n'.join([
                            f"  {context:20} : {count:,} fields"
                            for context, count in stats.items() if context != 'total' and count > 0
                        ])
                        response = f"""📊 LMDB Field Database Statistics

Database Path: {result['database_path']}

{stats_text}

Total: {stats['total']:,} fields"""
                    else:
                        response = "❌ Failed to get database statistics"

                    return [TextContent(type="text", text=response)]

                elif name == "generate_sql_for_fields":
                    result = await self.sql_gen_tool.execute(arguments)

                    if result['success']:
                        # Format success response
                        field_list = ', '.join(result['field_names'])
                        table_list = ', '.join(result['tables'])

                        response = f"""✅ SQL generated for fields: {field_list}

📋 Target tables: {table_list}
📊 Commands generated: {result['command_count']}

SQL Script:
```sql
{result['sql_script']}
```

⚠️  IMPORTANT:
1. Copy và chạy SQL trong SQL Server Management Studio
2. Chạy SQL trước khi deploy XML file lên server
3. Kiểm tra partition suffix ($) trong table names"""

                        if result.get('master_tables'):
                            response += f"\n\n🗂️  Master tables: {', '.join(result['master_tables'])}"

                    else:
                        response = f"❌ {result['error']}"

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
                        response = f"❌ {result.get('error', 'Unknown error')}"

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
                            response = f"📚 {api_type.upper()} API Reference:\n\n```json\n{json.dumps(result['api'], indent=2)}\n```"
                    else:
                        response = f"❌ {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "generate_code_from_pattern":
                    pattern_name = arguments.get('pattern_name')
                    variables = arguments.get('variables', {})
                    file_path = arguments.get('file_path')
                    xml_content = arguments.get('xml_content')

                    result = self.code_assistant.generate_code(pattern_name, variables, file_path, xml_content)

                    if result.get('success'):
                        response = f"""✅ Code generated from pattern: {pattern_name}

Pattern: {result.get('description', '')}
Context: {result.get('context', '')}
Location: {result.get('location', '')}

Generated Code:
```javascript
{result.get('code', '')}
```"""

                        if result.get('warnings'):
                            warnings_text = '\n'.join(result['warnings'])
                            response += f"\n\n⚠️  Warnings:\n{warnings_text}"
                    else:
                        response = f"❌ {result.get('error', 'Unknown error')}"

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
                        response = f"❌ {result.get('error', 'Unknown error')}"

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

                        response = f"⚠️  **Critical Rules for {file_type}"
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
                            response += "\n💡 **Recommendations:**\n"
                            for rec in recommendations:
                                response += f"  {rec}\n"
                    else:
                        response = f"❌ {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                # ============================================
                # XML HANDLER TOOLS HANDLERS
                # ============================================
                elif name == "add_onchange_handler":
                    file_path = arguments.get('file_path')
                    field_name = arguments.get('field_name')
                    handler_code = arguments.get('handler_code')

                    if not file_path or not field_name:
                        return [TextContent(type="text", text="❌ file_path and field_name are required")]

                    result = self.xml_handler.add_onchange_handler(file_path, field_name, handler_code)

                    if result.get('success'):
                        response = f"""✅ Đã thêm onChange handler cho field '{field_name}'

📝 Function name: {result.get('function_name', '')}

📝 Generated code:
```javascript
{result.get('generated_code', '')}
```

📁 File: {result.get('file_path', '')}

✨ Đã thêm vào XML:
1. Added <clientScript> to field definition
2. Generated function in <script> section
3. Used correct API based on context
"""
                    else:
                        response = f"❌ {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "add_onfocus_handler":
                    file_path = arguments.get('file_path')
                    field_name = arguments.get('field_name')
                    handler_code = arguments.get('handler_code')

                    if not file_path or not field_name:
                        return [TextContent(type="text", text="❌ file_path and field_name are required")]

                    result = self.xml_handler.add_onfocus_handler(file_path, field_name, handler_code)

                    if result.get('success'):
                        response = f"""✅ Đã thêm onFocus handler cho field '{field_name}'

📝 Function name: {result.get('function_name', '')}

📝 Generated code:
```javascript
{result.get('generated_code', '')}
```

📁 File: {result.get('file_path', '')}
"""
                    else:
                        response = f"❌ {result.get('error', 'Unknown error')}"

                    return [TextContent(type="text", text=response)]

                elif name == "add_form_lifecycle_handler":
                    file_path = arguments.get('file_path')
                    lifecycle = arguments.get('lifecycle')
                    handler_code = arguments.get('handler_code')

                    if not file_path or not lifecycle or not handler_code:
                        return [TextContent(type="text", text="❌ file_path, lifecycle, and handler_code are required")]

                    result = self.xml_handler.add_form_lifecycle_handler(file_path, lifecycle, handler_code)

                    if result.get('success'):
                        response = f"""✅ Đã thêm {lifecycle} lifecycle handler

📝 Function name: {result.get('function_name', '')}

📝 Generated code:
```javascript
{result.get('generated_code', '')}
```

📁 File: {result.get('file_path', '')}
"""
                    else:
                        response = f"❌ {result.get('error', 'Unknown error')}"

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
