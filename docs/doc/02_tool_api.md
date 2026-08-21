# 02 — Tool API: `summary_object`

## 1. Đăng ký MCP

Thêm vào `fastbusiness_mcp/mcp_app.py` (tool thứ 6). **Copy pattern** từ `query_database_tool` hiện có (`MCPServer` + `Annotated`/`Field` + `format_execution_error`) — không dùng FastMCP generic:

```python
from typing import Annotated, Literal
from pydantic import Field

from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.bridges.summary_format import format_summary_result
from fastbusiness_mcp.tool_errors import format_execution_error

@server.tool(name="summary_object")
def summary_object_tool(
    file_path: Annotated[str, Field(description="Path file FBO để resolve connection")],
    object_name: Annotated[str, Field(description="Tên proc/function/view, vd: zc_bcthlv hoặc dbo.zc_bcthlv")],
    mode: Annotated[
        Literal["summary", "snippet", "full"],
        Field(default="summary"),
    ] = "summary",
    # ... các tham số còn lại (xem bảng §2)
) -> str:
    """Phân tích proc/function/view — summary JSON gọn thay vì full sp_helptext."""
    try:
        result = summary_object(
            file_path=file_path,
            object_name=object_name,
            mode=mode,
            # ...
        )
        return format_summary_result(result)
    except Exception as e:
        return format_execution_error("summary_object", e)
```

Import từ bridge (**không** import `tsql_engine` / `sql_object_summary` trực tiếp).

## 2. Tham số input

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---------|------|----------|----------|-------|
| `file_path` | `str` | ✅ | — | Path file trong project FBO để resolve connection (giống `query_database`) |
| `object_name` | `str` | ✅ | — | Tên proc/function/view, vd: `zc_bcthlv` hoặc `dbo.zc_bcthlv` (xem §2.1) |
| `mode` | `enum` | — | `"summary"` | `summary` \| `snippet` \| `full` |
| `db_type` | `enum` | — | `"app"` | `app` \| `sys` |
| `schema` | `str` | — | `"dbo"` | Schema mặc định nếu object_name không có prefix |
| `max_depth` | `int` | — | `1` | Độ sâu đệ quy call graph (business objects, 0–3). View/Infra mặc định depth=0. |
| `max_objects` | `int` | — | `30` | Giới hạn số object tối đa trong 1 request call graph. Vượt quá sẽ lưu vào `truncated_objects`. |
| `expand` | `list[str]` | — | `[]` | Danh sách object infra cần bung thêm 1 cấp (override depth 0) |
| `exclude_like` | `list[str]` | — | xem §2.2 | Regex loại object khỏi đệ quy call graph (mặc định = infra patterns) |
| `include_called_by` | `bool` | — | `false` | Có truy inbound references không |
| `keywords` | `list[str]` | — | `[]` | **Bắt buộc khi mode=snippet** (trừ khi dùng `zones`) |
| `zones` | `list[str]` | — | `[]` | Vùng snippet: `header`, `params`, `key_filter`, `cursor`, `processing`, `result_set`, `pivot` |
| `max_snippet_lines` | `int` | — | `120` | Giới hạn dòng snippet |
| `max_full_chars` | `int` | — | `50000` | Giới hạn ký tự mode full |
| `use_cache` | `bool` | — | `true` | Dùng cache in-memory thread-safe (LRU 200 entries, TTL 3600s theo modify_date) |

### Pydantic Field (gợi ý copy vào mcp_app.py)

```python
object_name: Annotated[str, Field(description="Tên proc/function/view SQL Server, vd: zc_bcthlv, rs_rptInterestDetailedByLoanContract")]

mode: Annotated[
    Literal["summary", "snippet", "full"],
    Field(default="summary", description="summary=JSON gọn; snippet=đoạn SQL theo keywords/zones; full=definition (giới hạn max_full_chars)"),
] = "summary"

max_depth: Annotated[int, Field(default=1, ge=0, le=3, description="Độ sâu call graph cho object business (0-3). Infra/View mặc định depth=0.")]

max_objects: Annotated[int, Field(default=30, ge=1, le=50, description="Giới hạn số lượng object fetch tối đa trong 1 request đệ quy.")]

expand: Annotated[
    list[str] | None,
    Field(default=None, description="Chỉ định object infra cần bung subtree, vd: ['FastBusiness$Balance$BContract']"),
] = None

keywords: Annotated[
    list[str] | None,
    Field(default=None, description="mode=snippet: từ khóa tìm block SQL (vd: tl_th, @Status, ctdmku, WHILE)"),
] = None
```

### 2.1. Parse `object_name` + `schema`

Bridge gọi helper `resolve_object_ref(object_name, schema)` — bên trong đã `sanitize_sql_identifier` từng phần:

