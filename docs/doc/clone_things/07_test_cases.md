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

### TC-VAL-02 — type không hỗ trợ

- **Steps:** `type=2` (hoặc bất kỳ ∉ `{0,1}`).
- **Expected:** `success=false`, `error_code=unsupported_type`.
- **Note:** `type=1` **hợp lệ** (paste-for-edit) — xem [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md) và TC-T1-* bên dưới. **Không** còn expect `unsupported_type` cho type=1.

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

### TC-CORE-07 — dual lookup: object đã có trên target sys (skipped_exists)

- **Given:** `userinfo2` không có ở app DB nhưng có ở target sys DB.
- **Steps:** Seed `userinfo2`.
- **Expected:**
  - `skipped_exists` có `dbo.userinfo2`, `where="target"`, `db="sys"`
  - `cloned` rỗng, `not_found_both` rỗng
  - Không fetch source script

### TC-CORE-08 — dual lookup: object chỉ có trên source sys (cloned sys)

- **Given:** `syscheckfields` thiếu ở cả target app và sys; source app không có, nhưng source sys có.
- **Steps:** Seed `syscheckfields`.
- **Expected:**
  - `cloned` có `dbo.syscheckfields`, `from="source"`, `db="sys"`
  - `fetch_object_script` gọi với `db_type="sys"`
  - Nếu `execute_clone=true`: deploy vào target sys connection
  - `not_found_both` rỗng

### TC-CORE-09 — lọc system noise (tempdb, systypes, master...)

- **Given:** Seed hoặc extracted dependency chứa `tempdb`, `systypes`, `master`...
- **Expected:**
  - Xuất hiện trong `skipped_noise`
  - Không gọi database catalog / `sys.objects`
  - Không nằm trong `not_found_both`
  - Không ghi comment `-- not found in 2 project` vào file `.sql`

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

- [ ] TC-VAL-01..06 pass (TC-VAL-02: type∉{0,1} → unsupported; **type=1 hợp lệ**)
- [ ] TC-CORE-01..09 pass (gồm GO, normalize, exists table, dual app/sys, system noise)
- [ ] TC-DEP-01..04b pass
- [ ] TC-XML-01..02 pass
- [ ] TC-FILE-01..03 pass
- [ ] TC-T1-01..09 pass (paste-for-edit — chi tiết [11](./11_type1_paste_for_edit.md) §12)
- [ ] JSON schema khớp `04_json_response.md` (+ nhánh type=1)
- [ ] Tool description MCP nêu rõ type=0/1; type=1 không deploy DB
- [ ] `config.yaml` có block `clone_things` mẫu (có thể để `sql_temp_folder` rỗng trong repo mẫu + doc)

## 9. type=1 — Paste-for-edit (P0)

Chi tiết AC + pseudo: **[11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md)**.

| ID | Expected ngắn |
|----|----------------|
| TC-T1-01 | `CREATE`→`ALTER` transform unit |
| TC-T1-02 | Dedup detect đã có trong file |
| TC-T1-03 | `line_start`/`line_end` đúng |
| TC-T1-04 | Service mock JSON type=1 + `agent_message` |
| TC-T1-05 | Lần 2 cùng object → `skipped_already_in_file` |
| TC-T1-06 | `project_target=""` OK; type=0 thiếu target vẫn fail |
| TC-T1-07 | Parse list `a, b; c` |
| TC-T1-08 | `execute_clone` config true nhưng type=1 không deploy |
| TC-T1-09 | Sys object → sau `USE [source_sys]` |

## 10. Gợi ý fixture unit

```text
tests/clone_things/
  test_sql_temp_naming.py
  test_append_blank_line.py
  test_queue_visited_exclude.py
  test_target_first_mock.py
  test_open_editor_fallback.py
  test_response_schema.py
  test_type1_paste_for_edit.py
```

Mock: `exists(project, name)`, `fetch_full(project, name)`, `summarize_deps(name)`.
