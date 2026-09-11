# 03 — Resolution & Flow

## 1. Tổng quan thuật toán

```
1. Validate params + resolve connections (source, target)
2. Resolve output .sql path (path_to_pasted hoặc create sql temp)
3. Seed queue từ object (sql_name | xml summary)
4. visited = empty set
5. while queue not empty AND processed < max_objects:
     name = dequeue
     key = normalize_object_name(name)  # schema-qualified lowercase key
     skip if key in visited → add visited
     if excluded by exclude_like (dependency only; root seed luôn xử lý) → continue
     if exists_in_target(name):          # sys.objects — KHÔNG dùng fetch_one
         skipped_exists.append(...)
         continue                       # v1: không quét deps của object đã có ở target
     if not exists_in_source(name):
         not_found_both.append(name)   # chỉ accumulate — KHÔNG ghi comment trong loop
         continue
     script, object_type = fetch_full_from_source(name)
     append_script_block(sql_file, script, header)  # blank line + GO (xem §7)
     cloned.append(...)
     deps = extract_dependencies(name, object_type)  # summary / table refs
     enqueue sanitize(deps) not in visited           # bỏ #temp / @var
6. if not_found_both: append ONE summary comment at end of sql_file
7. open_file_for_user(sql_file)  # may warn
8. return JSON
```

## 2. Resolve connection

Reuse `find_connect_by_path` / `get_connection_config`:

- `file_path` giả = `project_source` (và tương tự target)
- `db_type` mặc định `app`

Mỗi lần kiểm tra tồn tại / fetch: gọi pipeline tương đương `query_database(..., file_path=project_*, query=name, query_type=0, ...)`.

**Cấm:** hardcode connection string; đoán server từ tên folder.

## 3. Resolve output file

### 3.1. `path_to_pasted` có giá trị

1. Normalize absolute path.
2. Phải kết thúc `.sql`.
3. Parent directory phải tồn tại.
4. Nếu file chưa tồn tại → tạo file rỗng (UTF-8).
5. Nếu đã tồn tại → mở append mode (sau này mỗi block có blank separator).

### 3.2. `path_to_pasted` rỗng — NewSqlTemp parity

1. Đọc `clone_things.sql_temp_folder` từ `config.yaml`.
2. Trống hoặc folder không tồn tại → error `sql_temp_folder_not_configured` (giống message extension).
3. Tạo file theo convention `createSqlTempFile` (extension JS):

   - `base_name` parity **NewSqlTemp `group.label`**: lấy từ **project_source**
     (2 segment cuối project root, vd. `...\VLOTUS\SP228` → `vlotus_sp228`),
     **không** dùng tên object SQL / stem XML.
   - Normalize: lower, space/`-` → `_`, strip `_`
   - `name.sql` → nếu trùng `name (2).sql`, `name (3).sql`…
4. Ghi initial content rỗng (hoặc header comment clone session).
5. Gán `path_to_pasted` = path vừa tạo (để trả JSON).

Chi tiết config + open: [`05_config_and_sql_temp.md`](./05_config_and_sql_temp.md).

## 4. Seed queue

### 4.1. mode_seed = `sql_name`

```
queue = [normalize_object_name(object)]
```

`normalize_object_name` — **bắt buộc** cho `visited` / dedupe queue (tránh `dbo.zc_helper` ≠ `zc_helper`):

- trim; case-insensitive
- tách `(schema, name)`; nếu thiếu schema → gán `dbo`
- **visited key** chuẩn: `dbo.<name_lower>` (hoặc `schema.lower() + "." + name.lower()`)
- Khi gọi catalog: truyền schema + name đã tách; display trong JSON có thể giữ dạng đã normalize

### 4.2. mode_seed = `xml`

1. Gọi `summary_xml` / `read_local_file(..., read_option=3)` với `file_path=object`, `reference_file` có thể = `object` hoặc `project_source` path hợp lệ.
2. Thu thập (dedupe case-insensitive):

   | Nguồn JSON | Đưa vào queue? |
   |------------|----------------|
   | `sql.procs[]` | Có |
   | `sql.tables[]` | Có |
   | `sql.views[]` | Có |
   | `controller.db_table` | Có nếu non-empty; normalize partition token (xem §4.3) |

3. **Không** enqueue:

   - Temp `#...`, biến `@...` (mọi tên bắt đầu `#` hoặc `@`)
   - `sp_executesql` (system) — đưa vào exclude mặc định hoặc skip list
   - Tên rỗng / signal-only

