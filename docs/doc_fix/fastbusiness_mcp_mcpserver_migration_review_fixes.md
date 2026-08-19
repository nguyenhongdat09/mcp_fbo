# FSPEC / PROMPT — Fix sau review: Migration MCPServer + Pydantic v2

> **Cách dùng:** Copy mục «PROMPT GỬI GEMINI» (cuối file) gửi Gemini kèm repo `mcp_fbo`.
>
> **Bối cảnh:** Migration FastMCP/MCPServer (`docs/doc/fastbusiness_mcp_fastmcp_migration.md`) đã merge. Review + chạy test thực tế:
> - `python scripts/verify_mcp_migration.py` → **PASS**
> - `python scripts/test_mcp_stdio_wire.py` → **PASS**
> - `python search_qlyc/test_search_qlyc.py` → **PASS (5/5)**
> - `dist\fastbusiness_mcp\fastbusiness_mcp.exe` → **PASS** (MCPServer + Pydantic validate)
> - `E:\fastbusiness_mcp\fastbusiness_mcp.exe` → **VẪN BẢN CŨ** (log `SQL/XML + FBOGraph`)
>
> Logic nghiệp vụ FBO **không đổi**. Chỉ vá regression UX Agent + code hygiene + deploy.

---

## Kết quả review (ngắn)

| Mức | Vấn đề | Ảnh hưởng |
|---|---|---|
| **P0** | `E:\fastbusiness_mcp\` chưa copy exe mới sau build | Cursor trỏ path deploy vẫn chạy **server cũ**, không có Pydantic validate / thread pool |
| **P1** | Lỗi validate Pydantic trả message **tiếng Anh** thô (`Field required`, link pydantic.dev) | Agent mất hint tiếng Việt + nhắc absolute path (`MISSING_ARG_MSG` cũ) |
| **P1** | Tool `query_database`, `get_xml_entities`, `read_local_file`, `search_qlyc` **không bọc** `GENERAL_EXECUTION_ERROR_MSG` | Exception bất ngờ → `Error executing tool ...` khó đọc; khác hành vi server cũ |
| **P1** | `query_radar_tool` chỉ map lỗi khi `res.startswith("Loi thuc thi Cypher:")` | JSON gate (`invalid_reference_file`), lỗi Kùzu khác format → **không** qua `QUERY_RADAR_ERROR_MSG` |
| **P2** | Dùng `Field(...)` làm **default value** tham số hàm | Chạy được (MCPServer chấp nhận) nhưng **không chuẩn** Pydantic; khó maintain |
| **P2** | Patch `print()` → stderr **trùng** ở `run_server.py` và `fastbusiness_mcp/server.py` | Dư thừa; dev `python -m fastbusiness_mcp.server` patch 2 lần nếu import chain lẫn |
| **P2** | `scripts/verify_mcp_migration.py` chưa assert message tiếng Việt sau fix | Regression dễ lọt lại |

**Không revert** MCPServer migration. **Không** bật lại `search_nodes` / `get_related_nodes` / `query_node_details`.

---

## P0 — Deploy exe mới ra thư mục production

### Hiện trạng

| Path | Log khởi động | Pydantic validate |
|---|---|---|
| `dist\fastbusiness_mcp\fastbusiness_mcp.exe` | `MCPServer + Pydantic v2` | ✅ `db_type=oracle` bị reject |
| `E:\fastbusiness_mcp\fastbusiness_mcp.exe` | `SQL/XML + FBOGraph` (cũ) | ❌ không có |

`scripts/test_mcp_connect.py` pass cả hai vì **cả hai đều có 5 tool** — test chỉ list tools, không phân biệt version.

### Hành vi bắt buộc sau fix

1. Sau `build_onedir.bat`, **copy** toàn bộ `dist\fastbusiness_mcp\` → `E:\fastbusiness_mcp\` (hoặc path deploy user đang dùng trong Cursor).
2. Cập nhật `build_onedir.bat`: cuối script in rõ lệnh copy deploy (nếu chưa có).
3. Thêm bước verify deploy trong `scripts/test_mcp_connect.py` (xem P2 test bên dưới): gọi `query_database` với `db_type=oracle` trên exe deploy — **phải** trả lỗi chứa `'app' or 'sys'`.

### Test P0

**`test_deploy_exe_has_pydantic_validation`**

- Chạy subprocess hoặc MCP client tới `E:\fastbusiness_mcp\fastbusiness_mcp.exe`.
- `call_tool('query_database', {file_path:'x', query:'SELECT 1', db_type:'oracle'})`.
- Assert response text chứa `app` và `sys` (Pydantic literal error).
- Nếu exe missing → SKIP, không fail CI local.

---

## P1 — Khôi phục thông báo lỗi tiếng Việt cho Agent (validate + execute)

### Hiện trạng

Server cũ (`_on_call_tool`):

```python
except KeyError as e:
    error_msg = MISSING_ARG_MSG.format(tool_name=name, missing_key=missing_key)
