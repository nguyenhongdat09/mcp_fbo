# FastBusiness MCP — Migration sang FastMCP / MCPServer + Pydantic v2 + MCP Inspector

> **Cách dùng tài liệu này:** Đọc từ mục 0 → 4 để nắm bối cảnh và lộ trình. Mục 5–8 là spec chi tiết từng tool + case lỗi. Mục 9–12 là test bằng MCP Inspector. Mục 13–16 là checklist triển khai và rủi ro.
>
> **Phạm vi Giai đoạn 1:** Chỉ refactor **lớp transport MCP** (`fastbusiness_mcp/server.py`). **Không** đổi logic nghiệp vụ trong `queryDatabase/`, `find_entity_by_xml/`, `xml_fbograph/`, `search_qlyc/`. **Không** bật lại các tool đã ẩn (`search_nodes`, `get_related_nodes`, `query_node_details`).

---

## 0. Tóm tắt 1 dòng

| Hiện tại | Mục tiêu | Lợi ích chính |
|---|---|---|
| Low-level `Server` + schema JSON thủ công + `if name == ...` dispatch | `@server.tool()` + type hints → Pydantic v2 sinh schema | Một nguồn sự thật, validate tự động, ít boilerplate ~60–70%, test bằng MCP Inspector |

---

## 1. Bối cảnh codebase hiện tại

### 1.1. Hai kiến trúc MCP đang tồn tại song song

| File | Kiểu | Trạng thái | Tools |
|---|---|---|---|
| `fastbusiness_mcp/server.py` | **Low-level** `mcp.server.Server` | **Production** — Cursor gọi qua `fastbusiness_mcp.exe` hoặc `python -m fastbusiness_mcp.server` | `query_database`, `get_xml_entities`, `query_radar`, `read_local_file`, `search_qlyc` |
| `mcp_server.py` | High-level decorator (`FastMCP` cũ) | **Legacy / tham khảo** — chưa là entry chính | `query_radar`, `search_nodes`, `get_related_nodes`, `query_node_details`, `read_local_file` |

Entry thực tế khi build exe:

```
run_server.py  →  fastbusiness_mcp.server.main()
                    → verify_and_enforce_license()
                    → FastBusinessMCPServer().run()  # stdio JSON-RPC
```

### 1.2. Vấn đề Low-level (đúng như Gemini mô tả)

**Case A — Schema và handler lệch nhau**

Trong `_on_list_tools` khai báo:

```python
"query_type": {"type": "integer", "default": 1}
"db_type": {"type": "string", "default": "app"}
```

Trong `_on_call_tool` lại parse riêng:

```python
query_type=int(arguments.get("query_type", 1))
db_type=arguments.get("db_type", "app")
```

Nếu dev thêm tham số mới ở handler mà quên cập nhật `inputSchema` → Agent nhìn schema cũ, gọi sai, khó debug.

**Case B — Validate tham số yếu**

| Agent gửi | Hành vi hiện tại | Hậu quả |
|---|---|---|
| `"page": "abc"` | `int("abc")` → `ValueError` | Rơi `except Exception` → message chung `GENERAL_EXECUTION_ERROR_MSG`, Agent không biết field nào sai |
| `"db_type": "oracle"` | Không validate enum | Chạy vào `query_database`, lỗi connection hoặc logic sâu bên trong |
| Thiếu `reference_file` | `KeyError` | Có `MISSING_ARG_MSG` (tốt) nhưng chỉ bắt `KeyError`, không bắt sai kiểu |
| `"read_option": 3` | `int(3)` OK, logic FBOGraph reject sau | Agent tốn 1 round-trip |

**Case C — Blocking I/O trên event loop**

Các hàm sync blocking:

- `query_database` → pyodbc
- `get_xml_entities` → đọc file XML
- `mcp_query_radar` / `mcp_read_local_file` → Kùzu + disk
- `search_qlyc` → HTTP API