### 4.3. Normalize `db_table` / partition token (FBO)

Token runtime trong XML **không** phải tên catalog. Giữ `$` của bảng partition template (`d91$`, `c00$`…), bỏ phần biến động.

Gợi ý regex (test với vài `db_table` thật trước khi chốt cứng):

```python
import re

def normalize_fbo_db_table(raw: str) -> str:
    """d91$@@prime$partition$current → d91$; c91$$$partition$current → c91$"""
    s = (raw or "").strip()
    if not s:
        return s
    # Bỏ token runtime @@... / $$... phía sau, giữ optional $ của template
    cleaned = re.sub(r"(\$)?(?:\$\$|@@).+$", r"\1", s).strip()
    return cleaned or s
```

Sau khi có `m41$` / `r00$` (hoặc `m41$202601`), **lookup/clone bắt buộc** map sang bảng cấu trúc `*$000000` (vd. `m41$000000`): target-first rồi source. Không clone từng bảng kỳ `$202601`.

Nếu sau normalize vẫn không lookup được → `warnings` + không đẩy bừa vào `not_found_both` nếu tên rõ là token hỏng.

5. Nếu summary fail (folder không phải Dir/Grid/Filter trực tiếp, encrypted…) → error `xml_summary_failed`. **Không** tự parse raw XML bằng regex riêng trong v1 (tránh 2 nguồn sự thật). Nếu sau này nới folder types — sửa summary_xml trước.

## 5. Kiểm tra tồn tại (target / source)

**CẤM** dùng `ObjectCatalogFetcher.fetch_one` cho exists/table: hàm đó `JOIN sys.sql_modules` — bảng `USER_TABLE` **không** có trong `sys.sql_modules` → luôn “không tồn tại” (xem `06`).

Exists / classify **bắt buộc** qua `sys.objects` (giống `query_database` / `build_object_lookup_sql`).

**Dual DB (app + sys):** mỗi project resolve cả `app` và `sys` từ Web.config (cùng `find_connect_by_path` / `query_database`). Thứ tự mặc định **app → sys**; nếu `db_type=sys` thì **sys → app**.

Thứ tự **bắt buộc** mỗi object:

1. Noise (`tempdb`, `systypes`, `master`…) → `skipped_noise`, không vào `not_found_both`
2. `exists(target app/sys)` → nếu true: `skipped_exists` (+ field `db`), không fetch source, không quét deps
3. Else `exists(source app/sys)` → nếu false: `not_found_both`
4. Else fetch full từ **source** đúng `db` tìm thấy; deploy (nếu bật) vào **target** cùng loại `db`
## 6. Fetch full script

| object_type | Cách lấy (reuse) | Field / hình dạng kết quả |
|-------------|------------------|---------------------------|
| USER_TABLE | `query_database` type=0 (nhánh table) | **Không** có `definition`. Script = ghép cột `val` từ `result_sets[0].rows` (reuse `_extract_script_text` / `resolved_as=table_schema`) |
| PROCEDURE / FUNCTION / VIEW | `query_database` type=0, `mode="full"` | Field `definition` từ `sys.sql_modules` |

Ví dụ ghép DDL table (nếu không gọi helper sẵn có):

```python
rows = result.get("result_sets", [{}])[0].get("rows", [])
# columns có 'val' — ưu tiên index cột val; fallback r[0] nếu schema 1 cột
ddl_script = "".join(str(r[val_idx]) for r in rows if r and r[val_idx])
```

Ghi vào file **nguyên văn** definition/DDL (có thể thêm header comment `-- clone_things: name | type | from source`).

**Không** tự chuyển `CREATE` → `CREATE OR ALTER` trong v1 (suggestion ở `09`).

## 7. Append rule (blank line + `GO`)

Yêu cầu BA:

1. Giữa nội dung cũ và block mới: **một dòng trống** (dễ nhìn).
2. Giữa các batch T-SQL (đặc biệt `CREATE PROCEDURE` / `FUNCTION` / `VIEW`): chèn **`GO`** — bắt buộc v1.

> Trong SQL Server, `CREATE PROCEDURE` / `CREATE FUNCTION` / `CREATE VIEW` phải là statement đầu batch. Chỉ cách dòng trống → SSMS/DBeaver Execute **lỗi hàng loạt**.

Thuật toán append mỗi block script:

