"""FastBusiness MCP Server Application — MCPServer (FastMCP pattern) + Pydantic v2."""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
import yaml
from pydantic import Field
from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .utils.logger import setup_logger
from .agent_messages import QUERY_RADAR_ERROR_MSG
from .tool_errors import format_execution_error, format_validation_error_message

from query_database import query_database
from query_database.formatter import format_query_result
from find_entity_by_xml import get_xml_entities
from find_entity_by_xml.formatter import format_entity_result

from xml_fbograph.mcp_tools import (
    mcp_query_radar,
    mcp_read_local_file,
)
from xml_fbograph.utils.any_path import (
    known_projects,
    project_switch_message,
    resolve_any_path,
)

from search_qlyc import search_qlyc
from search_qlyc.formatter import format_search_result

from clone_things import clone_things
from clone_things.formatter import format_clone_result

from compare_things import compare_things
from compare_things.formatter import format_compare_result

from search_files import search_files

logger = setup_logger(__name__)

# Khởi tạo instance MCPServer
server = MCPServer("fastbusiness-mcp-server")

_CONFIG: dict | None = None


def load_config(config_path: str = "config.yaml") -> dict:
    """Tải file cấu hình config.yaml và merge đường dẫn máy từ config_path.yaml."""
    global _CONFIG
    from fastbusiness_mcp.config_paths import (
        resolve_config_path,
        load_machine_paths,
        merge_config_with_machine_paths,
    )

    resolved = resolve_config_path(config_path)
    cfg: dict = {}
    if resolved is None:
        logger.warning(f"Config not found: {config_path}, using defaults")
    else:
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            rag = cfg.get("rag_qlyc") or {}
            if rag.get("base_url"):
                logger.info(f"Loaded config from {resolved} (rag_qlyc.base_url={rag.get('base_url')})")
            else:
                logger.info(f"Loaded config from {resolved}")
        except Exception as e:
            logger.warning(f"Failed to load config {resolved}: {e}, using defaults")
            cfg = {}

    machine = load_machine_paths()
    if machine:
        logger.info(f"Loaded machine paths: {list(machine.keys())}")
    cfg = merge_config_with_machine_paths(cfg, machine)

    kuzu_path = cfg.get("fbograph", {}).get("kuzu_db_base", "")
    sql_path = cfg.get("clone_things", {}).get("sql_temp_folder", "")
    logger.info(f"Effective paths: kuzu_db_base='{kuzu_path}', sql_temp_folder='{sql_path}'")

    _CONFIG = cfg
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
@server.tool(
    name="query_database",
    annotations=ToolAnnotations(readOnlyHint=True),
)
def query_database_tool(
    file_path: Annotated[
        str,
        Field(description="Path BẤT KỲ trong project FBO để resolve connection qua Web.config — abs file/dir (local/UNC) hoặc relative ('Grid/SOTran.xml', 'Web.config', project root). Relative tự resolve qua sticky project context sau call abs đầu tiên."),
    ],
    query: Annotated[
        str,
        Field(
            default="",
            description="Tên object (type=0: bảng hoặc proc/view/function), SQL inline (type=1), hoặc path .sql (type=2/3). Không bắt buộc khi mode='search' (dùng object_name/references).",
        ),
    ] = "",
    query_type: Annotated[
        int,
        Field(
            default=1,
            description="0=object (tự nhận bảng/proc/view/function), 1=SQL inline (default), 2=file .sql, 3=check file .sql qua SET PARSEONLY (parse-only, không execute — dùng trước khi deploy script; báo mọi lỗi syntax kèm dòng file gốc)",
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
        Literal["summary", "snippet", "full", "search"],
        Field(
            default="summary",
            description="Chế độ phân tích khi query_type=0 với proc/view/function: 'summary'=JSON tóm tắt (params, tables, calls, signals); 'snippet'=trích xuất code theo keywords/zones; 'full'=trả full source code. 'search'=tìm DB object theo object_name (LIKE) hoặc references (literal trong definition — 'proc nào dùng bảng/field X'), bỏ qua query/query_type.",
        ),
    ] = "summary",
    object_name: Annotated[
        str,
        Field(
            default="",
            description="mode='search': LIKE pattern trên tên object (vd 'zc_Create%', '%SttRec%').",
        ),
    ] = "",
    references: Annotated[
        str,
        Field(
            default="",
            description="mode='search': chuỗi literal cần có trong definition của object (vd 'fsdSttRecRef', 'so_hc'). Parameterized, an toàn với %/' /--.",
        ),
    ] = "",
    object_types: Annotated[
        str,
        Field(
            default="P,FN,IF,TF,V,TR",
            description="mode='search': lọc loại object, CSV whitelist P,FN,IF,TF,V,TR (mặc định tất cả).",
        ),
    ] = "P,FN,IF,TF,V,TR",
    include_snippet: Annotated[
        bool,
        Field(
            default=True,
            description="mode='search': trả matched_lines[] = các dòng definition chứa references (mặc định True).",
        ),
    ] = True,
    max_results: Annotated[
        int,
        Field(
            default=50,
            description="mode='search': giới hạn số object trả về (mặc định 50, quá giới hạn → truncated=true).",
        ),
    ] = 50,
    max_lines_per_object: Annotated[
        int,
        Field(
            default=10,
            description="mode='search': cap số matched_lines mỗi object (mặc định 10).",
        ),
    ] = 10,
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
- 3: path file .sql — check syntax qua SET PARSEONLY (chỉ parse, KHÔNG execute — chạy trước khi deploy script; báo MỌI lỗi kèm line_start = dòng file gốc). Lưu ý: parse-only không check tên bảng/cột tồn tại.

mode='search': tìm DB object (proc/view/func/trigger) theo tên hoặc theo nội dung — trả lời "object nào đang dùng bảng/field X" mà không cần tự viết query sys.sql_modules. Cần ít nhất object_name hoặc references; kết quả gồm objects[] (name/schema/type/modify_date/has_definition) + matched_lines[] (dòng chứa references). Xem tiếp object nào → dùng mode summary/snippet/full với query_type=0.

db_type: app (mặc định) hoặc sys."""
    try:
        resolved_path = resolve_any_path(file_path)
        if not resolved_path.ok:
            err = dict(resolved_path.error or {"success": False})
            err.setdefault("project_root", resolved_path.project_root)
            err.setdefault("resolved_via", resolved_path.resolved_via)
            return json.dumps(err, indent=2, ensure_ascii=False)
        if not resolved_path.project_root:
            return json.dumps(
                {
                    "success": False,
                    "error_code": "no_project_root",
                    "input": file_path,
                    "resolved_path": resolved_path.abs_path,
                    "project_root": None,
                    "resolved_via": resolved_path.resolved_via,
                    "message": (
                        "Path tồn tại nhưng không xác định được project root FBO "
                        "(không có App_Data/Web.config ở ancestors)."
                    ),
                    "known_projects": known_projects(),
                },
                indent=2,
                ensure_ascii=False,
            )
        result = query_database(
            file_path=resolved_path.abs_path,
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
            object_name=object_name,
            references=references,
            object_types=object_types,
            include_snippet=include_snippet,
            max_results=max_results,
            max_lines_per_object=max_lines_per_object,
        )
        # Sticky context visibility — echo project/via + cảnh báo khi context trôi
        if isinstance(result, dict):
            result.setdefault("project_root", resolved_path.project_root)
            result["resolved_via"] = resolved_path.resolved_via
            _warn = project_switch_message(
                resolved_path.switched_from, resolved_path.project_root
            )
            if _warn:
                _w = result.setdefault("warnings", [])
                if isinstance(_w, list):
                    _w.append(_warn)
        return format_query_result(result)
    except Exception as e:
        logger.error(f"query_database execution error: {e}")
        return format_execution_error("query_database", e)


# ============================================================================
# TOOL 2: get_xml_entities
# ============================================================================
@server.tool(
    name="get_xml_entities",
    annotations=ToolAnnotations(readOnlyHint=True),
)
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
        Literal["content", "path", "list", "checking"],
        Field(default="content", description="content (nội dung), path (vị trí), list (liệt kê), hoặc checking (check entity)"),
    ] = "content",
    source_roots: Annotated[
        list[str] | None,
        Field(default=None, description="Danh sách project root NGUỒN (abs path, UNC ok) — chỉ dùng với mode='checking': file/entity thiếu ở đây nhưng có sẵn ở source. Optional."),
    ] = None,
) -> str:
    """Đọc XML entity từ file_path. 
mode: 
- content: lấy nội dung entity (cần truyền entities)
- path: vị trí khai báo file:line (cần truyền entities)
- list: liệt kê toàn bộ ENTITY trong DOCTYPE (dùng khi chưa biết tên entity, không cần truyền entities). Mặc định mode=list chỉ trả về các entity loại 'general' được khai báo trực tiếp trong file.
- checking: kiểm tra entity — &name; dùng mà chưa khai báo + SYSTEM entity trỏ file thiếu (kèm gợi ý source nếu truyền source_roots).

CHÚ Ý QUAN TRỌNG: Nếu file XML cần đọc không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị."""
    try:
        result = get_xml_entities(
            file_path,
            entities,
            mode=mode,
            force_reload=False,
            list_all=False,
            source_roots=source_roots,
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


@server.tool(
    name="query_radar",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def query_radar_tool(
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
    ctx: Context = None,
) -> str:
    """Query hoặc đọc schema live của đồ thị Kùzu Graph DB (Radar tool).
Đây là tool DUY NHẤT để truy vấn Graph (các hàm cũ đã bị ẩn).

CHÚ Ý: Lược đồ đồ thị (Schema), 10 Template Cypher chuẩn và các nguyên tắc cú pháp nghiêm ngặt đã được cung cấp sẵn trong Rules hệ thống (KùzuDB Cypher Query Principles & FBOGraph Schema Guide). 
Bạn BẮT BUỘC phải đọc và tuân thủ các quy tắc, chỉ chọn 1 trong 10 Template đó khi gọi cypher_query. Tuyệt đối KHÔNG tự sáng tác câu lệnh Cypher.

mode:
- query (mặc định): chạy cypher_query.
- schema: trả schema live XmlFile/Rel (Agent chỉ gọi để check cấu trúc thực tế khi cần)."""
    loop = asyncio.get_running_loop()

    async def _safe_report_progress(progress: float, total: float | None = None, message: str | None = None) -> None:
        if ctx is not None:
            try:
                await ctx.report_progress(progress=progress, total=total, message=message)
            except Exception:
                pass

    def on_progress(done: int, total: int, msg: str = "") -> None:
        if ctx is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    _safe_report_progress(
                        progress=float(done),
                        total=float(total) if total else None,
                        message=msg,
                    ),
                    loop,
                )
            except Exception:
                pass

    cfg = get_config()
    timeout_sec = cfg.get("fbograph", {}).get("query_timeout_seconds", 1800)
    try:
        await _safe_report_progress(progress=0.0, total=100.0, message="Bắt đầu kiểm tra Kùzu Graph DB...")
        res = await asyncio.wait_for(
            asyncio.to_thread(
                mcp_query_radar,
                cypher_query,
                reference_file,
                mode,
                on_progress,
            ),
            timeout=float(timeout_sec) if timeout_sec else 1800.0,
        )
        await _safe_report_progress(progress=100.0, total=100.0, message="Thực thi hoàn tất.")
        return _format_query_radar_result(res)
    except asyncio.TimeoutError:
        err_msg = f"Truy vấn query_radar bị timeout sau {timeout_sec}s (30 phút)."
        logger.error(err_msg)
        return QUERY_RADAR_ERROR_MSG.format(error_detail=err_msg)
    except Exception as e:
        logger.error(f"query_radar error: {e}")
        return QUERY_RADAR_ERROR_MSG.format(error_detail=str(e))


# ============================================================================
# TOOL 4: read_local_file
# ============================================================================
@server.tool(
    name="read_local_file",
    annotations=ToolAnnotations(readOnlyHint=True),
)
def read_local_file_tool(
    file_path: Annotated[
        str,
        Field(description="Path BẤT KỲ — relative ('Dir/CPTran.xml', 'ClientScript/jAjax.js') hoặc absolute (local/UNC). MCP tự resolve qua project đang làm (sticky context) — không cần khai báo project sau call abs đầu tiên."),
    ],
    reference_file: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn ABSOLUTE tới 1 file trong project FBO — CHỈ là optional override khi làm nhiều project xen kẽ hoặc call đầu tiên chưa có path abs nào. Relative path tự resolve qua sticky context.",
        ),
    ] = "",
    read_option: Annotated[
        Literal[1, 2, 3, 4],
        Field(
            default=3,
            description=(
                "3: summary_xml (MẶC ĐỊNH / ƯU TIÊN GỌI ĐẦU TIÊN) — Trả về JSON tóm tắt cấu trúc cực gọn (hàm JS, bảng/views/procs SQL, kiểu field, lookup, onchange) giúp nắm bắt cấu trúc với chi phí token tối thiểu. CHỈ áp dụng cho file .xml trực thuộc thư mục Dir, Grid, Filter (vd Dir/a.xml); tự động chuyển về option 1 (raw) nếu không phải .xml trong Dir/Grid/Filter (vd .sql, .js, Report, Templates, Dir/A/a.xml,...). "
                "2: flat — Đọc toàn bộ XML sau khi resolve entities/includes (CHỈ DÙNG khi cần xem chi tiết từng dòng code để sửa file). "
                "1: raw — Đọc nội dung file gốc chưa resolve. "
                "4: suggest_edit — READ-ONLY gợi ý str_replace: locate vùng bằng symbol/block/start_line+end_line/old_string, trả old_string exact + physical_file (kể cả trong entity .ent) + diff_preview + post_edit_check. Dùng edits[] cho batch nhiều edit 1 file."
            ),
        ),
    ] = 3,
    start_line: Annotated[
        int,
        Field(default=0, description="Snippet mode: dòng bắt đầu (1-based) trên nội dung RAW. Khi truyền bất kỳ param snippet nào (start_line/end_line/symbol/block) tool trả JSON snippet thay vì dump."),
    ] = 0,
    end_line: Annotated[
        int,
        Field(default=0, description="Snippet mode: dòng kết thúc (inclusive); 0 = tới cuối file."),
    ] = 0,
    symbol: Annotated[
        str,
        Field(default="", description="Snippet mode: tên function JS cần trích (vd 'open$CreateVoucher'). Controller XML → trích trên flat view kèm origin=file|entity. Ưu tiên hơn start_line/end_line."),
    ] = "",
    block: Annotated[
        str,
        Field(default="", description="Snippet mode: selector khối SQL/XML trên controller — 'action:<id>' (vd action:GetCreatedVoucher), 'command:<event>' (vd command:Showing), 'field:<name>', 'query:<n>'."),
    ] = "",
    context_lines: Annotated[
        int,
        Field(default=0, description="Snippet mode: số dòng pad trước/sau vùng match (mặc định 0)."),
    ] = 0,
    line_numbers: Annotated[
        bool,
        Field(default=True, description="Snippet mode: prefix 'NNN|' cho từ dòng trong text (mặc định True)."),
    ] = True,
    old_string: Annotated[
        str,
        Field(default="", description="read_option=4: cách locate thứ 4 — truyền thẳng anchor text, server kiểm tra tồn tại/unique (kể cả trong entity .ent)."),
    ] = "",
    new_string: Annotated[
        str,
        Field(default="", description="read_option=4: code thay thế agent định ghi. Rỗng → chỉ trả location + old_string (không diff/validate)."),
    ] = "",
    edits: Annotated[
        Optional[List[Dict[str, Any]]],
        Field(default=None, description="read_option=4 batch: list edit [{'old_string|symbol|block|start_line+end_line', 'new_string'}] — apply tuần tự trên buffer in-memory (edit sau được khớp text do edit trước tạo), trả 1 diff tổng + 1 post_edit_check. Không truyền cùng selector top-level."),
    ] = None,
    max_expand: Annotated[
        int,
        Field(default=10, description="read_option=4: số dòng context tối đa tự mở rộng để old_string unique (mặc định 10)."),
    ] = 10,
    max_line_chars: Annotated[
        int,
        Field(default=2000, description="Snippet mode: dòng dài hơn giới hạn này (file minified) → trả cửa sổ ±500 ký tự quanh match kèm line_truncated (mặc định 2000)."),
    ] = 2000,
) -> str:
    """Đọc trực tiếp nội dung file controller FBO từ ổ cứng (đảm bảo dữ liệu mới nhất, không bị cache).

QUY TRÌNH AGENT (TIẾT KIỆM TOKEN):
1) BƯỚC 1 (MẶC ĐỊNH): Dùng read_option=3 (summary_xml) cho các file .xml trong Dir, Grid, Filter để nắm bản đồ controller (danh sách hàm JS, bảng/view SQL, fields lookup/onchange) với chi phí token cực thấp. Lưu ý: nếu file không phải .xml trực thuộc Dir, Grid, Filter (vd .sql, .js, Report, Templates, Dir/A/a.xml), tool sẽ tự động fallback sang read_option=1 (raw).
2) BƯỚC 2: Khi ĐÃ BIẾT hàm/khối cần sửa → dùng SNIPPET thay vì dump full: symbol='<tên hàm JS>' hoặc block='action:<id>'/'command:<event>'/'field:<name>' (trích trên flat view, kèm origin + warning nếu code nằm trong entity/include — số dòng flat KHÔNG dùng để str_replace file raw) hoặc start_line/end_line (cắt trên raw). symbol cũng hoạt động trên file thường (.js/.aspx/.html/.cshtml — generic JS extractor, view=raw). CHỈ gọi read_option=2 (flat full) khi snippet không đủ.
3) BƯỚC 3: get_xml_entities chỉ khi cần tra cứu vị trí file DTD/Entity chưa flat (vd origin=entity ở bước 2).
4) BƯỚC 4 (SỬA FILE): read_option=4 (suggest_edit) — truyền selector (symbol/block/start_line+end_line/old_string) + new_string → nhận old_string EXACT + physical_file + diff_preview + post_edit_check rồi tự StrReplace. Nhiều edit 1 file → edits[].
5) Sau khi sửa file bằng editor (Write/StrReplace), gọi lại read_option=3 để kiểm tra js.parse_status / sql.parse_status trước khi báo user.