Handler `_on_call_tool` là `async def` nhưng gọi trực tiếp hàm sync → **có thể block** toàn bộ event loop MCP trong thời gian query (3–30 phút nếu build Kuzu).

**Case D — Khó test nhanh**

Muốn test `search_qlyc` sau khi sửa logic → phải mở Cursor, viết prompt, hoặc viết script pytest import trực tiếp service (không qua MCP wire).

---

## 2. Công nghệ mới là gì?

### 2.1. MCP (Model Context Protocol)

Giao thức JSON-RPC giữa AI Agent (Cursor, Claude Desktop…) và server bên ngoài. Transport mặc định của `fastbusiness_mcp`: **stdio** (stdin/stdout). **Quan trọng:** stdout chỉ được chứa JSON-RPC — mọi `print()` debug phải ra stderr (đã xử lý trong `run_server.py`).

### 2.2. FastMCP → MCPServer (MCP Python SDK ≥ 2.0)

Trong tài liệu cộng đồng / Gemini thường gọi **FastMCP**. Trong repo này (`requirements.txt`: `mcp>=2.0.0`):

| Tên cũ (blog, Gemini) | Tên mới (SDK 2.x thực tế) | Import |
|---|---|---|
| `FastMCP` | **`MCPServer`** | `from mcp.server import MCPServer` |
| `mcp.server.fastmcp` | **Không còn** | `mcp_server.py` hiện tại sẽ `ImportError` nếu chạy trên SDK 2.x |

**Khi implement:** dùng `MCPServer`, giữ alias tương thích nếu cần:

```python
from mcp.server import MCPServer

server = MCPServer("fastbusiness-mcp-server")
# server.tool() — decorator đăng ký tool
```

`MCPServer` bên trong vẫn wrap low-level `Server` — không phải framework khác, chỉ là **lớp ergonomic** phía trên.

### 2.3. Pydantic v2 (tích hợp sẵn trong MCPServer)

Luồng xử lý khi Agent gọi tool:

```
JSON arguments từ Agent
    → Pydantic arg_model.model_validate(...)
    → (nếu sync fn) anyio.to_thread.run_sync(fn, **kwargs)
    → (nếu async fn) await fn(**kwargs)
    → convert_result → CallToolResult (TextContent)
```

Lỗi validate → MCP error code `INVALID_PARAMS` với message rõ field nào sai — **trước khi** vào logic FBO.

### 2.4. MCP Inspector

Công cụ dev chính thức — UI web test tool, xem JSON-RPC, đo latency.

```powershell
# Dev: chạy source Python
npx @modelcontextprotocol/inspector python -m fastbusiness_mcp.server

# Production exe (sau build)
npx @modelcontextprotocol/inspector E:\fastbusiness_mcp\fastbusiness_mcp.exe
```

---

## 3. So sánh trực tiếp — Before / After

### 3.1. Đăng ký tool `query_database`

**❌ Hiện tại (~40 dòng schema + ~10 dòng dispatch)**

```python
# _on_list_tools: Tool(name=..., inputSchema={...})
# _on_call_tool:
if name == "query_database":
    result = query_database(
        file_path=arguments["file_path"],
        query=arguments["query"],
        db_type=arguments.get("db_type", "app"),
        max_rows=int(arguments.get("max_rows", 20000)),
        query_type=int(arguments.get("query_type", 1)),
    )
    return CallToolResult(content=[TextContent(type="text", text=format_query_result(result))])
```

**✅ Sau migration (~20 dòng, 1 nơi)**