```
content = read(sql_file)
if content is not empty and not content.endswith("\n"):
    content += "\n"
if content is not empty:
    if not content.endswith("\n\n"):
        content += "\n"          # 1 dòng trống
    # Nếu block trước chưa kết thúc bằng GO (trừ lần đầu file chỉ có header comment):
    if last_meaningful_line is not "GO":
        content += "GO\n\n"
append header_optional
append script
if not script.endswith("\n"):
    content += "\n"
# Kết thúc batch routine bằng GO (table DDL nhiều statement cũng nên có GO sau block)
content += "GO\n"
write back
```

Separator chuẩn giữa hai object: `\n\nGO\n\n` (hoặc tương đương: blank + `GO` + blank).

### 7.1. Comment `not_found_both` — một dòng cuối file

**Strategy bắt buộc v1:** trong vòng lặp **chỉ** `not_found_both.append(name)` — **không** ghi comment từng object.

Sau khi queue xong, nếu list không rỗng, append **một** dòng:

```sql
-- not found in 2 project: funcA, funcB, procX
```

JSON vẫn giữ `not_found_both` là `string[]`.

## 8. Extract dependencies & enqueue

### 8.1. PROCEDURE / FUNCTION

Gọi summary trên **source** (`mode="summary"`, `max_depth` khuyến nghị `0` hoặc `1` chỉ để lấy direct calls — **clone_things tự quản lý queue**, tránh double-recursion nặng):

Enqueue từ:

- `summary.calls_direct[].name` (và/hoặc `calls_business`)
- `summary.tables_read[]`
- `summary.tables_write[]`

**Sanitize trước enqueue (defense-in-depth):** bỏ mọi tên bắt đầu `#` hoặc `@` (temp / table variable). Path summary chính thường đã tách sang `temp_tables`, nhưng clone_things vẫn phải lọc lại.

Áp dụng `exclude_like` trước khi enqueue.

### 8.2. VIEW

Nếu summary hỗ trợ tables trong view definition → enqueue tables. Nếu không: chỉ clone view script, không bắt buộc bung thêm (ghi `warnings` nếu parse partial).

### 8.3. USER_TABLE

v1: **không** bắt buộc bung FK → bảng khác (suggestion `09`). Chỉ clone DDL bảng đó.

### 8.4. Exclude mặc định

Giống `sql_object_summary/options.py`:

```
^FastBusiness\$
^ff_
^fsd_
```

Thêm khuyến nghị skip: `^sp_`, `^xp_`, `^sys.`, `sp_executesql`.

Object bị exclude khi đang ở hàng đợi dependency → **không** vào `not_found_both` (coi như cố ý bỏ). Nếu chính `object` seed root bị match exclude → vẫn xử lý root (exclude chỉ áp dụng dependency), trừ khi implementer document khác — **BA chốt: root seed luôn xử lý**.

## 9. Visited / cycle / limits

- `visited`: set **normalized key** (`dbo.name` lowercase) — xem §4.1.
- Khi `processed_count >= max_objects`: stop loop; `warnings` thêm `truncated_max_objects`; các object còn trong queue ghi `warnings` hoặc field `truncated_remaining` (optional trong JSON meta).

## 10. Open file for user visibility (BA chốt)

> Python `open(path)` chỉ đọc/ghi trong process — **không** đủ. Phải mở UI.

Sau khi ghi xong:

1. Nếu `open_file=false` → skip.
2. Else theo `clone_things.open_editor_cmd`:

| Value | Hành vi |
|-------|---------|
| `cursor` | `subprocess`: `cursor <abs_path>` (hoặc `cursor -g path`) |
| `code` | `code <abs_path>` |
| `auto` (default khuyến nghị) | thử `cursor`, rồi `code`, rồi fallback |
| `os` | bỏ CLI, dùng ngay `os.startfile` |

3. Fallback Windows: `os.startfile(abs_path)` — mở app mặc định của `.sql`.
4. Mọi lỗi mở editor → `warnings.append("open_file_failed: ...")`, **`success` vẫn true** nếu clone logic OK.

Chi tiết thêm: [`05_config_and_sql_temp.md`](./05_config_and_sql_temp.md).

## 11. Thứ tự object trong file

Không bắt buộc topological sort v1 (proc có thể đứng trước table dependency trong file). Suggestion: optional topo sau. Agent/user chạy script theo thứ tự tự xử lý.

Khuyến nghị nhẹ (không bắt buộc): append **tables trước**, rồi views, rồi functions, rồi procedures — nếu dễ làm với 2-pass queue. Nếu implement 2-pass, ghi rõ trong code comment + test.
