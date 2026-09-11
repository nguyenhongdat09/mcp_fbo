# 11 — `type=1`: Paste-for-edit (ALTER + XML seed + `mode_get` / `mode_recursion`)

> **Vai trò:** BA + Tester — spec để **Gemini implement** (Agent Cursor **không** code phase này).  
> **Bối cảnh:** Paste object ra `.sql` để chỉnh (tiết kiệm token vs `query_database` full). Đã có type=1 cơ bản (tên SQL → ALTER). **Mở rộng:** seed từ **XML**, lọc loại bằng **`mode_get`**, đệ quy deps bằng **`mode_recursion`**.  
> **Phạm vi code (Gemini):** [`clone_things/service.py`](../../../clone_things/service.py), [`clone_things/file_manager.py`](../../../clone_things/file_manager.py), [`fastbusiness_mcp/mcp_app.py`](../../../fastbusiness_mcp/mcp_app.py), `tests/clone_things/test_type1_*.py`.  
> **Không** đụng chrome_debug. **Không** đổi semantics type=0 (trừ thêm 2 param MCP bị type=0 **bỏ qua**).

---

## 1. WHY

| Nhu cầu | Giải pháp type=1 |
|---------|------------------|
| Sửa 1–n proc đã biết tên | `object` = tên / list → paste ALTER |
| Lấy hết proc (hoặc table/…) khai báo trong 1 controller XML | `object` = path `.xml` + `mode_get` |
| Lấy proc XML rồi kéo luôn object bên trong (như type=0 deps) | `mode_recursion=1` |
| Không deploy / không dump full SQL ra chat | Force no execute; JSON chỉ meta + line range |

---

## 2. So sánh `type=0` vs `type=1` (sau mở rộng)

| Tiêu chí | `type=0` | `type=1` |
|----------|----------|----------|
| Mục đích | Clone thiếu **source → target** | Paste-for-edit **1 project** (source) |
| `project_target` | Bắt buộc | Rỗng được |
| `object` | SQL name **hoặc** `.xml` seed | SQL name / list **hoặc** `.xml` seed |
| `mode_get` | Bỏ qua | Lọc **seed XML** (default `proc`) |
| `mode_recursion` | (luôn có deps queue) | Default `0` = không deps; `1` = deps như type=0 |
| Exists | Target-first | Chỉ **source** app→sys |
| Script | `CREATE` (+ wrap check) | Proc/func/view → **`ALTER`**; table → **giữ `CREATE`** + warning |
| Execute | Theo config | **Force false** |
| Dedup file | Visited 1 lần gọi | `skipped_already_in_file` nếu đã CREATE/ALTER trong `.sql` |
| `USE` | DB **target** | DB **source** |
| JSON | `cloned` / `skipped_exists` / … | `pasted` / `skipped_already_in_file` / `not_found_source` / `agent_message` |

---

## 3. Contract params

| Param | Type | Required | Default | Khi nào dùng |
|-------|------|----------|---------|--------------|
| `type` | `int` | không | `0` | `1` = paste-for-edit |
| `object` | `str` | **có** | — | Tên SQL / list `,`;`;`/newline **hoặc** absolute path `.xml` |
| `project_source` | `str` | **có** | — | Absolute project hoặc file trong project (resolve Web.config + tên sql temp) |
| `project_target` | `str` | type=0 có; type=1 không | `""` | type=1 bỏ qua |
| `path_to_pasted` | `str` | không | `""` | File `.sql`; rỗng → NewSqlTemp từ source |
| **`mode_get`** | `str` | không | **`"proc"`** | **Chỉ type=1.** Lọc kind khi seed từ XML. type=0 bỏ qua. |
| **`mode_recursion`** | `str` \| `int` | không | **`"0"`** | **Chỉ type=1.** `"0"`/`0` = không deps; `"1"`/`1` = đệ quy deps. type=0 bỏ qua. |

Optional sẵn có: `schema`, `db_type`, `max_objects`, `open_file`, `exclude_like`.

### 3.1. Phân loại `object` (type=1)

```
object.strip()
  → ends with .xml OR path tồn tại là file .xml
       → mode_seed = "xml"
       → summary_xml → seed list, rồi lọc theo mode_get
  → else
       → mode_seed = "sql_name"
       → parse list tên (mode_get KHÔNG lọc list tên — user đã chỉ định)
```

Resolve XML path: absolute; nếu relative thử dưới `project_source` (giống type=0). Không thấy → `xml_not_found`. Summary fail → `xml_summary_failed`.

