"""MCP response oversize guard — spill to local file when response exceeds token cap.

Spec: docs/doc/gemini/GEMINI-mcp-response-oversize-guard.md
Mục tiêu: Server chủ động chặn response oversize — ghi full payload ra file
local cạnh exe và trả JSON compact {success, oversized, result_file, summary, hint}
thay vì để client báo lỗi (token limit). Agent đọc tiếp bằng chính tool
read_local_file (start_line/end_line).

Ràng buộc cứng:
- Không đổi logic/format của bất kỳ tool nào.
- Không ghi spill lên UNC. Không ghi ra stdout (stdio MCP).
- Không để guard làm tool call fail — mọi lỗi IO trong guard → warn stderr,
  trả response gốc.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from typing import Any, Optional

from . import call_log

_MAX_RESPONSE_CHARS = 60_000
_warned = False


def _warn_once(msg: str) -> None:
    global _warned
    if _warned:
        return
    _warned = True
    try:
        sys.stderr.write(f"[response_guard] {msg}\n")
    except Exception:
        pass


def _reset_warned() -> None:
    """Test hook để reset flag cảnh báo."""
    global _warned
    _warned = False


def apply(
    tool: str,
    result: Any,
    text: Optional[str],
    max_chars: int = _MAX_RESPONSE_CHARS,
) -> tuple[Any, Optional[dict]]:
    """Kiểm tra và áp dụng oversize guard cho response.

    Returns:
        tuple[Any, Optional[dict]]: (new_result, guard_meta).
        Nếu không oversize hoặc có lỗi: guard_meta là None.
        Nếu oversize: guard_meta có dạng:
            {"oversized": True, "result_chars": N, "result_file": "<path>"}
    """
    if text is None or len(text) <= max_chars:
        return result, None

    try:
        result_chars = len(text)
        parsed: Any = None
        ext = "txt"
        try:
            parsed = json.loads(text)
            ext = "json"
        except Exception:
            pass

        now = datetime.now()
        ts_str = f"{now:%Y%m%d-%H%M%S}-{now.microsecond // 1000:03d}"
        filename = f"overflow-{tool}-{ts_str}.{ext}"

        # Ghi file local cạnh exe (tái dùng get_log_dir() — đã đảm bảo local, không UNC)
        try:
            log_dir = call_log.get_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            overflow_path = log_dir / filename
            with open(overflow_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            _warn_once(f"spill write failed: {e}")
            return result, None

        # Build summary
        if isinstance(parsed, dict):
            summary = call_log.summarize_dict(parsed)
        elif isinstance(parsed, list):
            summary = {"items_n": len(parsed)}
        else:
            summary = {"text_preview": text[:300]}

        success = True
        if isinstance(parsed, dict) and "success" in parsed:
            success = bool(parsed["success"])

        # result_file là path trên máy chạy MCP server (local abs path)
        compact_payload = {
            "success": success,
            "oversized": True,
            "tool": str(tool),
            "result_chars": result_chars,
            "result_file": str(overflow_path.resolve()),
            "summary": summary,
            "hint": (
                "Response vuot gioi han client. Doc tiep bang read_local_file "
                "(file_path=result_file, start_line/end_line) hoac goi lai tool "
                "voi pham vi hep hon (root/include_glob/max_files...)."
            ),
        }
        guard_meta = {
            "oversized": True,
            "result_chars": result_chars,
            "result_file": str(overflow_path.resolve()),
        }

        compact_json = json.dumps(compact_payload, ensure_ascii=False, indent=2)

        # 1. Trường hợp result là chuỗi thuần (str)
        if isinstance(result, str):
            return compact_json, guard_meta

        # 2. Trường hợp result có thuộc tính .content (vd: CallToolResult)
        if hasattr(result, "content"):
            from mcp.types import TextContent

            new_content = [TextContent(type="text", text=compact_json)]
            if hasattr(result, "model_copy"):
                try:
                    new_result = result.model_copy(update={"content": new_content})
                    return new_result, guard_meta
                except Exception:
                    pass

            try:
                new_result = copy.copy(result)
                new_result.content = new_content
                return new_result, guard_meta
            except Exception:
                pass

        # 3. Kiểu lạ không nhận ra → passthrough an toàn
        return result, None

    except Exception as e:
        _warn_once(f"guard apply error: {e}")
        return result, None
