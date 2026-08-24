"""FastBusiness MCP Server Application — MCPServer (FastMCP pattern) + Pydantic v2."""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal
import yaml
from pydantic import Field
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .utils.logger import setup_logger
from .agent_messages import QUERY_RADAR_ERROR_MSG
from .tool_errors import format_execution_error, format_validation_error_message

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

# Khởi tạo instance MCPServer
server = MCPServer("fastbusiness-mcp-server")

_CONFIG: dict | None = None


def load_config(config_path: str = "config.yaml") -> dict:
    """Tải file cấu hình config.yaml từ các đường dẫn khả dụng."""
    global _CONFIG
    from fastbusiness_mcp.config_paths import resolve_config_path

    resolved = resolve_config_path(config_path)
    if resolved is None:
        logger.warning(f"Config not found: {config_path}, using defaults")
        _CONFIG = {}
        return _CONFIG
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        rag = cfg.get("rag_qlyc") or {}
        if rag.get("base_url"):
            logger.info(f"Loaded config from {resolved} (rag_qlyc.base_url={rag.get('base_url')})")
        else:
            logger.info(f"Loaded config from {resolved}")
        _CONFIG = cfg
        return _CONFIG
    except Exception as e:
        logger.warning(f"Failed to load config {resolved}: {e}, using defaults")
        _CONFIG = {}
        return _CONFIG


def get_config() -> dict:
    """Lấy cấu hình hiện tại (tự động load nếu chưa khởi tạo)."""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG


def set_config(cfg: dict) -> None:
    """Đặt cấu hình thủ công (hữu ích khi test)."""
    global _CONFIG
    _CONFIG = cfg