except Exception as e:
    error_msg = GENERAL_EXECUTION_ERROR_MSG.format(tool_name=name, error_detail=str(e))
```

Server mới: Pydantic/MCPServer raise `ToolError` với message tiếng Anh:

```
Error executing tool query_database: 1 validation error ...
file_path
  Field required ...
  For further information visit https://errors.pydantic.dev/2.13/v/missing
```

### Thiết kế fix (bắt buộc)

#### Bước 1 — Thêm template vào `fastbusiness_mcp/agent_messages.py`

```python
VALIDATION_ERROR_MSG = """
[LỖI THAM SỐ KHÔNG HỢP LỆ] Tool '{tool_name}' — Agent cần sửa tham số rồi gọi lại.

{detail_vi}

Gợi ý:
- 'file_path' / 'reference_file': LUÔN dùng đường dẫn TUYỆT ĐỐI (VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SRTran.xml).
- 'db_type': chỉ 'app' hoặc 'sys'.
- 'mode' (get_xml_entities): 'content', 'path', 'list'.
- 'read_option': 1 hoặc 2.
- 'page', 'page_size', 'max_total': phải là số nguyên hợp lệ.
"""

PATH_HINT_FIELDS = frozenset({"file_path", "reference_file"})
```

#### Bước 2 — Tạo helper `fastbusiness_mcp/tool_errors.py` (file mới)

```python
"""Chuyển lỗi Pydantic / Exception sang message Agent-friendly (tiếng Việt)."""

from pydantic import ValidationError
from mcp.server.mcpserver.exceptions import ToolError

from .agent_messages import (
    VALIDATION_ERROR_MSG,
    GENERAL_EXECUTION_ERROR_MSG,
    MISSING_ARG_MSG,
    PATH_HINT_FIELDS,
)