### 3.2. `mode_get` — aliases (case-insensitive)

Tách bằng `,` hoặc `;`. Trim từng token.

| Token nhận | Kind nội bộ |
|------------|-------------|
| `proc`, `procedure`, `procedures`, `p` | `proc` |
| `func`, `function`, `functions`, `fn` | `func` |
| `view`, `views`, `v` | `view` |
| `table`, `tables`, `tbl`, `u` | `table` |
| `full`, `all`, `*` | cả bốn kind |

- Default `"proc"` → chỉ procedure từ XML.
- Ví dụ hợp lệ: `"proc,func"`, `"PROCEDURE, function"`, `"full"`.
- Token lạ → `warnings` (`unknown_mode_get_token: …`), bỏ token.
- Sau parse **không còn kind** → `error_code=invalid_mode_get`.

### 3.3. Map XML summary → seed (lọc theo kind)

Reuse `summary_xml` như type=0:

| Kind | Nguồn trong summary |
|------|---------------------|
| `proc` | `sql.procs[]` |
| `view` | `sql.views[]` |
| `table` | `sql.tables[]` + `controller.db_table` (qua `normalize_fbo_db_table`) |
| `func` | `sql.functions[]` hoặc `sql.funcs[]` **nếu có**. Không có field → **không bịa**; nếu `mode_get` đòi `func` → `warnings`: `xml_functions_not_in_summary` |

`mode_get=full` → union tất cả kind có dữ liệu.

Dedup tên trong seed (normalize `dbo.name`), giữ thứ tự.

### 3.4. `mode_recursion`

| Giá trị | Hành vi |
|---------|---------|
| `"0"` / `0` / rỗng / thiếu | Chỉ paste các object trong **seed** (XML đã lọc hoặc list tên) |
| `"1"` / `1` | Sau khi paste (hoặc skip dedup) một **proc/func**, gọi extract deps (reuse type=0 summary deps) → enqueue thêm table/proc/func/view… |
| Khác | `invalid_mode_recursion` |

**Deps không lọc lại bằng `mode_get`** — lấy đủ object bên trong để sửa được (parity type=0). Vẫn áp: visited, `max_objects`, noise denylist, exclude `#`/`@` / pattern hệ thống như type=0.

Chỉ đệ quy từ **proc/func** (không expand từ table/view seed trừ khi sau này BA đổi).

### 3.5. Validation type=1

| Điều kiện | `error_code` |
|-----------|--------------|
| `object` rỗng | `invalid_object` |
| XML không tồn tại | `xml_not_found` |
| summary_xml fail | `xml_summary_failed` |
| `mode_seed=sql_name` mà list parse rỗng | `invalid_object` |
| `mode_get` không còn kind hợp lệ | `invalid_mode_get` |
| `mode_recursion` không phải 0/1 | `invalid_mode_recursion` |
| `project_target` rỗng | **OK** |
| (Bỏ) XML → `invalid_object` | **Thu hồi** — XML được phép |

---

## 4. Flow thuật toán

```
type == 1:
  validate + parse mode_get → set[kind]
  parse mode_recursion → 0|1
  resolve output_file; load source_dbs; ensure_use (SOURCE catalog names)

  if mode_seed == xml:
      summary = summary_xml(object)
      queue = filter_xml_seed(summary, kinds)   # theo mode_get
      if queue empty: warnings xml_seed_empty; vẫn success với pasted=[]
  else:
      queue = parse_object_list(object)

  seed_set = set(queue)
  visited = set()
  pasted / skipped_already_in_file / not_found_source = []

  while queue and len(visited)+… < max_objects:
      name = dequeue
      normalize → visited skip if seen
      if object_already_in_sql_file → skipped_already_in_file; 
          if mode_recursion and is_proc_func: still may need deps?
          BA CHỐT: nếu đã in file → skip paste; nếu mode_recursion=1 và là proc/func
          → vẫn extract deps từ source definition (fetch) để enqueue (giống type=0 vẫn có thể cần deps thiếu)
          → nếu không muốn fetch khi skip: CHỐT đơn giản hơn = vẫn fetch summary deps khi recursion=1
      find source app→sys; miss → not_found_source
      fetch script
      if table: out = script (CREATE), warning table_kept_create, style=create
      elif proc/func/view: out = transform_create_to_alter(script), style=alter
      else: warning unsupported; continue
      append → line_start/end → pasted[]
      if mode_recursion==1 and is_proc_func:
          deps = extract_object_dependencies(...)  # reuse type=0
          enqueue chưa visited

  open file; return JSON + agent_message
  meta.mode_get / meta.mode_recursion / meta.mode_seed / execute_clone:false
```

