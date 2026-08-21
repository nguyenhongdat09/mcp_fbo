# 07 — Kiến trúc 3 lớp: tách ANTLR4, feature summary, nhúng nhẹ queryDatabase

> **Nguyên tắc:** Mỗi folder một trách nhiệm. Dependency chỉ đi **một chiều xuống**.  
> ANTLR4 nằm package riêng để sau này dùng cho formatter, lint SQL, enrich Graph… mà **không** đụng `queryDatabase` hay MCP.

---

## 1. Sơ đồ tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│  fastbusiness_mcp/          (Lớp MCP — mỏng)                  │
│  mcp_app.py  →  query_database_tool                         │
│              →  summary_object_tool  (gọi bridge, ~10 dòng)   │
└───────────────────────────┬─────────────────────────────────┘
                            │ import
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  queryDatabase/             (Lớp DB + bridge — mỏng)          │
│  service.py, connection.py, executor.py   ← giữ nguyên       │
│  object_catalog/            ← MỚI: đọc metadata SQL Server    │
│  bridges/                                                   │
│    summary_bridge.py        ← MỚI: nối catalog + summary      │
└───────────────┬─────────────────────────┬───────────────────┘
                │ definitions (string)      │ reuse connection
                ▼                           │
┌───────────────────────────────┐           │
│  sql_object_summary/          │           │
│  (Lớp nghiệp vụ — pure logic) │           │
│  KHÔNG import pyodbc/MCP      │           │
└───────────────┬───────────────┘           │
                │ parse AST                 │
                ▼                           │
┌───────────────────────────────┐           │
│  tsql_engine/                 │           │
│  (Lớp ANTLR4 — tái sử dụng)   │           │
│  ZERO phụ thuộc project khác  │           │
└───────────────────────────────┘           │
```

---

## 2. Ba package độc lập

### 2.1. `tsql_engine/` — Engine ANTLR4 (dùng lại được)

**Trách nhiệm duy nhất:** Biến `string SQL` → cây cú pháp + token stream + line map.

**Không được:**
- Gọi database
- Biết proc/function FBO, infra, pivot
- Import `queryDatabase`, `fastbusiness_mcp`

**Public API (ổn định, version sau không phá):**

```python
# tsql_engine/__init__.py
from tsql_engine.engine import TSqlEngine, ParseResult

def parse(source: str, *, entry_rule: str = "tsql_file") -> ParseResult:
    """Parse T-SQL text. Trả tree + errors + source map."""
    ...
```

```python
# tsql_engine/engine.py
@dataclass
class ParseResult:
    source: str
    tree: ParserRuleContext | None
    errors: list[ParseError]
    lines: list[str]                    # preprocess xong
    line_map: list[int] | None          # map parsed line → original (optional)
    status: Literal["ok", "partial", "failed"]

class TSqlEngine:
    def parse(self, source: str, entry_rule: str = "tsql_file") -> ParseResult: ...
    def parse_procedure_body(self, source: str) -> ParseResult: ...
```

**Cấu trúc folder:**

```
tsql_engine/
  __init__.py
  engine.py                 # facade parse()
  preprocess.py             # bỏ GO, normalize
  errors.py                 # CollectErrorListener
  grammar/
    TSqlLexer.g4
    TSqlParser.g4
  generated/                # ANTLR output — commit vào git
    TSqlLexer.py
    TSqlParser.py
    TSqlParserVisitor.py
  tools/
    generate.bat            # java -jar antlr ...
  README.md                 # hướng dẫn thêm visitor mới
```

**Mở rộng sau này (ví dụ):**

| Use case mới | Cách làm |
|--------------|----------|
| Format SQL | Package mới `tsql_formatter/` → visitor trên `tsql_engine` |
| Lint rule “cấm SELECT *” | `tsql_lint/rules/` + visitor |
| Extract table từ chuỗi Filter `exec proc ...` | `filter_sql/` visitor nhỏ |
| Enrich FBOGraph | `xml_fbograph/sql_enricher.py` import `tsql_engine` |

→ **Không sửa** `tsql_engine` trừ khi cần sửa grammar/lexer.

---

### 2.2. `sql_object_summary/` — Feature summary proc/func (pure logic)

**Trách nhiệm:** Từ **text definition** (+ metadata catalog optional) → JSON summary / snippet.

**Được phép import:** `tsql_engine` only.

**Không được:**
- `get_connection_config`, `execute_query`, `pyodbc`
- Biết `file_path`, Web.config, MCP

**Public API:**

```python
# sql_object_summary/__init__.py

