# 05 — Tích hợp: bridge mỏng trong `queryDatabase`

> **Đọc trước:** [07_architecture_layers.md](./07_architecture_layers.md)  
> **Nguyên tắc:** ANTLR nằm `tsql_engine/`, logic summary nằm `sql_object_summary/`, `queryDatabase` chỉ **fetch DB + bridge**.

---

## 1. Cấu trúc file (phiên bản tách lớp)

```
E:\PythonProject\mcp_fbo\
  tsql_engine/                      # Lớp ANTLR — portable
    __init__.py                     # parse()
    engine.py
    preprocess.py
    errors.py
    grammar/ + generated/
    tools/generate.bat

  sql_object_summary/               # Lớp nghiệp vụ — pure
    __init__.py                     # analyze_definition(), extract_snippet()
    models.py
    options.py
    analyze.py
    snippet.py
    call_graph.py
    classifier.py
    visitors/
      summary_visitor.py
    formatter.py                    # result_to_dict() — JSON thuần, không MCP markdown

  queryDatabase/                    # Lớp DB — existing + mỏng
    service.py
    connection.py
    executor.py
    query_resolver.py
    object_catalog/
      __init__.py
      models.py
      fetcher.py
    bridges/
      __init__.py
      summary_bridge.py             # summary_object() orchestration
      summary_format.py             # format_summary_result() — markdown MCP

  fastbusiness_mcp/
    mcp_app.py                      # summary_object_tool → gọi bridge only

  tests/
    tsql_engine/
    sql_object_summary/
    queryDatabase/
```

---

## 2. `queryDatabase/object_catalog/fetcher.py`

Tách **toàn bộ** đọc DB ra khỏi `sql_object_summary` (doc cũ `definition_loader.py` → chuyển vào đây).

```python
@dataclass
class DbObjectMeta:
    schema_name: str
    name: str
    object_id: int
    type_desc: str
    definition: str
    modify_date: datetime
    parameters: list[ParameterMeta]

class ObjectCatalogFetcher:
    def __init__(self, parsed_conn: dict, query_timeout: int = 10):
        self._parsed = parsed_conn
        self._query_timeout = query_timeout

    def fetch_one(self, name: str, schema: str = "dbo") -> DbObjectMeta | None:
        """sys.sql_modules + sys.parameters (Parameterized query, sanitize identifier)"""

    def fetch_many(self, keys: list[tuple[str, str]]) -> dict[str, DbObjectMeta]:
        """Batch cho call graph — 1 round-trip (timeout 15s)"""

    def fetch_callers(self, object_id: int, schema: str, name: str) -> list[str]:
        """include_called_by — primary sys.sql_expression_dependencies (theo object_id)"""
```

SQL templates đặt tại:

```
queryDatabase/object_catalog/queries/
  fetch_object.sql
  fetch_parameters.sql
  fetch_objects_batch.sql
  fetch_callers.sql           # sys.sql_expression_dependencies (inbound)
```

Bảo mật & tái sử dụng:

```python
from queryDatabase.connection import get_connection_config
from queryDatabase.executor import execute_query
from queryDatabase.query_resolver import sanitize_sql_identifier

# BẮT BUỘC sanitize trước khi query (pattern giống query_resolver.py):
safe_schema = sanitize_sql_identifier(schema)
safe_name = sanitize_sql_identifier(name)
# v1: SQL catalog có thể dùng N'{safe_name}' sau sanitize; phase 2 thêm execute_query params
```

**Timeout fetch:** `ObjectCatalogFetcher` đo `time.perf_counter()` mỗi lần gọi `execute_query`; vượt `query_timeout` → raise/return warning. Connection timeout 30s do `executor.py` (`pyodbc.connect(..., timeout=30)`).

---

## 3. `queryDatabase/bridges/summary_bridge.py`

**Điểm nối duy nhất** giữa DB và pure analyze — trả `dict` JSON (đã qua `sql_object_summary.formatter.result_to_dict`).

File **`summary_format.py`** (cùng folder `bridges/`) chứa `format_summary_result()` — bọc dict thành markdown MCP.

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
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    include_called_by: bool = False,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    max_snippet_lines: int = 120,
    max_full_chars: int = 50000,
    use_cache: bool = True,
) -> dict:
    ...
```

Helper `resolve_object_ref(object_name, schema)` — xem `02_tool_api.md` §2.1.

### Flow (không lẫn parse vào executor)

```python
DEFAULT_EXCLUDE_LIKE = [r"^FastBusiness\$", r"^ff_", r"^fsd_"]

