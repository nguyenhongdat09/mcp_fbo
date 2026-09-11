# 02 — Tool API: `clone_things`

## 1. Đăng ký MCP

- **Tool name:** `clone_things`
- **File wiring:** `fastbusiness_mcp/mcp_app.py` (chỉ signature + doc; logic ở package riêng)
- **Gợi ý package:** `clone_things/` hoặc `cloneThings/` — pure service + thin MCP wrapper (xem `06_reuse_existing.md`, `08_implementation_checklist.md`)

## 2. Parameters

| Param | Type | Required | Default | Mô tả |
|-------|------|----------|---------|--------|
| `type` | `int` | không | `0` | `0` = SQL clone giữa 2 project; `1` = paste-for-edit. Khác → `unsupported_type` |
| `object` | `str` | **có** | — | **type=0:** tên SQL hoặc path `.xml` seed. **type=1:** tên SQL / list **hoặc** path `.xml` seed (lọc bằng `mode_get`) |
| `project_source` | `str` | **có** | — | Absolute path project nguồn (root hoặc file trong project) |
| `project_target` | `str` | type=0: **có**; type=1: không | `""` | Absolute path project đích. **type=1: được rỗng** |
| `path_to_pasted` | `str` | không | `""` | Absolute path file `.sql` để append. Rỗng → tạo sql temp theo config |
| `mode_get` | `str` | không | `"proc"` | **Chỉ type=1.** Lọc kind khi seed XML: `proc`/`func`/`table`/`view`/`full` hoặc list `proc,func`. type=0 bỏ qua. Xem [11](./11_type1_paste_for_edit.md) |
| `mode_recursion` | `str` | không | `"0"` | **Chỉ type=1.** `"0"` = không deps; `"1"` = đệ quy deps như type=0. type=0 bỏ qua |

### 2.1. Tham số nội bộ / optional mở rộng v1 (khuyến nghị có sẵn, default an toàn)

Implementer **được phép** thêm các param optional sau (không bắt buộc Agent truyền), để khớp `query_database`:

| Param | Default | Mục đích |
|-------|---------|----------|
| `schema` | `"dbo"` | Schema mặc định khi object không có prefix |
| `db_type` | `"app"` | `app` \| `sys` — connection app/sys |
| `max_objects` | `50` | Giới hạn số object xử lý trong 1 lần gọi (anti runaway) |
| `exclude_like` | default infra patterns | Regex loại trừ khỏi enqueue dependency |
| `open_file` | `true` | Có mở editor sau khi ghi hay không |

Nếu chưa thêm param MCP, vẫn phải đọc tương đương từ `config.yaml` + hard default trong code.

## 3. Phân loại `object`

### type=0

```
object.strip()
  → ends with .xml (case-insensitive) OR path tồn tại là file .xml
       → mode_seed = "xml"
  → else
       → mode_seed = "sql_name"
```

**Lưu ý:** Với `type=0`, XML **không** bị clone như file; chỉ dùng để **seed** danh sách SQL object.

### type=1

```
object.strip()
  → .xml → mode_seed = "xml" → summary_xml → lọc theo mode_get
  → else → mode_seed = "sql_name" → parse list tên (mode_get không lọc list)
```

Chi tiết `mode_get` / `mode_recursion`: [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md).

## 4. Validation (fail-fast)

Trả lỗi dạng chuẩn MCP (string hoặc JSON error — thống nhất với `format_execution_error` hiện có). Bảng mã:

