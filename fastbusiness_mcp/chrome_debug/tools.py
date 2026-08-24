"""Đăng ký tool MCP chrome_debug với MCPServer."""

from __future__ import annotations

from typing import Annotated, Any, Callable, Dict
from pydantic import Field

from .config_loader import load_chrome_debug_config
from .service import dispatch_chrome_debug
from ..tool_errors import format_execution_error
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


def register_chrome_tools(server: Any, get_config_fn: Callable[[], dict]) -> None:
    """Đăng ký tool duy nhất `chrome_debug` vào instance MCPServer."""

    @server.tool(name="chrome_debug")
    def chrome_debug_tool(
        type: Annotated[
            int,
            Field(
                description="Phân loại thao tác: 1=status (kiểm tra CDP + tabs), 2=inspect (bắt lỗi + snapshot UI), 3=interact (fill/click), 4=execute (chạy JS)",
                ge=1,
                le=4,
            ),
        ],
        tab_keyword: Annotated[
            str,
            Field(
                default="",
                description="Từ khóa lọc tab theo Title hoặc URL (ví dụ: 'hóa đơn', 'arcthd'). Để trống để chọn tab active gần nhất.",
            ),
        ] = "",
        mode: Annotated[
            str,
            Field(
                default="interactive",
                description="Chế độ snapshot (mặc định 'interactive')",
            ),
        ] = "interactive",
        include_errors: Annotated[
            bool,
            Field(
                default=True,
                description="type=2: Bao gồm danh sách lỗi console & network trong kết quả (mặc định True)",
            ),
        ] = True,
        clear_errors: Annotated[
            bool,
            Field(
                default=False,
                description="type=2: Xóa buffer lỗi sau khi đọc (mặc định False)",
            ),
        ] = False,
        click: Annotated[
            str,
            Field(
                default="",
                description="type=3: Định danh phần tử cần click (VD: ref 'e17', selector '#btnSave', hoặc text nút 'Lưu')",
            ),
        ] = "",
        fields_json: Annotated[
            str,
            Field(
                default="",
                description="type=3: JSON Object chứa danh sách trường cần điền (VD: '{\"ma_kh\": \"123\", \"ngay_ct\": \"2025-01-01\"}')",
            ),
        ] = "",
        frame_index: Annotated[
            int,
            Field(
                default=0,
                description="type=3: Index của iframe cần thao tác (mặc định 0 là main frame)",
            ),
        ] = 0,
        script: Annotated[
            str,
            Field(
                default="",
                description="type=4: Đoạn mã JavaScript expression / IIFE cần thực thi trên browser",
            ),
        ] = "",
    ) -> str:
        """Tool chẩn đoán và tương tác runtime với FastBusiness trên Chrome thật qua CDP.
        
        Quy tắc phân loại 'type':
        - type=1: Kiểm tra CDP sống hay chết và liệt kê danh sách tab.
        - type=2: Đọc buffer lỗi console/network + snapshot các phần tử tương tác (gắn ref e0, e1...).
        - type=3: Điền form (fields_json) và/hoặc click phần tử (click).
        - type=4: Chạy JavaScript expression/IIFE trực tiếp trên trang.
        """
        try:
            parent_cfg = get_config_fn()
            chrome_cfg = load_chrome_debug_config(parent_cfg)

            return dispatch_chrome_debug(
                cfg=chrome_cfg,
                type=type,
                tab_keyword=tab_keyword,
                mode=mode,
                include_errors=include_errors,
                clear_errors=clear_errors,
                click=click,
                fields_json=fields_json,
                frame_index=frame_index,
                script=script,
            )
        except Exception as e:
            logger.error(f"Error executing chrome_debug (type={type}): {e}", exc_info=True)
            return format_execution_error("chrome_debug", e)

    logger.info("Registered MCP tool 'chrome_debug' successfully.")