# ============================================================================
# TOOL 1: query_database
# ============================================================================
@server.tool(name="query_database")
def query_database_tool(
    file_path: Annotated[
        str,
        Field(description="Path file trong project FBO (XML/SQL) để resolve connection"),
    ],
    query: Annotated[
        str,
        Field(
            description="Tên object (type=0: bảng hoặc proc/view/function), SQL inline (type=1), hoặc path .sql (type=2)"
        ),
    ],
    query_type: Annotated[
        int,
        Field(
            default=1,
            description="0=object (tự nhận bảng/proc/view/function), 1=SQL inline (default), 2=file .sql",
        ),
    ] = 1,
    db_type: Annotated[
        Literal["app", "sys"],
        Field(default="app", description="app hoặc sys (default: app)"),
    ] = "app",
    max_rows: Annotated[
        int,
        Field(default=20000, description="Giới hạn số dòng trả về (default: 20000)"),
    ] = 20000,
    mode: Annotated[
        Literal["summary", "snippet", "full"],
        Field(
            default="summary",
            description="Chế độ phân tích khi query_type=0 với proc/view/function: 'summary'=JSON tóm tắt (params, tables, calls, signals); 'snippet'=trích xuất code theo keywords/zones; 'full'=trả full source code.",
        ),
    ] = "summary",
    schema: Annotated[
        str,
        Field(
            default="dbo",
            description="Schema mặc định nếu object không có tiền tố schema (mặc định 'dbo').",
        ),
    ] = "dbo",
    max_depth: Annotated[
        int,
        Field(
            default=1,
            ge=0,
            le=3,
            description="Độ sâu đệ quy call graph cho business object (0-3). Mặc định=1. View và Infra mặc định depth=0.",
        ),
    ] = 1,
    max_objects: Annotated[
        int,
        Field(
            default=30,
            ge=1,
            le=50,
            description="Giới hạn số lượng object fetch tối đa trong 1 request đệ quy (mặc định=30).",
        ),
    ] = 30,
    expand: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Danh sách infra object cần bung thêm 1 cấp (override depth 0), vd: ['FastBusiness$Balance$BContract'].",
        ),
    ] = None,
    exclude_like: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Danh sách regex pattern loại trừ khỏi đệ quy call graph (mặc định loại FastBusiness$%, ff_%, fsd_%).",
        ),
    ] = None,
    include_called_by: Annotated[
        bool,
        Field(
            default=False,
            description="Có truy vấn danh sách object gọi tới object này không (inbound references).",
        ),
    ] = False,
    keywords: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="mode='snippet': Danh sách từ khóa để trích xuất khối code (vd: ['tl_th', '@Status', 'ctdmku', 'WHILE']).",
        ),
    ] = None,
    zones: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="mode='snippet': Danh sách vùng cấu trúc cần lấy: 'header', 'params', 'key_filter', 'cursor', 'processing', 'result_set', 'pivot'.",
        ),
    ] = None,
    max_snippet_lines: Annotated[
        int,
        Field(
            default=120,
            ge=10,
            le=500,
            description="Giới hạn số dòng tối đa cho mode snippet (mặc định 120 dòng).",
        ),
    ] = 120,
    max_full_chars: Annotated[
        int,
        Field(
            default=50000,
            ge=1000,
            le=200000,
            description="Giới hạn số ký tự tối đa cho mode full (mặc định 50,000 ký tự).",
        ),
    ] = 50000,
    use_cache: Annotated[
        bool,
        Field(
            default=True,
            description="Có sử dụng cache in-memory thread-safe không (mặc định True).",
        ),
    ] = True,
) -> str:
    """Chạy SQL trên SQL Server — tự resolve connection từ file_path (Web.config).

query_type:
- 0: tên object (bảng hoặc proc/view/function)
  * Bảng (USER_TABLE): lấy toàn bộ Script tạo Table/Index/Constraint (CREATE TABLE, CREATE INDEX, CONSTRAINT). AI TUYỆT ĐỐI KHÔNG dùng type=1 để tự viết SQL tra cứu index của bảng nữa.
  * Stored Procedure / Function / View (Tích hợp summary_object): Phân tích cú pháp AST ANTLR4 — trả tóm tắt JSON cực gọn thay vì sp_helptext dài dòng (tiết kiệm token). Hỗ trợ:
    + mode='summary' (mặc định): biết params, tables, calls, signals, complexity.
    + mode='snippet': trích xuất block code theo keywords hoặc zones.
    + mode='full': trả full source code.
- 1: SQL ngắn inline (mặc định)
- 2: path file .sql — dùng cho script dài (tiết kiệm token)

db_type: app (mặc định) hoặc sys."""
    try:
        result = query_database(
            file_path=file_path,
            query=query,
            db_type=db_type,
            max_rows=max_rows,
            query_type=query_type,
            mode=mode,
            schema=schema,
            max_depth=max_depth,
            max_objects=max_objects,
            expand=expand,
            exclude_like=exclude_like,
            include_called_by=include_called_by,
            keywords=keywords,
            zones=zones,
            max_snippet_lines=max_snippet_lines,
            max_full_chars=max_full_chars,
            use_cache=use_cache,
        )
        return format_query_result(result)
    except Exception as e:
        logger.error(f"query_database execution error: {e}")
        return format_execution_error("query_database", e)


# ============================================================================
# TOOL 2: get_xml_entities
# ============================================================================
@server.tool(name="get_xml_entities")
def get_xml_entities_tool(
    file_path: Annotated[
        str,
        Field(description="Đường dẫn file XML (.xml, .f, ...)"),
    ],
    entities: Annotated[
        list[str] | None,
        Field(default=None, description="Danh sách tên entity (vd: XMLWhenVoucherInit, ListField) - Không bắt buộc khi mode='list'"),
    ] = None,
    mode: Annotated[
        Literal["content", "path", "list"],
        Field(default="content", description="content (nội dung), path (vị trí), hoặc list (liệt kê)"),
    ] = "content",
) -> str:
    """Đọc XML entity từ file_path. 
mode: 
- content: lấy nội dung entity (cần truyền entities)
- path: vị trí khai báo file:line (cần truyền entities)
- list: liệt kê toàn bộ ENTITY trong DOCTYPE (dùng khi chưa biết tên entity, không cần truyền entities). Mặc định mode=list chỉ trả về các entity loại 'general' được khai báo trực tiếp trong file.

CHÚ Ý QUAN TRỌNG: Nếu file XML cần đọc không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị."""
    try:
        result = get_xml_entities(
            file_path,
            entities,
            mode=mode,
            force_reload=False,
            list_all=False,
        )
        return format_entity_result(result)
    except Exception as e:
        logger.error(f"get_xml_entities execution error: {e}")
        return format_execution_error("get_xml_entities", e)