| Điều kiện | `error_code` | Message gợi ý |
|-----------|--------------|---------------|
| Thiếu `object` / rỗng | `invalid_object` | object is required |
| Thiếu `project_source` | `invalid_project_source` | project_source is required |
| Thiếu `project_target` khi **type=0** | `invalid_project_target` | project_target is required |
| `project_target` rỗng khi **type=1** | *(không lỗi)* | bỏ qua target |
| `type` ∉ `{0, 1}` | `unsupported_type` | type={n} not implemented; only type=0\|1 |
| type=1 `mode_get` không còn kind hợp lệ | `invalid_mode_get` | |
| type=1 `mode_recursion` ∉ {0,1} | `invalid_mode_recursion` | |
| Không resolve được Web.config source | `invalid_project_source` | cannot resolve connection from project_source |
| Không resolve được Web.config target (type=0) | `invalid_project_target` | cannot resolve connection from project_target |
| `path_to_pasted` có giá trị nhưng parent folder không tồn tại | `invalid_path_to_pasted` | parent directory does not exist |
| `path_to_pasted` trỏ tới path không phải `.sql` | `invalid_path_to_pasted` | path_to_pasted must be a .sql file |
| `path_to_pasted` rỗng và `sql_temp_folder` trống / không tồn tại | `sql_temp_folder_not_configured` | giống NewSqlTemp: chưa cấu hình thư mục |
| XML seed (type=0 hoặc type=1) nhưng file không tồn tại | `xml_not_found` | XML path not found |
| XML seed nhưng không summary được | `xml_summary_failed` | kèm lý do; **không** fallback silent sang raw full XML |

### 4.1. Path bắt buộc absolute cho project_*

- `project_source` / `project_target`: **bắt buộc absolute** (giống tinh thần `reference_file` FBOGraph).
- Relative → `invalid_project_source` / `invalid_project_target` với message rõ.
- Cho phép truyền path file bên trong project (ví dụ `...\Dir\SVTran.xml`) — resolver đi lên `Web.config` / cắt trước `App_Data`.

## 5. Signature gợi ý (Python / MCP)

```python
@server.tool(name="clone_things")
def clone_things_tool(
    object: Annotated[str, Field(description="type=0/1: tên SQL hoặc path .xml seed; type=1 cũng nhận list tên")],
    project_source: Annotated[str, Field(description="Absolute path project nguồn (hoặc file trong project)")],
    project_target: Annotated[str, Field(description="Absolute path project đích; type=1 được rỗng")] = "",
    type: Annotated[int, Field(default=0, description="0=clone 2 project; 1=paste-for-edit")] = 0,
    path_to_pasted: Annotated[
        str,
        Field(default="", description="File .sql để append; rỗng = tạo sql temp + mở editor"),
    ] = "",
    mode_get: Annotated[
        str,
        Field(default="proc", description="type=1 only: lọc kind seed XML — proc|func|table|view|full hoặc list"),
    ] = "proc",
    mode_recursion: Annotated[
        str,
        Field(default="0", description="type=1 only: 0=không deps; 1=đệ quy deps như type=0"),
    ] = "0",
) -> str:
    ...
```

Return: **JSON string** đúng schema `04_json_response.md` (nhánh type=0 hoặc type=1). Khi exception không kiểm soát → `format_execution_error("clone_things", e)`.

## 6. Side effects (phải document trong tool description)

1. **Ghi / tạo file** trên đĩa (`path_to_pasted` hoặc sql temp).
2. **Mở editor** (subprocess / `os.startfile`) nếu `open_file` hiệu lực.
3. **Đọc** catalog + definition từ SQL Server (type=0: source+target; type=1: chỉ source) — **không** INSERT/UPDATE/DROP.
4. **type=1:** không deploy dù config `execute_clone=true`.

Tool description MCP phải nêu rõ hai mode và: script nằm trong file, không trả full SQL trong JSON.

## 7. Idempotency

- **type=0:** Gọi lại cùng `path_to_pasted` → **append thêm** (có blank line), không truncate file cũ. Object đã có trong `visited` trong **một** lần gọi → không xử lý lại.
- **type=1:** Gọi lại cùng object đã có `CREATE`/`ALTER` trong file → `skipped_already_in_file`, **không** paste trùng.
- `path_to_pasted=""` → tạo file **mới** (tên tăng `(2)`, `(3)`…) — parity `createSqlTempFile`.

## 8. Quyền / an toàn

- Không log password connection.
- Không ghi connection string vào file `.sql`.
- Header comment trong `.sql` chỉ chứa: tên object, object_type, nguồn, mode (clone vs paste-edit); timestamp optional.
