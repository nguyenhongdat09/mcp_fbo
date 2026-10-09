"""Recovery tầng wrapper — gắn "bước tiếp theo" vào response lỗi của tool.

Áp trong ``_logged_call_tool`` (mcp_app.py) cho MỌI tool: response JSON có
``success: false`` + ``error_code`` khớp luật → thêm key ``recovery``
``{rule, kind: fix_args|switch_tool, hint, next: {tool, call}}``.

Nhiều tool đã tự trả hint (path_not_found có "Gần giống", symbol_not_found
có available_functions...) — luật chỉ bổ sung phần còn THIẾU: gọi gì tiếp.
Lỗi DB (Invalid column/object) do query_database tự xử lý (column_hint /
object_hint) vì cần kết nối DB.

Nguồn luật: thống kê lỗi thật 16/9–9/10 (543 lỗi / 5.833 call).
"""
from __future__ import annotations

import copy
import difflib
import json
import ntpath
import re
from typing import Any, Callable

_REQUIRED_RE = re.compile(r"\b([a-z_]+)\s+is required", re.IGNORECASE)


def _old_string_not_found(tool: str, args: dict, data: dict) -> dict | None:
    if data.get("closest_match"):
        return None   # tool đã chỉ đoạn gần đúng
    return {
        "kind": "fix_args",
        "hint": "Đừng gõ lại old_string bằng tay — lấy vùng cần sửa bằng "
                "symbol/block/start_line+end_line (read_option=4) rồi copy "
                "nguyên old_string từ response",
        "next": {"tool": "read_local_file",
                 "call": {"file_path": args.get("file_path"),
                          "read_option": 4,
                          "block": "<command:X | action:X | field:x>"}},
    }


def _symbol_not_found(tool: str, args: dict, data: dict) -> dict | None:
    symbol = args.get("symbol") or data.get("symbol")
    if not symbol:
        return None
    fp = str(args.get("file_path") or "")
    folder = ntpath.dirname(fp) or "<thư mục controller>"
    return {
        "kind": "switch_tool",
        "hint": f"'{symbol}' không định nghĩa trong file này — có thể ở file "
                "include/entity hoặc JS chung; tìm nơi định nghĩa trước",
        "next": {"tool": "search_files",
                 "call": {"root": folder, "mode": "content",
                          "pattern": symbol}},
    }


def _block_not_found(tool: str, args: dict, data: dict) -> dict | None:
    block = str(args.get("block") or data.get("block") or "")
    avail = data.get("available") or {}
    if ":" not in block or not isinstance(avail, dict):
        return None
    kind, name = block.split(":", 1)
    pool = avail.get(kind.strip().lower() + "s") or []
    if not isinstance(pool, list) or not pool:
        return None
    close = difflib.get_close_matches(name.strip(), [str(p) for p in pool],
                                      n=3, cutoff=0.5)
    out = {"kind": "fix_args",
           "hint": f"Không có {kind} '{name}' — chọn tên trong "
                   f"available.{kind}s"}
    if close:
        out["did_you_mean"] = [f"{kind}:{c}" for c in close]
    return out


def _path_not_found(tool: str, args: dict, data: dict) -> dict | None:
    if data.get("hint"):
        return None   # tool đã gợi ý tên gần giống
    path = str(data.get("input") or args.get("file_path")
               or args.get("root") or "")
    base = ntpath.basename(path.rstrip("\\/"))
    stem = base.split(".")[0]
    if not stem:
        return None
    return {
        "kind": "switch_tool",
        "hint": "Path không tồn tại — tìm file theo tên trong project",
        "next": {"tool": "search_files",
                 "call": {"root": ntpath.dirname(path) or "<project>",
                          "mode": "files_only",
                          "include_glob": f"*{stem}*"}},
    }


def _missing_param(tool: str, args: dict, data: dict) -> dict | None:
    msg = str(data.get("message") or data.get("error") or "")
    m = _REQUIRED_RE.search(msg)
    if not m:
        return None
    need = m.group(1)
    passed = [k for k, v in (args or {}).items() if v not in (None, "", [])]
    out = {"kind": "fix_args",
           "hint": f"Thiếu param '{need}'. Đã truyền: {', '.join(passed)}"}
    near = difflib.get_close_matches(need, passed, n=1, cutoff=0.3)
    wrong = [k for k in passed if k not in ("root", "file_path", "mode")]
    if near and near[0] != need:
        out["hint"] += f" — '{near[0]}' không phải tên đúng, dùng '{need}'"
    elif wrong:
        out["hint"] += (f" — có thể giá trị đang nằm ở {wrong[0]}; truyền "
                        f"vào '{need}'")
    return out


# error_code → handler. Handler trả None = không có gì thêm.
RULES: dict[str, Callable[[str, dict, dict], dict | None]] = {
    "old_string_not_found": _old_string_not_found,
    "symbol_not_found": _symbol_not_found,
    "block_not_found": _block_not_found,
    "path_not_found": _path_not_found,
    "invalid_pattern": _missing_param,
    "snippet_params_required": _missing_param,
    "missing_target": _missing_param,
}


def build_recovery(tool: str, args: dict, text: str | None) -> dict | None:
    """Tính khối recovery từ response text (JSON lỗi). Không raise."""
    try:
        if not text or not text.lstrip().startswith("{"):
            return None
        data = json.loads(text)
        if not isinstance(data, dict) or data.get("success") is not False:
            return None
        if data.get("recovery"):
            return None   # tool đã tự gắn (vd query_database)
        code = str(data.get("error_code") or "")
        handler = RULES.get(code)
        if handler is None and _REQUIRED_RE.search(
                str(data.get("message") or data.get("error") or "")):
            handler, code = _missing_param, "missing_param"
        if handler is None:
            return None
        rec = handler(tool, args or {}, data)
        if rec:
            rec = {"rule": code, **rec}
        return rec
    except Exception:
        return None


def attach_recovery(result: Any, text: str | None,
                    rec: dict) -> tuple[Any, str | None]:
    """Gắn ``recovery`` vào JSON response (vẫn là JSON hợp lệ — call log
    đọc ``recovery.rule``). Trả (result mới, text mới); lỗi → giữ nguyên."""
    try:
        data = json.loads(text or "")
        data["recovery"] = rec
        new_text = json.dumps(data, ensure_ascii=False, indent=2)
        if isinstance(result, str):
            return new_text, new_text
        from mcp.types import TextContent

        content = [TextContent(type="text", text=new_text)]
        if hasattr(result, "model_copy"):
            try:
                return result.model_copy(update={"content": content}), new_text
            except Exception:
                pass
        new_result = copy.copy(result)
        new_result.content = content
        return new_result, new_text
    except Exception:
        return result, text