# ============================================================================
# TOOL 3: query_radar
# ============================================================================
def _format_query_radar_result(res: str) -> str:
    """Chuyển đổi kết quả / lỗi từ mcp_query_radar sang message Agent-friendly."""
    if not isinstance(res, str):
        return str(res)

    if res.startswith("Loi thuc thi Cypher:"):
        return QUERY_RADAR_ERROR_MSG.format(error_detail=res)

    stripped = res.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(res)
        except json.JSONDecodeError:
            return res
        if isinstance(data, dict):
            err = data.get("error")
            if err == "invalid_reference_file":
                msg = data.get("message", "reference_file không hợp lệ")
                ref = data.get("reference_file", "")
                return (
                    "[LỖI REFERENCE_FILE]\n"
                    f"{msg}\n"
                    f"reference_file đã nhận: '{ref}'\n"
                    "Agent: BẮT BUỘC truyền đường dẫn ABSOLUTE tới file XML trong App_Data\\Controllers "
                    "(VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml)."
                )
            if err or data.get("status") == "building":
                return QUERY_RADAR_ERROR_MSG.format(
                    error_detail=json.dumps(data, ensure_ascii=False)
                )
    return res


@server.tool(name="query_radar")
def query_radar_tool(
    reference_file: Annotated[
        str,
        Field(description="BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.\nVí dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml\nhoặc UNC: \\\\server\\CustomerPro\\FBO\\...\\App_Data\\Controllers\\Dir\\SVTran.xml\nCẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.\nThiếu hoặc relative sẽ bị reject; không dùng để build Kuzu."),
    ],
    cypher_query: Annotated[
        str,
        Field(default="", description="Cypher cần chạy; bắt buộc khi mode=query, có thể để rỗng khi mode=schema"),
    ] = "",
    mode: Annotated[
        Literal["query", "schema"],
        Field(default="query", description="query=chạy Cypher; schema=trả schema live + hướng dẫn"),
    ] = "query",
) -> str:
    """Query hoặc đọc schema live của đồ thị Kùzu Graph DB (Radar tool).
Đây là tool DUY NHẤT để truy vấn Graph (các hàm cũ đã bị ẩn).

CHÚ Ý: Lược đồ đồ thị (Schema), 10 Template Cypher chuẩn và các nguyên tắc cú pháp nghiêm ngặt đã được cung cấp sẵn trong Rules hệ thống (KùzuDB Cypher Query Principles & FBOGraph Schema Guide). 
Bạn BẮT BUỘC phải đọc và tuân thủ các quy tắc, chỉ chọn 1 trong 10 Template đó khi gọi cypher_query. Tuyệt đối KHÔNG tự sáng tác câu lệnh Cypher.

mode:
- query (mặc định): chạy cypher_query.
- schema: trả schema live XmlFile/Rel (Agent chỉ gọi để check cấu trúc thực tế khi cần)."""
    try:
        res = mcp_query_radar(cypher_query, reference_file, mode)
        return _format_query_radar_result(res)
    except Exception as e:
        logger.error(f"query_radar error: {e}")
        return QUERY_RADAR_ERROR_MSG.format(error_detail=str(e))


