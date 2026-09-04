# 07 — Test Cases (BA / QA)

## 1. Quy ước

| Cột | Ý nghĩa |
|-----|---------|
| **ID** | Mã test |
| **Priority** | P0 = bắt buộc trước merge; P1 = nên có; P2 = nice |
| **Type** | Unit / Integration / Manual |
| **Expected** | Kết quả quan sát được |

Fixture khuyến nghị: mock catalog fetcher + temp dirs — không bắt buộc SQL Server thật cho mọi case; P0 integration cần ít nhất 1 case live nếu môi trường có 2 DB.

---

## 2. Validation / config (P0)

### TC-VAL-01 — thiếu project_source

- **Steps:** Gọi tool với `project_source=""`.
- **Expected:** `success=false`, `error_code=invalid_project_source`, không tạo file.

### TC-VAL-02 — type khác 0

- **Steps:** `type=1`.
- **Expected:** `success=false`, `error_code=unsupported_type`.

### TC-VAL-03 — sql_temp_folder chưa cấu hình

- **Steps:** `path_to_pasted=""`, config `sql_temp_folder=""`.
- **Expected:** `success=false`, `error_code=sql_temp_folder_not_configured`, không tạo file ngầm.

### TC-VAL-04 — sql_temp_folder không tồn tại

- **Steps:** Config trỏ `E:\NotExistFolder\SqlTemp`.
- **Expected:** Cùng nhóm lỗi config / folder missing.

### TC-VAL-05 — path_to_pasted không phải .sql

- **Steps:** `path_to_pasted=E:\tmp\out.txt`.
- **Expected:** `invalid_path_to_pasted`.

### TC-VAL-06 — project path relative

- **Steps:** `project_source=SP2263`.
- **Expected:** `invalid_project_source`.

---

## 3. Target-first & clone (P0)

### TC-CORE-01 — object chỉ có ở source

- **Given:** Target không có `zc_only_src`; source có.
- **Steps:** Clone `zc_only_src`, `path_to_pasted` trỏ file trống.
- **Expected:**
  - `cloned` chứa object
  - File có definition
  - `skipped_exists` rỗng
  - `not_found_both` rỗng

### TC-CORE-02 — object đã có ở target (skipped_exists)

- **Given:** Cả target và source đều có `dmkh`.
- **Steps:** Seed `dmkh`.
- **Expected:**
  - `cloned` rỗng
  - `skipped_exists` có `dmkh`, `where=target`
  - File **không** chứa CREATE TABLE `dmkh` mới (hoặc chỉ header session nếu có)

### TC-CORE-02b — root đã có target → không quét deps con

- **Given:** Root `procA` có ở target; `funcB` (được `procA` gọi) chỉ có ở source, thiếu target.
- **Steps:** Seed `procA`.
- **Expected (v1 cố ý):** `skipped_exists` có `procA`; `cloned` **không** có `funcB`; không fail.

### TC-CORE-03 — not found in 2 project

- **Given:** `funcGhost` không có source lẫn target.
- **Expected:**
  - `not_found_both` chứa `funcGhost`
  - Cuối file có **một** dòng `-- not found in 2 project: ...funcGhost...` (không spam trong loop)
  - Không fail `success`

### TC-CORE-04 — blank line + GO separator

- **Given:** File `.sql` sẵn nội dung; clone thêm 2 proc thành công.
- **Expected:**
  - Giữa các block có dòng trống
  - Có dòng `GO` giữa các `CREATE PROCEDURE` (file Execute được trên SSMS về mặt batch)
  - Không dính liền hai `CREATE` chỉ bằng whitespace

### TC-CORE-04b — visited normalize schema

- **Given:** Deps xuất hiện cả `dbo.zc_helper` và `zc_helper`.
- **Expected:** Chỉ xử lý **một** lần (visited key `dbo.zc_helper`).

### TC-CORE-05 — append idempotent

- **Steps:** Gọi 2 lần cùng `path_to_pasted`, cùng object chỉ có ở source (object vẫn không có trên target).
- **Expected:** File chứa **hai** bản script (append), không truncate lần 1.

> Ghi chú QA: đây là hành vi append cố ý; user muốn tránh duplicate thì tự quản lý file / xóa trước.

### TC-CORE-06 — exists table không dùng fetch_one

- **Unit:** Mock/spy — đường exists cho `dmkh` phải query `sys.objects` (hoặc `query_database` lookup), **không** gọi `ObjectCatalogFetcher.fetch_one`.
- **Expected:** Table tồn tại trên target được `skipped_exists`, không `not_found_both`.

---

## 4. Đệ quy dependency (P0/P1)

### TC-DEP-01 — proc → func thiếu ở target

- **Given:** `procA` (source) gọi `funcB`; target thiếu cả hai; source có cả hai.
- **Expected:** `cloned` gồm `procA` và `funcB` (thứ tự không bắt buộc).

