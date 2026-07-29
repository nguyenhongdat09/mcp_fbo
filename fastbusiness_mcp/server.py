"""FastBusiness MCP Server — SQL/XML tools + FBOGraph."""

import asyncio
import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .utils.logger import setup_logger

from queryDatabase import query_database
from queryDatabase.formatter import format_query_result
from find_entity_by_xml import get_xml_entities
from find_entity_by_xml.formatter import format_entity_result

from xml_fbograph.mcp_tools import (
    mcp_query_radar,
    mcp_search_nodes,
    mcp_get_related_nodes,
    mcp_query_node_details,
    mcp_read_local_file,
)

logger = setup_logger(__name__)


class FastBusinessMCPServer:
    """FastBusiness MCP Server — tools agents call via MCP."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.server = Server("fastbusiness-mcp-server")
        self._register_tools()
        logger.info("FastBusiness MCP Server (SQL/XML + FBOGraph) initialized")

    def _load_config(self, config_path: str) -> dict:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
            return {}

    def _register_tools(self) -> None:
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="query_database",
                    description="""Chạy SQL trên SQL Server — tự resolve connection từ file_path (Web.config).

query_type:
- 0: tên object (dmkh, ff_xxx) — lấy toàn bộ Script tạo Table/Proc/View. LƯU Ý: Kết quả đã tự động bao gồm toàn bộ Index (CREATE INDEX) và Khóa chính/Ngoại (CONSTRAINT) của Table. AI TUYỆT ĐỐI KHÔNG dùng type=1 để tự viết SQL tra cứu index của bảng nữa.
- 1: SQL ngắn inline (mặc định)
- 2: path file .sql — dùng cho script dài (tiết kiệm token)

