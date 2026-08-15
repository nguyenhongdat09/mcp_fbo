"""FastBusiness MCP Server — SQL/XML tools + FBOGraph."""

import asyncio
import yaml
from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ListToolsResult,
    CallToolResult,
    PaginatedRequestParams,
    CallToolRequestParams,
)

from .utils.logger import setup_logger
from .agent_messages import QUERY_RADAR_ERROR_MSG, MISSING_ARG_MSG, GENERAL_EXECUTION_ERROR_MSG

from queryDatabase import query_database
from queryDatabase.formatter import format_query_result
from find_entity_by_xml import get_xml_entities
from find_entity_by_xml.formatter import format_entity_result

from xml_fbograph.mcp_tools import (
    mcp_query_radar,
    mcp_read_local_file,
)

from search_qlyc import search_qlyc
from search_qlyc.formatter import format_search_result

logger = setup_logger(__name__)


class FastBusinessMCPServer:
    """FastBusiness MCP Server — tools agents call via MCP."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        # MCP SDK >=2.0: đăng ký handler qua constructor (không còn @list_tools/@call_tool)
        self.server = Server(
            "fastbusiness-mcp-server",
            on_list_tools=self._on_list_tools,
            on_call_tool=self._on_call_tool,
        )
        logger.info("FastBusiness MCP Server (SQL/XML + FBOGraph) initialized")

    def _load_config(self, config_path: str) -> dict:
        from fastbusiness_mcp.config_paths import resolve_config_path

        resolved = resolve_config_path(config_path)
        if resolved is None:
            logger.warning(f"Config not found: {config_path}, using defaults")
            return {}
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            rag = cfg.get("rag_qlyc") or {}
            if rag.get("base_url"):
                logger.info(f"Loaded config from {resolved} (rag_qlyc.base_url={rag.get('base_url')})")
            else:
                logger.info(f"Loaded config from {resolved}")
            return cfg
        except Exception as e:
            logger.warning(f"Failed to load config {resolved}: {e}, using defaults")
            return {}

    async def _on_list_tools(
        self,
        ctx: ServerRequestContext,
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        return ListToolsResult(
            tools=[
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
                    description="""Đọc XML entity từ file_path. 