### 4.1. Vẫn cấm ở type=1

- Target-first / `skipped_exists` / `not_found_both`
- Deploy / `execute_clone`
- Full SQL trong JSON
- **Xóa/ghi đè** block đã có trong file (dedup = skip only).  
  **Regression:** bỏ logic regex xóa block cũ trong `append_script_block` nếu còn (bug `GOUSE [Sys]`) — xem review trước.

### 4.2. Header file

```sql
-- clone_things type=1: dbo.zc_foo | SQL_STORED_PROCEDURE | paste-for-edit | from source
ALTER PROCEDURE ...
GO
```

---

## 5. Transform CREATE → ALTER

Giữ như spec trước:

- `CREATE PROC/PROCEDURE/FUNCTION/VIEW` → `ALTER …` (lần đầu, MULTILINE).
- `CREATE OR ALTER` giữ nguyên.
- **Table:** không đổi ALTER TABLE toàn khối — paste nguyên DDL `CREATE` + `warnings: table_kept_create: …`.

**Thu hồi** hành vi code hiện tại `table_not_supported` + skip: khi table nằm trong seed/deps (ví dụ `mode_get=table|full` hoặc recursion kéo table) → **phải paste**.

---

## 6. Dedup / USE / line range

- Dedup: § cũ — detect CREATE/ALTER + tên → `skipped_already_in_file` (+ line nếu được).
- USE App/Sys: tên DB **source** ([10](./10_sql_file_use_db_sections.md)).
- `line_start` / `line_end`: 1-based, inclusive, sau ghi file.

---

## 7. JSON response type=1

### 7.1. Top-level (bổ sung)

| Field | Mô tả |
|-------|--------|
| `mode` | `"paste_for_edit"` |
| `mode_seed` | `"xml"` \| `"sql_name"` |
| `pasted[]` | như cũ + `script_style` |
| `skipped_already_in_file[]` | |
| `not_found_source[]` | |
| `agent_message` | |
| `meta.mode_get` | string đã normalize, vd. `"proc"` hoặc `"proc,func"` |
| `meta.mode_recursion` | `0` \| `1` |
| `meta.execute_clone` | luôn `false` |
| `meta.seed_count` | optional số object sau lọc XML / list |

### 7.2. Sample — XML + mode_get=proc + recursion=0

```json
{
  "success": true,
  "type": 1,
  "object": "E:\\\\FBO\\\\SHOWA\\\\FBISP242\\\\App_Data\\\\Controllers\\\\Dir\\\\SVTran.xml",
  "mode": "paste_for_edit",
  "mode_seed": "xml",
  "project_target": "",
  "path_to_pasted": "E:\\\\SQL Temp\\\\showa_fbisp242 (7).sql",
  "pasted": [
    {
      "name": "dbo.zc_sv_save",
      "object_type": "SQL_STORED_PROCEDURE",
      "db": "app",
      "line_start": 10,
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
    "mode_recursion": 0,
    "mode_seed": "xml",
    "execute_clone": false,
    "seed_count": 1
  }
}
```

---

## 8. Agent workflow

1. XML chỉ muốn proc: `type=1`, `object=<xml>`, `mode_get=proc`, `mode_recursion=0`.
2. Muốn kèm deps: `mode_recursion=1`.
3. Sửa trong file theo line range — không dump SQL ra chat; user F5.
4. type=0 vẫn dùng khi clone **sang project khác**.

---

## 9. Acceptance criteria

| ID | Given | Then |
|----|--------|------|
| AC-T1-01…04, 07…10 | (giữ) paste tên SQL, dedup, no execute, USE sys, type=0 regress | như trước |
| AC-T1-05 | `object` = path `.xml` tồn tại, `mode_get=proc` | **success**; seed chỉ proc; **không** `invalid_object` |
| AC-T1-06 | XML + `mode_get=table` (hoặc recursion kéo table) | paste table **CREATE** + `table_kept_create`; **không** skip `table_not_supported` |
| AC-T1-GET-01 | XML có proc+table, `mode_get=proc` | chỉ proc trong `pasted` / seed |
| AC-T1-GET-02 | `mode_get=proc,func` hoặc `PROCEDURE, function` | parse đúng 2 kind |
| AC-T1-GET-03 | `mode_get=full` | union procs/tables/views/(funcs nếu có) |
| AC-T1-GET-04 | `mode_get=nope` | `invalid_mode_get` |
| AC-T1-GET-05 | object = list tên SQL, `mode_get=table` | vẫn paste đúng list (mode_get không chặn tên) |
| AC-T1-REC-01 | XML + `mode_recursion=0` | không enqueue deps |
| AC-T1-REC-02 | 1 proc seed + `mode_recursion=1`, proc gọi func/table | pasted gồm proc + deps (ALTER/CREATE đúng kind) |
| AC-T1-REC-03 | `mode_recursion=2` | `invalid_mode_recursion` |