# ============================================================================
# TOOL 4: read_local_file
# ============================================================================
@server.tool(name="read_local_file")
def read_local_file_tool(
    file_path: Annotated[
        str,
        Field(description="Relative path (e.g., 'Dir/CPTran.xml') or absolute path"),
    ],
    reference_file: Annotated[
        str,
        Field(description="BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.\nVí dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml\nhoặc UNC: \\\\server\\CustomerPro\\FBO\\...\\App_Data\\Controllers\\Dir\\SVTran.xml\nCẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.\nThiếu hoặc relative sẽ bị reject; không dùng để build Kuzu."),
    ],
    read_option: Annotated[
        Literal[1, 2, 3],
        Field(
            default=3,
            description=(
                "3: summary_xml (MẶC ĐỊNH / ƯU TIÊN GỌI ĐẦU TIÊN) — Trả về JSON tóm tắt cấu trúc cực gọn (hàm JS, bảng/views/procs SQL, kiểu field, lookup, onchange) giúp nắm bắt toàn bộ file với chi phí token tối thiểu. Tự động switch sang option 1 raw nếu file không phải .xml (vd .sql, .js, .txt, .config). "
                "2: flat — Đọc toàn bộ XML sau khi resolve entities/includes (CHỈ DÙNG khi cần xem chi tiết từng dòng code để sửa file). "
                "1: raw — Đọc nội dung file gốc chưa resolve."
            ),
        ),
    ] = 3,
) -> str:
    """Đọc trực tiếp nội dung file controller FBO từ ổ cứng (đảm bảo dữ liệu mới nhất, không bị cache).

QUY TRÌNH AGENT (TIẾT KIỆM TOKEN):
1) BƯỚC 1 (MẶC ĐỊNH): LUÔN LUÔN dùng read_option=3 (summary_xml) để nắm toàn bộ bản đồ controller (danh sách hàm JS, bảng/view SQL, fields lookup/onchange) với chi phí token cực thấp. Lưu ý: nếu file không phải .xml (vd .sql, .js, .txt, .config), tool sẽ tự động switch sang read_option=1 (raw).
2) BƯỚC 2: CHỈ gọi read_option=2 (flat) khi bạn ĐÃ XÁC ĐỊNH ĐƯỢC hàm/khối lệnh cần sửa và cần xem code chi tiết để viết code thay thế.
3) BƯỚC 3: get_xml_entities chỉ khi cần tra cứu vị trí file DTD/Entity chưa flat.

CHÚ Ý QUAN TRỌNG: Nếu file cần đọc không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị."""
    try:
        return mcp_read_local_file(file_path, reference_file, read_option)
    except Exception as e:
        logger.error(f"read_local_file execution error: {e}")
        return format_execution_error("read_local_file", e)


