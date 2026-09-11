# 12 — type=1 bổ sung: XML seed + `mode_get` + `mode_recursion`

> **Vai trò:** BA + Tester — **file spec bổ sung** để **Gemini implement**.  
> **Không** sửa các `.md` cũ (`11`, `02`, `04`, `07`, `08`, `README`, …) trong phase này.  
> **Quan hệ với [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md):** Doc 11 = nền type=1 (paste-for-edit, ALTER, dedup, line range, không execute). **File 12 supersede / mở rộng** các điểm dưới đây khi implement. Gemini **đọc 12 làm nguồn sự thật cho feature này**; tham chiếu 11 / [03](./03_resolution_and_flow.md) / [10](./10_sql_file_use_db_sections.md) để reuse, không bắt chỉnh 11.  
> **Phạm vi code (sau khi doc chốt):** [`clone_things/service.py`](../../../clone_things/service.py), [`clone_things/file_manager.py`](../../../clone_things/file_manager.py), [`fastbusiness_mcp/mcp_app.py`](../../../fastbusiness_mcp/mcp_app.py), tests mới hoặc mở rộng `tests/clone_things/test_type1_*.py`.  
> **Không** đụng chrome_debug. **Không** đổi semantics type=0 (hai param mới: type=0 **bỏ qua**).

---

## 0. Điểm supersede so với doc 11 (v1)

Nếu bản 11 đang nói **cấm** XML / **không** recursion / table **skip** — khi làm theo file 12 thì:

| # | Doc 11 (cũ / lệch) | Theo file 12 (chốt) |
|---|--------------------|---------------------|
| 1 | `object` type=1 chỉ tên SQL; XML → `invalid_object` | **Cho phép** path `.xml` → `summary_xml` → seed |
| 2 | Không có `mode_get` / `mode_recursion` | Thêm 2 param (default `proc` / `0`) |
| 3 | Không đệ quy deps | `mode_recursion=1` → deps giống type=0 (chỉ source, ALTER/CREATE paste) |
| 4 | Table có thể bị skip (`table_not_supported`) | Khi seed/dep là table → **paste giữ `CREATE`** + warning `table_kept_create` |
| 5 | `mode_get` không tồn tại | Lọc **chỉ seed từ XML**; list tên SQL **không** bị `mode_get` chặn |

Phần **giữ nguyên** từ type=1: `project_target` rỗng OK; USE theo **source**; `execute_clone` force false; dedup `skipped_already_in_file`; JSON `pasted` + `line_start`/`line_end` + `agent_message`; **cấm** full SQL trong JSON.

---

## 1. WHY

| Nhu cầu user/agent | Cách gọi |
|--------------------|----------|
| Sửa 1–n object đã biết tên | `object` = tên / list (như type=1 cũ) |
| Lấy các proc (hoặc table/…) khai báo trong 1 controller XML | `object` = path `.xml` + `mode_get` |
| Lấy seed rồi kéo luôn object bên trong proc/func | `mode_recursion=1` |
| Không dump full SQL ra chat / không tự F5 | Giữ contract type=1 |

---

## 2. So sánh nhanh

| Tiêu chí | type=0 | type=1 (+ file 12) |
|----------|--------|---------------------|
| Mục đích | Clone thiếu source→target | Paste-for-edit 1 project |
| `object` XML | Seed + luôn có thể deps | Seed + lọc `mode_get`; deps chỉ khi `mode_recursion=1` |
| `mode_get` | Bỏ qua | Lọc kind **seed XML** (default `proc`) |
| `mode_recursion` | (queue deps luôn) | `0` = không deps; `1` = deps như type=0 |
| Exists | Target-first | Chỉ source |
| Script | CREATE | Proc/func/view → ALTER; table → CREATE + warning |
| Execute | Config | Force false |
| USE | Target DB names | Source DB names |

---

## 3. Contract params (bổ sung)

Cùng tool `clone_things`. Khi `type=1`:

| Param | Type | Required | Default | Mô tả |
|-------|------|----------|---------|--------|
| `type` | `int` | không | `0` | `1` = paste-for-edit |
| `object` | `str` | **có** | — | Tên SQL / list `,` `;` newline **hoặc** path `.xml` (absolute; relative thử dưới `project_source`) |
| `project_source` | `str` | **có** | — | Absolute project hoặc file trong project |
| `project_target` | `str` | không (type=1) | `""` | Bỏ qua |
| `path_to_pasted` | `str` | không | `""` | File `.sql`; rỗng → sql temp từ source |
| **`mode_get`** | `str` | không | **`"proc"`** | Chỉ type=1. Lọc kind khi seed XML. type=0 bỏ qua. |
| **`mode_recursion`** | `str` hoặc `int` | không | **`"0"`** | Chỉ type=1. `"0"`/`0` = không deps; `"1"`/`1` = đệ quy. type=0 bỏ qua. |

Optional sẵn có: `schema`, `db_type`, `max_objects`, `open_file`, `exclude_like`.

### 3.1. Phân loại `object`

```
object.strip()
  → ends with .xml OR file tồn tại suffix .xml
       → mode_seed = "xml"
       → summary_xml → thu thập theo kind → lọc mode_get → seed[]
  → else
       → mode_seed = "sql_name"
       → parse_object_list → seed[]
       → mode_get KHÔNG lọc seed (user đã chỉ định tên)
```

- XML không tìm thấy → `xml_not_found`
- `summary_xml` fail → `xml_summary_failed`
- List tên rỗng sau parse → `invalid_object`

### 3.2. `mode_get` — aliases

Case-insensitive. Tách `,` hoặc `;`. Trim.

| Token nhận | Kind nội bộ |
|------------|-------------|
| `proc`, `procedure`, `procedures`, `p` | `proc` |
| `func`, `function`, `functions`, `fn` | `func` |
| `view`, `views`, `v` | `view` |
| `table`, `tables`, `tbl`, `u` | `table` |
| `full`, `all`, `*` | cả bốn kind |

- Default `"proc"`.
- Hợp lệ: `"proc,func"`, `"PROCEDURE, function"`, `"full"`.
- Token lạ → `warnings` (`unknown_mode_get_token: …`), bỏ token.
- Sau parse **không còn kind** → `error_code=invalid_mode_get`.

Khi `mode_seed=sql_name`: vẫn parse `mode_get` để echo `meta.mode_get_kinds`; **không** dùng để loại tên trong list.

### 3.3. Map XML summary → seed

Reuse `summary_xml` (cùng type=0):

| Kind | Nguồn |
|------|--------|
| `proc` | `sql.procs[]` |
| `view` | `sql.views[]` |
| `table` | `sql.tables[]` + `controller.db_table` (`normalize_fbo_db_table`) |
| `func` | `sql.functions[]` hoặc `sql.funcs[]` **nếu summary có**. Không field → không bịa tên; nếu `mode_get` đòi `func` → warning `xml_functions_not_in_summary` |

`mode_get=full` → union các kind có dữ liệu. Dedup `dbo.name` lowercase, giữ thứ tự.

### 3.4. `mode_recursion`

| Giá trị | Hành vi |
|---------|---------|
| `"0"` / `0` / rỗng / default | Chỉ paste seed. Không `extract_object_dependencies`. |
| `"1"` / `1` | Sau khi paste thành công một **proc hoặc func** (seed hoặc đã enqueue), chạy summary deps như type=0 → enqueue tên chưa `visited`. |
| Khác | `invalid_mode_recursion` |

**Deps không lọc bởi `mode_get`** — lấy đủ object bên trong (table/view/proc/func…) để sửa được, giống type=0. Seed XML vẫn đã lọc bởi `mode_get`.

Áp dụng: `visited`, `max_objects`, noise denylist, exclude `#`/`@` / pattern type=0 đang dùng cho deps. **Không** target-first. **Không** `not_found_both` (dùng `not_found_source`).

### 3.5. Validation bổ sung

