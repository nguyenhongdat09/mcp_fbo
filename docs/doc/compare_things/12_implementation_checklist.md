# 12 — Implementation Checklist + Prompt Gemini

## 1. Vai trò

- **Docs đã đủ** trong `docs/doc/compare_things/` — implementer (Gemini) code theo checklist này.
- Agent viết doc **không** scaffold `.py` thay Gemini trừ khi user đổi yêu cầu.

## 2. Phase implement (bắt buộc tuần tự)

### Phase P0 — Skeleton + `kind=file`

- [ ] Tạo package `compare_things/` đúng cây [03_architecture.md](./03_architecture.md)
- [ ] `text_normalize.py`, `meta_stat.py`, `models.py`, `formatter.py`
- [ ] `file_compare.py` + tests TC-FILE-01..06
- [ ] `service.py` validate + route `file`
- [ ] Wire `@server.tool(name="compare_things")` trong `fastbusiness_mcp/mcp_app.py`
- [ ] JSON hunks line_start/end + next_actions theo [04](./04_json_response.md)

### Phase P0b — `kind=folder`

- [ ] `folder_compare.py`
- [ ] missing / different_meta / truncate / glob
- [ ] `compare_content` default false
- [ ] Tests TC-FOLDER-01..05
- [ ] (Optional) smoke UNC LIVE

### Phase P1 — `kind=sql`

- [ ] `db_access.py` wrap `clone_things.db_ops`
- [ ] `sql_seed_scan.py`, `sql_fingerprint.py`, `sql_compare.py`
- [ ] encrypted_skip; hunks source_/target_; signals
- [ ] Tests TC-SQL-01..05 (+ LIVE 07 nếu có env)

### Phase P2 — `kind=xml`

- [ ] `xml_compare.py` resolve Controllers path + gọi file engine
- [ ] Tests TC-XML-*

### Phase P3 — `kind=table`

- [ ] `table_schema.py` fingerprint **sort theo tên cột** (cấm ordinal)
- [ ] `table_compare.py` + `schema_diff`
- [ ] Tests TC-TABLE-01..06 đặc biệt **K,L vs L,K = identical**

### Phase Polish

- [ ] Chạy full P0 matrix [11](./11_test_cases.md)
- [ ] Seed scan đúng SQL `sys.sql_modules` LIKE (07 §3.3); db_type=both conflict = exists cả app+sys cùng phía
- [ ] XML resolve qua `get_project_root_from_path` + `resolve_controllers_dir` (08)
- [ ] only_line_ending_diff = identical_content ∧ sha256_raw khác (05)
- [ ] Folder compare_content text → content.hunks bắt buộc (06 + 04 §5.4.1)

## 3. Definition of Done

1. Agent gọi đủ 5 kind (trên fixture hoặc LIVE) → JSON đúng schema `04`.
2. File/proc different → nêu được “lệch dòng X–Y” từ hunks.
3. CRLF-only → only_line_ending_diff.
4. Table đảo cột → identical.
5. Folder báo missing + khác size/ngày.
6. Không ghi file SQL, không ALTER, không copy DLL.
7. Encrypted → encrypted_skip.
8. Architecture tách file — không một service monolith.

## 4. Anti-patterns

Xem [10_reuse_existing.md](./10_reuse_existing.md) §3. Nhắc lại: không dump full body; không so CREATE TABLE raw; không hash hết bin mặc định.

## 5. Prompt Gemini (copy-paste)

```text
Bạn đang implement MCP tool `compare_things` trong repo FastBusiness MCP:
E:\PythonProject\mcp_fbo\

ĐỌC VÀ LÀM ĐÚNG TOÀN BỘ:
docs/doc/compare_things/README.md
docs/doc/compare_things/01_overview.md
docs/doc/compare_things/02_tool_api.md
docs/doc/compare_things/03_architecture.md
docs/doc/compare_things/04_json_response.md
docs/doc/compare_things/05_kind_file.md
docs/doc/compare_things/06_kind_folder.md
docs/doc/compare_things/07_kind_sql.md
docs/doc/compare_things/08_kind_xml.md
docs/doc/compare_things/09_kind_table.md
docs/doc/compare_things/10_reuse_existing.md
docs/doc/compare_things/11_test_cases.md
docs/doc/compare_things/12_implementation_checklist.md

YÊU CẦU BẮT BUỘC:
1. Tạo package compare_things/ TÁCH FILE đúng 03_architecture.md (service mỏng; mỗi kind một file; helpers riêng).
2. Đăng ký tool compare_things trong fastbusiness_mcp/mcp_app.py — không nhét logic vào mcp_app.
3. JSON agent-actionable: khi file/sql/xml khác nội dung phải có hunks với line_start/line_end; có next_actions + message; CẤM chỉ trả different=true; CẤM dump full proc/XML mặc định.
4. ignore_line_endings default true; only_line_ending_diff khi chỉ khác CRLF/LF.
5. kind=folder: so missing + size/created/modified; compare_content default false (bin UNC).
6. kind=table: schema ngữ nghĩa — cột K,L vs L,K cùng type = identical; different chỉ type/cột thiếu/PK/index/trigger; dùng catalog không so raw CREATE TABLE.
7. kind=sql: reuse clone_things.db_ops qua db_access.py; encrypted_skip; seed scan; signals FBO (dmduyet vs vdmduyetuq).
8. Tests tests/compare_things/ theo 11_test_cases.md P0.
9. Không auto clone/ALTER/deploy/copy file. Không tạo tool compare_files riêng.
10. Implement theo phase P0 → P0b → P1 → P2 → P3 trong checklist này.

Bắt đầu Phase P0 và báo cáo file đã tạo + test pass.
```

## 6. Gợi ý cập nhật `.cursorrules` (sau khi code xong)

Thêm mục MCP tools:

- `compare_things` — so sql/table/xml/file/folder giữa 2 project hoặc 2 path; gọi **trước** `clone_things` khi chỉ cần biết lệch/thiếu.