def analyze_definition(
    definition: str,
    *,
    object_name: str = "dbo.unknown",
    object_type: str = "PROCEDURE",
    catalog_meta: ObjectCatalogMeta | None = None,
    options: AnalyzeOptions | None = None,
) -> SummaryResult:
    """Pure: string in → SummaryResult out."""

def extract_snippet(
    definition: str,
    *,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    max_lines: int = 120,
) -> SnippetResult:
    """Pure: không cần DB."""

def build_call_graph(
    root_name: str,
    definitions: dict[str, str],   # name → definition text, do caller cung cấp
    *,
    max_depth: int = 1,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    truncated_objects: list[str] | None = None,
) -> CallGraphResult:
    """Pure: graph từ dict definitions đã fetch sẵn."""
```

**Cấu trúc folder:**

```
sql_object_summary/
  __init__.py
  models.py                   # SummaryResult, Signals, ParamInfo, Pydantic
  options.py                  # AnalyzeOptions, infra patterns, DEFAULT_EXCLUDE_LIKE
  classifier.py               # infra vs business
  analyze.py                  # orchestrate: parse → visitors → model
  snippet.py                  # keyword/zone extract (có thể dùng line-based, không bắt buộc AST)
  call_graph.py               # build_call_graph(definitions dict)
  visitors/
    summary_visitor.py        # extends TSqlParserVisitor — extract calls/tables/signals
    param_effects.py          # heuristic rules
  formatter.py                # SummaryResult → dict JSON (không format MCP text)
```

**Unit test:** Chỉ cần fixture `.sql` string — **không cần DB**.

---

### 2.3. `queryDatabase/` — DB + bridge mỏng

**Giữ nguyên** `service.py`, `connection.py`, `executor.py`, `query_resolver.py` — **không** nhét ANTLR vào đây.

**Thêm 2 subfolder nhỏ:**

```
queryDatabase/
  ... (existing)
  object_catalog/
    __init__.py
    models.py                 # DbObjectMeta(definition, params, modify_date, ...)
    fetcher.py                # SQL sys.objects / sys.sql_modules / sys.parameters
  bridges/
    __init__.py
    summary_bridge.py         # ĐIỂM NỐI DUY NHẤT feature ↔ DB
    summary_format.py         # format_summary_result() cho MCP
```

#### `object_catalog/fetcher.py`

Trách nhiệm: **I/O SQL Server** — fetch definition, parameters, callers, batch definitions.

```python
class ObjectCatalogFetcher:
    def __init__(self, parsed_conn: dict, query_timeout: int = 10):
        self._parsed = parsed_conn
        self._query_timeout = query_timeout

    def fetch_one(self, name: str, schema: str = "dbo") -> DbObjectMeta | None: ...

    def fetch_parameters(self, object_id: int) -> list[ParameterMeta]: ...

    def fetch_callers(self, object_id: int, schema: str, name: str) -> list[str]: ...

    def fetch_many(self, names: list[tuple[str, str]]) -> dict[str, DbObjectMeta]: ...