| Input | Kết quả `(schema, name)` |
|-------|--------------------------|
| `zc_bcthlv` + `schema="dbo"` | `("dbo", "zc_bcthlv")` |
| `dbo.zc_bcthlv` + `schema="dbo"` | `("dbo", "zc_bcthlv")` — **param `schema` bị bỏ qua** |
| `FastBusiness$Balance$BContract` | `("dbo", "FastBusiness$Balance$BContract")` — không có `.`, giữ nguyên tên |
| `dbo.FastBusiness$Balance$BContract` | split dấu `.` **đầu tiên** → `("dbo", "FastBusiness$Balance$BContract")` |

**Quy tắc:**

1. Trim whitespace; bỏ `[]`/`"` bọc ngoài (giống `sanitize_sql_identifier`).
2. Nếu có dấu `.` → split **lần đầu** thành `(schema_part, name_part)`; sanitize từng phần; **`schema` param không dùng**.
3. Nếu không có `.` → `name = object_name`, `schema = schema` param (mặc định `dbo`).
4. Catalog fetch filter **cả schema + name** (`fetch_one(name, schema)`) — khác `query_database type=0` (chỉ lookup theo `name`).

```python
def resolve_object_ref(object_name: str, schema: str = "dbo") -> tuple[str, str]:
    cleaned = object_name.strip()
    if "." in cleaned:
        schema_part, _, name_part = cleaned.partition(".")
        return sanitize_sql_identifier(schema_part), sanitize_sql_identifier(name_part)
    return sanitize_sql_identifier(schema), sanitize_sql_identifier(cleaned)
```

### 2.2. `exclude_like` — default

Khi Agent không truyền `exclude_like`, bridge dùng (regex, match tên object **không** gồm schema):

```python
DEFAULT_EXCLUDE_LIKE = [
    r"^FastBusiness\$",
    r"^ff_",
    r"^fsd_",
]
```

Object match → không đệ quy fetch con (tương đương `kind: infra`, depth 0), trừ khi có trong `expand`.

`AnalyzeOptions.exclude_like` nhận list đã merge; `sql_object_summary/classifier.py` dùng chung với `INFRA_PATTERNS`.

### 2.3. Mapping `sys.objects.type` → `object_type` JSON

Response JSON dùng enum cao cấp; bridge map từ catalog:

| `sys.objects.type` | `type_desc` (gợi ý) | `object_type` JSON |
|--------------------|---------------------|-------------------|
| `P` | SQL_STORED_PROCEDURE | `PROCEDURE` |
| `FN` | SQL_SCALAR_FUNCTION | `FUNCTION` |
| `IF` | SQL_INLINE_TABLE_VALUED_FUNCTION | `FUNCTION` |
| `TF` | SQL_TABLE_VALUED_FUNCTION | `FUNCTION` |
| `V` | VIEW | `VIEW` |
| `TR` | SQL_TRIGGER | — → **`unsupported_type`** |
| `U` | USER_TABLE | — → **`unsupported_type`** (dùng `query_database type=0`) |

```python
def map_object_type(sys_type: str) -> str:
    if sys_type == "P":
        return "PROCEDURE"
    if sys_type in ("FN", "IF", "TF"):
        return "FUNCTION"
    if sys_type == "V":
        return "VIEW"
    raise UnsupportedObjectType(sys_type)
```

## 3. Tool description (cho Agent)

```
Phân tích proc/function SQL Server — trả summary JSON gọn thay vì full sp_helptext.

QUY TRÌNH AGENT (tiết kiệm token):
1) summary_object(mode=summary) — biết params, tables, calls, signals
2) summary_object(mode=snippet, keywords=[...]) — lấy đúng block logic cần đọc
3) summary_object(mode=full) — chỉ khi snippet thiếu
4) TRÁNH query_database query_type=0 chỉ để "xem proc làm gì"

Infra (FastBusiness$%, ff_%, fsd_%) không expand mặc định.
```

## 4. Response format (text cho MCP)

Formatter trả string markdown tương tự `format_query_result`:

```markdown
[OK] summary_object
Object: dbo.rs_rptInterestDetailedByLoanContract (PROCEDURE)
Mode: summary
Database: FBISP242 @ SERVER
Parse: ok | partial | failed
Cache: hit | miss

```json
{ ... }
```
```

Lỗi:

```markdown
[ERROR] Không tìm thấy object: xyz
File: E:\...\Filter\zcbcthlv.xml
```

## 5. Ba mode chi tiết

### 5.1. `mode=summary` (mặc định)

Trả JSON theo schema `03_json_schema.md` — **không** có `sql_text` / `definition`.

Pipeline:

1. Resolve connection từ `file_path` (reuse `queryDatabase.connection.get_connection_config`)
2. Lookup `sys.objects` + `sys.sql_modules.definition` (hoặc `sp_helptext` ghép chuỗi)
3. ANTLR parse → visitor extract
4. Phân loại infra/business
5. Nếu `max_depth > 0`: đệ quy fetch + parse object con (business); infra chỉ tên
6. Optional `called_by` từ catalog views
7. Build JSON + stats (`line_count`, `estimated_tokens_saved`)

### 5.2. `mode=snippet`

Trả JSON:

```json
{
  "object": "dbo.rs_rptInterestDetailedByLoanContract",
  "mode": "snippet",
  "snippets": [
    {
      "id": "block_1",
      "match_reason": "keyword:tl_th",
      "line_start": 210,
      "line_end": 268,
      "sql": "..."
    }
  ],
  "total_lines": 45,
  "truncated": false
}
```

**Chiến lược extract snippet (ưu tiên):**

1. **zones** nếu có — map vùng FBO (xem bảng dưới)
2. **keywords** — tìm dòng chứa keyword, lấy block `BEGIN…END` bao quanh (hoặc ±N dòng)
3. Gộp block overlap
4. Cắt `max_snippet_lines`

| Zone | Heuristic nhận diện |
|------|---------------------|
| `header` | `CREATE PROCEDURE` … `AS` + param list |
| `params` | Dòng `--`, `@` declare đầu proc |
| `key_filter` | Comment `-- KEY`, `-- JOIN`, `WHERE` lớn sau temp insert |
| `cursor` | `DECLARE … CURSOR`, `FETCH`, `WHILE @@FETCH_STATUS` |
| `processing` | `WHILE`, `UPDATE #`, vòng lặp ngày |
| `result_set` | `SELECT` cuối không gán biến (trước `RETURN`/`END`) |
| `pivot` | `#pivot`, `xpivot`, `npivot`, `xsearch` |

### 5.3. `mode=full`

Trả JSON:

```json
{
  "object": "dbo.zc_bcthlv",
  "mode": "full",
  "definition": "CREATE PROCEDURE ...",
  "line_count": 482,
  "char_count": 28400,
  "truncated": false,
  "truncated_at_char": null
}
```

- Nguồn: `sys.sql_modules.definition` (unicode) hoặc ghép `sp_helptext`
- Cắt tại `max_full_chars` → `truncated: true`
- Dùng khi Agent thật sự cần sửa body — **không** mặc định

## 6. SQL lấy definition (`queryDatabase/object_catalog/fetcher.py`)

Module **`ObjectCatalogFetcher`** — không đặt trong `sql_object_summary`.

### Ưu tiên: `sys.sql_modules`

```sql
-- Placeholder @name, @schema: truyền qua pyodbc parameter SAU sanitize_sql_identifier().
-- v1 có thể build SQL giống query_resolver (N'{safe_name}') nếu executor chưa hỗ trợ params.
SELECT
    o.object_id,
    SCHEMA_NAME(o.schema_id) AS schema_name,
    o.name,
    o.type,
    o.type_desc,
    m.definition,
    o.modify_date
FROM sys.objects o
JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name = @name
  AND SCHEMA_NAME(o.schema_id) = @schema
```

### Fallback: `sp_helptext`

Giống `queryDatabase/queries_config.yaml` template `object_definition`.

Ghép nhiều dòng Text thành một string (giữ `\n`).

### Pre-process trước ANTLR

1. Bỏ dòng `GO` (batch separator)
2. Normalize `\r\n` → `\n`
3. **Không** strip comment (visitor cần bỏ qua comment channel)
4. Nếu definition NULL (encrypted) → error rõ ràng

## 7. Call graph đệ quy

```
resolve(root)
  → parse root → calls_direct
  → for each call in calls_direct:
        if total_objects >= max_objects:
            add to truncated_objects; continue  # Truncate graceful
        if is_infra(name) and name not in expand:
            add { name, kind: "infra" }  # STOP
        elif depth < max_depth:
            resolve(child)  # business or expanded infra
        else:
            add { name, kind: "business", depth_limited: true }
```

- **Chống vòng lặp:** `visited: set[(schema, name)]`
- **Giới hạn an toàn:** `max_objects` (mặc định 30, tối đa 50 object / request).
- **Xử lý khi vượt giới hạn:** Khi `len(visited) >= max_objects`, hệ thống **không báo lỗi** mà dừng đệ quy nhánh tiếp theo, ghi nhận danh sách các object chưa duyệt vào `truncated_objects: list[str]` và set `truncated: true` trong `call_graph`.

## 8. Inbound (`include_called_by=true`)

