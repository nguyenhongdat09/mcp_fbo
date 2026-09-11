# 02 — Tool API: `compare_things`

## 1. Đăng ký MCP

- **Tool name:** `compare_things`
- **Wiring:** `fastbusiness_mcp/mcp_app.py` — chỉ signature + docstring; logic ở package `compare_things/`
- **Formatter:** `compare_things.formatter.format_compare_result` → `json.dumps(..., ensure_ascii=False, indent=2)`
- **Lỗi:** thống nhất `format_execution_error` / validation message tiếng Việt như tool khác

## 2. Parameters

| Param | Type | Required | Default | Mô tả |
|-------|------|----------|---------|--------|
| `kind` | `str` | **có** | — | `sql` \| `table` \| `xml` \| `file` \| `folder` |
| `project_source` | `str` | trừ `file`/`folder` | `""` | Abs path project nguồn (root hoặc file trong project có Web.config) |
| `project_target` | `str` | trừ `file`/`folder` | `""` | Abs path project đích |
| `object` | `str` | tùy kind | `""` | Tên SQL / list `a,b` / relative XML path (list `,` hoặc `;`) |
| `seed` | `str` | không | `""` | Chỉ `kind=sql`: keyword scan khi `object` rỗng — vd `dmuqduyet,vdmduyetuq` |
| `db_type` | `str` | không | `"app"` | `app` \| `sys` \| `both` |
| `mode` | `str` | không | `"summary"` | `summary` \| `hunks` \| `body` |
| `file_a` / `file_b` | `str` | `kind=file` | `""` | Absolute path 2 file |
| `folder_a` / `folder_b` | `str` | `kind=folder` | `""` | Absolute/UNC path 2 thư mục |
| `ignore_line_endings` | `bool` | không | `true` | Chuẩn hóa CRLF/LF trước so text (file/xml/sql definition) |
| `ignore_whitespace` | `bool` | không | `false` | Strip khoảng trắng đầu/cuối mỗi dòng khi so |
| `max_diff_lines` | `int` | không | `200` | Truncate unified_diff / preview dài |
| `max_objects` | `int` | không | `50` (sql/table/xml) / `200` (folder) | Giới hạn số entry chi tiết / quét |
| `recursive` | `bool` | không | `true` | Chỉ `folder` |
| `compare_content` | `bool` | không | `false` | Chỉ `folder` (và ảnh hưởng hash); default tắt cho `bin` |
| `hash_max_bytes` | `int` | không | `1048576` | Chỉ hash file ≤ ngưỡng khi `compare_content` |
| `include_glob` | `str` | không | `"*"` | Folder: pattern `,`-separated |
| `exclude_glob` | `str` | không | `""` | Folder: loại trừ |
| `name_compare` | `str` | không | `"case_insensitive"` | Folder: so relative path |
| `meta_tolerance_seconds` | `int` | không | `0` | Folder: dung sai mtime/ctime |
| `context_lines` | `int` | không | `3` | Số dòng ngữ cảnh quanh hunk (`difflib`) — áp dụng **file / xml / sql** text diff và folder khi `compare_content` + text |
| `schema` | `str` | không | `"dbo"` | Schema mặc định khi object không có prefix — **chỉ `kind=sql` và `kind=table`**; bỏ qua với file/folder/xml |

### 2.1. `mode` — độ chi tiết trả về

| `mode` | Bắt buộc có | Thêm |
|--------|-------------|------|
| `summary` (default) | `summary`, `compared[]` status, **hunks với line_start/line_end**, preview ngắn (≤ ~5 dòng/hunk), signals/schema_diff/meta_diff, `next_actions`, `message` | Không bắt buộc full `unified_diff` |
| `hunks` | Như summary | `unified_diff` (truncate `max_diff_lines`), preview dài hơn |
| `body` | Như hunks | Thêm `body_a`/`body_b` (hoặc source/target) **cửa sổ quanh hunk** — sample [04](./04_json_response.md) §5.6; **CẤM** full proc/file |

**CẤM:** `mode=summary` mà chỉ `"status":"different"` không có hunk ranges (với file/sql/xml/folder-text khác nội dung).

## 3. Validation theo `kind` (fail-fast)

| Điều kiện | `error_code` |
|-----------|--------------|
| `kind` không thuộc enum | `invalid_kind` |
| `mode` ∉ summary/hunks/body | `invalid_mode` |
| `kind` ∈ sql/table/xml và thiếu `project_source` hoặc `project_target` | `invalid_project_source` / `invalid_project_target` |
| Không resolve Web.config | cùng mã project |
| `kind=file` thiếu `file_a`/`file_b` hoặc path không tồn tại | `invalid_file_a` / `invalid_file_b` / `file_not_found` |
| `kind=folder` thiếu folder hoặc không phải directory | `invalid_folder_a` / `invalid_folder_b` / `folder_not_found` |
| `kind=sql` và `object` rỗng và `seed` rỗng | `invalid_object_or_seed` |
| `kind=table`/`xml` và `object` rỗng | `invalid_object` |
| `db_type` ∉ app/sys/both | `invalid_db_type` |
| `max_objects` / `max_diff_lines` ≤ 0 | `invalid_limit` |
| Không resolve được Controllers (`kind=xml`) | `controllers_not_found` |

Path project / file / folder: **khuyến nghị absolute** (UNC OK). Relative: reject hoặc resolve theo cwd — **chốt: require absolute** (giống spirit `reference_file` FBOGraph) để agent không nhầm project.

## 4. Phân loại `object` / `seed`

### `kind=sql`

```
object không rỗng → parse list tên (split , ; whitespace) → so từng object
object rỗng + seed → seed_scan(keywords) trên source (và/hoặc target) → candidate list ≤ max_objects
```

### `kind=table`

Parse list tên bảng (có/không `dbo.`).

### `kind=xml`

Parse list relative path (vd `Dir/Foo.xml`, `Filter/Bar.xml`). Normalize `\` → `/`. Map vào Controllers root từng project (xem `08_kind_xml.md`).

### `kind=file` / `folder`

Không dùng `object`; dùng `file_*` / `folder_*`.

## 5. Docstring MCP (gợi ý tiếng Việt)

Nhấn mạnh:

- So lệch giữa 2 project / 2 file / 2 folder — **không** ghi `.sql`, **không** deploy
- Khi khác nội dung text: JSON có **khoảng dòng** để agent biết sửa chỗ nào
- So 2 project trước khi clone: gọi `compare_things` rồi mới `clone_things` nếu cần
- Folder `bin`: mặc định chỉ meta + missing

## 6. Side effects

| Side effect | Có? |
|-------------|-----|
| Đọc DB source/target | Có (`sql`/`table`) |
| Đọc file/folder disk/UNC | Có |
| Ghi file / ALTER / EXECUTE | **Không** |
| Mở editor | **Không** |
