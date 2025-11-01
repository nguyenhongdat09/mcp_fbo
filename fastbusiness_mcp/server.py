"""FastBusiness MCP Server - Main entry point."""

import asyncio
import yaml
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

from .analyzers.file_type_detector import FileTypeDetector
from .analyzers.language_detector import LanguageDetector
from .analyzers.sql_parser import SQLParser
from .validators.partition_validator import PartitionValidator
from .validators.result_access_validator import ResultAccessValidator
from .validators.parent_form_validator import ParentFormValidator
from .validators.lookup_validator import LookupValidator
from .generators.field_generator import FieldGenerator
from .generators.script_generator import ScriptGenerator
from .generators.command_generator import CommandGenerator
from .fixers.partition_fixer import PartitionFixer
from .fixers.result_access_fixer import ResultAccessFixer
from .tools.generate_field_from_lmdb import GenerateFieldFromLMDBTool
from .utils.logger import setup_logger
from .utils.file_utils import read_file

logger = setup_logger(__name__)


class FastBusinessMCPServer:
    """FastBusiness MCP Server."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize MCP server."""
        self.config = self._load_config(config_path)
        self.server = Server("fastbusiness-xml-context")

        # Initialize analyzers
        self.file_detector = FileTypeDetector()
        self.lang_detector = LanguageDetector()
        self.sql_parser = SQLParser()

        # Initialize validators
        self.partition_validator = PartitionValidator()
        self.result_validator = ResultAccessValidator()
        self.parent_validator = ParentFormValidator()
        self.lookup_validator = LookupValidator()

        # Initialize generators
        self.field_generator = FieldGenerator()
        self.script_generator = ScriptGenerator()
        self.command_generator = CommandGenerator()

        # Initialize fixers
        self.partition_fixer = PartitionFixer()
        self.result_fixer = ResultAccessFixer()

        # Initialize LMDB field tool
        self.lmdb_field_tool = GenerateFieldFromLMDBTool(db_path="data/fields_lmdb")

        # Register handlers
        self._register_resources()
        self._register_tools()

        logger.info("FastBusiness MCP Server initialized")

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
                },
                "validation": {"strict_mode": True, "auto_fix": False},
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
                    uri="fastbusiness://docs/partition-strategy",
                    name="Partition Strategy Guide",
                    mimeType="text/plain",
                    description="Complete guide for partition strategy (CRITICAL)",
                ),
                Resource(
                    uri="fastbusiness://docs/result-access",
                    name="Result Access Guide",
                    mimeType="text/plain",
                    description="Guide for accessing SQL results in JavaScript (CRITICAL)",
                ),
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read resource content."""
            if uri == "fastbusiness://docs/quick-reference":
                path = self.config["data"]["quick_reference"]
                content = read_file(path)
                if content:
                    return content
                # Fallback to ProjecInfomationRelative_2.txt
                return read_file("ProjecInfomationRelative_2.txt") or "Resource not found"

            elif uri == "fastbusiness://docs/xml-summary":
                path = self.config["data"]["xml_summary"]
                content = read_file(path)
                if content:
                    return content
                # Fallback to ProjecInfomationRelative_1.txt
                return read_file("ProjecInfomationRelative_1.txt") or "Resource not found"

            elif uri == "fastbusiness://docs/partition-strategy":
                return """# Partition Strategy (CRITICAL)

Table Structure: d91$202501 (prefix$YYYYMM)

## ALWAYS Use Placeholders:
- @@partition$current → 202501
- @@partition$previous → 202412
- @@master → m91$202501
- @@prime$partition$current → d91$202501
- @@prime$partition$previous → d91$202412

## NEVER Hardcode:
❌ select * from d91$202501
✅ select * from @@prime$partition$current

## Cross-Month Updates:
delete @@prime$partition$previous where stt_rec = @stt_rec
insert into @@prime$partition$current select * from @d91
"""

            elif uri == "fastbusiness://docs/result-access":
                return """# SQL Result Access (CRITICAL)

## Golden Rule: Access by INDEX, not property!

SQL: select ma_kh, ten_kh, dia_chi from dmkh

JavaScript:
✅ var maKH = result[0].Value;   // ma_kh (column 1)
✅ var tenKH = result[1].Value;  // ten_kh (column 2)
✅ var diaChi = result[2].Value; // dia_chi (column 3)

❌ var maKH = result[0].ma_kh;   // WRONG! Returns undefined