def _format_validation_detail_vi(tool_name: str, exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = str(loc[-1]) if loc else "?"
        err_type = err.get("type") or ""
        msg = err.get("msg") or ""

        if err_type == "missing":
            lines.append(f"- Thiếu tham số bắt buộc: '{field}'")
            if field in PATH_HINT_FIELDS:
                lines.append("  → Dùng đường dẫn ABSOLUTE tới file XML trong project FBO.")
        elif err_type == "literal_error":
            lines.append(f"- '{field}': giá trị không hợp lệ. {msg}")
        elif err_type == "int_parsing":
            lines.append(f"- '{field}': phải là số nguyên, không phải chuỗi.")
        else:
            lines.append(f"- '{field}': {msg}")

    return "\n".join(lines) if lines else str(exc)


def raise_validation_tool_error(tool_name: str, exc: ValidationError) -> None:
    detail_vi = _format_validation_detail_vi(tool_name, exc)
    raise ToolError(VALIDATION_ERROR_MSG.format(tool_name=tool_name, detail_vi=detail_vi).strip())


def format_execution_error(tool_name: str, exc: Exception) -> str:
    return GENERAL_EXECUTION_ERROR_MSG.format(
        tool_name=tool_name,
        error_detail=str(exc),
    ).strip()
```

**Lưu ý:** Không import `ValidationError` từ chỗ khác nếu không cần — dùng `pydantic.ValidationError`.

#### Bước 3 — Đăng ký middleware trên `MCPServer` trong `mcp_app.py`

Sau `server = MCPServer(...)`, thêm middleware bắt `ToolError` gốc từ validate và rewrite (nếu SDK không cho hook validate trực tiếp):

**Cách ưu tiên:** bọc từng tool bằng decorator nội bộ `_safe_tool` thay vì middleware phức tạp:

```python
from functools import wraps
from pydantic import ValidationError
from mcp.server.mcpserver.exceptions import ToolError
from .tool_errors import raise_validation_tool_error, format_execution_error

def _safe_tool(tool_name: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except ValidationError as e:
                raise_validation_tool_error(tool_name, e)
            except ToolError:
                raise  # đã format
            except Exception as e:
                return format_execution_error(tool_name, e)
        return wrapper
    return decorator
```

**Quan trọng:** ValidationError xảy ra **trước** khi vào hàm tool (trong MCPServer arg validate). Decorator trên hàm **không bắt được** lỗi validate Pydantic.

→ **Bắt buộc dùng Server middleware** hoặc subclass/wrap `server.call_tool` handler.

**Cách implement đúng (middleware):**

```python
from mcp.server.context import ServerRequestContext, CallNext, HandlerResult
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError
import re

@server.middleware
async def agent_friendly_errors(ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
    try:
        return await call_next(ctx)
    except ToolError as e:
        msg = str(e)
        # Pattern MCPServer: "Error executing tool {name}: ..."
        m = re.match(r"Error executing tool ([^:]+):\s*(.+)", msg, re.DOTALL)
        if not m:
            raise
        tool_name = m.group(1).strip()
        body = m.group(2).strip()
        if "validation error" in body.lower() or "pydantic.dev" in body:
            # Parse field hints từ body text (fallback nếu không có ValidationError object)
            detail_vi = _pydantic_body_to_vi(body)
            raise ToolError(VALIDATION_ERROR_MSG.format(tool_name=tool_name, detail_vi=detail_vi).strip())
        raise
```

Implement `_pydantic_body_to_vi(body: str) -> str` parse các dòng kiểu:

```
file_path
  Field required [type=missing, ...]
db_type
  Input should be 'app' or 'sys' ...
```

Map sang tiếng Việt như `_format_validation_detail_vi`.

**Alternative đơn giản hơn (chấp nhận được):** không middleware — override bằng custom `Server` extension nếu quá phức tạp; nhưng **kết quả wire** phải là text tiếng Việt `[LỖI THAM SỐ...]`, không còn link pydantic.dev.

#### Bước 4 — Bọc execution errors trong từng tool

Mỗi tool body (trừ validate — đã xử lý middleware):

```python
@server.tool(name="query_database")
def query_database_tool(...) -> str:
    try:
        result = query_database(...)
        return format_query_result(result)
    except Exception as e:
        logger.error(f"query_database error: {e}")
        return format_execution_error("query_database", e)
```

Áp dụng cho: `query_database`, `get_xml_entities`, `read_local_file`, `search_qlyc`.  
`query_radar` đã có try/except riêng — giữ và mở rộng (mục P1 query_radar).

### Test P1 — validate tiếng Việt

Cập nhật `scripts/verify_mcp_migration.py`:

```python
# missing file_path
try:
    await server.call_tool("query_database", {"query": "SELECT 1"})
except ToolError as e:
    msg = str(e)
    assert "[LỖI THAM SỐ" in msg or "[LỖI THIẾU THAM SỐ" in msg
    assert "file_path" in msg
    assert "pydantic.dev" not in msg

# invalid db_type — assert tiếng Việt + gợi ý app/sys
```

Chạy qua **stdio wire** (`test_mcp_stdio_wire.py` hoặc test mới): client `call_tool` **không raise** — kiểm tra `result.content[0].text` chứa `[LỖI THAM SỐ`.

---

## P1 — `query_radar` map lỗi đầy đủ

### Hiện trạng

```python
res = mcp_query_radar(cypher_query, reference_file, mode)
if isinstance(res, str) and res.startswith("Loi thuc thi Cypher:"):
    return QUERY_RADAR_ERROR_MSG.format(error_detail=res)
return res
```

`mcp_query_radar` còn trả:

| Format | Ví dụ | Hiện xử lý |
|---|---|---|
| Cypher exception string | `Loi thuc thi Cypher: ...` | ✅ map QUERY_RADAR |
| JSON gate | `{"error":"invalid_reference_file",...}` | ❌ trả thẳng JSON |
| JSON lỗi mode | `{"error":"cypher_query la bat buoc..."}` | ❌ trả thẳng |
| Success JSON | `[{...}]` hoặc schema dict | ✅ OK |

### Hành vi bắt buộc

Tạo helper `_format_query_radar_result(res: str) -> str` trong `mcp_app.py`:

```python
import json

def _format_query_radar_result(res: str) -> str:
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
            if err in ("invalid_reference_file",):
                return (
                    "[LỖI REFERENCE_FILE]\n"
                    f"{data.get('message', '')}\n"
                    f"reference_file: {data.get('reference_file', '')}\n"
                    "Agent: truyền đường dẫn ABSOLUTE tới file XML trong App_Data\\Controllers "
                    "(VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml)."
                )
            if err or data.get("status") == "building":
                return QUERY_RADAR_ERROR_MSG.format(
                    error_detail=json.dumps(data, ensure_ascii=False)
                )
    return res
```

`query_radar_tool`:

```python
try:
    res = mcp_query_radar(cypher_query, reference_file, mode)
    return _format_query_radar_result(res)
except Exception as e:
    ...
```

### Test P1 query_radar

Thêm vào `verify_mcp_migration.py`:

```python
# invalid reference (absolute nhưng không có Controllers)
r = await server.call_tool("query_radar", {
    "reference_file": r"E:\nonexistent\x.xml",
    "mode": "schema",
})
text = r.content[0].text
assert "[LỖI REFERENCE_FILE]" in text or "[LỖI CÚ PHÁP CYPHER" in text
assert "ABSOLUTE" in text or "absolute" in text.lower()
```

---

## P2 — Refactor `Field()` → `Annotated[..., Field(...)]`

### Hiện trạng (không chuẩn)

```python
def query_database_tool(
    file_path: str = Field(description="..."),  # Field làm default
    query_type: int = Field(default=1, description="..."),
```

### Pattern bắt buộc sau fix

```python
from typing import Annotated, Literal

def query_database_tool(
    file_path: Annotated[str, Field(description="Path file trong project FBO ...")],
    query: Annotated[str, Field(description="Object name ...")],
    query_type: Annotated[int, Field(default=1, description="0=object ...")] = 1,
    db_type: Annotated[Literal["app", "sys"], Field(default="app", description="app hoặc sys")] = "app",
    max_rows: Annotated[int, Field(default=20000, description="Giới hạn ...")] = 20000,
) -> str:
```

**Quy tắc:**

- Required param: chỉ `Annotated[T, Field(description=...)]` — **không** default.
- Optional/default: `Annotated[T, Field(...)] = default_value` — default là **giá trị Python**, không phải `Field(...)`.
- Refactor **cả 5 tool** trong `mcp_app.py`.
- Sau refactor chạy lại `verify_mcp_migration.py` — schema `required` / `properties` **không đổi**.

---

## P2 — Gom patch `print()` về một nơi

### Hiện trạng

| File | Patch print |
|---|---|
| `run_server.py` | ✅ (entry exe) |
| `fastbusiness_mcp/server.py` | ✅ (entry `python -m`) |

### Fix

1. Tạo `fastbusiness_mcp/stdio_safe.py`:

```python
import builtins
import sys

_PATCHED = False

def ensure_stdio_safe_print() -> None:
    global _PATCHED
    if _PATCHED:
        return
    _orig = builtins.print
    def _safe(*args, **kwargs):
        if kwargs.get("file") in (None, sys.stdout):
            kwargs["file"] = sys.stderr
        try:
            _orig(*args, **kwargs)
        except Exception:
            pass
    builtins.print = _safe
    _PATCHED = True
```

2. `run_server.py`: thay block patch inline → `from fastbusiness_mcp.stdio_safe import ensure_stdio_safe_print; ensure_stdio_safe_print()`.
3. `fastbusiness_mcp/server.py`: **xóa** block patch inline; đầu file gọi `ensure_stdio_safe_print()` **trước** import logger/mcp_app.
4. Assert idempotent: gọi 2 lần không lỗi.

---

## P2 — Cứng hóa `test_mcp_connect.py`

### Thêm sau list tools

```python
# Phân biệt exe cũ vs mới
res = await session.call_tool("query_database", {
    "file_path": "x.xml",
    "query": "SELECT 1",
    "db_type": "oracle",
})
text = res.content[0].text if res.content else ""
if "Input should be 'app' or 'sys'" in text or "[LỖI THAM SỐ" in text:
    print("OK - Pydantic validation active")
else:
    print("WARN - exe may be OLD build (no pydantic enum check)")
```

In `WARN` không fail test (deploy path có thể cũ), nhưng log rõ cho user.

---

## File cần sửa (tóm tắt)

| File | Thay đổi |
|---|---|
| `fastbusiness_mcp/agent_messages.py` | Thêm `VALIDATION_ERROR_MSG`, `PATH_HINT_FIELDS` |
| `fastbusiness_mcp/tool_errors.py` | **Mới** — format lỗi validate/execute |
| `fastbusiness_mcp/stdio_safe.py` | **Mới** — patch print idempotent |
| `fastbusiness_mcp/mcp_app.py` | Middleware/errors, `_format_query_radar_result`, Annotated refactor, execution wrap |
| `fastbusiness_mcp/server.py` | Dùng `stdio_safe`, bỏ patch trùng |
| `run_server.py` | Dùng `stdio_safe` |
| `scripts/verify_mcp_migration.py` | Assert message tiếng Việt + query_radar reference |
| `scripts/test_mcp_connect.py` | Warn exe cũ |
| `build_onedir.bat` | Nhắc copy deploy (nếu chưa có) |

**Không sửa:** `queryDatabase/`, `xml_fbograph/mcp_tools.py` logic nghiệp vụ (trừ khi test bắt buộc).

---

## Checklist Done

- [ ] `verify_mcp_migration.py` pass + assert không còn `pydantic.dev` trong message Agent
- [ ] `test_mcp_stdio_wire.py` pass
- [ ] `search_qlyc/test_search_qlyc.py` pass
- [ ] `query_radar` + reference invalid → message `[LỖI REFERENCE_FILE]` hoặc Cypher template
- [ ] `mcp_app.py` dùng `Annotated` — không còn `param: str = Field(...)` cho required
- [ ] `stdio_safe` — một nơi patch print
- [ ] Rebuild exe + copy `dist\fastbusiness_mcp\` → `E:\fastbusiness_mcp\`
- [ ] `test_mcp_connect.py` trên exe deploy: log `Pydantic validation active`

---

## PROMPT GỬI GEMINI

```
Fix sau review migration MCPServer — đọc đầy đủ:
docs/doc_fix/fastbusiness_mcp_mcpserver_migration_review_fixes.md

Thực hiện theo thứ tự P0 → P1 → P2. Không revert MCPServer. Không bật tool ẩn.

P0: Sau build, hướng dẫn/copy dist → E:\fastbusiness_mcp; test_mcp_connect phân biệt exe cũ/mới.

P1:
- agent_messages.py: VALIDATION_ERROR_MSG
- tool_errors.py (mới): format lỗi validate/execute tiếng Việt
- mcp_app.py: middleware hoặc cách tương đương để ToolError validate không còn pydantic.dev / Field required tiếng Anh
- Bọc query_database, get_xml_entities, read_local_file, search_qlyc: Exception → GENERAL_EXECUTION_ERROR_MSG
- query_radar: _format_query_radar_result() cho JSON invalid_reference_file + Cypher string

P2:
- Field() default → Annotated[..., Field(...)] = value cho cả 5 tool
- stdio_safe.py (mới); server.py + run_server.py dùng chung, bỏ patch trùng
- Cập nhật verify_mcp_migration.py + test_mcp_connect.py

Chạy và pass:
  python scripts/verify_mcp_migration.py
  python scripts/test_mcp_stdio_wire.py
  python search_qlyc/test_search_qlyc.py
  python scripts/test_mcp_connect.py

UTF-8 BOM cho file .py/.md mới hoặc sửa lớn.
```

---

*Tài liệu fix review migration MCPServer — FastBusiness MCP Server.*