---

## 10. Test cases (Gemini)

| ID | Priority | Mô tả |
|----|----------|--------|
| TC-T1-01…09 | P0/P1 | Giữ test cũ (đổi AC table: paste CREATE thay vì skip) |
| TC-T1-XML-01 | P0 | Mock summary_xml → filter `mode_get=proc` |
| TC-T1-XML-02 | P0 | `mode_get=full` lấy tables+views+procs |
| TC-T1-GET-01 | P0 | Parse aliases PROCEDURE / function / full |
| TC-T1-REC-01 | P0 | recursion=1 enqueue deps (mock extract) |
| TC-T1-REC-02 | P0 | recursion=0 không gọi extract deps |
| TC-T1-REG-01 | P0 | type=0 không đổi khi truyền `mode_get`/`mode_recursion` |
| TC-T1-APPEND-01 | P0 | append **không** xóa block cũ / không tạo `GOUSE` |

File: mở rộng `tests/clone_things/test_type1_paste_for_edit.py` (+ file mới nếu cần).

---

## 11. Implementation checklist (Gemini) — phase mở rộng

Baseline type=1 tên SQL đã có. Cần thêm:

- [ ] Bỏ reject XML khi type=1; seed qua `summary_xml` + `mode_get`
- [ ] MCP params `mode_get`, `mode_recursion` (+ description); type=0 ignore
- [ ] `parse_mode_get` / `parse_mode_recursion` + error codes
- [ ] Queue + `mode_recursion=1` reuse `extract_object_dependencies` / exclude / visited / max_objects
- [ ] Table: paste CREATE + `table_kept_create` (xóa nhánh `table_not_supported` skip)
- [ ] JSON: `mode_seed`, `meta.mode_get`, `meta.mode_recursion`
- [ ] Sửa/regression `append_script_block`: **không** regex-xóa block cũ gây `GOUSE`
- [ ] Unit TC-T1-XML / GET / REC; cập nhật test table skip → paste
- [ ] Không regress type=0

---

## 12. Prompt Gemini (copy-paste)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

CHỈ implement theo docs — đừng đổi BA:
docs/doc/clone_things/11_type1_paste_for_edit.md
(+ 02_tool_api.md, 04_json_response.md).

Mở rộng type=1 đã có:
1) object được phép là path .xml → summary_xml seed (reuse type=0).
2) Param mode_get (default "proc"): lọc kind seed XML. Aliases proc/procedure/func/function/table/view/full; list "proc,func". Khi object là list tên SQL thì KHÔNG lọc bằng mode_get.
3) Param mode_recursion default "0"; "1" = đệ quy deps như type=0 (visited/max_objects/exclude). Deps KHÔNG lọc lại bằng mode_get. Chỉ expand từ proc/func.
4) Table trong seed/deps: paste giữ CREATE + warning table_kept_create (BỎ skip table_not_supported).
5) Vẫn: ALTER cho proc/func/view; USE source DB; dedup skipped_already_in_file; execute_clone=false; line_start/end; agent_message; cấm full SQL JSON.
6) type=0 bỏ qua mode_get/mode_recursion; không regress.
7) FIX: append_script_block không được xóa block cũ bằng regex (tránh GOUSE).
8) Tests TC-T1-XML/GET/REC + cập nhật test table.

Không viết lại toàn bộ type=0; reuse summary_xml + extract deps hiện có.
```

---

## 13. Ví dụ gọi

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

**Proc + table từ XML, kèm deps:**

```json
{
  "type": 1,
  "object": "E:\\\\FBO\\\\SHOWA\\\\FBISP242\\\\App_Data\\\\Controllers\\\\Dir\\\\SVTran.xml",
  "project_source": "E:\\\\FBO\\\\SHOWA\\\\FBISP242",
  "mode_get": "proc,table",
  "mode_recursion": "1",
  "path_to_pasted": "E:\\\\SQL Temp\\\\showa_fbisp242 (5).sql"
}
```