Column mapping = SELECT column order (0-based index)
"""

            return "Resource not found"

    def _register_tools(self) -> None:
        """Register MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="detect_file_type",
                    description="Detect FastBusiness XML file type (Filter, Dir, Grid View, Grid Detail)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "xml_content": {
                                "type": "string",
                                "description": "XML file content",
                            }
                        },
                        "required": ["xml_content"],
                    },
                ),
                Tool(
                    name="validate_partition",
                    description="Validate partition usage in SQL (CRITICAL - checks for hardcoded tables)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string", "description": "SQL code to validate"}
                        },
                        "required": ["sql"],
                    },
                ),
                Tool(
                    name="validate_result_access",
                    description="Validate SQL result access in JavaScript (CRITICAL)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "javascript": {
                                "type": "string",
                                "description": "JavaScript code to validate",
                            },
                            "sql_query": {
                                "type": "string",
                                "description": "Optional SQL query for column mapping",
                            },
                        },
                        "required": ["javascript"],
                    },
                ),
                Tool(
                    name="validate_xml_structure",
                    description="Validate entire XML file structure",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "xml_content": {
                                "type": "string",
                                "description": "XML content to validate",
                            }
                        },
                        "required": ["xml_content"],
                    },
                ),
                Tool(
                    name="fix_partition",
                    description="Automatically fix hardcoded partitions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string", "description": "SQL code to fix"}
                        },
                        "required": ["sql"],
                    },
                ),
                Tool(
                    name="fix_result_access",
                    description="Automatically fix result access patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "javascript": {
                                "type": "string",
                                "description": "JavaScript code to fix",
                            },
                            "sql_query": {
                                "type": "string",
                                "description": "Optional SQL query for column mapping",
                            },
                        },
                        "required": ["javascript"],
                    },
                ),
                Tool(
                    name="generate_field",
                    description="Generate field definition with optional lookup (manual)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Field name"},
                            "field_type": {
                                "type": "string",
                                "description": "Field type (String, DateTime, Decimal, etc.)",
                            },
                            "header_vi": {
                                "type": "string",
                                "description": "Vietnamese header",
                            },
                            "header_en": {"type": "string", "description": "English header"},
                            "is_lookup": {
                                "type": "boolean",
                                "description": "Whether this is a lookup field",
                            },
                            "lookup_controller": {
                                "type": "string",
                                "description": "Controller for lookup",
                            },
                        },
                        "required": ["name"],
                    },
                ),
                Tool(
                    name="generate_command",
                    description="Generate SQL command for events (Inserting, Updating, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "event": {
                                "type": "string",
                                "description": "Event type (Inserting, Updating, Deleting, Loading, Processing)",
                            },
                            "has_detail": {
                                "type": "boolean",
                                "description": "Whether voucher has detail table",
                            },
                        },
                        "required": ["event"],
                    },
                ),
                Tool(
                    name="generate_script",
                    description="Generate JavaScript script template",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "script_type": {
                                "type": "string",
                                "description": "Script type (form_init, grid_init, response_handler, etc.)",
                            },
                            "file_type": {
                                "type": "string",
                                "description": "File type (dir, grid_view, grid_detail)",
                            },
                        },
                        "required": ["script_type"],
                    },
                ),
                Tool(
                    name="generate_field_from_lmdb",
                    description="""⭐ Generate field from LMDB database - USE THIS when user asks to add fields!

AUTOMATIC CONTEXT DETECTION:
- Provide xml_content (current file) and tool will auto-detect context type
- Or manually specify context_type if known

LOOKUP TYPE PARSING (from Vietnamese):
- "thêm trường X" / "add field X" → lookup_type='default'
- "thêm trường X dạng lookup" / "dạng chọn lookup" → lookup_type='autocomplete' (default for lookup)
- "thêm trường X lookup chọn nhiều" / "chọn nhiều" → lookup_type='lookup'
- "thêm trường X autocomplete" → lookup_type='autocomplete'

EXAMPLES:
User: "Thêm trường mã khách hàng dạng lookup"
→ field_name='ma_kh', lookup_type='autocomplete', xml_content='<current file>'

User: "Thêm trường mã kh dạng lookup chọn nhiều"
→ field_name='ma_kh', lookup_type='lookup', xml_content='<current file>'

User: "Thêm số lượng"
→ field_name='so_luong', lookup_type='default', xml_content='<current file>'

The tool will:
1. Auto-detect context from xml_content (DIR/FILTER_VOUCHER/FILTER_NORMAL/GRID_VIEW/GRID_INPUT)
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
                            "xml_content": {
                                "type": "string",
                                "description": "Current XML file content for auto-detecting context type (recommended)",
                            },
                            "context_type": {
                                "type": "string",
                                "description": "Manual context type if xml_content not provided: DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT",
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
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "detect_file_type":
                    context = self.file_detector.detect(arguments["xml_content"])
                    return [
                        TextContent(
                            type="text",
                            text=f"""File Type: {context.file_type.value}
Table: {context.table_name or 'N/A'}
Has Partition: {context.has_partition}
Partition Field: {context.partition_field or 'N/A'}
Events: {', '.join([e.value for e in context.events])}""",
                        )
                    ]

                elif name == "validate_partition":
                    result = self.partition_validator.validate(arguments["sql"])
                    if result.is_valid:
                        return [TextContent(type="text", text="✅ No partition issues found")]
                    else:
                        errors = "\n".join(
                            [
                                f"Line {e.line}: {e.message}\n  Suggestion: {e.suggestion}"
                                for e in result.errors
                            ]
                        )
                        return [
                            TextContent(type="text", text=f"❌ Partition issues found:\n\n{errors}")
                        ]

                elif name == "validate_result_access":
                    result = self.result_validator.validate(
                        arguments["javascript"], arguments.get("sql_query")
                    )
                    if result.is_valid:
                        return [TextContent(type="text", text="✅ No result access issues found")]
                    else:
                        errors = "\n".join(
                            [
                                f"Line {e.line}: {e.message}\n  Suggestion: {e.suggestion}"
                                for e in result.errors
                            ]
                        )
                        return [
                            TextContent(
                                type="text", text=f"❌ Result access issues found:\n\n{errors}"
                            )
                        ]

                elif name == "validate_xml_structure":
                    # Comprehensive validation
                    xml_content = arguments["xml_content"]
                    results = []

                    # Detect file type
                    context = self.file_detector.detect(xml_content)
                    results.append(f"File Type: {context.file_type.value}")

                    # Validate lookup fields
                    lookup_result = self.lookup_validator.validate(xml_content)
                    if not lookup_result.is_valid:
                        results.append(
                            "\n❌ Lookup Validation Errors:\n"
                            + "\n".join([e.message for e in lookup_result.errors])
                        )

                    return [TextContent(type="text", text="\n".join(results))]

                elif name == "fix_partition":
                    fix_result = self.partition_fixer.fix(arguments["sql"])
                    if fix_result.success:
                        changes = "\n".join(fix_result.changes)
                        return [
                            TextContent(
                                type="text",
                                text=f"""✅ {fix_result.message}

Changes:
{changes}

Fixed Code:
{fix_result.fixed}""",
                            )
                        ]
                    else:
                        return [TextContent(type="text", text=fix_result.message)]

                elif name == "fix_result_access":
                    fix_result = self.result_fixer.fix(
                        arguments["javascript"], arguments.get("sql_query")
                    )
                    if fix_result.success:
                        changes = "\n".join(fix_result.changes)
                        return [
                            TextContent(
                                type="text",
                                text=f"""✅ {fix_result.message}

Changes:
{changes}

Fixed Code:
{fix_result.fixed}""",
                            )
                        ]
                    else:
                        return [TextContent(type="text", text=fix_result.message)]

                elif name == "generate_field":
                    field_xml = self.field_generator.generate_field(
                        name=arguments["name"],
                        field_type=arguments.get("field_type", "String"),
                        header_vi=arguments.get("header_vi", ""),
                        header_en=arguments.get("header_en", ""),
                        is_lookup=arguments.get("is_lookup", False),
                        lookup_controller=arguments.get("lookup_controller"),
                    )

                    # Add companion if lookup
                    if arguments.get("is_lookup"):
                        companion = self.field_generator.generate_companion_field(
                            arguments["name"]
                        )
                        field_xml += f"\n\n<!-- Companion field (required for lookup) -->\n{companion}"

                    return [TextContent(type="text", text=field_xml)]

                elif name == "generate_command":
                    event = arguments["event"]
                    has_detail = arguments.get("has_detail", False)

                    if event == "Inserting":
                        sql = self.command_generator.generate_inserting_command(
                            "m91", has_detail
                        )
                    elif event == "Updating":
                        sql = self.command_generator.generate_updating_command(has_detail)
                    elif event == "Deleting":
                        sql = self.command_generator.generate_deleting_command(has_detail)
                    elif event == "Loading":
                        sql = self.command_generator.generate_loading_command()
                    elif event == "Processing":
                        sql = self.command_generator.generate_processing_command("sp_Report")
                    else:
                        sql = "-- Command template\n"

                    return [TextContent(type="text", text=sql)]

                elif name == "generate_script":
                    script_type = arguments["script_type"]

                    if script_type == "form_init":
                        js = self.script_generator.generate_form_init()
                    elif script_type == "grid_init":
                        js = self.script_generator.generate_grid_detail_init()
                    elif script_type == "response_handler":
                        js = self.script_generator.generate_response_handler(
                            "ActionName", [(0, "column1"), (1, "column2")]
                        )
                    else:
                        js = "// Script template\n"

                    return [TextContent(type="text", text=js)]

                elif name == "generate_field_from_lmdb":
                    # Auto-detect context type from xml_content if provided
                    if 'xml_content' in arguments and arguments['xml_content']:
                        xml_content = arguments['xml_content']
                        detected_context = self._detect_context_type_from_xml(xml_content)

                        # Override context_type with detected value
                        if detected_context != 'UNKNOWN':
                            arguments['context_type'] = detected_context
                            logger.info(f"Auto-detected context type: {detected_context}")
                        else:
                            # Fallback to DIR if detection fails
                            arguments['context_type'] = arguments.get('context_type', 'DIR')
                            logger.warning(f"Cannot detect context, using: {arguments['context_type']}")

                    # Remove xml_content from arguments (not needed by execute)
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

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    def _detect_context_type_from_xml(self, xml_content: str) -> str:
        """
        Detect context type from XML content using regex

        Args:
            xml_content: XML file content

        Returns:
            Context type: DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT, or UNKNOWN
        """
        import re

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
        logger.info("Starting FastBusiness MCP Server...")

        # Run server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


def main():
    """Main entry point."""
    server = FastBusinessMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