```python
from typing import Literal
from pydantic import Field
from mcp.server import MCPServer

server = MCPServer("fastbusiness-mcp-server")

@server.tool(name="query_database")
def query_database_tool(
    file_path: str = Field(description="Path file trong project FBO (XML/SQL) để resolve connection"),
    query: str = Field(description="Object name (type=0), SQL inline (type=1), hoặc path .sql (type=2)"),
    query_type: int = Field(default=1, description="0=object, 1=SQL inline (default), 2=file .sql"),
    db_type: Literal["app", "sys"] = Field(default="app", description="app hoặc sys (default: app)"),
    max_rows: int = Field(default=20000, description="Giới hạn số dòng trả về (default: 20000)"),
) -> str:
    """Chạy SQL trên SQL Server — tự resolve connection từ file_path (Web.config).

    query_type:
    - 0: tên object (dmkh, ff_xxx) — Script Table/Proc/View + Index/CONSTRAINT
    - 1: SQL inline ngắn (mặc định)
    - 2: path file .sql

    db_type: app (mặc định) hoặc sys.
    """
    result = query_database(
        file_path=file_path,
        query=query,
        db_type=db_type,
        max_rows=max_rows,
        query_type=query_type,
    )
    return format_query_result(result)
```

**Mapping tự động:**

| Python type hint | JSON Schema sinh ra |
|---|---|
| `str` | `"type": "string"` |
| `int = 1` | `"type": "integer", "default": 1` |
| `Literal["app", "sys"]` | `"enum": ["app", "sys"]` |
| `Field(description="...")` | `"description": "..."` (mô tả từng tham số) |
| Docstring hàm | `description` cấp tool của MCP Tool |

### 3.2. Threading — sync tool không block event loop

SDK gọi (trích `mcp/server/mcpserver/utilities/func_metadata.py`):

```python
if fn_is_async:
    return await fn(**arguments_parsed_dict)
else:
    return await anyio.to_thread.run_sync(functools.partial(fn, **arguments_parsed_dict))
```

→ Hàm `def query_database_tool(...)` vẫn viết sync bình thường; MCPServer tự đẩy sang thread pool.

---

## 4. Lộ trình migration (Giai đoạn 1)

### Phase 1 — Chuẩn bị (không đổi hành vi)

| Bước | Việc làm | Ghi chú |
|---|---|---|
| 1.1 | Tạo `fastbusiness_mcp/mcp_app.py` (file mới) | Chứa `MCPServer` instance + đăng ký 5 tool (`@server.tool(name="...")`) |
| 1.2 | Giữ `server.py` gọi `mcp_app` | `main()` vẫn license + `server.run()` (`run_server.py` giữ nguyên không cần sửa) |
| 1.3 | Port docstring tool + dùng `Field(description=...)` cho từng param | Giữ trọn vẹn context cho Agent trong `input_schema` |
| 1.4 | Cập nhật `mcp_server.py` (legacy) sang `MCPServer` | Sửa import `from mcp.server import MCPServer as FastMCP` tránh lỗi SDK 2.x |

### Phase 2 — Tool từng cái một

Thứ tự đề xuất (ít phụ thuộc → nhiều phụ thuộc):

1. `get_xml_entities` — pure file, dễ validate `mode: Literal["content","path","list"]`
2. `read_local_file` — tương tự, thêm `read_option: Literal[1, 2]`
3. `query_database` — thêm `Literal` cho `db_type`
4. `query_radar` — custom error Cypher (mục 7.3)
5. `search_qlyc` — config từ YAML + default `bp_lt` (mục 7.5)

### Phase 3 — Xóa boilerplate cũ

- Xóa `_on_list_tools` / `_on_call_tool` thủ công
- Giữ `agent_messages.py` cho lỗi nghiệp vụ (Cypher, thiếu config RAG)
- Chạy regression: `search_qlyc/test_search_qlyc.py`, `scripts/test_mcp_connect.py`

### Phase 4 — PyInstaller + deploy

Cập nhật `fastbusiness_mcp.spec` hiddenimports:

```python
'mcp.server.mcpserver',
'mcp.server.mcpserver.server',
'mcp.server.mcpserver.tools',
'mcp.server.mcpserver.utilities.func_metadata',
'pydantic', 'pydantic_core', 'anyio',
```

---

