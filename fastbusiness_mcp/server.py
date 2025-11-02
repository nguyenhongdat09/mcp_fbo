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
from .utils.logger import setup_logger
from .utils.file_utils import read_file

logger = setup_logger(__name__)


class FastBusinessMCPServer:
    """FastBusiness MCP Server - LMDB Field Generation."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize MCP server."""
        self.config = self._load_config(config_path)
        self.server = Server("fastbusiness-field-generator")

        # Initialize LMDB field tool
        self.lmdb_field_tool = GenerateFieldFromLMDBTool(db_path="data/fields_lmdb")

        # Initialize SQL generation tool
        self.sql_gen_tool = GenerateSQLForFieldsTool()

        # Register handlers
        self._register_resources()
        self._register_tools()

        logger.info("FastBusiness MCP Server (LMDB Field Generation) initialized")

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
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "generate_field_from_lmdb":
                    # Auto-detect context type from file_path (preferred) or xml_content
                    file_path = arguments.get('file_path', '')
                    xml_content = arguments.get('xml_content', '')

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
                            logger.info(f"Auto-detected context type: {detected_context}")
                        else:
                            # Fallback to DIR if detection fails
                            arguments['context_type'] = arguments.get('context_type', 'DIR')
                            logger.warning(f"Cannot detect context, using: {arguments['context_type']}")

                    # Remove file_path and xml_content from arguments (not needed by execute)
                    arguments.pop('file_path', None)
                    arguments.pop('xml_content', None)

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
                        if 'similar_fields' in result:
                            similar = '\n'.join([f"  - {f['field_name']}: {f['header']}" for f in result['similar_fields'][:5]])
                            response += f"\n\n💡 Similar fields found:\n{similar}"
                        if 'suggestion' in result:
                            response += f"\n\n{result['suggestion']}"

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
        logger.info("Starting FastBusiness MCP Server (LMDB Field Generation)...")

        # Run server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    server = FastBusinessMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
