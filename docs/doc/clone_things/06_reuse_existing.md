# 06 — Reuse Existing Modules

## 1. Nguyên tắc

> **Cấm** viết lại SQL tra `sys.objects` / `sp_helptext` / DDL table khi `query_database` type=0 đã làm.
>
> **Cấm** viết parser XML SQL riêng khi `summary_xml` đã có.
>
> `clone_things` = **orchestration** (2 connection + queue + file I/O + open editor).

## 2. Bản đồ reuse

| Nhu cầu | Module / API hiện có | Cách dùng trong clone_things |
|---------|----------------------|------------------------------|
| Resolve DB từ path project | `find_connect_by_path`, `query_database/connection.py` | `file_path=project_source` / `project_target` |
| Phân loại + tồn tại object | `sys.objects` lookup giống `query_database/service.py` + `build_object_lookup_sql` | **CẤM** `ObjectCatalogFetcher.fetch_one` cho table/exists |
| DDL table | `query_database` type=0 (table branch) + ghép `val` / `_extract_script_text` | Không dùng field `definition` |
| Full proc/func/view | `summary_object` mode=`full` | `definition` |
| Dependency proc/func | `summary_object` mode=`summary` | `calls_*`, `tables_read`, `tables_write` (+ lọc `#`/`@`) |
| Seed từ XML | `mcp_read_local_file` / `summary_xml` bridge | `read_option=3` |
| Format lỗi MCP | `format_execution_error` | Exception không kiểm soát |
| Config YAML | loader hiện có của fastbusiness_mcp | Đọc `clone_things.*` |

## 3. Gợi ý API nội bộ (không bắt buộc tên exact)

```text
clone_things/
  __init__.py
  service.py          # clone_things(...) → dict
  queue.py            # normalize, visited, exclude
  sql_temp.py         # createSqlTempFile port
  open_editor.py      # CLI + os.startfile
  response.py         # dict → JSON string
```

`fastbusiness_mcp/mcp_app.py`:

```python
@server.tool(name="clone_things")
def clone_things_tool(...):
    return format_or_json(clone_things_service(...))
```

**Cấm** nhét thuật toán queue vào `mcp_app.py`.

## 4. Cách gọi `query_database` (hợp đồng logic)

### 4.1. Exists check

**CẤM Cách A cũ:** `ObjectCatalogFetcher.fetch_one` — SQL có `JOIN sys.sql_modules`, nên **bảng (`U`) luôn trả `None`** → clone_things sẽ đẩy toàn bộ table vào `not_found_both`. Chỉ dùng `fetch_one` / `summary_object` sau khi đã biết object là P/FN/IF/TF/V.

**Cách bắt buộc:** tra `sys.objects` trực tiếp (reuse logic `query_database` type=0 bước lookup, hoặc `build_object_lookup_sql` + `parse_object_lookup_result`):

```sql
SELECT type, type_desc FROM sys.objects WHERE name = N'{clean_name}'
```

Có hàng → exists + lấy `type` / `type_desc` để phân nhánh fetch.

**Cách B (ổn):** gọi `query_database(..., query_type=0)` và interpret:
- error “Không tìm thấy object trong sys.objects” → not exists
- success + `object_type` / nhánh table hoặc summary → exists

Phải phân biệt:

- Not found
- Permission / connection error → **fail job** (không đẩy vào `not_found_both`)

### 4.2. Fetch script

```text
table   → query_database(file_path=source, query=name, query_type=0)
          → ghép result_sets[0] cột val (reuse query_database.formatter._extract_script_text
             khi resolved_as == "table_schema"; KHÔNG đọc field "definition")
routine → query_database(..., query_type=0, mode="full") → field "definition"
```

### 4.3. Dependencies

```text
query_database(..., query_type=0, mode="summary", max_depth=0 hoặc 1)
```

`clone_things` **tự** loop queue — không dựa vào `call_graph` bung sẵn toàn bộ depth=3 để ghi file (tránh vượt `max_objects` không kiểm soát). Có thể đọc `calls_direct` của **một** object vừa fetch.

## 5. XML summary fields dùng làm seed

Từ JSON summary_xml:

```text
sql.tables[]
sql.procs[]
sql.views[]
controller.db_table   # optional, sau normalize partition token
```

**Limitation hiện tại (phải document trong warning nếu đụng):**

- `read_option=3` chỉ Dir/Grid/Filter trực tiếp dưới Controllers
- Không có `sql.functions` riêng — function có thể lọt vào tables/procs theo heuristic hoặc **bỏ sót**
- `sql.views` là heuristic tên — vẫn đưa vào queue; classify thật khi hit catalog

Khi limitation ảnh hưởng seed → `warnings` ví dụ: `xml_summary_limited_folder_types`.

## 6. Exclude patterns

Reuse default từ `sql_object_summary/options.py` (hoặc import constant — **không** copy-paste lệch). Cho phép override qua config / param `exclude_like`.

## 7. Partition / tên bảng FBO

Tuân thủ workspace rule:

- Không hardcode partition `d91$202501`
- Giữ `$` trong tên partitioned table khi là object thật (`d91$`, …)
- Token runtime `@@prime$partition$current` / `$$partition$current` trong XML **không** phải tên object catalog → normalize trước khi enqueue (xem `03` §4.3) + `warnings` nếu không resolve được

## 8. Anti-patterns (cấm)

1. Agent-side pseudo tool: bảo Agent tự loop `query_database` thay vì implement `clone_things`.
2. Ghi full script vào JSON response.
3. EXECUTE script trên target DB.
4. Dùng relative `project_source` / `project_target`.
5. Tạo sql temp khi folder config trống rồi “im lặng thành công”.
6. Bỏ qua `skipped_exists` trong JSON.
7. Coi `open()` Python là đủ cho “open file”.
8. Fork copy toàn bộ `summary_bridge` vào package mới — import và gọi.
9. Dùng `ObjectCatalogFetcher.fetch_one` để kiểm tra tồn tại **bảng** / exists tổng quát.
10. Append nhiều `CREATE PROCEDURE` chỉ cách dòng trống — **thiếu `GO`**.