### TC-DEP-02 — proc → table đã có target

- **Given:** `procA` đọc `dmkh`; target có `dmkh`.
- **Expected:** clone `procA`; `skipped_exists` có `dmkh`.

### TC-DEP-03 — cycle A ↔ B

- **Given:** Hai proc gọi lẫn nhau, cả hai thiếu target, có source.
- **Expected:** Mỗi object clone **một lần**; không infinite loop; `visited` hoạt động.

### TC-DEP-04 — exclude infra

- **Given:** Proc gọi `FastBusiness$Something` / `fsd_xxx`.
- **Expected:** Không xuất hiện trong `cloned` / `not_found_both` vì exclude; root proc vẫn clone.

### TC-DEP-04b — bỏ temp `#` / `@`

- **Given:** Summary (hoặc mock deps) có `#tmp` và `@tv`.
- **Expected:** Không enqueue; không `not_found_both` cho chúng.

### TC-DEP-05 — max_objects truncate

- **Steps:** Cấu hình `max_objects=2`, seed object có >2 deps thiếu.
- **Expected:** `warnings` hoặc `meta.truncated_max_objects=true`; không treo.

---

## 5. XML seed (P0/P1)

### TC-XML-01 — Dir XML summary seed

- **Steps:** `object` = absolute path `...\Controllers\Dir\SomeTran.xml` hợp lệ summary.
- **Expected:** `mode_seed=xml`; queue có tables/procs từ summary; chạy target-first.

### TC-XML-02 — XML không tồn tại

- **Expected:** `xml_not_found`, success false.

### TC-XML-03 — XML folder không hỗ trợ summary (Report/Lookup/nested)

- **Expected:** `xml_summary_failed` (không silent regex fallback).

### TC-XML-04 — tên file sql temp theo project label (NewSqlTemp)

- **Steps:** `path_to_pasted=""`, `project_source` = `...\VLOTUS\SP228\...\zcbkctnb.xml`.
- **Expected:** File tạo dạng `vlotus_sp228.sql` (hoặc `vlotus_sp228 (N).sql` nếu trùng) — **không** `zcbkctnb.sql`.

---

## 6. SQL temp & open file (P0)

### TC-FILE-01 — tạo file mới + tên trùng

- **Given:** Đã có `vlotus_sp228.sql` … `vlotus_sp228 (3).sql` trong sql_temp_folder.
- **Steps:** Clone với `project_source` thuộc VLOTUS/SP228, `path_to_pasted` rỗng.
- **Expected:** Tạo `vlotus_sp228 (4).sql`.

### TC-FILE-02 — open_editor auto success

- **Manual / Integration:** Sau clone, file xuất hiện trên Cursor (hoặc process `cursor`/`code` được gọi — có thể mock subprocess trong unit test).
- **Expected:** `meta.open_file_ok=true` khi mock CLI return success.

### TC-FILE-03 — open fail soft

- **Steps:** Mock CLI fail + `os.startfile` raise.
- **Expected:** `success=true`, `warnings` chứa `open_file_failed`, file vẫn tồn tại trên đĩa.

### TC-FILE-04 — open_file=false

- **Expected:** Không gọi CLI; `meta.open_file_attempted=false`.

---

## 7. Connection / error phân loại (P1)

### TC-DB-01 — source Web.config invalid

- **Expected:** Fail fast `invalid_project_source` / connection error — **không** ghi `not_found_both` cho seed.

### TC-DB-02 — target connection ok, source object missing, target missing

- **Expected:** `not_found_both` (đúng nghĩa thiếu object, không phải lỗi mạng).

### TC-DB-03 — permission denied khi fetch definition

- **Expected:** Fail hoặc warning rõ; **không** nhầm thành not_found_both.

---

## 8. Acceptance checklist (sign-off)

Trước khi coi v1 done:

- [ ] TC-VAL-01..06 pass
- [ ] TC-CORE-01..06 pass (gồm GO, normalize, exists table)
- [ ] TC-DEP-01..04b pass
- [ ] TC-XML-01..02 pass
- [ ] TC-FILE-01..03 pass
- [ ] JSON schema khớp `04_json_response.md`
- [ ] Tool description MCP nêu rõ không deploy DB
- [ ] `config.yaml` có block `clone_things` mẫu (có thể để `sql_temp_folder` rỗng trong repo mẫu + doc)

## 9. Gợi ý fixture unit

```text
tests/clone_things/
  test_sql_temp_naming.py
  test_append_blank_line.py
  test_queue_visited_exclude.py
  test_target_first_mock.py
  test_open_editor_fallback.py
  test_response_schema.py
```

Mock: `exists(project, name)`, `fetch_full(project, name)`, `summarize_deps(name)`.