# ============================================================================
# TOOL 5: search_qlyc
# ============================================================================
@server.tool(name="search_qlyc")
def search_qlyc_tool(
    query: Annotated[
        str,
        Field(default="", description="Câu tìm kiếm đã được agent chuẩn hóa từ ý user (ngắn, rõ nghiệp vụ/chức năng cần tra lịch sử). Có thể truyền rỗng '' nếu muốn tìm chính xác theo fcode1 / ma_da. Đổi query chỉ sau khi đã lật hết trang của query hiện tại; tối đa 3 cách diễn đạt mỗi lượt (xem description tool)."),
    ] = "",
    fcode1: Annotated[
        str | None,
        Field(default=None, description="Mã yêu cầu (ID) của ticket cần tìm kiếm (VD: YC00123). Dùng để tìm chính xác một ticket."),
    ] = None,
    ma_da: Annotated[
        str | None,
        Field(default=None, description="Filter đúng mã dự án. CHỈ truyền khi user yêu cầu lọc theo dự án; không thì bỏ trống / không gửi để search toàn bộ dự án."),
    ] = None,
    bp_lt: Annotated[
        str | None,
        Field(default=None, description="Filter bộ phận LT (vd. FSD). CHỈ truyền khi user yêu cầu lọc theo bộ phận; không thì bỏ trống / không gửi để search mọi bộ phận."),
    ] = None,
    page: Annotated[
        int,
        Field(default=1, description="Số trang (từ 1). Lần đầu dùng 1; nếu chưa thấy kết quả liên quan thì tăng page đến hết total_pages trước khi đổi query."),
    ] = 1,
    page_size: Annotated[
        int,
        Field(default=20, description="Số item mỗi trang (1…50). Mặc định 20."),
    ] = 20,
    max_total: Annotated[
        int,
        Field(default=100, description="Cửa sổ xếp hạng tối đa sau search (1…100). Mặc định 100 — dùng để biết còn bao nhiêu trang (total_pages)."),
    ] = 100,
) -> str:
    """Tra cứu lịch sử yêu cầu (UR/ticket) đã từng làm — dùng khi user hỏi kiểu: trước đây có yêu cầu / chức năng ABC chưa? dự án này từng làm gì liên quan X?

Agent tự phân tích câu hỏi user → chuẩn hóa thành query ngắn gọn (tiếng Việt, nêu đúng nghiệp vụ/chức năng) rồi gọi tool.
Kết quả gồm fcode1, ma_da, noi_dung, score, page, total_pages… để agent đọc và trả lời có/không + dẫn chứng.

Lưu ý: Nếu bạn chỉ muốn tra cứu chính xác một hoặc nhiều vé theo Mã yêu cầu / Mã dự án mà không cần tìm theo từ khóa ngữ nghĩa, bạn hãy truyền tham số query bằng chuỗi rỗng "" và điền giá trị vào fcode1 hoặc ma_da. Hành động này sẽ giúp API lấy dữ liệu ngay lập tức (Bypass AI) siêu nhanh!

Quy trình bắt buộc khi chưa thấy yêu cầu liên quan:
1) Giữ nguyên query — tăng page lần lượt (page=2, 3, …) đến hết total_pages / trang cuối. Không bỏ qua trang.
2) Hết trang mà vẫn không thấy → mới đổi cách diễn đạt query (từ đồng nghĩa, bỏ từ thừa, nêu chức năng cụ thể hơn) rồi lặp lại bước 1 với query mới.
3) Tối đa 3 lần đổi query (3 cách diễn đạt) trong một lượt trả lời user. CẤM tự ý thử quá 3 lần.
4) Sau 3 lần vẫn không thấy → dừng, báo user rõ đã thử những query nào + đã lật trang ra sao; để user xem và quyết định. Chỉ khi user yêu cầu tìm lại thì mới search tiếp — và lại tối đa 3 lần đổi query (mỗi lần vẫn lật hết trang trước khi đổi query)."""
    try:
        cfg = get_config()
        rag_config = cfg.get("rag_qlyc") or {}
        default_bp_lt = rag_config.get("bp_lt")
        if default_bp_lt is None:
            default_bp_lt = ""

        resolved_bp_lt = default_bp_lt if bp_lt is None else bp_lt

        result = search_qlyc(
            query=query,
            fcode1=fcode1,
            ma_da=ma_da,
            bp_lt=resolved_bp_lt,
            page=page,
            page_size=page_size,
            max_total=max_total,
            config=rag_config,
        )
        return format_search_result(result)
    except Exception as e:
        logger.error(f"search_qlyc execution error: {e}")
        return format_execution_error("search_qlyc", e)


# ============================================================================
# TOOL 6: chrome_debug (CDP Runtime Debugging)
# ============================================================================
try:
    from fastbusiness_mcp.chrome_debug.tools import register_chrome_tools
    register_chrome_tools(server, get_config)
except Exception as e:
    logger.warning(f"Failed to register chrome_debug tools: {e}")


# ============================================================================
# Intercept ToolError để trả thông báo tiếng Việt chuẩn cho Agent
# ============================================================================
_orig_call_tool = server.call_tool


async def _safe_call_tool(name: str, arguments: dict, context=None):
    try:
        return await _orig_call_tool(name, arguments, context)
    except ToolError as e:
        msg = str(e)
        m = re.match(r"Error executing tool ([^:]+):\s*(.+)", msg, re.DOTALL)
        if m:
            tool_name = m.group(1).strip()
            body = m.group(2).strip()
            if "validation error" in body.lower() or "pydantic.dev" in body:
                vi_msg = format_validation_error_message(tool_name, body)
                raise ToolError(vi_msg) from None
        raise


server.call_tool = _safe_call_tool
