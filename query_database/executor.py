"""Execute SQL Server query via pyodbc."""

from __future__ import annotations

import re
import time
from typing import Any

DEFAULT_MAX_ROWS = 20000

# GO là batch separator của SSMS/sqlcmd, KHÔNG phải T-SQL — pyodbc báo
# "Incorrect syntax near 'GO'" nếu đưa nguyên file. Chỉ split dòng đứng riêng.
_GO_BATCH_RE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
ODBC_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


def _format_pyodbc_message(item: object) -> str | None:
    """Chuẩn hóa 1 phần tử từ cursor.messages hoặc pyodbc.Error.args."""
    if item is None:
        return None
    if isinstance(item, (list, tuple)):
        if len(item) >= 2 and item[1]:
            return str(item[1]).strip()
        if len(item) == 1 and item[0]:
            return str(item[0]).strip()
        return None
    text = str(item).strip()
    return text or None


def collect_cursor_messages(cursor: Any) -> list[str]:
    """Lấy PRINT / info messages từ pyodbc cursor (sau execute)."""
    seen: set[str] = set()
    out: list[str] = []
    for item in getattr(cursor, "messages", None) or []:
        text = _format_pyodbc_message(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def format_pyodbc_error(exc: Exception) -> str:
    """Gộp toàn bộ thông báo lỗi SQL Server từ pyodbc exception."""
    parts: list[str] = []
    seen: set[str] = set()

    def add(text: str | None) -> None:
        if not text:
            return
        cleaned = text.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            parts.append(cleaned)

    add(str(exc))
    for arg in getattr(exc, "args", ()) or ():
        if isinstance(arg, (list, tuple)):
            for item in arg:
                add(_format_pyodbc_message(item))
        else:
            add(_format_pyodbc_message(arg))

    return "\n".join(parts) if parts else "Unknown SQL error"


def _is_driver_missing_error(exc: Exception) -> bool:
    """Kiểm tra xem lỗi có phải do chưa cài ODBC Driver hay không (IM002)."""
    msg = str(exc).lower()
    return "im002" in msg or "data source name not found" in msg or "no default driver" in msg


def _build_connection_string(parsed: dict[str, str]) -> str:
    server = parsed.get("server", "")
    database = parsed.get("database", "")
    user = parsed.get("user", "")
    password = parsed.get("password", "")
    # Web.config thường có App=%UserID (placeholder FBO) — không dùng nguyên chữ cho Profiler.
    raw_app = (parsed.get("app_name") or "").strip()
    app_name = "FSD" if (not raw_app or "%" in raw_app) else raw_app

    if not server or not database:
        raise ValueError("Connection thiếu server hoặc database")

    last_error: Exception | None = None
    for driver in ODBC_DRIVERS:
        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server}",
            f"DATABASE={database}",
            f"APP={app_name}",
            "TrustServerCertificate=yes",
            "Encrypt=no",
        ]
        if user:
            parts.extend([f"UID={user}", f"PWD={password}"])
        else:
            parts.append("Trusted_Connection=yes")

        conn_str = ";".join(parts) + ";"
        try:
            import pyodbc

            conn = pyodbc.connect(conn_str, timeout=5)
            conn.close()
            return conn_str
        except Exception as exc:
            last_error = exc
            if _is_driver_missing_error(exc):
                continue
            raise ConnectionError(
                f"Không kết nối được SQL Server (database '{database}'): {format_pyodbc_error(exc)}"
            ) from exc

    raise ConnectionError(
        f"Không kết nối được SQL Server (database '{database}'): {last_error}"
    )


