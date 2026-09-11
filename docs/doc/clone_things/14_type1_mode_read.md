# 14 — type=1 bổ sung: `mode_read` (summary / ghi `.sql` / full body JSON)

> **Vai trò:** BA + Tester — **file spec bổ sung** để **Gemini implement**.  
> **Không** sửa các `.md` cũ (`11`–`13`, `02`, `04`, `README`…) trong phase này.  
> **Phụ thuộc:** [11](./11_type1_paste_for_edit.md), [12](./12_type1_xml_mode_get_recursion.md), [13](./13_type1_parent_child_relations.md).  
> **Phạm vi code:** [`clone_things/service.py`](../../../clone_things/service.py), [`fastbusiness_mcp/mcp_app.py`](../../../fastbusiness_mcp/mcp_app.py), skill `fbo-clone-things`, tests type=1.  
> **Vấn đề thực tế:** Agent chỉ cần **đọc/phân tích** proc nhưng `clone_things` type=1 luôn ghi `.sql` → agent lại **đọc file lần 2**; đọc 10 proc → 10 file rác + tốn bước.

---

## 0. WHY

| Workflow hiện tại | Hệ quả |
|-------------------|--------|
| `clone_things(type=1)` → ghi `.sql` → Agent `read` file | Làm **2 lần** chỉ để xem code |
| Nhiều proc / XML seed | Nhiều file temp, khó dọn |

**Giải pháp:** thêm `mode_read` cho type=1 — tách **chỉ xem** vs **ghi file để sửa** vs **trả body trong JSON một phát**.

---

## 1. Contract param

| Param | Type | Default | Scope |
|-------|------|---------|--------|
| **`mode_read`** | `int` hoặc `str` `"0"`\|`"1"`\|`"3"` | **`1`** | **Chỉ type=1.** type=0 **bỏ qua**. |

Giá trị hợp lệ (normalize `"0"`/`0`, `"1"`/`1`, `"3"`/`3`):

| `mode_read` | Tên gợi nhớ | Hành vi |
|-------------|-------------|---------|
| **`1`** | summary / analyze | **Không ghi** `.sql` (hoặc không tạo file mới). JSON tóm tắt + quan hệ (`child_*`, `encrypt_proc`, …). `path_to_pasted` = `null` hoặc `""`. |
| **`0`** | file / paste-edit | **Như type=1 hiện tại:** ghi/append `.sql` (ALTER/CREATE), `line_start`/`line_end`, mở editor theo config. |
| **`3`** | full body JSON | **Không bắt buộc ghi** `.sql`. JSON kèm **full definition** (đã transform ALTER cho proc/func/view nếu lấy được body). |

Giá trị khác → `error_code=invalid_mode_read`.

> User có thể nói nhầm “ghi ra `.db`” — **chốt: ghi `.sql`**.

---

## 2. Ma trận hành vi (chốt BA)

| | `mode_read=1` | `mode_read=0` | `mode_read=3` |
|--|---------------|---------------|---------------|
| Resolve / tạo `path_to_pasted` | **Không** (bỏ qua `path_to_pasted` input; không NewSqlTemp) | Có | **Không** (mặc định); nếu user vẫn truyền path — **bỏ qua ghi** (không append) |
| `ensure_use` / `append_script_block` | Không | Có | Không |
| `open_file` | Không | Theo config / param | Không |
| Fetch definition | Chỉ khi cần classify/deps (summary path); **không** trả full trong JSON | Fetch + ghi file | Fetch + **đưa vào JSON** |
| `child_*` / `parent_*` / `encrypt_proc` | **Có** (doc 13; recursion theo `mode_recursion`) | Có | Có (trên cùng object đã analyze) |
| `mode_get` / XML seed | Có (doc 12) | Có | Có — nhưng xem giới hạn §3 |
| `execute_clone` | false | false | false |
| Full SQL trong JSON | **Cấm** | **Cấm** | **Cho phép** trên field chỉ định (§4) |

### 2.1. `mode_recursion` kết hợp

- `mode_read=1` + `mode_recursion=0`: analyze seed → JSON `analyzed[]` (hoặc tái dùng shape gần `pasted[]` nhưng **không** line range file) + `child_*`.
- `mode_read=1` + `mode_recursion=1`: enqueue deps như doc 12 nhưng **chỉ metadata** (không paste file); encrypt vẫn → `encrypt_proc`.
- `mode_read=0` + recursion: giữ behavior hiện tại (ghi file).
- `mode_read=3` + recursion=1: **cấm hoặc thu hẹp** — chốt: **chỉ cho phép `mode_recursion=0`** khi `mode_read=3`. Nếu recursion=1 → `error_code=invalid_mode_read_combo` (tránh JSON phình hàng chục full body).

