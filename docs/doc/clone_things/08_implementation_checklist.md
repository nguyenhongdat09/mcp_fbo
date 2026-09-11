# 08 — Implementation Checklist + Prompt Gemini

## 1. Thứ tự implement (bắt buộc tuần tự)

### Phase A — Skeleton

- [ ] Tạo package `clone_things/` (service tách khỏi `mcp_app.py`)
- [ ] Thêm block `clone_things` vào `config.yaml` + loader đọc được
- [ ] Đăng ký `@server.tool(name="clone_things")` với params đúng `02_tool_api.md`
- [ ] Trả JSON stub `success=false, error_code=not_implemented` tạm — rồi thay bằng logic thật

### Phase B — File I/O & open

- [ ] Port `createSqlTempFile` → `sql_temp.py`
- [ ] Append: blank line + **`GO`** giữa các block CREATE (SSMS-valid)
- [ ] `open_editor.py`: auto → cursor (PATH + default LocalAppData path) → code → `os.startfile`; **Popen** non-blocking; soft-fail warnings
- [ ] Unit tests TC-FILE-* / append / GO

### Phase C — Dual connection + target-first

- [ ] Resolve source/target via existing connection helpers
- [ ] Exists qua **sys.objects** (CẤM `fetch_one` cho table); fetch table = ghép `val`; routine = `definition`
- [ ] `skipped_exists` / `cloned` / `not_found_both` (comment tổng hợp cuối file)
- [ ] Tests TC-CORE-*

### Phase D — Dependency queue

- [ ] Summary deps enqueue + exclude + visited + max_objects
- [ ] Tests TC-DEP-*

### Phase E — XML seed

- [ ] Gọi summary_xml / read_option=3
- [ ] Map fields → queue
- [ ] Tests TC-XML-*

### Phase F — Polish

- [ ] README tool trong root `README.md` (một dòng bảng MCP tools)
- [ ] Docstring MCP tiếng Việt rõ side effects
- [ ] Chạy full acceptance `07` P0
- [ ] Không commit secrets / connection string

### Phase G — type=1 paste-for-edit

Spec: [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md).

- [x] Branch `type==1` trong service + MCP description (`0=clone`, `1=paste-for-edit`)
- [x] `project_target` optional; XML-as-object → `invalid_object`
- [x] `parse_object_list` + `transform_create_to_alter` + `object_already_in_sql_file`
- [x] Append trả `line_start`/`line_end`; USE sections từ **source** DB names
- [x] Force `execute_clone=False`; JSON `pasted` / `skipped_already_in_file` / `not_found_source` / `agent_message`
- [x] **Cấm** full SQL trong JSON; **cấm** deploy
- [x] Tests `tests/clone_things/test_type1_paste_for_edit.py` (TC-T1-*)
- [x] Không regress type=0
- [ ] *(Sau code)* Cập nhật `.cursorrules` / skill `fbo-clone-things` — agent habit type=1

## 2. Definition of Done

1. Agent gọi `clone_things` type=0 với 2 project path thật → nhận JSON đúng schema.
2. User thấy file `.sql` mở trên editor (hoặc warning rõ nếu CLI thiếu).
3. Object đã có target không bị paste lại; có trong `skipped_exists`.
4. Missing cả hai xuất hiện trong JSON + comment tổng hợp trong file.
5. Không có thao tác DDL execute trên DB target (type=0 theo config; type=1 luôn không).
6. type=1: paste ALTER + line range + dedup; AC-T1-* pass.

## 3. Anti-patterns (nhắc lại)

Xem `06_reuse_existing.md` §8. Đặc biệt:

- Không implement “clone” chỉ bằng hướng dẫn Agent tự làm tay.
- Không bỏ `skipped_exists` (type=0).
- Không dùng `open()` như là “đã mở file cho user”.
- Không dùng `ObjectCatalogFetcher.fetch_one` để exists bảng.
- Không quên `GO` giữa các CREATE/ALTER PROCEDURE/FUNCTION/VIEW.
- **type=1:** không trả full definition trong JSON; không execute; không dùng type=1 cho clone XML Controllers.

## 4. Prompt Gemini — type=0 (đã có / regression)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

Nhiệm vụ: maintain/regression clone_things type=0 theo docs/doc/clone_things/.

Yêu cầu cứng type=0:
1. type mặc định 0. object = tên SQL hoặc path .xml (XML chỉ seed).
2. project_source + project_target bắt buộc absolute.
3. Target-first + deps + not_found_both + GO + USE target DB names.
4. Không phá khi thêm type=1.
```

## 4b. Prompt Gemini — type=1 (copy-paste)

Xem prompt đầy đủ ở [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md) §14. Tóm tắt:

```text
Implement clone_things type=1 theo docs/doc/clone_things/11_type1_paste_for_edit.md.
Paste-for-edit: project_target rỗng OK; object = SQL name/list; CREATE→ALTER;
dedup file; line_start/line_end; execute_clone=false; không full SQL trong JSON;
USE theo source DB; tests TC-T1-*. Không regress type=0.
```

## 5. Smoke manual (sau code)

```text
type=0:
1. Điền clone_things.sql_temp_folder = thư mục có thật
2. Restart MCP server
3. Gọi clone_things type=0 với object proc biết thiếu ở target
4. Xác nhận: file mở, JSON cloned đúng, skipped_exists đúng

type=1:
5. Gọi type=1 object=proc thật, project_target="", path_to_pasted có sẵn hoặc ""
6. Xác nhận: ALTER trong file, pasted[].line_*, agent_message; gọi lại → skipped_already_in_file
7. F5 thủ công — tool không tự execute
```