def execute_query(
    parsed: dict[str, str],
    query: str,
    max_rows: int = DEFAULT_MAX_ROWS,
    params: tuple | list | None = None,
) -> dict[str, Any]:
    """Chạy SQL query và trả về kết quả. ``params`` → parameterized execute (pyodbc '?')."""
    import pyodbc

    if not query or not query.strip():
        return {"success": False, "error": "query is required"}

    conn_str = _build_connection_string(parsed)
    started = time.perf_counter()

    try:
        with pyodbc.connect(conn_str, timeout=30) as conn:
            conn.autocommit = True
            cursor = conn.cursor()
            if params:
                cursor.execute(query, *params)
            else:
                cursor.execute(query)

            result_sets: list[dict[str, Any]] = []
            messages: list[str] = []
            total_rows = 0
            truncated = False

            def append_messages() -> None:
                for msg in collect_cursor_messages(cursor):
                    if msg not in messages:
                        messages.append(msg)

            append_messages()

            while True:
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    rows: list[list[Any]] = []
                    fetched = 0

                    while True:
                        batch = cursor.fetchmany(min(1000, max(1, max_rows - total_rows)))
                        if not batch:
                            break
                        for row in batch:
                            if total_rows >= max_rows:
                                truncated = True
                                break
                            rows.append([_serialize_cell(v) for v in row])
                            total_rows += 1
                            fetched += 1
                        if truncated or total_rows >= max_rows:
                            break

                    result_sets.append(
                        {
                            "columns": columns,
                            "rows": rows,
                            "row_count": len(rows),
                        }
                    )

                if not cursor.nextset():
                    break
                append_messages()

            append_messages()

            if cursor.rowcount >= 0 and not result_sets:
                affected = f"({cursor.rowcount} row(s) affected)"
                if affected not in messages:
                    messages.append(affected)

            elapsed_ms = int((time.perf_counter() - started) * 1000)

            return {
                "success": True,
                "result_sets": result_sets,
                "messages": messages,
                "row_count": total_rows,
                "truncated": truncated,
                "max_rows": max_rows,
                "execution_time_ms": elapsed_ms,
                "database": parsed.get("database", ""),
                "server": parsed.get("server", ""),
            }
    except Exception as exc:
        return {
            "success": False,
            "error": format_pyodbc_error(exc),
            "database": parsed.get("database", ""),
            "server": parsed.get("server", ""),
        }


def _serialize_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def split_go_batches(script: str) -> list[str]:
    """Tách script thành các batch T-SQL theo dòng ``GO`` đứng riêng.

    Dùng chung cho ``query_database`` type=2 và ``deploy_script_to_target`` —
    cùng 1 regex, không lệch hành vi deploy vs query.
    """
    return [b.strip() for b in _GO_BATCH_RE.split(script or "") if b.strip()]


def split_go_batches_with_lines(script: str) -> list[tuple[str, int]]:
    """Như ``split_go_batches`` nhưng trả ``(batch_text, start_line)`` —
    ``start_line`` là dòng 1-based trong file gốc chứa ký tự đầu tiên của batch
    (sau khi strip). Batch rỗng bị bỏ nhưng line vẫn tích lũy đúng.

    Dùng ``_GO_BATCH_RE.finditer`` positions — KHÔNG sửa ``split_go_batches``
    (execute/deploy đang dùng).
    """
    script = script or ""
    bounds = [(m.start(), m.end()) for m in _GO_BATCH_RE.finditer(script)]

    segments: list[tuple[int, int]] = []
    prev_end = 0
    for m_start, m_end in bounds:
        segments.append((prev_end, m_start))
        prev_end = m_end
    segments.append((prev_end, len(script)))

    out: list[tuple[str, int]] = []
    for seg_start, seg_end in segments:
        seg = script[seg_start:seg_end]
        stripped = seg.strip()
        if not stripped:
            continue
        leading_ws = seg[: len(seg) - len(seg.lstrip())]
        line = 1 + script.count("\n", 0, seg_start) + leading_ws.count("\n")
        out.append((stripped, line))
    return out