---

## 3. Giới hạn `mode_read=3` (bắt buộc)

Mục tiêu: tránh agent dump 10 full proc vào chat.

| Rule | Chi tiết |
|------|----------|
| R1 | `mode_recursion` phải `0` |
| R2 | Sau parse seed: **tối đa N object** có `definition` trong JSON — **N = 3** (const / config `clone_things.mode_read_full_max_objects`, default 3). Vượt → `invalid_mode_read` hoặc chỉ full **N object đầu** + `warnings` `mode_read_3_truncated_objects` — **CHỐT: fail-fast `invalid_mode_read`** nếu seed count > N. |
| R3 | XML + `mode_get` ra nhiều proc: nếu count > N → lỗi, bảo agent dùng `mode_read=1` trước hoặc chỉ định đúng 1–N tên SQL. |
| R4 | Optional truncate: `max_full_chars` (reuse summary_object) — nếu cắt, `warnings` + `definition_truncated: true` trên item. |

---

## 4. JSON shape

### 4.1. Echo

```json
"mode_read": 1,
"meta": { "mode_read": 1, ... }
```

### 4.2. Danh sách object

Tái sử dụng mảng gần `pasted[]` để agent/skill ít đổi:

| `mode_read` | Mảng chính | Ghi chú |
|-------------|------------|---------|
| `0` | `pasted[]` | Có `line_start`/`line_end`, `path_to_pasted` set |
| `1` | `analyzed[]` **hoặc** `pasted[]` với `script_style` omit / `line_*=null` — **CHỐT dùng `analyzed[]`** để khỏi nhầm đã ghi file |
| `3` | `analyzed[]` (+ field `definition`) | `path_to_pasted` null |

**Chốt:** `mode_read` ∈ {1,3} → mảng **`analyzed[]`**; `mode_read=0` → **`pasted[]`** như cũ.  
`skipped_already_in_file` chỉ meaningful khi `mode_read=0`.  
`encrypt_proc`, `not_found_source`, `warnings`, `agent_message` giữ cho cả 3 mode.

### 4.3. Phần tử `analyzed[]` (`mode_read=1`)

```json
{
  "name": "dbo.zc_sctnt",
  "object_type": "SQL_STORED_PROCEDURE",
  "db": "app",
  "child_proc": "dbo.B,dbo.C",
  "child_func": "...",
  "child_table": "...",
  "parent_proc": "dbo.A"
}
```

Không `definition`. Không `line_start`/`line_end` (hoặc omit).

### 4.4. Phần tử `analyzed[]` (`mode_read=3`)

Thêm:

| Field | Type | Mô tả |
|-------|------|--------|
| `definition` | `string` | Full body (proc/func/view đã `CREATE`→`ALTER` nếu áp dụng; table = DDL CREATE) |
| `script_style` | `string` | `alter` \| `create` \| `raw` |
| `chars` | `int` | optional |
| `definition_truncated` | `bool` | optional |

Encrypted → không có `definition`; tên trong `encrypt_proc`.

### 4.5. Sample — `mode_read=1` (default)

```json
{
  "success": true,
  "type": 1,
  "mode": "paste_for_edit",
  "mode_seed": "sql_name",
  "mode_read": 1,
  "path_to_pasted": null,
  "pasted": [],
  "analyzed": [
    {
      "name": "dbo.zc_sctnt",
      "object_type": "SQL_STORED_PROCEDURE",
      "db": "app",
      "child_proc": "dbo.FastBusiness$Balance$BContract,dbo.FastBusiness$Partition$Execute",
      "child_table": "dbo.cdku,dbo.dmku"
    }
  ],
  "encrypt_proc": [],
  "not_found_source": [],
  "skipped_already_in_file": [],
  "agent_message": "Đã analyze 1 object (mode_read=1, không ghi .sql). Xem analyzed[].child_* / encrypt_proc. Cần sửa file → gọi lại mode_read=0; cần full body → mode_read=3 (≤3 object).",
  "meta": { "mode_read": 1, "mode_recursion": 0, "execute_clone": false }
}
```

### 4.6. Sample — `mode_read=3`

```json
{
  "mode_read": 3,
  "path_to_pasted": null,
  "analyzed": [
    {
      "name": "dbo.zc_sctnt",
      "object_type": "SQL_STORED_PROCEDURE",
      "db": "app",
      "script_style": "alter",
      "definition": "ALTER PROCEDURE [dbo].[zc_sctnt]\n...\n",
      "chars": 9959,
      "child_proc": "..."
    }
  ],
  "agent_message": "Đã trả full body trong analyzed[].definition (mode_read=3, không ghi .sql). Không dump lại ra chat nếu đã có trong JSON."
}
```

