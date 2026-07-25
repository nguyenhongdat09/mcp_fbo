"""Execute SQL Server query via pyodbc."""

from __future__ import annotations

import time
from typing import Any

DEFAULT_MAX_ROWS = 20000
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

    if not server or not database:
        raise ValueError("Connection thiếu server hoặc database")

    last_error: Exception | None = None
    for driver in ODBC_DRIVERS:
        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={server}",
            f"DATABASE={database}",
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
) -> dict[str, Any]:
    """Chạy SQL query và trả về kết quả."""
    import pyodbc

    if not query or not query.strip():
        return {"success": False, "error": "query is required"}

    conn_str = _build_connection_string(parsed)
    started = time.perf_counter()

    try:
        with pyodbc.connect(conn_str, timeout=30) as conn:
            conn.autocommit = True
            cursor = conn.cursor()
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