| Điều kiện | `error_code` |
|-----------|--------------|
| `mode_get` parse ra 0 kind | `invalid_mode_get` |
| `mode_recursion` không phải 0/1 | `invalid_mode_recursion` |
| XML path không tồn tại | `xml_not_found` |
| summary_xml fail | `xml_summary_failed` |

(Các lỗi type=1 cũ: `invalid_object`, `invalid_project_source`, `invalid_path_to_pasted`, `sql_temp_folder_not_configured` — giữ.)

---

## 4. Flow thuật toán

```
type == 1:
  parse mode_get → kinds[]  (fail → invalid_mode_get)
  parse mode_recursion → 0|1 (fail → invalid_mode_recursion)
  resolve output .sql; load source_dbs; ensure USE [source_app] / [source_sys]

  if object is XML:
      summary_xml → raw lists by kind
      seed = filter by kinds; dedupe
      mode_seed = "xml"
  else:
      seed = parse_object_list(object)
      mode_seed = "sql_name"

  queue = seed (copy)
  visited = empty
  pasted / skipped_already_in_file / not_found_source = []

  while queue and len(processed) < max_objects:
      name = dequeue
      if visited: continue
      mark visited

      if object_already_in_sql_file: → skipped_already_in_file; continue
         # optional BA: vẫn có thể enqueue deps nếu recursion=1 và biết là proc?
         # CHỐT: nếu skip vì đã trong file, VẪN cho phép enqueue deps khi recursion=1
         # nếu fetch được type là proc/func (đọc catalog) — để kéo thiếu deps.
         # Nếu không fetch được → chỉ skip.

      find on source app→sys
      if missing: not_found_source; continue

      fetch script
      if table: out = script (CREATE), warning table_kept_create, style=create
      elif proc|func|view: out = transform_create_to_alter(script), style=alter
      else: paste raw + warning unsupported_object_kind  (hoặc skip — CHỐT: paste raw + warning)

      append_script_block(..., header_tag=paste_edit) → line_start, line_end
      pasted.append(...)

      if mode_recursion == 1 and is_proc_or_func:
          deps = extract_object_dependencies(script/summary)  # reuse type=0
          enqueue deps not visited (không lọc mode_get)

  open file; return JSON
```

### 4.1. Script / USE / execute

- Proc/func/view: `CREATE` → `ALTER` (giữ `CREATE OR ALTER` nếu source đã vậy) — reuse `transform_create_to_alter`.
- Table: giữ `CREATE` + `table_kept_create: …`.
- `append_script_block` đúng section app/sys theo **source** DB names ([10](./10_sql_file_use_db_sections.md)).
- `execute_clone` luôn false.
- Dedup: không paste trùng; **không** xóa/ghi đè block user đang sửa.

### 4.2. Cảnh báo implement — bug `append_script_block` replace

Nếu code hiện có regex **xóa** block `clone_things` cũ rồi ghi lại: có thể làm dính `GOUSE [db]` (nuốt newline). Khi đụng `file_manager.append_script_block` cho type=1:

- **Cấm** replace/xóa block khi dedup — chỉ skip.
- Nên **gỡ** logic `old_pat` sub nếu làm hỏng type=0 append, hoặc sửa để không nuốt newline sau `GO`.

---

## 5. JSON response (delta type=1)

Giữ field type=1 từ doc 11: `pasted`, `skipped_already_in_file`, `not_found_source`, `agent_message`, `mode: "paste_for_edit"`.

**Bổ sung / bắt buộc:**

| Field | Mô tả |
|-------|--------|
| `mode_seed` | `"xml"` \| `"sql_name"` |
| `meta.mode_get` | Echo string input (vd. `"proc,func"`) |
| `meta.mode_get_kinds` | `["proc","func"]` sau normalize |
| `meta.mode_recursion` | `0` hoặc `1` (int) |
| `meta.execute_clone` | `false` |
| `meta.db_lookup_order` | `["app","sys"]` (hoặc đảo nếu `db_type=sys`) |

`pasted[]` giữ: `name`, `object_type`, `db`, `line_start`, `line_end`, `script_style` (`alter`\|`create`), optional `chars`.

