"""Chuyển lỗi Pydantic / Exception sang message Agent-friendly (tiếng Việt)."""

from __future__ import annotations

import re
from pydantic import ValidationError
from mcp.server.mcpserver.exceptions import ToolError

from .agent_messages import (
    VALIDATION_ERROR_MSG,
    GENERAL_EXECUTION_ERROR_MSG,
    PATH_HINT_FIELDS,
)


def _extract_literal_values(msg: str) -> str:
    """Trích giá trị hợp lệ từ Pydantic literal_error msg.

    VD: "Input should be 'app' or 'sys'" → "'app' hoặc 'sys'"
    VD: "Input should be 1 or 2"         → "1 hoặc 2"
    """
    # Xoá tiền tố "Input should be "
    body = re.sub(r"^Input should be\s+", "", msg, flags=re.IGNORECASE).strip()
    # Chuẩn hoá "X or Y" → "X hoặc Y"
    body = re.sub(r"\bor\b", "hoặc", body)
    return body if body else msg


def _format_validation_detail_vi(tool_name: str, exc: ValidationError) -> str:
    """Format đối tượng ValidationError thành tiếng Việt."""
    lines = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = str(loc[-1]) if loc else "?"
        err_type = err.get("type") or ""
        msg = err.get("msg") or ""

        if err_type == "missing":
            lines.append(f"- Thiếu tham số bắt buộc: '{field}'")
            if field in PATH_HINT_FIELDS:
                lines.append("  → Dùng đường dẫn ABSOLUTE tới file XML trong project FBO (VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml).")
        elif err_type == "literal_error":
            valid_vals = _extract_literal_values(msg)
            lines.append(f"- '{field}': giá trị không hợp lệ. Chỉ chấp nhận {valid_vals}.")
        elif err_type == "int_parsing":
            lines.append(f"- '{field}': phải là số nguyên (integer), không phải chuỗi.")
        else:
            lines.append(f"- '{field}': {msg}")

    return "\n".join(lines) if lines else str(exc)


def _pydantic_body_to_vi(body: str) -> str:
    """Parse text thông báo lỗi Pydantic trong ToolError sang tiếng Việt."""
    lines = []
    current_field = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("For further information") or "pydantic.dev" in line:
            continue
        if not raw_line.startswith(" ") and not raw_line.startswith("\t") and "validation error" not in line.lower():
            current_field = line.strip()
        elif current_field and ("[type=" in line or "Field required" in line or "Input should" in line):
            if "type=missing" in line or "Field required" in line:
                lines.append(f"- Thiếu tham số bắt buộc: '{current_field}'")
                if current_field in PATH_HINT_FIELDS:
                    lines.append("  → Dùng đường dẫn ABSOLUTE tới file XML trong project FBO (VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml).")
            elif "type=literal_error" in line or "Input should be" in line:
                m_lit = re.search(r"Input should be\s+([^\[]+)", line)
                raw_hint = m_lit.group(1).strip() if m_lit else "giá trị được quy định"
                val_hint = re.sub(r"\bor\b", "hoặc", raw_hint).strip()
                lines.append(f"- '{current_field}': giá trị không hợp lệ. Chỉ chấp nhận {val_hint}.")
            elif "type=int_parsing" in line or "integer" in line.lower():
                lines.append(f"- '{current_field}': phải là số nguyên (integer), không phải chuỗi.")
            else:
                clean_msg = re.sub(r"\[type=[^\]]+\]", "", line).strip()
                lines.append(f"- '{current_field}': {clean_msg}")
            current_field = None

    return "\n".join(lines) if lines else body


def format_validation_error_message(tool_name: str, body: str) -> str:
    """Tạo chuỗi thông báo lỗi tiếng Việt hoàn chỉnh cho Agent."""
    detail_vi = _pydantic_body_to_vi(body)
    return VALIDATION_ERROR_MSG.format(tool_name=tool_name, detail_vi=detail_vi).strip()


def raise_validation_tool_error(tool_name: str, exc: ValidationError) -> None:
    """Raise ToolError với thông báo tiếng Việt."""
    detail_vi = _format_validation_detail_vi(tool_name, exc)
    raise ToolError(VALIDATION_ERROR_MSG.format(tool_name=tool_name, detail_vi=detail_vi).strip())


def format_execution_error(tool_name: str, exc: Exception) -> str:
    """Format lỗi execution thành GENERAL_EXECUTION_ERROR_MSG."""
    return GENERAL_EXECUTION_ERROR_MSG.format(
        tool_name=tool_name,
        error_detail=str(exc),
    ).strip()