db_type: app (mặc định) hoặc sys.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path file trong project FBO (XML/SQL) để resolve connection",
                            },
                            "query": {
                                "type": "string",
                                "description": "Object name (type=0), SQL inline (type=1), hoặc path .sql (type=2)",
                            },
                            "query_type": {
                                "type": "integer",
                                "description": "0=object, 1=SQL inline (default), 2=file .sql",
                                "default": 1,
                            },
                            "db_type": {
                                "type": "string",
                                "description": "app hoặc sys (default: app)",
                                "default": "app",
                            },
                            "max_rows": {
                                "type": "integer",
                                "description": "Giới hạn số dòng trả về (default: 20000)",
                            },
                        },
                        "required": ["file_path", "query"],
                    },
                ),
                Tool(
                    name="get_xml_entities",
                    description="""Đọc XML entity từ file_path . 
mode: content = nội dung entity; path = vị trí khai báo file:line (F12).
CHÚ Ý QUAN TRỌNG: Nếu file XML cần đọc không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Đường dẫn file XML (.xml, .f, ...)",
                            },
                            "entities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Danh sách tên entity (vd: XMLWhenVoucherInit, ListField)",
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["content", "path"],
                                "description": "content hoặc path để định nghĩa thông tin cần lấy",
                                "default": "content",
                            },
                        },
                        "required": ["file_path", "entities"],
                    },
                ),
                Tool(
                    name="query_radar",
                    description="""Query hoặc đọc schema live của đồ thị Kùzu Graph DB (Radar tool).
Dành cho việc truy vấn nâng cao hoặc các trường hợp ad-hoc.
Khuyến khích sử dụng search_nodes, get_related_nodes, query_node_details cho các câu hỏi thông thường.

CHÚ Ý: Lược đồ đồ thị (Schema), 10 Template Cypher chuẩn và các nguyên tắc cú pháp nghiêm ngặt đã được cung cấp sẵn trong Rules hệ thống (KùzuDB Cypher Query Principles & FBOGraph Schema Guide). 
Bạn BẮT BUỘC phải đọc và tuân thủ các quy tắc, chỉ chọn 1 trong 10 Template đó khi gọi cypher_query. Tuyệt đối KHÔNG tự sáng tác câu lệnh Cypher.

mode:
- query (mặc định): chạy cypher_query.
- schema: trả schema live XmlFile/Rel (Agent chỉ gọi để check cấu trúc thực tế khi cần).""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cypher_query": {
                                "type": "string",
                                "description": "Cypher cần chạy; bắt buộc khi mode=query, có thể để rỗng khi mode=schema",
                                "default": "",
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["query", "schema"],
                                "description": "query=chạy Cypher; schema=trả schema live + hướng dẫn",
                                "default": "query",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "Any XML file path in the project to resolve paths",
                            },
                        },
                        "required": ["reference_file"],
                    },
                ),
                Tool(
                    name="search_nodes",
                    description="""Tim kiem node/field/code trong du an FBO.
Synonym ASCII (uu tien, tranh loi encoding): truyen query KHONG DAU.
Vi du: 'giay bao no' -> CPTran; 'phieu chi' -> CDTran; 'dien giai' -> dien_giai; 'gia ban' -> gia2/gia_nt2; 'ten hang hoa' -> ten_vt.
Van chap nhan co dau (tu dong fold), nhung agent nen dung khong dau.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Keyword ASCII uu tien: 'giay bao no', 'phieu chi', 'dien giai', 'ma_kh', 'CPTran'",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "Any XML file path in the project to resolve paths",
                            },
                            "match_type": {
                                "type": "string",
                                "description": "Match type: 'all' (default), 'field', 'code', 'file'",
                            },
                            "folder_filter": {
                                "type": "string",
                                "description": "Folders to search, comma separated (e.g. 'Dir,Grid'). Defaults to Dir,Grid,Filter,Report,Lookup",
                            },
                            "limit": {
                                "type": "number",
                                "description": "Maximum results (default: 20)",
                            },
                        },
                        "required": ["query", "reference_file"],
                    },
                ),
                Tool(
                    name="get_related_nodes",
                    description="""Truy vấn các file/node liên quan đến file target.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "Target file relative path or basename (e.g., 'Dir/CPTran.xml', 'CPTax.xml')",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "Any XML file path in the project to resolve paths",
                            },
                            "mode": {
                                "type": "string",
                                "description": "Mode: 'navigate' (default), 'dependencies', 'dependents'",
                            },
                            "include_shared": {
                                "type": "boolean",
                                "description": "Include SHARED_INCLUDE relationships (default: false)",
                            },
                        },
                        "required": ["target", "reference_file"],
                    },
                ),
                Tool(
                    name="query_node_details",
                    description="""Truy vấn chi tiết thông tin cấu trúc bên trong của một file/controller.
CHÚ Ý QUAN TRỌNG: Nếu file XML cần truy vấn không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "Target file relative path or basename (e.g., 'Dir/CPTran.xml', 'CPTax.xml')",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "Any XML file path in the project to resolve paths",
                            },
                            "view": {
                                "type": "string",
                                "description": "View type: 'context' (default) or 'blocks'",
                            },
                        },
                        "required": ["target", "reference_file"],
                    },
                ),
                Tool(
                    name="read_local_file",
                    description="""Đọc trực tiếp nội dung file vật lý từ ổ cứng (đảm bảo dữ liệu mới nhất, không bị cache). Tool này hoạt động như một chiếc 'kính lúp' để xem nội dung code.
Các tính năng nổi bật:
1. Hỗ trợ đường dẫn tuyệt đối hoặc tương đối (tự động phân giải từ gốc dự án hoặc thư mục Controllers).
2. Tùy chọn đọc nội dung gốc (raw) hoặc nội dung phẳng (flat - tự động phân giải tất cả XML entities và includes).
3. Hỗ trợ tự động giải mã font Tiếng Việt Windows-1258.
4. Chặn truy cập (sandbox) ra ngoài thư mục dự án để đảm bảo an toàn.

CHÚ Ý QUAN TRỌNG: Nếu file cần đọc không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị.""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Relative path (e.g., 'Dir/CPTran.xml') or absolute path",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "Any XML file path in the project to resolve paths",
                            },
                            "read_option": {
                                "type": "integer",
                                "description": "1: Đọc theo nội dung gốc (mặc định), 2: Đọc theo nội dung flat sau khi resolve entities/includes",
                                "default": 1,
                                "enum": [1, 2],
                            },
                        },
                        "required": ["file_path", "reference_file"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "query_database":
                    result = query_database(
                        file_path=arguments["file_path"],
                        query=arguments["query"],
                        db_type=arguments.get("db_type", "app"),
                        max_rows=int(arguments.get("max_rows", 20000)),
                        query_type=int(arguments.get("query_type", 1)),
                    )
                    return [TextContent(type="text", text=format_query_result(result))]

                elif name == "get_xml_entities":
                    result = get_xml_entities(
                        arguments["file_path"],
                        arguments.get("entities"),
                        mode=arguments.get("mode", "content"),
                        force_reload=False,
                        list_all=False,
                    )
                    return [TextContent(type="text", text=format_entity_result(result))]

                elif name == "query_radar":
                    cypher_query = arguments.get("cypher_query", "")
                    reference_file = arguments["reference_file"]
                    mode = arguments.get("mode", "query")
                    res = mcp_query_radar(cypher_query, reference_file, mode)
                    return [TextContent(type="text", text=res)]

                elif name == "search_nodes":
                    query = arguments["query"]
                    reference_file = arguments["reference_file"]
                    match_type = arguments.get("match_type", "all")
                    folder_filter = arguments.get("folder_filter")
                    limit = int(arguments.get("limit", 20))
                    res = mcp_search_nodes(query, reference_file, match_type, folder_filter, limit)
                    return [TextContent(type="text", text=res)]

                elif name == "get_related_nodes":
                    target = arguments["target"]
                    reference_file = arguments["reference_file"]
                    mode = arguments.get("mode", "navigate")
                    include_shared = arguments.get("include_shared", False)
                    res = mcp_get_related_nodes(target, reference_file, mode, include_shared)
                    return [TextContent(type="text", text=res)]

                elif name == "query_node_details":
                    target = arguments["target"]
                    reference_file = arguments["reference_file"]
                    view = arguments.get("view", "context")
                    res = mcp_query_node_details(target, reference_file, view)
                    return [TextContent(type="text", text=res)]

                elif name == "read_local_file":
                    file_path = arguments["file_path"]
                    reference_file = arguments["reference_file"]
                    read_option = int(arguments.get("read_option", 1))
                    res = mcp_read_local_file(file_path, reference_file, read_option)
                    return [TextContent(type="text", text=res)]

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting FastBusiness MCP Server (SQL/XML + FBOGraph)...")

        # Run server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    server = FastBusinessMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