## 5. Spec từng tool — mapping đầy đủ

### 5.1. `query_database`

| Tham số | Kiểu | Bắt buộc | Default | Case cần cover |
|---|---|---|---|---|
| `file_path` | `str` | ✅ | — | Absolute/UNC path tới XML/SQL trong project FBO |
| `query` | `str` | ✅ | — | Object name / SQL inline / path `.sql` |
| `query_type` | `int` | ❌ | `1` | `0` object, `1` inline, `2` file |
| `db_type` | `Literal["app","sys"]` | ❌ | `"app"` | Agent gửi `"oracle"` → INVALID_PARAMS |
| `max_rows` | `int` | ❌ | `20000` | Agent gửi `"abc"` → INVALID_PARAMS |

**Case test MCP Inspector:**

```json
{
  "file_path": "E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml",
  "query": "SELECT TOP 5 ma_kh FROM dmkh",
  "query_type": 1,
  "db_type": "app"
}
```

**Case lỗi nghiệp vụ (sau validate):** Web.config sai, SQL lỗi → vẫn trả text từ `format_query_result`, không crash server.

---

### 5.2. `get_xml_entities`

| Tham số | Kiểu | Bắt buộc | Default | Ghi chú |
|---|---|---|---|---|
| `file_path` | `str` | ✅ | — | `.xml`, `.f`, … |
| `entities` | `list[str] \| None` | ❌ | `None` | Bắt buộc khi `mode=content/path` |
| `mode` | `Literal["content","path","list"]` | ❌ | `"content"` | `list` không cần `entities` |

**Case A — `mode=list`**

```json
{ "file_path": "E:\\FBO\\...\\Dir\\CPTran.xml", "mode": "list" }
```

**Case B — `mode=content` thiếu entities**

Validate Pydantic pass (entities optional) → lỗi nghiệp vụ từ `get_xml_entities` → format text.

**Case C — File không tồn tại**

Tool description đã cảnh báo: **KHÔNG tự tạo file** — trả lỗi cho Agent.

---

### 5.3. `query_radar`

| Tham số | Kiểu | Bắt buộc | Default | Ghi chú |
|---|---|---|---|---|
| `reference_file` | `str` | ✅ | — | **ABSOLUTE** path XML; relative → reject ở lớp FBOGraph |
| `cypher_query` | `str` | ❌ | `""` | Bắt buộc khi `mode=query` |
| `mode` | `Literal["query","schema"]` | ❌ | `"query"` | `schema` không cần Cypher |

**Case A — Thiếu Kuzu, sync-build in-process**

MCP block 15–30 phút, build xong, trả kết quả Cypher (không trả `build_cmd` cho Agent). Agent **không** tự chạy build.

**Case B — Cypher syntax sai**

Giữ custom message `QUERY_RADAR_ERROR_MSG` — bọc trong tool:

```python
@server.tool(name="query_radar")
def query_radar_tool(
    reference_file: str = Field(description="BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root."),
    cypher_query: str = Field(default="", description="Cypher cần chạy; bắt buộc khi mode=query, có thể để rỗng khi mode=schema"),
    mode: Literal["query", "schema"] = Field(default="query", description="query=chạy Cypher; schema=trả schema live + hướng dẫn"),
) -> str:
    try:
        return mcp_query_radar(cypher_query, reference_file, mode)
    except Exception as e:
        return QUERY_RADAR_ERROR_MSG.format(error_detail=str(e))
```

**Case C — `reference_file` relative**

```json
{ "reference_file": "Dir/SVTran.xml", "mode": "schema" }
```

→ Lỗi từ `mcp_query_radar` (invalid_reference_file), Agent sửa path absolute.

---

### 5.4. `read_local_file`