def check_sql_batches(
    parsed: dict[str, str],
    script: str,
) -> dict[str, Any]:
    """Check syntax toàn file qua ``SET PARSEONLY`` — KHÔNG execute.

    - Mở 1 conn; trước MỖI batch: cur.execute("SET PARSEONLY ON") ở batch
      riêng (re-issue per batch: phòng file tự chứa SET PARSEONLY OFF).
    - cur.execute(batch) — session đang PARSEONLY → chỉ parse, không run.
    - finally: SET PARSEONLY OFF + close conn (stateless như thiết kế cũ).
    - Gom hết errors[] kèm line_start (giữ nguyên contract response).
    """
    import pyodbc

    base: dict[str, Any] = {
        "database": parsed.get("database", ""),
        "server": parsed.get("server", ""),
    }
    batches = split_go_batches_with_lines(script)
    if not batches:
        return {
            "success": False,
            "error": "script không có batch nào sau khi tách GO",
            "check_mode": "parseonly",
            "batch_count": 0,
            "batches_ok": 0,
            "errors": [],
            **base,
        }

    try:
        conn_str = _build_connection_string(parsed)
        conn = pyodbc.connect(conn_str, timeout=30)
        conn.autocommit = True
    except Exception as exc:
        return {
            "success": False,
            "error": format_pyodbc_error(exc) if hasattr(exc, "args") else str(exc),
            "check_mode": "parseonly",
            "batch_count": len(batches),
            "batches_ok": 0,
            "errors": [],
            **base,
        }

    errors: list[dict[str, Any]] = []
    cur = None
    try:
        cur = conn.cursor()
        conn_alive = True
        for idx, (batch, line_start) in enumerate(batches):
            if not conn_alive:
                break

            try:
                cur.execute("SET PARSEONLY ON")
                try:
                    while cur.nextset():
                        pass
                except Exception:
                    pass
            except Exception as exc:
                if idx == 0:
                    return {
                        "success": False,
                        "error": f"Không bật được PARSEONLY: {format_pyodbc_error(exc)}",
                        "check_mode": "parseonly",
                        "batch_count": len(batches),
                        "batches_ok": 0,
                        "errors": [],
                        **base,
                    }
                errors.append(
                    {
                        "batch_index": idx + 1,
                        "line_start": line_start,
                        "message": f"Connection lost hoặc không set được PARSEONLY: {format_pyodbc_error(exc)}",
                        "batch_preview": batch[:200],
                    }
                )
                conn_alive = False
                break

            try:
                cur.execute(batch)
                try:
                    while cur.nextset():
                        pass
                except Exception:
                    pass
                collect_cursor_messages(cur)
            except Exception as exc:
                msg = format_pyodbc_error(exc)
                errors.append(
                    {
                        "batch_index": idx + 1,
                        "line_start": line_start,
                        "message": msg,
                        "batch_preview": batch[:200],
                    }
                )
                if any(code in msg for code in ("08S01", "08003", "08007", "Communication link failure", "Shared Memory Provider")):
                    conn_alive = False
    finally:
        if cur is not None:
            try:
                cur.execute("SET PARSEONLY OFF")
            except Exception:
                pass
            try:
                cur.close()
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass

    return {
        "success": not errors,
        "check_mode": "parseonly",
        "batch_count": len(batches),
        "batches_ok": len(batches) - len(errors),
        "errors": errors,
        "scope_note": (
            "PARSEONLY chỉ check syntax/structure — KHÔNG check tên bảng/cột "
            "tồn tại (object binding bị skip). Phù hợp check script deploy "
            "trước khi F5."
        ),
        **base,
    }



def execute_sql_batches(
    parsed: dict[str, str],
    script: str,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    """Chạy tuần tự các batch T-SQL tách bởi ``GO`` (file .sql / script dài).

    - Script không có GO → đúng 1 batch (tương đương ``execute_query``).
    - Batch lỗi → dừng ngay, trả ``failed_batch_index`` (1-based theo file)
      + ``failed_batch_preview`` (≤200 chars) + ``error`` gốc ODBC.
    - Thành công → gộp ``result_sets``/``messages`` của mọi batch,
      kèm ``batch_count`` / ``batches_ok``.
    """
    base: dict[str, Any] = {
        "database": parsed.get("database", ""),
        "server": parsed.get("server", ""),
    }
    batches = split_go_batches(script)
    if not batches:
        return {
            "success": False,
            "error": "script không có batch nào sau khi tách GO",
            "batch_count": 0,
            "batches_ok": 0,
            **base,
        }

    result_sets: list[dict[str, Any]] = []
    messages: list[str] = []
    total_rows = 0
    elapsed_ms = 0
    truncated = False

    for idx, batch in enumerate(batches):
        res = execute_query(parsed, batch, max_rows=max_rows)
        if not res.get("success"):
            return {
                "success": False,
                "error": res.get("error", "Unknown SQL error"),
                "failed_batch_index": idx + 1,
                "failed_batch_preview": batch[:200],
                "batch_count": len(batches),
                "batches_ok": idx,
                **base,
            }
        result_sets.extend(res.get("result_sets") or [])
        for msg in res.get("messages") or []:
            if msg not in messages:
                messages.append(msg)
        total_rows += int(res.get("row_count") or 0)
        elapsed_ms += int(res.get("execution_time_ms") or 0)
        truncated = truncated or bool(res.get("truncated"))

    return {
        "success": True,
        "result_sets": result_sets,
        "messages": messages,
        "row_count": total_rows,
        "truncated": truncated,
        "max_rows": max_rows,
        "execution_time_ms": elapsed_ms,
        "batch_count": len(batches),
        "batches_ok": len(batches),
        **base,
    }