mode: 
- content: lấy nội dung entity (cần truyền entities)
- path: vị trí khai báo file:line (cần truyền entities)
- list: liệt kê toàn bộ ENTITY trong DOCTYPE (dùng khi chưa biết tên entity, không cần truyền entities). Mặc định mode=list chỉ trả về các entity loại 'general' được khai báo trực tiếp trong file.

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
                                "description": "Danh sách tên entity (vd: XMLWhenVoucherInit, ListField) - Không bắt buộc khi mode='list'",
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["content", "path", "list"],
                                "description": "content (nội dung), path (vị trí), hoặc list (liệt kê)",
                                "default": "content",
                            },
                        },
                        "required": ["file_path"],
                    },
                ),
                Tool(
                    name="query_radar",
                    description="""Query hoặc đọc schema live của đồ thị Kùzu Graph DB (Radar tool).
Đây là tool DUY NHẤT để truy vấn Graph (các hàm cũ đã bị ẩn).

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
                                "description": "BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.\nVí dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml\nhoặc UNC: \\\\server\\CustomerPro\\FBO\\...\\App_Data\\Controllers\\Dir\\SVTran.xml\nCẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.\nThiếu hoặc relative sẽ bị reject; không dùng để build Kuzu.",
                            },
                        },
                        "required": ["reference_file"],
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
                                "description": "BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.\nVí dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml\nhoặc UNC: \\\\server\\CustomerPro\\FBO\\...\\App_Data\\Controllers\\Dir\\SVTran.xml\nCẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.\nThiếu hoặc relative sẽ bị reject; không dùng để build Kuzu.",
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
                Tool(
                    name="search_qlyc",
                    description="""Tra cứu lịch sử yêu cầu (UR/ticket) đã từng làm — dùng khi user hỏi kiểu: trước đây có yêu cầu / chức năng ABC chưa? dự án này từng làm gì liên quan X?

Agent tự phân tích câu hỏi user → chuẩn hóa thành query ngắn gọn (tiếng Việt, nêu đúng nghiệp vụ/chức năng) rồi gọi tool.
Kết quả gồm fcode1, ma_da, noi_dung, score, page, total_pages… để agent đọc và trả lời có/không + dẫn chứng.

Quy trình bắt buộc khi chưa thấy yêu cầu liên quan:
1) Giữ nguyên query — tăng page lần lượt (page=2, 3, …) đến hết total_pages / trang cuối. Không bỏ qua trang.
2) Hết trang mà vẫn không thấy → mới đổi cách diễn đạt query (từ đồng nghĩa, bỏ từ thừa, nêu chức năng cụ thể hơn) rồi lặp lại bước 1 với query mới.
3) Tối đa 3 lần đổi query (3 cách diễn đạt) trong một lượt trả lời user. CẤM tự ý thử quá 3 lần.
4) Sau 3 lần vẫn không thấy → dừng, báo user rõ đã thử những query nào + đã lật trang ra sao; để user xem và quyết định. Chỉ khi user yêu cầu tìm lại thì mới search tiếp — và lại tối đa 3 lần đổi query (mỗi lần vẫn lật hết trang trước khi đổi query).
 .""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Câu tìm kiếm đã được agent chuẩn hóa từ ý user (ngắn, rõ nghiệp vụ/chức năng cần tra lịch sử). Không nhét nguyên câu chat dài nếu có thể rút gọn. Đổi query chỉ sau khi đã lật hết trang của query hiện tại; tối đa 3 cách diễn đạt mỗi lượt (xem description tool).",
                            },
                            "ma_da": {
                                "type": "string",
                                "description": "Filter đúng mã dự án. CHỈ truyền khi user yêu cầu lọc theo dự án; không thì bỏ trống / không gửi để search toàn bộ dự án.",
                            },
                            "bp_lt": {
                                "type": "string",
                                "description": "Filter bộ phận LT (vd. FSD). CHỈ truyền khi user yêu cầu lọc theo bộ phận; không thì bỏ trống / không gửi để search mọi bộ phận.",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Số trang (từ 1). Lần đầu dùng 1; nếu chưa thấy kết quả liên quan thì tăng page đến hết total_pages trước khi đổi query.",
                                "default": 1,
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "Số item mỗi trang (1…50). Mặc định 20.",
                                "default": 20,
                            },
                            "max_total": {
                                "type": "integer",
                                "description": "Cửa sổ xếp hạng tối đa sau search (1…100). Mặc định 100 — dùng để biết còn bao nhiêu trang (total_pages).",
                                "default": 100,
                            },
                        },
                        "required": ["query"],
                    },
                ),
            ]
        )

    async def _on_call_tool(
        self,
        ctx: ServerRequestContext,
        params: CallToolRequestParams,
    ) -> CallToolResult:
        """Handle tool calls."""
        name = params.name
        arguments = params.arguments or {}
        try:
            if name == "query_database":
                result = query_database(
                    file_path=arguments["file_path"],
                    query=arguments["query"],
                    db_type=arguments.get("db_type", "app"),
                    max_rows=int(arguments.get("max_rows", 20000)),
                    query_type=int(arguments.get("query_type", 1)),
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=format_query_result(result))]
                )

            elif name == "get_xml_entities":
                result = get_xml_entities(
                    arguments["file_path"],
                    arguments.get("entities"),
                    mode=arguments.get("mode", "content"),
                    force_reload=False,
                    list_all=False,
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=format_entity_result(result))]
                )

            elif name == "query_radar":
                cypher_query = arguments.get("cypher_query", "")
                reference_file = arguments["reference_file"]
                mode = arguments.get("mode", "query")
                res = mcp_query_radar(cypher_query, reference_file, mode)
                return CallToolResult(content=[TextContent(type="text", text=res)])

            elif name == "read_local_file":
                file_path = arguments["file_path"]
                reference_file = arguments["reference_file"]
                read_option = int(arguments.get("read_option", 1))
                res = mcp_read_local_file(file_path, reference_file, read_option)
                return CallToolResult(content=[TextContent(type="text", text=res)])

            elif name == "search_qlyc":
                rag_config = self.config.get("rag_qlyc") or {}
                default_bp_lt = rag_config.get("bp_lt")
                if default_bp_lt is None:
                    default_bp_lt = ""
                
                bp_lt = arguments.get("bp_lt")
                if bp_lt is None:
                    bp_lt = default_bp_lt

                result = search_qlyc(
                    query=arguments["query"],
                    ma_da=arguments.get("ma_da"),
                    bp_lt=bp_lt,
                    page=int(arguments.get("page", 1)),
                    page_size=int(arguments.get("page_size", 20)),
                    max_total=int(arguments.get("max_total", 100)),
                    config=rag_config,
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=format_search_result(result))]
                )

            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                    is_error=True,
                )

        except KeyError as e:
            missing_key = str(e).strip("'")
            error_msg = MISSING_ARG_MSG.format(tool_name=name, missing_key=missing_key)
            logger.error(f"Tool {name} missing argument: {missing_key}")
            return CallToolResult(
                content=[TextContent(type="text", text=error_msg)],
                is_error=True,
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            if name == "query_radar":
                error_msg = QUERY_RADAR_ERROR_MSG.format(error_detail=str(e))
            else:
                error_msg = GENERAL_EXECUTION_ERROR_MSG.format(tool_name=name, error_detail=str(e))
            return CallToolResult(
                content=[TextContent(type="text", text=error_msg)],
                is_error=True,
            )
    async def run(self) -> None:
        """Run the MCP server."""
        logger.info("Starting FastBusiness MCP Server (SQL/XML + FBOGraph)...")

        # Run server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())


def main():
    """Entry point for the MCP server."""
    from fastbusiness_mcp.license import verify_and_enforce_license

    verify_and_enforce_license()
    server = FastBusinessMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