### 5.1. Sample — XML + mode_get=proc + recursion=0

```json
{
  "success": true,
  "spec_version": "1.0",
  "type": 1,
  "object": "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242\\App_Data\\Controllers\\Templates\\Upload\\SVTran.xml",
  "mode": "paste_for_edit",
  "mode_seed": "xml",
  "project_source": "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242",
  "project_target": "",
  "path_to_pasted": "E:\\\\SQL Temp\\\\showa_fbisp242 (7).sql",
  "pasted": [
    {
      "name": "dbo.SomeUploadProc",
      "object_type": "SQL_STORED_PROCEDURE",
      "db": "app",
      "line_start": 12,
      "line_end": 200,
      "script_style": "alter"
    }
  ],
  "skipped_already_in_file": [],
  "not_found_source": [],
  "warnings": [],
  "agent_message": "Đã paste 1 object vào E:\\SQL Temp\\showa_fbisp242 (7).sql. Sửa theo pasted[].line_start–line_end. User tự F5.",
  "meta": {
    "mode_get": "proc",
    "mode_get_kinds": ["proc"],
    "mode_recursion": 0,
    "execute_clone": false,
    "open_file_ok": true,
    "db_lookup_order": ["app", "sys"]
  }
}
```

### 5.2. Sample — recursion=1

Seed 1 proc từ XML; deps thêm table/func → nhiều phần tử `pasted` (table `script_style=create`).

---

## 6. Ví dụ gọi

**Chỉ proc trong XML:**

```json
{
  "type": 1,
  "object": "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242\\App_Data\\Controllers\\Templates\\Upload\\SVTran.xml",
  "project_source": "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242",
  "project_target": "",
  "path_to_pasted": "",
  "mode_get": "proc",
  "mode_recursion": "0"
}
```

**Proc + table từ XML, có đệ quy deps:**

```json
{
  "type": 1,
  "object": "...\\SVTran.xml",
  "project_source": "...\\FBISP242",
  "project_target": "",
  "mode_get": "proc,table",
  "mode_recursion": "1",
  "path_to_pasted": "e:\\\\SQL Temp\\\\showa_fbisp242 (5).sql"
}
```

**List tên (mode_get không lọc seed):**

```json
{
  "type": 1,
  "object": "dbo.zc_a, dbo.zc_b",
  "project_source": "E:\\\\FBO\\\\SHOWA\\\\FBISP242",
  "mode_get": "proc",
  "mode_recursion": "1"
}
```

→ Paste đúng `zc_a`, `zc_b` rồi deps của chúng (nếu là proc/func).

---

## 7. Acceptance criteria

| ID | Given | Then |
|----|--------|------|
| AC-12-01 | XML + `mode_get=proc` + `recursion=0` | Chỉ paste procs từ summary; ALTER; không table/view trừ khi nằm trong procs list |
| AC-12-02 | XML + `mode_get=full` | Seed gồm procs+tables+views (+funcs nếu summary có) |
| AC-12-03 | XML + `mode_get=proc,func` / `PROCEDURE, function` | Parse kinds đúng; paste đúng kind |
| AC-12-04 | XML + token lạ hết → 0 kind | `invalid_mode_get` |
| AC-12-05 | `mode_recursion=1` + 1 proc seed có deps | `pasted` gồm proc + deps; deps không bị `mode_get` lọc |
| AC-12-06 | `mode_recursion=0` | Không gọi extract deps / không enqueue con |
| AC-12-07 | `object` = list tên + `mode_get=table` | Vẫn paste các tên trong list (không skip vì mode_get) |
| AC-12-08 | Table trong seed/dep | File có `CREATE TABLE`; warning `table_kept_create`; `script_style=create` |
| AC-12-09 | type=0 truyền `mode_get`/`mode_recursion` | Bỏ qua; behavior type=0 không đổi |
| AC-12-10 | Dedup lần 2 cùng XML | `skipped_already_in_file`; không nhân đôi block; không xóa block cũ |
| AC-12-11 | JSON | Có `mode_seed`, `meta.mode_get_kinds`, `meta.mode_recursion`; không full SQL |