| Tham số | Kiểu | Bắt buộc | Default | Ghi chú |
|---|---|---|---|---|
| `file_path` | `str` | ✅ | — | Relative hoặc absolute (trong sandbox project) |
| `reference_file` | `str` | ✅ | — | Absolute — resolve project root |
| `read_option` | `Literal[1, 2]` | ❌ | `1` | `1`=raw, `2`=flat entity |

**Case A — File `.f` mã hóa**

Trả nội dung / hint `needs_xml` tùy parser — không crash.

**Case B — Path traversal (ngoài project)**

Sandbox từ chối — message lỗi rõ.

**Case C — Windows-1258 tiếng Việt**

Giữ nguyên pipeline decode hiện có trong `mcp_read_local_file`.

---

### 5.5. `search_qlyc`

| Tham số | Kiểu | Bắt buộc | Default | Ghi chú |
|---|---|---|---|---|
| `query` | `str` | ❌ | `""` | Semantic search; có thể rỗng nếu có `fcode1`/`ma_da` |
| `fcode1` | `str \| None` | ❌ | `None` | Tra cứu chính xác ticket |
| `ma_da` | `str \| None` | ❌ | `None` | Filter dự án |
| `bp_lt` | `str \| None` | ❌ | từ config | Default `rag_qlyc.bp_lt` trong `config.yaml` |
| `page` | `int` | ❌ | `1` | ≥ 1 |
| `page_size` | `int` | ❌ | `20` | 1–50 (clamp trong service) |
| `max_total` | `int` | ❌ | `100` | 1–100 |

**Case đặc biệt — config.yaml không load được vào tool**

Low-level hiện tại: `self.config.get("rag_qlyc")` trong class.

FastMCP pattern — dùng **lifespan** hoặc module-level config:

```python
from contextlib import asynccontextmanager
from dataclasses import dataclass
from mcp.server.mcpserver.server import Context  # nếu dùng Context inject

@dataclass
class AppState:
    rag_config: dict

@asynccontextmanager
async def lifespan(app: MCPServer):
    cfg = _load_config("config.yaml")
    yield AppState(rag_config=cfg.get("rag_qlyc") or {})

server = MCPServer("fastbusiness-mcp-server", lifespan=lifespan)

@server.tool(name="search_qlyc")
def search_qlyc_tool(
    query: str = "",
    fcode1: str | None = None,
    ma_da: str | None = None,
    bp_lt: str | None = None,
    page: int = 1,
    page_size: int = 20,
    max_total: int = 100,
    ctx: Context | None = None,  # inject Context nếu cần state
) -> str:
    ...
```

Hoặc đơn giản hơn cho Giai đoạn 1: load config một lần lúc import `mcp_app.py` thông qua hàm helper `_get_config()` / `load_config()` (giống pattern hiện tại của class).

**Case — Bypass semantic (query rỗng + fcode1)**

```json
{ "query": "", "fcode1": "YC00123", "ma_da": "SP2263", "page": 1 }
```

**Case — Thiếu base_url/api_key**

Service trả `ok: false, error: config_thieu` — format qua `format_search_result`.

---

## 6. Bảng case validate — Agent gửi sai

| Tool | Payload sai | Low-level hiện tại | Sau MCPServer |
|---|---|---|---|
| Mọi tool | Thiếu field required | `KeyError` → `MISSING_ARG_MSG` | Pydantic → INVALID_PARAMS (field name rõ) |
| `query_database` | `"max_rows": "abc"` | ValueError → general error | `"max_rows: Input should be a valid integer"` |
| `query_database` | `"db_type": "oracle"` | Chạy, lỗi sâu | `"db_type: Input should be 'app' or 'sys'"` |
| `get_xml_entities` | `"mode": "full"` | Chạy, lỗi logic | Enum validation fail ngay |
| `read_local_file` | `"read_option": 99` | int OK, lỗi logic | Literal[1,2] fail nếu dùng Literal |
| `search_qlyc` | `"page": -1` | `max(1, page)` trong service | Có thể thêm `Field(ge=1)` nếu muốn reject sớm |
| `query_radar` | `"mode": "build"` | Chạy, lỗi logic | Enum fail sớm |