```

→ Phần này **tái sử dụng** cho feature khác (vd. sync Graph, diff proc versions).

#### `bridges/summary_bridge.py`

**Toàn bộ wiring** giữa DB và pure logic:

```python
def summary_object(
    *,
    file_path: str,
    object_name: str,
    mode: str = "summary",
    db_type: str = "app",
    schema: str = "dbo",
    max_depth: int = 1,
    max_objects: int = 30,
    **kwargs,
) -> dict:
    # 1. Sanitize & connection
    safe_schema = sanitize_sql_identifier(schema)
    safe_name = sanitize_sql_identifier(object_name)
    conn = get_connection_config(file_path, db_type)
    if not conn.get("success"):
        return conn

    # 2. Thread-safe cache check (LRU 200, TTL 3600s)
    cached = _get_from_cache(conn, safe_schema, safe_name, mode, max_depth)
    if cached:
        return cached

    # 3. Catalog fetch (query timeout 10s)
    fetcher = ObjectCatalogFetcher(conn["parsed"], query_timeout=10)
    meta = fetcher.fetch_one(safe_name, safe_schema)
    if not meta:
        return {"success": False, "error": "object_not_found", "message": f"Không tìm thấy {safe_schema}.{safe_name}"}

    # 4. Pure analyze — KHÔNG DB
    if mode == "full":
        result = _full_response(meta, ...)
    elif mode == "snippet":
        result = extract_snippet(meta.definition, keywords=..., zones=...)
    else:
        result = analyze_definition(
            meta.definition,
            object_name=f"{safe_schema}.{safe_name}",
            object_type=meta.type_desc.strip(),
            catalog_meta=meta.to_catalog_meta(),
            options=AnalyzeOptions(
                max_depth=max_depth,
                expand=expand or [],
                exclude_like=exclude_patterns,
            ),
        )
        if max_depth > 0:
            defs, truncated_list = _collect_definitions(fetcher, result.calls, max_depth, expand, max_objects=max_objects)
            result.call_graph = build_call_graph(..., definitions=defs, truncated_objects=truncated_list)

    # 5. Attach DB metadata & save cache
    final_output = _attach_metadata(result, conn, file_path, meta)
    _set_to_cache(conn, meta, mode, max_depth, final_output)
    return final_output
```

**Export public** từ `queryDatabase/__init__.py`:

```python
from queryDatabase.service import query_database
from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.bridges.summary_format import format_summary_result
```

---

## 3. Lớp MCP — chỉ gọi bridge

`fastbusiness_mcp/mcp_app.py` **không** import `tsql_engine` hay `sql_object_summary` trực tiếp.

```python
from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.bridges.summary_format import format_summary_result

@server.tool(name="summary_object")
def summary_object_tool(...) -> str:
    result = summary_object(file_path=..., object_name=..., mode=...)
    return format_summary_result(result)
```

**Formatter:** `result_to_dict()` nằm `sql_object_summary/formatter.py`; `format_summary_result()` nằm `queryDatabase/bridges/summary_format.py`.

---

## 4. Quy tắc dependency (bắt buộc)

```
fastbusiness_mcp  →  queryDatabase
queryDatabase     →  sql_object_summary, object_catalog (internal)
sql_object_summary →  tsql_engine
tsql_engine       →  antlr4-python3-runtime ONLY
```

| Cấm | Lý do |
|-----|-------|
| `tsql_engine` import `queryDatabase` | Engine phải portable |
| `sql_object_summary` import `pyodbc` | Test pure, reuse offline |
| ANTLR visitor trong `executor.py` | Lẫn I/O và parse |
| Grammar `.g4` trong `sql_object_summary` | Grammar thuộc engine |

**Kiểm tra CI (gợi ý):** script `scripts/check_imports.py` fail nếu vi phạm.

---

## 5. Luồng dữ liệu (sequence)

```
Agent
  │ summary_object(file_path, "zc_bcthlv", mode=summary)
  ▼
mcp_app.summary_object_tool
  ▼
queryDatabase.bridges.summary_bridge.summary_object
  ├─► connection.get_connection_config(file_path)
  ├─► object_catalog.fetcher.fetch_one("zc_bcthlv")
  │       └─► execute_query (existing)
  ├─► sql_object_summary.analyze_definition(definition_text)
  │       └─► tsql_engine.parse(definition_text)
  │               └─► SummaryVisitor walk tree
  ├─► (optional) fetcher.fetch_many(called procs)
  └─► sql_object_summary.build_call_graph(definitions_dict)
  ▼
dict JSON + metadata
  ▼