def summary_object(...):
    # 1. Resolve schema + name, sanitize
    safe_schema, safe_name = resolve_object_ref(object_name, schema)
    exclude_patterns = exclude_like if exclude_like is not None else DEFAULT_EXCLUDE_LIKE

    # 2. Connection config
    conn = get_connection_config(file_path, db_type)
    if not conn.get("success"):
        return conn

    # 3. Snippet validation (trước fetch DB)
    if mode == "snippet" and not (keywords or zones):
        return {
            "success": False,
            "error": "snippet_params_required",
            "message": "mode=snippet cần keywords hoặc zones",
        }

    # 4. Cache check (Thread-safe LRU + TTL)
    if use_cache:
        cached = _get_from_cache(conn, safe_schema, safe_name, mode, max_depth)
        if cached:
            return cached

    fetcher = ObjectCatalogFetcher(conn["parsed"], query_timeout=10)
    meta = fetcher.fetch_one(safe_name, safe_schema)
    if not meta:
        return {"success": False, "error": "object_not_found", "message": f"Không tìm thấy {safe_schema}.{safe_name}"}

    if map_object_type(meta.type) is None:  # TR, U, ...
        return {"success": False, "error": "unsupported_type", "message": meta.type_desc}

    if mode == "full":
        return _wrap_full(meta, conn, file_path, max_full_chars)

    if mode == "snippet":
        pure = extract_snippet(meta.definition, keywords=keywords, zones=zones, max_lines=max_snippet_lines)
    else:
        pure = analyze_definition(
            meta.definition,
            object_name=f"{meta.schema_name}.{meta.name}",
            object_type=map_object_type(meta.type),
            catalog_meta=meta,
            options=AnalyzeOptions(
                max_depth=max_depth,
                expand=expand or [],
                exclude_like=exclude_patterns,
            ),
        )
        if max_depth > 0 and pure.calls:
            # Thu thập child definitions có kiểm soát giới hạn max_objects
            child_defs, truncated_list = _fetch_child_definitions(
                fetcher, pure, max_depth, expand, exclude_patterns, max_objects=max_objects
            )
            pure.call_graph = build_call_graph(
                f"{meta.schema_name}.{meta.name}",
                child_defs,
                max_depth=max_depth,
                expand=expand,
                exclude_like=exclude_patterns,
                truncated_objects=truncated_list,
            )

    if include_called_by:
        try:
            pure.called_by = fetcher.fetch_callers(meta.object_id, safe_schema, safe_name)
        except Exception as e:
            pure.warnings.append(f"Không thể truy vấn callers: {str(e)}")

    result = _attach_db_metadata(pure, conn, file_path, meta)
    
    if use_cache:
        _set_to_cache(conn, meta, mode, result)

    return result
```

### Export

```python
# queryDatabase/__init__.py
from queryDatabase.service import query_database
from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.bridges.summary_format import format_summary_result
```

---

## 4. MCP — không import ANTLR

```python
# fastbusiness_mcp/mcp_app.py
from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.bridges.summary_format import format_summary_result

@server.tool(name="summary_object")
def summary_object_tool(...) -> str:
    try:
        result = summary_object(file_path=..., object_name=..., mode=..., ...)
        return format_summary_result(result)
    except Exception as e:
        return format_execution_error("summary_object", e)
```

**Cấm** trong `mcp_app.py`:

```python
from tsql_engine import ...                   # ❌
from sql_object_summary.visitors import ...   # ❌
```

---

## 5. Quan hệ với `query_database` (tool cũ)

| Nhu cầu | Tool / module |
|---------|----------------|
| Schema bảng | `query_database type=0` |
| Chạy EXEC test | `query_database type=1` |
| Script deploy `.sql` | `query_database type=2` |
| Summary / snippet proc | `summary_object` → `summary_bridge` |
| Fetch definition (nội bộ) | `object_catalog.fetcher` — **dùng chung** feature sau |

**Không** nhét summary vào `resolve_query()` / `executor.py`.

---

## 6. Cache Thread-safe & Chính sách Eviction

| Layer | File | Cơ chế | Key |
|-------|------|--------|-----|
| Summary response | `queryDatabase/bridges/summary_bridge.py` | `threading.Lock` + `OrderedDict` (LRU 200, TTL 3600s optional) | `(server, db, object_id, modify_date, mode, max_depth)` |

- **Invalidate chính:** `modify_date` đổi sau ALTER object → cache miss.
- **TTL 3600s (optional v1):** Bảo vệ stale khi metadata catalog chậm cập nhật — có thể bật sau MVP.

---

## 7. Config (`config.yaml` — optional)

```yaml
summary_object:
  default_max_depth: 1
  max_objects_per_request: 30
  query_timeout_seconds: 10
  batch_timeout_seconds: 15
  request_timeout_seconds: 30
  cache:
    max_entries: 200
    ttl_seconds: 3600
  infra_patterns:
    - "^FastBusiness\\$"
    - "^ff_"
    - "^fsd_"
  # exclude_like mặc định = infra_patterns (override qua tham số tool)
```

Bridge đọc qua `get_config()`; `sql_object_summary.options` nhận config đã parse (pure dict).

---

## 8. PyInstaller

Hidden imports:

```
tsql_engine.generated.*
sql_object_summary.visitors.summary_visitor
queryDatabase.bridges.summary_bridge
queryDatabase.bridges.summary_format
queryDatabase.object_catalog.fetcher
```

---

## 9. Phase 2 (không làm v1)

- `queryDatabase/bridges/graph_sync_bridge.py` — sync proc vào Kùzu
- `tsql_formatter/` — feature mới, cùng pattern bridge
- `query_type=3` alias