**Quyết định thiết kế:** Giữ clamp trong `search_qlyc` service (page_size, max_total) **và** có thể thêm `Field(ge=1, le=50)` ở layer MCP để Agent nhận lỗi sớm hơn.

---

## 7. Xử lý lỗi — phân tầng

```
Tầng 1: Pydantic validate arguments     → INVALID_PARAMS (JSON-RPC)
Tầng 2: KeyError / thiếu config         → Text MISSING_ARG / config_thieu
Tầng 3: Lỗi nghiệp vụ FBO               → Text format_* (SQL, Cypher, RAG)
Tầng 4: Exception không mong đợi      → GENERAL_EXECUTION_ERROR_MSG + log stderr
```

### 7.1. Giữ `agent_messages.py`

Không xóa — vẫn cần hướng dẫn Agent sửa Cypher (`QUERY_RADAR_ERROR_MSG`).

### 7.2. Khi nào dùng `ToolError` (MCPServer)

```python
from mcp.server.mcpserver.exceptions import ToolError

raise ToolError("reference_file phải là đường dẫn absolute tới file XML trong project FBO")
```

Dùng cho lỗi **do caller sửa được ngay** mà chưa vào được service layer.

### 7.3. Không nuốt lỗi validate

**Sai:**

```python
try:
    page = int(arguments.get("page", 1))
except:
    page = 1
```

**Đúng:** để Pydantic validate `page: int`.

---

## 8. Mở rộng tương lai (Giai đoạn 2+) — Resources & Prompts

Không bắt buộc Giai đoạn 1. Ghi spec sẵn để tránh refactor lần 2.

### 8.1. Resource — schema bảng SQL

```python
@server.resource("fbo://schema/{table_name}")
def get_table_schema(table_name: str) -> str:
    """Metadata cột + index — gọi query_type=0 nội bộ."""
    ...
```

Agent đọc URI thay vì gọi tool ad-hoc.

### 8.2. Prompt — review XML FBO

```python
@server.prompt()
def review_fbo_xml(file_path: str) -> str:
    return f"""Review {file_path} theo quy tắc:
    - snake_case cho biến local
    - Partition: @@prime$partition$current
    - Không hardcode d91$202501
    """
```

### 8.3. Tool đã ẩn — KHÔNG bật lại trong migration

Backup: `fastbusiness_mcp/backup_hidden_tools.py`. Lý do ẩn: Agent dùng `query_radar` + Template Cypher trong Rules, tránh trùng tool gây nhầm.

---

## 9. MCP Inspector — hướng dẫn test từng case

### 9.1. Cài và chạy

```powershell
cd E:\PythonProject\mcp_fbo
.\.venv\Scripts\activate
npx @modelcontextprotocol/inspector python -m fastbusiness_mcp.server
```

Trình duyệt mở UI → tab **Tools** → chọn tool → điền form → **Run**.

### 9.2. Checklist test regression (5 tool live)

| # | Tool | Input tóm tắt | Kỳ vọng |
|---|---|---|---|
| 1 | `query_database` | SQL TOP 5 từ path SP có Web.config | Rows hoặc lỗi SQL rõ |
| 2 | `get_xml_entities` | `mode=list` trên CPTran.xml | Danh sách entity |
| 3 | `query_radar` | `mode=schema` + reference absolute | Schema XmlFile/Rel |
| 4 | `query_radar` | Template 1 Cypher CPTran | Rows ≤ LIMIT |
| 5 | `read_local_file` | Dir/CPTran.xml, read_option=1 | Nội dung XML |
| 6 | `search_qlyc` | fcode1 + ma_da, query="" | Ticket đúng (nếu config OK) |
| 7 | `search_qlyc` | query semantic + page=2 | Pagination metadata |

### 9.3. Test validate (Inspector → cố ý gửi sai)