---

## 5. Agent habit (ghi trong doc + cập nhật skill sau khi code xong)

| Nhu cầu | Gọi |
|---------|-----|
| Nhìn deps / relative / XML toàn cảnh | `type=1`, **`mode_read=1`** (default) |
| Xem body 1–3 proc, không sửa file | `mode_read=3`, `mode_recursion=0` |
| Sửa code / user F5 | **`mode_read=0`**, có `path_to_pasted` |

**Cấm:** mặc định `mode_read=3` cho mọi lần “đọc”; loop 10 proc với `mode_read=3`.

---

## 6. Validation

| Điều kiện | `error_code` |
|-----------|--------------|
| `mode_read` ∉ {0,1,3} | `invalid_mode_read` |
| `mode_read=3` và `mode_recursion=1` | `invalid_mode_read_combo` |
| `mode_read=3` và số seed > `mode_read_full_max_objects` (default 3) | `invalid_mode_read` (message rõ: dùng mode_read=1 hoặc giảm object) |

---

## 7. Acceptance

| ID | Given | Then |
|----|--------|------|
| AC-MR-01 | Default không truyền `mode_read` | Hành vi = `1`: không tạo/ghi `.sql`, có `analyzed[]` |
| AC-MR-02 | `mode_read=0` | Ghi file + `pasted[]` + line range như trước |
| AC-MR-03 | `mode_read=1` + XML + recursion=0 | `child_*` có; `path_to_pasted` null; disk không file mới |
| AC-MR-04 | `mode_read=3` + 1 proc | `analyzed[0].definition` non-empty (nếu không encrypt); không ghi file |
| AC-MR-05 | `mode_read=3` + recursion=1 | Lỗi `invalid_mode_read_combo` |
| AC-MR-06 | `mode_read=3` + 5 tên SQL | Lỗi hoặc không trả 5 full — theo chốt fail-fast |
| AC-MR-07 | Encrypt + `mode_read=3` | Tên trong `encrypt_proc`; không `definition` giả |
| AC-MR-08 | type=0 + `mode_read=1` | Bỏ qua; type=0 không đổi |

---

## 8. Test cases

| ID | Priority | Mô tả |
|----|----------|--------|
| TC-MR-01 | P0 | Default mode_read=1 no file write |
| TC-MR-02 | P0 | mode_read=0 still pastes + lines |
| TC-MR-03 | P0 | mode_read=3 returns definition |
| TC-MR-04 | P0 | mode_read=3 + recursion=1 → error |
| TC-MR-05 | P1 | mode_read=3 seed > 3 → error |
| TC-MR-06 | P1 | encrypt_proc with mode_read=1 and 3 |

File: `tests/clone_things/test_type1_mode_read.py`.

---

## 9. Implementation checklist (Gemini)

- [ ] MCP param `mode_read: int = 1` (+ docstring)
- [ ] Branch type=1 theo 0/1/3; default 1 **đổi behavior** — cập nhật test type=1 cũ đang assume luôn ghi file (truyền `mode_read=0` trong test paste)
- [ ] `analyzed[]` cho 1/3; giữ `pasted[]` cho 0
- [ ] Không open_file / không ensure_use khi 1 hoặc 3
- [ ] Giới hạn combo + max objects cho 3
- [ ] Unit TC-MR-*
- [ ] Sau merge: nhờ Agent cập nhật skill `fbo-clone-things` (phase riêng nếu cần)

---

## 10. Prompt Gemini (copy-paste)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

Implement theo docs/doc/clone_things/14_type1_mode_read.md
(Không rewrite md 11–13; tham chiếu 12/13 cho mode_get/recursion/child/encrypt.)

Yêu cầu cứng:
1) type=1 thêm mode_read default=1: không ghi .sql; trả analyzed[] + child_*/encrypt_proc.
2) mode_read=0: giữ paste file + pasted[] + line range như hiện tại.
3) mode_read=3: không ghi file; analyzed[].definition = full body (ALTER transform); mode_recursion phải 0; seed ≤ 3 object (fail-fast nếu hơn).
4) type=0 bỏ qua mode_read.
5) Sửa unit test type=1 cũ: chỗ cần ghi file phải truyền mode_read=0.
6) Tests tests/clone_things/test_type1_mode_read.py (TC-MR-*).
```

---

## 11. Ngoài phạm vi

- Không đổi type=0.
- Không bắt buộc amend skill trong cùng PR code (nhưng checklist nhắc).
- Không `mode_read=2` (để trống số 2 tránh nhầm read_option XML).
