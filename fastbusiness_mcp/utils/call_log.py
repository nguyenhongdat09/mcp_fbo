"""MCP tool call logging — JSONL daily file, local cạnh exe.

Spec: docs/doc/gemini/GEMINI-mcp-call-logging.md
Mục đích: review lại tool call để cải tiến MCP (tool underused → retire,
error_code lặp lại → friction cần spec mới).

Ràng buộc cứng:
- KHÔNG ghi ra stdout (stdio MCP — 1 byte rác stdout hỏng protocol).
- KHÔNG ghi lên UNC — log luôn local cạnh exe.
- Logging fail (disk đầy, read-only...) → warn stderr 1 lần, KHÔNG bao giờ
  làm tool call hỏng hay nuốt exception của tool.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

_FIELD_CAP = 4000  # cap mỗi field input (đủ xem lại SQL/edit)
_RESULT_FULL_CAP = 8000  # cap response full khi fail/exception
_SUMMARY_SCALAR_CAP = 300  # cap scalar/preview trong result_summary
_RETENTION_DAYS = 30  # xóa mcp-*.jsonl cũ hơn N ngày lúc server start
_OVERFLOW_RETENTION_DAYS = 7  # xóa overflow-* cũ hơn N ngày lúc server start
_MAX_SANITIZE_DEPTH = 6
_LOG_FILE_RE = re.compile(r"^mcp-(\d{8})\.jsonl$")
_OVERFLOW_FILE_RE = re.compile(r"^overflow-.*?-(\d{8})-\d{6}-\d+\.(?:json|txt)$")

_SENSITIVE_KEY_RE = re.compile(r"pass|secret|token|key", re.IGNORECASE)
_SKIP_SUMMARY_KEYS = frozenset(
    {
        "success",
        "error_code",
        "message",
        "error",
        "project_root",
        "resolved_via",
        "warnings",
        "truncated",
    }
)
# Error trả về dạng text (không phải JSON) — vd GENERAL_EXECUTION_ERROR_MSG,
# QUERY_RADAR_ERROR_MSG, formatter "[ERROR] ...", mcp_tools "Loi doc file:..."
_TEXT_ERROR_PREFIXES = (
    "[LỖI",
    "[LOI",
    "[ERROR",
    "Loi",
    "Lỗi",
    "Error executing tool",
)

_lock = threading.Lock()
_warned = False
_initialized = False
_log_dir_override: Optional[Path] = None  # test hook


def set_log_dir(path: Any) -> None:
    """Override log dir (tests / env FASTBUSINESS_CALL_LOG_DIR). None → mặc định."""
    global _log_dir_override, _warned
    _log_dir_override = Path(path) if path else None
    _warned = False


def _is_unc(p: Path) -> bool:
    s = str(p)
    return s.startswith("\\\\") or s.startswith("//")


def get_log_dir() -> Path:
    """Log dir hiệu lực: override > env > <exe dir>\\logs. UNC → fallback exe dir."""
    cand = _log_dir_override
    if cand is None:
        env = os.environ.get("FASTBUSINESS_CALL_LOG_DIR", "").strip()
        if env:
            cand = Path(env)
    if cand is not None and not _is_unc(cand):
        return cand
    from fastbusiness_mcp.config_paths import get_exe_dir

    return get_exe_dir() / "logs"


def _now_ts() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _today_file(log_dir: Path) -> Path:
    return log_dir / f"mcp-{datetime.now():%Y%m%d}.jsonl"


def _warn_once(msg: str) -> None:
    global _warned
    if _warned:
        return
    _warned = True
    try:
        sys.stderr.write(f"[call_log] {msg}\n")
    except Exception:
        pass


def _write_line(record: dict) -> None:
    """Append 1 dòng JSONL. Mọi lỗi IO → warn stderr 1 lần, không raise."""
    try:
        line = json.dumps(record, ensure_ascii=False, default=str)
    except Exception:
        line = json.dumps(
            {"ts": _now_ts(), "event": "log_serialize_error"}, ensure_ascii=False
        )
    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        path = _today_file(log_dir)
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        _warn_once(f"log write failed: {e}")


def _cleanup_old_logs(log_dir: Path) -> None:
    """Xóa mcp-YYYYMMDD.jsonl cũ hơn _RETENTION_DAYS ngày và overflow-* cũ hơn 7 ngày."""
    cutoff = (datetime.now() - timedelta(days=_RETENTION_DAYS)).date()
    cutoff_overflow = (datetime.now() - timedelta(days=_OVERFLOW_RETENTION_DAYS)).date()
    try:
        for entry in log_dir.iterdir():
            m = _LOG_FILE_RE.match(entry.name)
            if m:
                try:
                    file_date = datetime.strptime(m.group(1), "%Y%m%d").date()
                    if file_date < cutoff:
                        entry.unlink()
                except (ValueError, OSError):
                    pass
                continue

            mo = _OVERFLOW_FILE_RE.match(entry.name)
            if mo:
                try:
                    file_date = datetime.strptime(mo.group(1), "%Y%m%d").date()
                    if file_date < cutoff_overflow:
                        entry.unlink()
                except (ValueError, OSError):
                    pass
    except Exception:
        pass


def init_call_logging() -> None:
    """Chạy lúc server start: tạo log dir, dọn file cũ, ghi server_start."""
    global _initialized
    if _initialized:
        return
    _initialized = True
    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        _cleanup_old_logs(log_dir)
    except Exception as e:
        _warn_once(f"init failed: {e}")
    from fastbusiness_mcp import __version__

    _write_line(
        {
            "event": "server_start",
            "ts": _now_ts(),
            "version": __version__,
            "pid": os.getpid(),
            "cwd": os.getcwd(),
        }
    )


def _sanitize(value: Any, key: str = "", depth: int = 0) -> Any:
    """Redact key nhạy cảm + cap field dài, đệ quy vào dict/list."""
    if key and _SENSITIVE_KEY_RE.search(key):
        return "***"
    if depth >= _MAX_SANITIZE_DEPTH:
        return "..."
    if isinstance(value, dict):
        return {k: _sanitize(v, str(k), depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v, "", depth + 1) for v in value]
    if isinstance(value, str) and len(value) > _FIELD_CAP:
        return value[:_FIELD_CAP] + f"... [truncated {len(value) - _FIELD_CAP} chars]"
    return value


def _summarize_dict(data: dict) -> dict:
    """Giữ key nhỏ; mảng/dict → '<key>_n' độ dài + item đầu nếu ≤300 chars."""
    summary: dict = {}
    for k, v in data.items():
        if k in _SKIP_SUMMARY_KEYS:
            continue
        if isinstance(v, list):
            summary[f"{k}_n"] = len(v)
            if v:
                try:
                    first = json.dumps(v[0], ensure_ascii=False, default=str)
                except Exception:
                    first = str(v[0])
                if len(first) <= _SUMMARY_SCALAR_CAP:
                    summary[f"{k}_first"] = v[0]
        elif isinstance(v, dict):
            summary[f"{k}_n"] = len(v)
        elif isinstance(v, str):
            if len(v) <= _SUMMARY_SCALAR_CAP:
                summary[k] = v
            else:
                summary[k] = (
                    v[:_SUMMARY_SCALAR_CAP]
                    + f"... [truncated {len(v) - _SUMMARY_SCALAR_CAP} chars]"
                )
        else:
            summary[k] = v
    return summary


# Expose alias cho response_guard tái dùng
summarize_dict = _summarize_dict


def extract_response_text(result: Any) -> tuple[Optional[str], bool]:
    """Trích (text, is_error) từ CallToolResult / str thuần. Không raise."""
    if result is None:
        return None, False
    if isinstance(result, str):
        return result, False
    is_error = bool(getattr(result, "is_error", False))
    texts = [
        block.text
        for block in (getattr(result, "content", None) or [])
        if isinstance(getattr(block, "text", None), str)
    ]
    if texts:
        return "\n".join(texts), is_error
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        try:
            return json.dumps(structured, ensure_ascii=False, default=str), is_error
        except Exception:
            pass
    return None, is_error


def log_tool_call(
    tool: str,
    arguments: Any,
    elapsed_ms: float,
    response_text: Optional[str] = None,
    is_error: bool = False,
    exc: Optional[BaseException] = None,
    extra: Optional[dict] = None,
) -> None:
    """Ghi 1 dòng JSONL cho 1 tool call. Wrapper chỉ quan sát — không sửa response."""
    record: dict = {
        "ts": _now_ts(),
        "tool": str(tool),
        "ms": round(elapsed_ms, 1),
        "input": _sanitize(arguments) if arguments is not None else {},
    }

    data: Optional[dict] = None
    parsed_list: Optional[list] = None
    if response_text:
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                data = parsed
            elif isinstance(parsed, list):
                parsed_list = parsed
        except Exception:
            pass

    ok = exc is None and not is_error
    if ok and data is not None:
        if (
            data.get("success") is False
            or data.get("error_code")
            or data.get("error")
        ):
            ok = False
    if ok and data is None and response_text:
        if response_text.lstrip().startswith(_TEXT_ERROR_PREFIXES):
            ok = False
    record["ok"] = ok

    if not ok:
        if exc is not None:
            record["error_code"] = "exception"
            record["exc_type"] = type(exc).__name__
            record["message"] = str(exc)[:500]
        elif data is not None:
            record["error_code"] = data.get("error_code") or "error_response"
            msg = data.get("message") or data.get("error")
            if isinstance(msg, str) and msg:
                record["message"] = msg[:500]
        else:
            record["error_code"] = "error_response"
        if response_text:
            record["result_full"] = response_text[:_RESULT_FULL_CAP]
            if len(response_text) > _RESULT_FULL_CAP:
                record["result_full"] += (
                    f"... [truncated {len(response_text) - _RESULT_FULL_CAP} chars]"
                )

    if data is not None:
        if data.get("project_root") is not None:
            record["project_root"] = data["project_root"]
        if data.get("resolved_via"):
            record["resolved_via"] = data["resolved_via"]
        warnings = data.get("warnings")
        if isinstance(warnings, list) and warnings:
            record["warnings"] = warnings
        if "truncated" in data:
            record["truncated"] = bool(data["truncated"])
        summary = _summarize_dict(data)
        if summary:
            record["result_summary"] = summary
    elif parsed_list is not None:
        record["result_summary"] = {"items_n": len(parsed_list)}
    elif response_text:
        record["result_summary"] = {
            "text_preview": response_text[:_SUMMARY_SCALAR_CAP]
        }

    if extra and isinstance(extra, dict):
        record.update(extra)

    _write_line(record)