| # | Tool | Payload | Kỳ vọng |
|---|---|---|---|
| V1 | `query_database` | bỏ `file_path` | Lỗi thiếu required |
| V2 | `query_database` | `db_type: "x"` | Enum error |
| V3 | `search_qlyc` | `page: "abc"` | Integer error |
| V4 | `query_radar` | reference relative | Lỗi FBOGraph invalid path |
| V5 | `get_xml_entities` | `mode: "invalid"` | Enum error |

### 9.4. Debug JSON-RPC

Inspector hiển thị:

- Request `tools/call` đầy đủ arguments
- Response `content[0].text` hoặc error object
- Thời gian ms — so sánh trước/sau `to_thread` (không nên block UI Inspector khi chạy 2 request song song)

### 9.5. Test exe đóng gói

```powershell
npx @modelcontextprotocol/inspector E:\fastbusiness_mcp\fastbusiness_mcp.exe
```

Working directory Inspector = thư mục chứa `config.yaml` + exe.

---

## 10. Cấu hình Cursor / VS Code

### 10.1. Dev (source)

```json
{
  "mcpServers": {
    "fastbusiness-mcp-dev": {
      "command": "E:\\PythonProject\\mcp_fbo\\.venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\PythonProject\\mcp_fbo"
    }
  }
}
```

Tham khảo: `example_mcp_config.json`

### 10.2. Production (exe)

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\fastbusiness_mcp\\fastbusiness_mcp.exe",
      "cwd": "E:\\fastbusiness_mcp"
    }
  }
}
```

**Case:** Sau migration, **không đổi** tên tool → Cursor config cũ vẫn hoạt động.

---

## 11. Cấu trúc file đề xuất sau migration

```
fastbusiness_mcp/
├── server.py              # main(), license, server.run()
├── mcp_app.py             # MCPServer instance + @server.tool() x5
├── agent_messages.py      # Giữ nguyên
├── config_paths.py
├── backup_hidden_tools.py # Không đụng
└── tools/
    └── (optional) tách từng tool nếu mcp_app.py dài
```

**Ví dụ `server.py` mỏng:**

```python
def main():
    from fastbusiness_mcp.license import verify_and_enforce_license
    verify_and_enforce_license()
    from fastbusiness_mcp.mcp_app import server
    server.run()  # MCPServer.run() là synchronous (tự gọi anyio.run nội bộ)
```

> [!WARNING]
> `MCPServer.run()` là hàm synchronous và tự quản lý event loop bằng `anyio.run(self.run_stdio_async)`. **TUYỆT ĐỐI KHÔNG** bọc `asyncio.run(server.run())` như ở phiên bản low-level cũ ([server.py:376](file:///e:/PythonProject/mcp_fbo/fastbusiness_mcp/server.py#L376)), nếu không sẽ gây lỗi `RuntimeError: This event loop is already running`.

---

## 12. PyInstaller — case hay vỡ

| Case | Triệu chứng | Cách xử lý |
|---|---|---|
| Thiếu hiddenimport `mcp.server.mcpserver` | exe start → ImportError | Thêm vào `.spec` |
| Thiếu `pydantic_core` | Validate fail / crash | Thêm hiddenimport |
| `print()` ra stdout | Cursor parse JSON lỗi | Giữ patch `run_server.py` |
| `config.yaml` không bundle | search_qlyc config_thieu | `datas=[('config.yaml', '.')]` — đã có |
| License check | exe từ chối chạy | Không đổi `verify_and_enforce_license()` |

---

## 13. Rủi ro và mitigation

| Rủi ro | Mức | Mitigation |
|---|---|---|
| Docstring tool ngắn hơn schema cũ → Agent kém context | Trung bình | Copy nguyên description dài từ `_on_list_tools` sang docstring |
| `Literal[1,2]` vs `int` cho read_option | Thấp | Giữ `int` + mô tả docstring nếu Literal gây khó Agent |
| Lifespan config search_qlyc | Trung bình | Giai đoạn 1: load config module-level |
| SDK đổi tên FastMCP → MCPServer | Thấp | Doc + code dùng `MCPServer` |
| Build Kuzu block thread pool | Trung bình | Chấp nhận Giai đoạn 1; Giai đoạn 2 cân nhắc `async` + progress Context |
| Regression exe | Cao | Inspector + `scripts/test_mcp_connect.py` trước khi phát hành |

---

## 14. Tiêu chí Done (Definition of Done)

- [ ] `fastbusiness_mcp/server.py` không còn `_on_list_tools` / `_on_call_tool` thủ công
- [ ] 5 tool live giữ **đúng tên** và hành vi như trước
- [ ] Tool hidden **không** xuất hiện trong `list_tools`
- [ ] License + `config.yaml` + stderr-safe print vẫn hoạt động
- [ ] MCP Inspector pass checklist mục 9.2
- [ ] Validate cases mục 9.3 trả lỗi rõ (không general exception)
- [ ] `build_onedir.bat` → exe chạy Inspector OK
- [ ] `search_qlyc/test_search_qlyc.py` pass
- [ ] README cập nhật 1 dòng: dùng MCPServer (FastMCP)

---

## 15. Prompt mẫu gửi AI implement (copy-paste)

```
Implement migration fastbusiness_mcp/server.py sang mcp.server.MCPServer (SDK 2.x, KHÔNG dùng mcp.server.fastmcp).