PATH: truyền bất kỳ — abs file/dir hay relative ('Dir/SOTran.xml', 'ClientScript/jAjax.js'); MCP tự resolve qua sticky project context.

MULTI-PROJECT: Làm 2 project xen kẽ → truyền abs path hoặc reference_file để pin project; sticky context theo call abs gần nhất (response luôn kèm project_root/resolved_via để kiểm tra).

CHÚ Ý QUAN TRỌNG: Nếu file cần đọc không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị."""
    try:
        return mcp_read_local_file(
            file_path,
            reference_file,
            read_option,
            start_line=start_line,
            end_line=end_line,
            symbol=symbol,
            block=block,
            context_lines=context_lines,
            line_numbers=line_numbers,
            old_string=old_string,
            new_string=new_string,
            edits=edits,
            max_expand=max_expand,
            max_line_chars=max_line_chars,
        )
    except Exception as e:
        logger.error(f"read_local_file execution error: {e}")
        return format_execution_error("read_local_file", e)


# ============================================================================
# TOOL 5: search_qlyc
# ============================================================================
@server.tool(
    name="search_qlyc",
    annotations=ToolAnnotations(readOnlyHint=True),
)
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
# TOOL 5: clone_things
# ============================================================================
@server.tool(name="clone_things")
def clone_things_tool(
    object: Annotated[
        str,
        Field(
            description="type=0/1: tên SQL, danh sách tên SQL (phân cách ',' ';' hoặc newline — clone/paste nhiều object 1 call) hoặc đường dẫn file .xml controller để seed; type=3: đường dẫn relative, danh sách path, glob (*, ?), hoặc preset ('mail'); type=3 hỗ trợ mapping SRC->DST: DST literal = tên mới (không '/' -> cùng folder; có '/' -> relative target root; trailing '/' = folder đích); rl(s|e,N,V) / rl(FROM,TO) rename pattern trên tên không đuôi, rlx(...) trên full basename; suite:Old->New đổi tên cả bộ controller"
        ),
    ],
    project_source: Annotated[
        str,
        Field(
            description="Đường dẫn tuyệt đối (absolute path) tới project nguồn (chứa Web.config hoặc App_Data)"
        ),
    ],
    project_target: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn tuyệt đối (absolute path) tới project đích (bắt buộc khi type=0; type=1 và type=3 được để trống = clone trong cùng project_source đi kèm -> rename)",
        ),
    ] = "",
    type: Annotated[
        int,
        Field(
            default=0,
            description="Loại clone: 0=SQL clone giữa 2 project (mặc định), 1=paste-for-edit (xuất object từ source ra .sql dạng ALTER để chỉnh sửa trực tiếp), 3=copy file bất kỳ từ project_source sang project_target",
        ),
    ] = 0,
    path_to_pasted: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn file .sql để append; để trống sẽ tự tạo file temp và mở lên editor",
        ),
    ] = "",
    mode_get: Annotated[
        str,
        Field(
            default="proc",
            description="Chỉ dùng khi type=1 và object là file XML: lọc loại object khi lấy seed ('proc', 'func', 'view', 'table', 'full' hoặc kết hợp 'proc,table'). Mặc định 'proc'.",
        ),
    ] = "proc",
    mode_recursion: Annotated[
        str,
        Field(
            default="0",
            description="Chỉ dùng khi type=1: '0'=không đệ quy dependency (mặc định), '1'=đệ quy lấy dependency con từ source.",
        ),
    ] = "0",
    mode_read: Annotated[
        int,
        Field(
            default=1,
            description="Chỉ dùng khi type=1: 1=summary/analyze không ghi file (mặc định), 0=ghi file .sql để sửa (paste-for-edit), 3=trả full definition trong JSON (tối đa 3 object, recursion=0). Type=0,3 bỏ qua.",
        ),
    ] = 1,
    execute: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng khi type=3: false=dry-run chỉ lên danh sách planned (mặc định); true=thực hiện copy file qua shutil.copy2.",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng khi type=3: false=không ghi đè file đã có trên target (mặc định); true=cho phép ghi đè sau khi user xác nhận.",
        ),
    ] = False,
    confirm_overwrite: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng khi type=3: chốt chặn an toàn soft-gate. True=cho phép thực hiện ghi đè file đã có sau khi user đã đồng ý. Mặc định False.",
        ),
    ] = False,
    expand_dirs: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng khi type=3: True=nếu object trỏ tới thư mục, tự động mở rộng quét các file con đệ quy (loại trừ *.f). Mặc định False.",
        ),
    ] = False,
    max_files: Annotated[
        int,
        Field(
            default=100,
            description="Chỉ dùng khi type=3: Giới hạn số file tối đa expand/copy (mặc định 100) để chống nuốt token và chặn copy nhầm.",
        ),
    ] = 100,
    copy_filter: Annotated[
        str,
        Field(
            default="",
            description="Chỉ dùng khi type=3: Bộ lọc khi copy: 'missing' (chỉ copy file thiếu trên target, mặc định khi overwrite=false), 'different' (chỉ copy file khác nội dung), 'all' (copy cả thiếu và có sẵn).",
        ),
    ] = "",
    list_presets: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng khi type=3: True=liệt kê danh sách presets có sẵn (mail, ajax...). Mặc định False.",
        ),
    ] = False,
    planned_sample_size: Annotated[
        int,
        Field(
            default=10,
            description="Chỉ dùng khi type=3: Số phần tử planned[] tối đa hiển thị mẫu khi vượt quá max_files (truncated=True). Mặc định 10.",
        ),
    ] = 10,
) -> str:
    """
    BƯỚC 1 BẮT BUỘC khi cần clone object SQL giữa 2 dự án FBO hoặc lấy object ra chỉnh sửa hoặc copy file:

    1) type=0 (SQL clone giữa 2 dự án):
       - Kiểm tra Target-first, đệ quy dependency và xuất toàn bộ script thiếu vào file .sql temp.
       - Tự động resolve và quét cả hai Database (App DB và Sys DB theo Web.config) cho cả Source và Target.
    2) type=1 (paste-for-edit / analyze):
       - mode_read=1 (mặc định): Phân tích dependency con/cha (child_*/parent_*), phát hiện mã hóa mà KHÔNG ghi file .sql.
       - mode_read=0: Lấy object từ project_source ra file .sql dưới dạng ALTER (proc/func/view) hoặc CREATE (table) để chỉnh sửa trực tiếp (có line_start, line_end).
       - mode_read=3: Trả full SQL body trong JSON analyzed[].definition (tối đa 3 object, mode_recursion=0).
       - object có thể là tên SQL, danh sách tên SQL, hoặc đường dẫn file .xml controller (hỗ trợ mode_get để lọc proc/table/view/func và mode_recursion=1 để đệ quy dependency).
       - project_target được phép để trống. Không deploy lên database.
    3) type=3 (copy file giữa 2 dự án hoặc trong cùng dự án):
       - Copy file bất kỳ (relative path, list, glob, preset 'mail', 'ajax') từ project_source sang project_target.
       - Hỗ trợ mapping SRC->DST: DST literal (không '/' = sibling cùng folder, có '/' = relative root_target, trailing '/' = folder đích).
       - Rename pattern: rl(s|e, N, VALUE) hoặc rl(FROM, TO) trên tên không đuôi (giữ ext), rlx(...) trên full basename.
       - suite:Old->New: clone và đổi tên cả bộ controller.
       - project_target được để trống = clone trong cùng project_source (đi kèm -> rename).
       - execute=False (mặc định): dry-run, không ghi đĩa.
       - execute=True: chỉ copy file chưa có trên target (overwrite=False mặc định).
       - confirm_overwrite=True: cần thiết kèm overwrite=True để ghi đè file có sẵn.
       - expand_dirs=True: mở rộng thư mục quét file con.
       - list_presets=True: xem các presets đăng ký.
    """
    try:
        cfg = get_config()
        result = clone_things(
            object=object,
            project_source=project_source,
            project_target=project_target,
            type=type,
            path_to_pasted=path_to_pasted,
            mode_get=mode_get,
            mode_recursion=mode_recursion,
            mode_read=mode_read,
            execute=execute,
            overwrite=overwrite,
            confirm_overwrite=confirm_overwrite,
            expand_dirs=expand_dirs,
            max_files=max_files,
            copy_filter=copy_filter,
            list_presets=list_presets,
            planned_sample_size=planned_sample_size,
            config=cfg,
        )
        return format_clone_result(result)
    except Exception as e:
        logger.error(f"clone_things execution error: {e}")
        return format_execution_error("clone_things", e)


# ============================================================================
# TOOL 6: compare_things
# ============================================================================
@server.tool(
    name="compare_things",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def compare_things_tool(
    kind: Annotated[
        str,
        Field(
            description="Loại so sánh: 'file' (so 2 file bất kỳ trừ .f) | 'folder' (quét thư mục trừ .f) | 'xml' (tiện ích relative Controllers/ XML) | 'sql' | 'table'"
        ),
    ],
    project_source: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn tuyệt đối (absolute path) tới project nguồn (bắt buộc với kind='sql', 'table', 'xml')",
        ),
    ] = "",
    project_target: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn tuyệt đối (absolute path) tới project đích (bắt buộc với kind='sql', 'table', 'xml')",
        ),
    ] = "",
    object: Annotated[
        str,
        Field(
            default="",
            description="Tên SQL / danh sách tên SQL / relative XML path(s) dưới Controllers/ (phân cách bởi dấu phẩy hoặc chấm phẩy). Lưu ý: file .ent/.txt hãy dùng kind='file' hoặc kind='folder'",
        ),
    ] = "",
    seed: Annotated[
        str,
        Field(
            default="",
            description="Từ khóa tìm kiếm candidate: 'sql' (tìm proc/func/view); 'xml' (quét tìm file XML dưới Controllers/ khi chưa biết path cụ thể); 'folder' (lọc file theo tên/relative path chứa từ khóa, kết hợp include_glob).",
        ),
    ] = "",
    seed_mode: Annotated[
        str,
        Field(
            default="contains",
            description="Chỉ dùng với kind='folder' (+ inventory): cách khớp seed — 'contains' (mặc định, chuỗi con), 'prefix' (tiền tố basename/stem), 'token' (ranh giới từ). Seed token < 4 ký tự sẽ có warning seed_token_short.",
        ),
    ] = "contains",
    db_type: Annotated[
        str,
        Field(
            default="app",
            description="Loại database: 'app' | 'sys' | 'both' (mặc định 'app')",
        ),
    ] = "app",
    mode: Annotated[
        str,
        Field(
            default="summary",
            description="Độ chi tiết trả về: 'summary' (mặc định có hunks line ranges + preview) | 'hunks' (thêm unified_diff) | 'body' (thêm context snippet quanh hunk)",
        ),
    ] = "summary",
    file_a: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn tuyệt đối file A trên đĩa (bắt buộc khi kind='file', hỗ trợ mọi đuôi text/config .ent, .txt, .sql, .xml, .js... TRỪ .f mã hóa)",
        ),
    ] = "",
    file_b: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn tuyệt đối file B trên đĩa (bắt buộc khi kind='file', hỗ trợ mọi đuôi text/config .ent, .txt, .sql, .xml, .js... TRỪ .f mã hóa)",
        ),
    ] = "",
    folder_a: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn thư mục A trên đĩa hoặc UNC (bắt buộc khi kind='folder', quét mọi file khớp glob trừ file .f mã hóa)",
        ),
    ] = "",
    folder_b: Annotated[
        str,
        Field(
            default="",
            description="Đường dẫn thư mục B trên đĩa hoặc UNC (bắt buộc khi kind='folder', quét mọi file khớp glob trừ file .f mã hóa)",
        ),
    ] = "",
    detail: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng cho kind='folder': mặc định False (chỉ trả summary inventory tên file theo bucket, so bin/folder cực gọn); True (kèm compared[] chi tiết per-file). Với kind khác: giữ nguyên.",
        ),
    ] = False,
    detail_status: Annotated[
        str,
        Field(
            default="",
            description="Chỉ dùng khi kind='folder' và detail=True: lọc status xuất ra compared[] bằng danh sách CSV (ví dụ 'different_content' hoặc 'missing_on_b,different_content'). Rỗng = mọi status.",
        ),
    ] = "",
    include_compared: Annotated[
        Optional[bool],
        Field(
            default=None,
            description="Alias của detail (khi được truyền, giá trị này sẽ ghi đè detail).",
        ),
    ] = None,
    ignore_line_endings: Annotated[
        bool,
        Field(
            default=True,
            description="Bỏ qua khác biệt xuống dòng CRLF vs LF khi so sánh nội dung text (mặc định True)",
        ),
    ] = True,
    ignore_whitespace: Annotated[
        bool,
        Field(
            default=False,
            description="Bỏ qua khoảng trắng đầu/cuối mỗi dòng khi so sánh text (mặc định False)",
        ),
    ] = False,
    max_diff_lines: Annotated[
        int,
        Field(
            default=200,
            description="Giới hạn số dòng unified_diff hoặc preview (mặc định 200)",
        ),
    ] = 200,
    max_objects: Annotated[
        Optional[int],
        Field(
            default=None,
            description="Giới hạn số object/file chi tiết được trả về (mặc định 50 cho sql/table/xml, 200 cho folder)",
        ),
    ] = None,
    recursive: Annotated[
        bool,
        Field(
            default=True,
            description="Quét đệ quy thư mục con (chỉ dùng cho kind='folder', mặc định True)",
        ),
    ] = True,
    compare_content: Annotated[
        bool,
        Field(
            default=False,
            description="So sánh nội dung hash/hunks cho file trong folder (chỉ dùng cho kind='folder', mặc định False)",
        ),
    ] = False,
    hash_max_bytes: Annotated[
        int,
        Field(
            default=1048576,
            description="Kích thước tối đa của file để tính hash khi compare_content=True (mặc định 1MB)",
        ),
    ] = 1048576,
    include_glob: Annotated[
        str,
        Field(
            default="*",
            description="Pattern lọc file trong folder, ví dụ '*.dll' (mặc định '*')",
        ),
    ] = "*",
    exclude_glob: Annotated[
        str,
        Field(
            default="",
            description="Pattern loại trừ file trong folder, ví dụ '*.pdb' (mặc định '')",
        ),
    ] = "",
    name_compare: Annotated[
        str,
        Field(
            default="case_insensitive",
            description="So sánh tên file relative: 'case_insensitive' hoặc 'case_sensitive'",
        ),
    ] = "case_insensitive",
    meta_tolerance_seconds: Annotated[
        int,
        Field(
            default=0,
            description="Dung sai thời gian (giây) cho created/modified (mặc định 0)",
        ),
    ] = 0,
    context_lines: Annotated[
        int,
        Field(
            default=3,
            description="Số dòng ngữ cảnh quanh vùng thay đổi (mặc định 3)",
        ),
    ] = 3,
    schema: Annotated[
        str,
        Field(
            default="dbo",
            description="Database schema mặc định khi tên object không có tiền tố (chỉ dùng cho sql/table, mặc định 'dbo')",
        ),
    ] = "dbo",
    xml_view: Annotated[
        str,
        Field(
            default="original",
            description="Chỉ dùng cho kind='xml': 'original' (hoặc 'raw')=so file gốc trên đĩa; 'flat' (hoặc 'expanded')=so sau khi expand ENTITY/Include (giống read_local_file option=2)",
        ),
    ] = "original",
    include_unified_diff: Annotated[
        bool,
        Field(
            default=False,
            description="Bật xuất chuỗi unified_diff (mặc định False để tiết kiệm token chat)",
        ),
    ] = False,
    include_text_snippets: Annotated[
        bool,
        Field(
            default=False,
            description="Bật trích xuất dòng code preview/snippet trong hunk (mặc định False, tool chỉ báo điểm khác biệt qua line ranges)",
        ),
    ] = False,
    max_hunks_summary: Annotated[
        int,
        Field(
            default=5,
            description="Số lượng hunk tối đa trả về trong mode='summary' (mặc định 5, kèm hunk_count thật và hunks_omitted)",
        ),
    ] = 5,
    max_hunks_detail: Annotated[
        int,
        Field(
            default=30,
            description="Số lượng hunk tối đa trả về trong mode='hunks' hoặc 'body' (mặc định 30)",
        ),
    ] = 30,
    inventory: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng khi kind='folder': True=liệt kê file trong 1 thư mục (chỉ cần folder_a, không so sánh 2 bên, không omit tên file trùng). Mặc định False.",
        ),
    ] = False,
    list_identical: Annotated[
        bool,
        Field(
            default=False,
            description="Chỉ dùng khi kind='folder': True=liệt kê danh sách tên file trùng nhau trong summary.identical thay vì giấu trong omitted_identical_count. Mặc định False.",
        ),
    ] = False,
    ctx: Context = None,
) -> str:
    """
    MCP Tool compare_things: So sánh file bất kỳ trên đĩa (.xml, .ent, .txt, .sql, .js, .config...) trừ .f mã hóa; folder tương tự; xml = convenience controller relative; sql/table = database objects.
    - kind='file': So sánh 2 file bất kỳ trên đĩa hoặc UNC trừ file .f mã hóa FBO. Tự động phát hiện diff_reason (bom, line_ending, whitespace, binary, text_lines).
    - kind='folder': Quét và so sánh thư mục (loại trừ *.f mã hóa). Hỗ trợ 'seed' để lọc relative path / filename chứa từ khóa. 'detail'=False mặc định trả về summary gọn (chỉ danh sách tên file theo từng bucket missing_on_b/missing_on_a/different_content/different_meta), compared=[]. Đặt 'detail'=True để nhận compared[] chi tiết từng file kèm diff_reason. Khi byte khác nhưng normalized line bằng nhau, xếp vào different_meta với diff_reason (bom, line_ending, whitespace, encoding_or_bytes), không báo review_hunks giả.
    - kind='xml': Tiện ích so sánh controller XML relative dưới Controllers/ (không dùng cho .ent/.txt). Hỗ trợ 'seed' để tự discover relative path theo từ khóa (union hits 2 bên) khi chưa biết đường dẫn chính xác.
    - kind='sql', kind='table': So sánh procedure/function/view hoặc schema bảng giữa 2 database.
    Tư duy: Tool CHỈ BÁO ĐIỂM KHÁC BIỆT (khoảng dòng thay đổi, schema_diff, signals, metadata). CẤM preview/dump nội dung mặc định để tiết kiệm token chat.
    Semantics: project_source là nguồn clone/tham chiếu, project_target là project đang sửa.
    Tool là READ-ONLY, hoàn toàn không tự ý clone, ALTER, deploy hay copy/sửa file.
    """
    loop = asyncio.get_running_loop()

    async def _safe_report_progress(progress: float, total: float | None = None, message: str | None = None) -> None:
        if ctx is not None:
            try:
                await ctx.report_progress(progress=progress, total=total, message=message)
            except Exception:
                pass

    def on_progress(done: int, total: int, msg: str = "") -> None:
        if ctx is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    _safe_report_progress(
                        progress=float(done),
                        total=float(total) if total else None,
                        message=msg,
                    ),
                    loop,
                )
            except Exception:
                pass

    try:
        cfg = get_config()
        await _safe_report_progress(progress=0.0, total=100.0, message=f"Bắt đầu so sánh ({kind})...")
        result = await asyncio.to_thread(
            compare_things,
            kind=kind,
            project_source=project_source,
            project_target=project_target,
            object=object,
            seed=seed,
            seed_mode=seed_mode,
            db_type=db_type,
            mode=mode,
            file_a=file_a,
            file_b=file_b,
            folder_a=folder_a,
            folder_b=folder_b,
            detail=detail,
            detail_status=detail_status,
            include_compared=include_compared,
            ignore_line_endings=ignore_line_endings,
            ignore_whitespace=ignore_whitespace,
            max_diff_lines=max_diff_lines,
            max_objects=max_objects,
            recursive=recursive,
            compare_content=compare_content,
            hash_max_bytes=hash_max_bytes,
            include_glob=include_glob,
            exclude_glob=exclude_glob,
            name_compare=name_compare,
            meta_tolerance_seconds=meta_tolerance_seconds,
            context_lines=context_lines,
            schema=schema,
            xml_view=xml_view,
            include_unified_diff=include_unified_diff,
            include_text_snippets=include_text_snippets,
            max_hunks_summary=max_hunks_summary,
            max_hunks_detail=max_hunks_detail,
            inventory=inventory,
            list_identical=list_identical,
            config=cfg,
            on_progress=on_progress,
        )
        await _safe_report_progress(progress=100.0, total=100.0, message="So sánh hoàn tất.")

        return format_compare_result(result)
    except Exception as e:
        logger.error(f"compare_things execution error: {e}")
        return format_execution_error("compare_things", e)


# ============================================================================
# TOOL 7: search_files
# ============================================================================
@server.tool(
    name="search_files",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def search_files_tool(
    root: Annotated[
        str,
        Field(description="Path BẤT KỲ cần tìm kiếm: abs folder, abs FILE (search đúng file đó, files_candidate=1), project root, hoặc relative ('ClientScript', 'Grid') — MCP tự resolve qua sticky project context (hỗ trợ local hoặc UNC)"),
    ],
    pattern: Annotated[
        str,
        Field(default="", description="Từ khóa hoặc biểu thức chính quy (regex) cần tìm kiếm — bắt buộc khi mode='content'; bỏ trống được khi mode='definition'/'files_only'"),
    ] = "",
    regex: Annotated[
        bool,
        Field(default=False, description="True=tìm theo regex; False=tìm literal text chính xác. Mặc định False."),
    ] = False,
    include_glob: Annotated[
        str,
        Field(
            default="*.{xml,aspx,js,html,config,ent,txt,sql}",
            description="Mẫu glob file cần quét (phân tách bởi dấu phẩy, hỗ trợ cú pháp mở rộng {...}).",
        ),
    ] = "*.{xml,aspx,js,html,config,ent,txt,sql}",
    glob: Annotated[
        str,
        Field(
            default="",
            description="Alias của include_glob (tương thích call cũ). Chỉ áp dụng khi include_glob để mặc định.",
        ),
    ] = "",
    exclude_glob: Annotated[
        str,
        Field(
            default="**/*.f,**/*.dll,**/*.pdb,**/bin/**",
            description="Mẫu glob file cần loại trừ (tự động loại trừ *.f mã hóa và file nhị phân).",
        ),
    ] = "**/*.f,**/*.dll,**/*.pdb,**/bin/**",
    recursive: Annotated[
        bool,
        Field(default=True, description="Quét đệ quy các thư mục con (mặc định True)"),
    ] = True,
    case_sensitive: Annotated[
        bool,
        Field(default=False, description="Phân biệt hoa thường (mặc định False)"),
    ] = False,
    max_files: Annotated[
        int,
        Field(default=50, description="Số lượng file tối đa quét qua (mặc định 50)"),
    ] = 50,
    max_matches_per_file: Annotated[
        int,
        Field(default=5, description="Số lượng dòng khớp tối đa trên mỗi file (mặc định 5)"),
    ] = 5,
    max_total_matches: Annotated[
        int,
        Field(default=100, description="Tổng số dòng khớp tối đa trả về toàn bộ (mặc định 100)"),
    ] = 100,
    context_lines: Annotated[
        int,
        Field(default=0, description="Số dòng ngữ cảnh quanh dòng khớp (0=chỉ trả về dòng khớp, mặc định 0)"),
    ] = 0,
    prefer_name_match: Annotated[
        bool,
        Field(
            default=True,
            description="Ưu tiên quét các file có tên/path khớp pattern và các thư mục trọng yếu (Filter, Grid, Dir, ClientScript, Main, Templates) trước. Mặc định True.",
        ),
    ] = True,
    mode: Annotated[
        str,
        Field(
            default="content",
            description="'content' (mặc định, grep như cũ) | 'definition' (tìm nơi ĐỊNH NGHĨA symbol JS — trả definitions[], definition_found, usage_hint) | 'references' (list usage file:line của symbol — usages[] + definitions[] phân loại, dùng khi rename/refactor) | 'files_only' (chỉ list candidate path, không đọc nội dung — xác định phạm vi trước khi grep).",
        ),
    ] = "content",
    symbol: Annotated[
        str,
        Field(
            default="",
            description="Tên symbol khi mode='definition'/'references' (vd 'Base64', '$message', 'open$CreateVoucher'). Server tự build regex định nghĩa (function/var/window./assign/object literal) và escape ký tự đặc biệt.",
        ),
    ] = "",
    include_definitions: Annotated[
        bool,
        Field(
            default=True,
            description="Chỉ dùng khi mode='references': True=trả kèm definitions[] (mặc định); False=chỉ trả usages[].",
        ),
    ] = True,
    reference_file: Annotated[
        str,
        Field(
            default="",
            description="Optional override — đường dẫn ABSOLUTE tới 1 file trong project FBO khi root là relative và cần chỉ định đúng project (làm nhiều project xen kẽ). Thường bỏ trống nhờ sticky context.",
        ),
    ] = "",
    time_budget_seconds: Annotated[
        float,
        Field(
            default=0,
            description="Giới hạn thời gian wall-clock cho enumeration + scan (giây). 0 = dùng config search_files.time_budget_seconds (mặc định 45). Hết budget → trả partial với timed_out=true thay vì treo tới client timeout.",
        ),
    ] = 0,
    ctx: Context = None,
) -> str:
    """
    MCP Tool search_files: Tìm kiếm nội dung văn bản (grep) an toàn trong các thư mục dự án trên ổ đĩa local hoặc mạng UNC.
    - CẤM đọc file *.f mã hóa của FastBusiness; tự động bỏ qua file nhị phân.
    - Hỗ trợ giải mã UTF-8 và Windows-1258 (CP1258).
    - Có chốt chặn số file và số kết quả để tránh làm tràn bộ nhớ/context.
    - root nhận path BẤT KỲ: abs folder, abs file (search đúng file đó), hoặc relative — MCP tự resolve qua sticky project context.
    - mode='definition' + symbol: trả lời "symbol X có được định nghĩa ở đâu / có tồn tại không" (definitions[] + definition_found + usage_hint) thay vì list hàng trăm dòng usage. definition_found=false + truncated → KHÔNG kết luận chưa định nghĩa, hẹp root/include_glob.
    - mode='files_only': list candidate path sau glob + priority sort, không mở file nào.
    - Lưu ý DX: Root rộng dễ truncated — ưu tiên Filter/, ClientScript/, hoặc glob tên controller; tool đã ưu tiên filename match.
    - Quét UNC root rộng: tool tự dừng sau time_budget_seconds và trả kết quả partial (timed_out=true) — hẹp root/include_glob rồi gọi lại.
    - MULTI-PROJECT: Làm 2 project xen kẽ → truyền abs path hoặc reference_file để pin project; sticky context theo call abs gần nhất (response kèm project_root/resolved_via + warnings khi context vừa đổi project).
    """
    loop = asyncio.get_running_loop()

    async def _safe_report_progress(progress: float, total: float | None = None, message: str | None = None) -> None:
        if ctx is not None:
            try:
                await ctx.report_progress(progress=progress, total=total, message=message)
            except Exception:
                pass

    def on_progress(done: int, total: int, msg: str = "") -> None:
        if ctx is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    _safe_report_progress(
                        progress=float(done),
                        total=float(total) if total else None,
                        message=msg,
                    ),
                    loop,
                )
            except Exception:
                pass

    try:
        cfg = get_config()
        budget = time_budget_seconds or float(
            (cfg.get("search_files") or {}).get("time_budget_seconds", 45.0)
        )
        # 'glob' là alias: chỉ dùng khi caller không truyền include_glob tường minh
        effective_include = include_glob
        if glob and include_glob == "*.{xml,aspx,js,html,config,ent,txt,sql}":
            effective_include = glob

        await _safe_report_progress(progress=0.0, total=100.0, message="Bat dau search_files...")
        result = await asyncio.to_thread(
            search_files,
            root=root,
            pattern=pattern,
            regex=regex,
            include_glob=effective_include,
            exclude_glob=exclude_glob,
            recursive=recursive,
            case_sensitive=case_sensitive,
            max_files=max_files,
            max_matches_per_file=max_matches_per_file,
            max_total_matches=max_total_matches,
            context_lines=context_lines,
            prefer_name_match=prefer_name_match,
            mode=mode,
            symbol=symbol,
            reference_file=reference_file,
            include_definitions=include_definitions,
            on_progress=on_progress,
            time_budget_seconds=budget,
        )
        await _safe_report_progress(progress=100.0, total=100.0, message="search_files hoan tat.")
        import json
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"search_files execution error: {e}")
        return format_execution_error("search_files", e)



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


# ============================================================================
# Call logging & Response oversize guard
# (docs/doc/gemini/GEMINI-mcp-call-logging.md & GEMINI-mcp-response-oversize-guard.md)
# ============================================================================
from .utils import call_log, response_guard

call_log.init_call_logging()

_inner_call_tool = server.call_tool  # _safe_call_tool (ToolError → tiếng Việt)


async def _logged_call_tool(name: str, arguments: dict, context=None):
    t0 = time.perf_counter()
    try:
        result = await _inner_call_tool(name, arguments, context)
    except Exception as e:
        call_log.log_tool_call(
            name, arguments, (time.perf_counter() - t0) * 1000, exc=e
        )
        raise
    text, is_error = call_log.extract_response_text(result)
    cfg = get_config()
    guard_cfg = cfg.get("response_guard") or {}
    max_chars = guard_cfg.get("max_chars", response_guard._MAX_RESPONSE_CHARS)
    result, guard_meta = response_guard.apply(name, result, text, max_chars=max_chars)
    call_log.log_tool_call(
        name, arguments, (time.perf_counter() - t0) * 1000,
        response_text=text, is_error=is_error, extra=guard_meta,
    )
    return result


server.call_tool = _logged_call_tool