---

## 8. Test cases (Gemini)

| ID | Priority | Mô tả |
|----|----------|--------|
| TC-T1-GET-01 | P0 | Parse `mode_get` aliases + `full` + invalid |
| TC-T1-XML-01 | P0 | Mock `summary_xml` → seed chỉ procs khi `mode_get=proc` |
| TC-T1-XML-02 | P0 | `mode_get=proc,table` lấy đủ 2 kind + `db_table` |
| TC-T1-XML-03 | P0 | XML missing → `xml_not_found` |
| TC-T1-REC-01 | P0 | `recursion=0` không enqueue deps |
| TC-T1-REC-02 | P0 | `recursion=1` enqueue deps; table CREATE; proc ALTER |
| TC-T1-REC-03 | P1 | `mode_get=proc` nhưng dep là table vẫn paste khi recursion=1 |
| TC-T1-GET-02 | P1 | sql_name list bỏ qua lọc mode_get |
| TC-T1-REG-01 | P0 | type=0 regression (target-first) vẫn pass |
| TC-T1-REG-02 | P0 | append không tạo `GOUSE` khi ghi nhiều block |

Gợi ý file: `tests/clone_things/test_type1_xml_mode_get_recursion.py`.

---

## 9. Implementation checklist (Gemini)

- [ ] MCP: thêm `mode_get`, `mode_recursion` (default `proc` / `0`); docstring type=1 nêu XML + 2 mode
- [ ] Bỏ reject XML trong nhánh type=1; wire `summary_xml` + filter `mode_get`
- [ ] `parse_mode_get` / `parse_mode_recursion` + error codes
- [ ] Queue + `mode_recursion=1` reuse `extract_object_dependencies` (hoặc tương đương type=0)
- [ ] Table: paste CREATE + warning (không `table_not_supported` skip khi đang paste)
- [ ] JSON: `mode_seed`, `meta.mode_get*`, `meta.mode_recursion`
- [ ] Sửa/gỡ replace-block gây `GOUSE` nếu còn trong `append_script_block`
- [ ] Tests TC-T1-GET / XML / REC / REG
- [ ] Không regress type=0; không sửa docs cũ trừ khi BA yêu cầu phase riêng

---

## 10. Prompt Gemini (copy-paste)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

Nhiệm vụ: mở rộng clone_things type=1 theo đúng:
docs/doc/clone_things/12_type1_xml_mode_get_recursion.md
(Tham chiếu 11 / 03 / 10 để reuse; KHÔNG bắt buộc sửa các file md cũ.)

Yêu cầu cứng:
1) type=1: object được phép là path .xml → summary_xml → seed.
2) Param mode_get (default "proc"): chỉ lọc kind khi seed XML; aliases proc/procedure/func/function/view/table/full; "proc,func" OK. List tên SQL không bị mode_get chặn.
3) Param mode_recursion (default "0"): "1" → đệ quy deps như type=0 (visited, max_objects, exclude noise); deps KHÔNG lọc bởi mode_get.
4) Vẫn paste-for-edit: ALTER proc/func/view; table giữ CREATE + table_kept_create; project_target rỗng OK; USE source; execute_clone=false; dedup skipped_already_in_file; line_start/line_end; agent_message; cấm full SQL trong JSON.
5) type=0 bỏ qua mode_get/mode_recursion; không regress.
6) Nếu append_script_block còn logic xóa block cũ gây GOUSE — gỡ hoặc sửa.
7) Unit tests TC-T1-GET / XML / REC trong tests/clone_things/test_type1_xml_mode_get_recursion.py.
```

---

## 11. Ngoài phạm vi file 12 / phase doc

- Không implement trong phase chỉ viết doc này.
- Không cập nhật README / 02 / 04 / 07 / 08 (để BA/phase sau nếu cần index).
- Không clone file XML Controllers (type=2 dự phòng).