Ràng buộc:
1. Tạo fastbusiness_mcp/mcp_app.py — đăng ký 5 tool: query_database, get_xml_entities, query_radar, read_local_file, search_qlyc.
2. Mỗi tool: @server.tool(name="<tool_name>"), type hints + Field(description=...) cho từng tham số, docstring = copy description tool từ server.py cũ.
3. db_type: Literal["app","sys"]; mode get_xml_entities: Literal["content","path","list"]; mode query_radar: Literal["query","schema"]; read_option: Literal[1,2].
4. Gọi lại hàm core hiện có — KHÔNG đổi queryDatabase/, find_entity_by_xml/, xml_fbograph/, search_qlyc/.
5. query_radar: bọc try/except → QUERY_RADAR_ERROR_MSG.
6. search_qlyc: load config.yaml (rag_qlyc), default bp_lt như server.py cũ.
7. server.py main(): license + mcp_app.server.run() (không dùng asyncio.run bọc ngoài).
8. KHÔNG bật search_nodes/get_related_nodes/query_node_details.
9. Cập nhật fastbusiness_mcp.spec hiddenimports cho mcpserver + pydantic.
10. Test: npx @modelcontextprotocol/inspector python -m fastbusiness_mcp.server

Tham chiếu spec: docs/doc/fastbusiness_mcp_fastmcp_migration.md
```

---

## 16. FAQ nhanh

**Q: FastMCP và MCPServer có khác nhau không?**  
A: Cùng ý tưởng. SDK ≥2.0 đổi tên `FastMCP` → `MCPServer`. Blog/Gemini vẫn gọi FastMCP.

**Q: Có phải đổi logic build Kuzu không?**  
A: Không. Migration chỉ đổi lớp MCP wrapper.

**Q: MCP Inspector có thay pytest không?**  
A: Không — Inspector test wire protocol + UX; pytest vẫn cần cho service unit test.

**Q: Agent có cần sửa Rules Cursor không?**  
A: Không nếu giữ nguyên tên tool và mô tả tương đương.

**Q: `mcp_server.py` xử lý thế nào?**  
A: Deprecate hoặc migrate sang `MCPServer` để dev local FBOGraph; không trùng entry `run_server.py`.

---

*Tài liệu này mô tả kiến trúc migration FastMCP/MCPServer cho FastBusiness MCP Server — Giai đoạn 1 (refactor transport, giữ nguyên nghiệp vụ FBO).*