formatter → markdown string → Agent
```

---

## 6. Tích hợp nhẹ với `query_database` (tool hiện có)

**Không** gộp summary vào `query_type=0` (tránh breaking + lẫn contract).

Hai tool MCP **song song**, dùng chung:

| Shared | Vị trí |
|--------|--------|
| Connection resolve | `queryDatabase.connection` |
| Execute SQL | `queryDatabase.executor` |
| Sanitize tên object | `queryDatabase.query_resolver` |
| Fetch definition | `queryDatabase.object_catalog` (**mới**, dùng chung) |

**Sau này nếu muốn 1 tool:** thêm `query_type=3` trong `queries_config.yaml` chỉ là **alias** gọi `summary_bridge` — implementation vẫn nằm bridge, không trong `resolve_query()`.

```yaml
# queries_config.yaml (phase 2, optional)
types:
  3:
    name: object_summary
    description: Alias → summary_bridge (không parse SQL inline)
```

---

## 7. Cache — đặt ở đâu?

| Cache | Layer | Cơ chế & Key |
|-------|-------|--------------|
| Parse AST | `tsql_engine` | memory dict, key: `sha256(source text)` (optional) |
| Summary JSON | `queryDatabase.bridges` | `threading.Lock` + LRU (~200); key: `(server, db, object_id, modify_date, mode, max_depth)`; TTL 3600s **optional** |

- **Invalidate chính:** `modify_date` thay đổi.
- **Không** cache Summary JSON trong `sql_object_summary`.

---

## 8. Test strategy theo layer

```
tests/
  tsql_engine/
    test_parse_basic.py       # không DB
    test_identifier_dollar.py
  sql_object_summary/
    test_analyze_proc.py      # fixture .sql
    test_snippet.py
    test_call_graph.py
  queryDatabase/
    test_object_catalog.py    # mock execute_query
    test_summary_bridge.py    # mock fetcher + real analyze
  integration/
    test_summary_fbisp242.py  # cần DB thật — optional CI
```

---

## 9. PyInstaller / deploy

Hidden imports:

```
tsql_engine.generated.TSqlLexer
tsql_engine.generated.TSqlParser
tsql_engine.generated.TSqlParserVisitor
sql_object_summary.visitors.summary_visitor
queryDatabase.bridges.summary_bridge
queryDatabase.bridges.summary_format
queryDatabase.object_catalog.fetcher
```

**Không** bundle Java ANTLR — chỉ `generated/`.

---

## 10. Roadmap mở rộng ANTLR4 (ví dụ)

```
tsql_engine          ← grammar + parse (ổn định)
    ├── sql_object_summary     ← proc summary (feature 1)
    ├── tsql_formatter         ← format file .sql (feature 2)
    ├── filter_exec_parser     ← parse exec trong Filter.xml (feature 3)
    └── fbograph_sql_sync      ← edge SQL_PROC_CALL (feature 4)

queryDatabase.object_catalog   ← fetch definition dùng chung mọi feature
queryDatabase.bridges.*        ← mỗi feature 1 file bridge, không phình service.py
```

---

## 11. Anti-patterns (tránh)

| ❌ Sai | ✅ Đúng |
|--------|---------|
| `SummaryVisitor` trong `tsql_engine/visitors/` | `SummaryVisitor` trong `sql_object_summary/visitors/` |
| `executor.py` gọi ANTLR sau mỗi query | Chỉ `summary_bridge` gọi analyze |
| Một file `summary_service.py` 800 dòng (DB+parse+format) | Tách catalog / analyze / bridge / format |
| `sql_object_summary` nhận `file_path` | Nhận `definition: str`; bridge lo path |

---

## 12. Checklist refactor so với doc cũ

- [ ] Đổi tên/vị trí parser: `sql_object_summary/parser/` → **`tsql_engine/`**
- [ ] Logic analyze không còn `definition_loader.py` trong summary — chuyển sang **`object_catalog/fetcher.py`**
- [ ] Entry MCP → **`queryDatabase.bridges.summary_bridge`**
- [ ] Cập nhật `04_antlr4_parser.md` trỏ package `tsql_engine`
- [ ] Cập nhật `06_implementation_checklist.md` theo 3 phase: engine → summary → bridge
