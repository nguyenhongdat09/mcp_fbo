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

## 2. Definition of Done

1. Agent gọi `clone_things` với 2 project path thật → nhận JSON đúng schema.
2. User thấy file `.sql` mở trên editor (hoặc warning rõ nếu CLI thiếu).
3. Object đã có target không bị paste lại; có trong `skipped_exists`.
4. Missing cả hai xuất hiện trong JSON + comment tổng hợp trong file.
5. Không có thao tác DDL execute trên DB target.

## 3. Anti-patterns (nhắc lại)

Xem `06_reuse_existing.md` §8. Đặc biệt:

- Không implement “clone” chỉ bằng hướng dẫn Agent tự làm tay.
- Không bỏ `skipped_exists`.
- Không dùng `open()` như là “đã mở file cho user”.
- Không dùng `ObjectCatalogFetcher.fetch_one` để exists bảng.
- Không quên `GO` giữa các CREATE PROCEDURE/FUNCTION/VIEW.

## 4. Prompt Gemini (copy-paste)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

Nhiệm vụ: implement MCP tool `clone_things` theo đúng bộ spec:
docs/doc/clone_things/ (đọc theo thứ tự README.md).

Yêu cầu cứng:
1. type mặc định 0 (SQL only). object = tên SQL hoặc path .xml (XML chỉ để seed SQL qua summary_xml).
2. project_source + project_target bắt buộc absolute; resolve Web.config bằng module hiện có.
3. Target-first: có ở target → skipped_exists, không lấy source; v1 không quét deps của object đã có ở target.
4. Không có target → lấy full script từ source.
5. Không có cả hai → not_found_both + 1 dòng comment tổng hợp cuối file "-- not found in 2 project: ...".
6. Proc/func: dùng summary để enqueue dependency; loop + visited (normalize dbo.name) + max_objects; exclude FastBusiness$/ff_/fsd_ (root seed vẫn xử lý). Lọc tên bắt đầu # hoặc @.
7. path_to_pasted rỗng → tạo .sql trong clone_things.sql_temp_folder (parity createSqlTempFile); mở file bằng cursor/code (PATH + default LocalAppData *.cmd), Popen non-blocking, fallback os.startfile. open() không đủ. Fail mở → warnings, success vẫn true.
8. Append: 1 dòng trống + chèn GO giữa các block (CREATE PROC/FUNC/VIEW phải đầu batch).
9. Response JSON đúng 04_json_response.md.
10. Tách package clone_things/; mcp_app.py chỉ wire tool. Reuse query_database + summary_xml.

Lưu ý kỹ thuật bắt buộc khi implement:
- Kiểm tra tồn tại (exists) và phân loại object: tra cứu sys.objects trực tiếp (CẤM ObjectCatalogFetcher.fetch_one cho bảng vì sys.sql_modules không chứa Table).
- Lấy script Table: đọc result_sets cột val (reuse _extract_script_text / resolved_as=table_schema), không tìm field "definition".
- Phân cách block: chèn \n\nGO\n\n giữa các block CREATE PROCEDURE / FUNCTION / VIEW.
- Lọc dependency: bỏ qua bảng tạm / biến bắt đầu bằng '#' hoặc '@'.
- Normalize visited key: luôn schema-qualified lowercase (default dbo).

Làm theo checklist Phase A→F trong 08_implementation_checklist.md.
Viết tests theo 07_test_cases.md (ưu tiên P0).
Không deploy/execute DDL lên database target.
Không sửa docs trừ khi phát hiện mâu thuẫn — khi đó ghi chú trong PR.
```

## 5. Smoke manual (sau code)

```text
1. Điền clone_things.sql_temp_folder = thư mục có thật
2. Restart MCP server
3. Gọi clone_things với object proc biết thiếu ở target
4. Xác nhận: file mở, JSON cloned đúng, skipped_exists đúng với bảng chung
5. Gọi với object giả → not_found_both
```