> **Lưu ý:** `sys.dm_sql_referenced_entities` trả **outbound** (object X reference tới ai) — **không dùng** cho `called_by`.

### Primary — `sys.sql_expression_dependencies`

```sql
-- @object_id lấy từ fetch_one (sys.objects.object_id)
SELECT DISTINCT
    OBJECT_SCHEMA_NAME(d.referencing_id) + '.' + OBJECT_NAME(d.referencing_id) AS caller
FROM sys.sql_expression_dependencies AS d
WHERE d.referenced_id = @object_id
  AND d.referencing_id <> d.referenced_id
ORDER BY caller
```

### Fallback — theo tên (khi thiếu quyền / catalog chưa sync)

```sql
-- @safe_name: đã qua sanitize_sql_identifier()
SELECT DISTINCT
    OBJECT_SCHEMA_NAME(d.referencing_id) + '.' + OBJECT_NAME(d.referencing_id) AS caller
FROM sys.sql_expression_dependencies AS d
INNER JOIN sys.objects AS ro ON ro.object_id = d.referenced_id
WHERE ro.name = @safe_name
  AND (@safe_schema IS NULL OR OBJECT_SCHEMA_NAME(ro.object_id) = @safe_schema)
ORDER BY caller
```

- **Xử lý lỗi:** Nếu cả primary và fallback đều lỗi, trả `"called_by": []` kèm warning trong `meta.warnings` — **không fail** toàn bộ request.

## 9. Quan hệ với `query_database`

| Nhu cầu | Tool |
|---------|------|
| Schema bảng (`dmku`) | `query_database type=0` |
| Chạy EXEC test | `query_database type=1` |
| Script deploy file .sql | `query_database type=2` |
| Hiểu proc / dependency / snippet / view | **`summary_object`** |

Không sửa behavior `query_database` hiện tại trong v1.

## 10. Lỗi chuẩn

| Code | HTTP MCP | Message |
|------|----------|---------|
| `object_not_found` | ToolError | Không tìm thấy trong sys.objects |
| `unsupported_type` | ToolError | Chỉ hỗ trợ P, FN, IF, TF, V — trigger (`TR`) và bảng (`U`) từ chối rõ |
| `encrypted` | ToolError | Object encrypted, không đọc definition |
| `snippet_params_required` | ToolError | `mode=snippet` nhưng cả `keywords` và `zones` đều rỗng |
| `parse_failed` | OK + warning | Trả partial summary + raw line_count |
| `connection_failed` | ToolError | Giống query_database |

Dùng `fastbusiness_mcp.tool_errors.format_execution_error` cho nhất quán.

## 11. Bảo mật & Sanitization

- **Sanitize bắt buộc:** `object_name`, `schema`, mọi tên trong `expand` phải qua `sanitize_sql_identifier()` (regex `^[a-zA-Z0-9_$]+$`) — giống `queryDatabase/query_resolver.py`.
- **v1 — identifier trong SQL:** Sau sanitize, được phép embed vào SQL dạng `N'{safe_name}'` (pattern hiện có của `build_object_lookup_sql`). **Cấm** nối chuỗi user input thô.
- **Không nhét SQL từ Agent:** Catalog fetch chỉ dùng tên đã sanitize hoặc `object_id` (integer từ DB).
- **Phase 2 (khuyến khích):** Mở rộng `execute_query(..., params=...)` + pyodbc `?` cho catalog — không bắt buộc v1 nếu giữ sanitize.

## 12. Timeout & graceful degradation

| Giới hạn | Giá trị | Cách implement v1 |
|----------|---------|-------------------|
| Connection | 30s | `pyodbc.connect(..., timeout=30)` — đã có trong `executor.py` |
| Fetch đơn (`fetch_one`, `fetch_callers`) | 10s | `time.perf_counter()` trong bridge/fetcher; abort/log warning nếu vượt |
| Batch (`fetch_many`) | 15s | Tương tự |
| Tổng request `summary_object` | 30s | Bridge kiểm tra trước mỗi bước đệ quy |

- **Partial child failure:** Object con fetch lỗi/timeout → node `{ "name": "...", "status": "error", "error": "fetch_timeout" }`, tiếp tục nhánh khác.
- **Không có circuit breaker v1** (không đếm lỗi liên tiếp / open-half-open).

## 13. Formatter — tách JSON vs MCP text

| Hàm | Package | Output |
|-----|---------|--------|
| `result_to_dict(SummaryResult)` | `sql_object_summary/formatter.py` | `dict` JSON thuần |
| `format_summary_result(dict)` | `queryDatabase/bridges/summary_format.py` | Markdown string cho MCP |

MCP **chỉ** gọi `format_summary_result`; không format markdown trong `sql_object_summary`.
