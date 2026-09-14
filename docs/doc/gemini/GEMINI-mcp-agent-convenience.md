# GEMINI — MCP agent convenience (sau polish)

> **File độc lập** — gửi Gemini chỉ cần file này.  
> **Repo:** `E:\PythonProject\mcp_fbo\`  
> **Bối cảnh:** Verify toàn diện 2026-09-14 — gaps / residual / polish **đã ship**.  
> Spec này = **DX còn lại** cho agent tiện hơn.  
> **Loại trừ (KHÔNG làm):** mở rộng `query_radar` / CodeGraph index `Main/*.aspx` hay `Templates/Mail`. Suite file ngoài Controllers dùng `compare_things` folder `seed` trên project root (đã đủ) — **không** đụng radar.

**Không** regress type=0/1/3 core, inventory, search_files, confirm_overwrite.  
**Không** Shell UNC.  
**Không** thêm MCP tạo/xóa/đổi tên file tùy ý (xem §P3).

---

## Mục tiêu

| Ưu tiên | Gap | Việc |
|---------|-----|------|
| **P1** | `copy_filter=different` dễ hiểu nhầm | Message / warning rõ |
| **P1** | Bộ file 1 controller phải ghép tay | Convenience expand `suite:` / tương đương |
| **P2** | Path Options hay đoán sai | Hint khi `missing_on_source` |
| **P2** | `user_prompt` truncated `..` kép | Fix format |
| **P2** | `seed` substring dính tên gần | `seed_mode` hoặc boundary |
| **P2** | UNC project dài, không alias | Optional `list_projects` / alias config |
| **P3** | Ranh giới tạo vs clone | **Chỉ document** (skill) — không code tool mới |

---

## P1-1 — `copy_filter=different` + thiếu overwrite

### Quan sát

`copy_filter=different`, `overwrite=false` (default):

- `summary_counts.exists_different > 0`
- nhưng `will_copy=[]` / `will_copy` count = 0  
→ Agent có thể nghĩ “không có gì để copy”.

Đúng semantics: file **different** chỉ vào `will_copy` khi có `overwrite` (+ `confirm_overwrite` khi execute đè).

### Hành vi đúng

Khi `copy_filter` ∈ {`different`, `all`} và có exists `content=different` nhưng **chưa** đủ quyền đè (`overwrite=false` hoặc execute sẽ cần confirm):

1. Giữ `will_copy` như hiện tại (không tự đè).
2. Bắt buộc `warnings` hoặc `agent_message` dạng:

```text
copy_filter=different: N file khác nội dung nhưng chưa nằm trong will_copy vì overwrite=false.
Muốn copy các file different → dry-run/execute với overwrite=true và confirm_overwrite=true (sau khi hỏi user).
```

Optional field: `blocked_different: ["ClientScript/jAjax.js", ...]` (sample ≤10).

### AC

- [x] AC-CF-1: `copy_filter=different`, overwrite=false, jAjax different → `will_copy` rỗng **và** warning/message nêu rõ cần overwrite+confirm
- [x] AC-CF-2: cùng object + `overwrite=true` + `confirm_overwrite=true` dry-run → `will_copy` có file
- [x] AC-CF-3: `copy_filter=missing` không bị thêm warning giả

---

## P1-2 — Expand “suite” theo tên controller

### Quan sát

Agent hay cần cả bộ:

- `Filter/{name}.xml`, `Filter/{name}Form.xml`
- `Grid/{name}.xml`, `Grid/{name}Grid.xml`
- `Main/{name}.aspx`
- `Templates/Mail/{name}.html` (nếu có)

Hiện: `compare` folder `seed` trên project root **đã liệt kê được** — nhưng type=3 copy vẫn phải paste list path thủ công.

### Thiết kế

Thêm token object type=3 (và/hoặc compare convenience):

| Cú pháp | Ý nghĩa |
|---------|---------|
| `suite:{name}` | Expand whitelist path **ứng viên** (POSIX), chỉ giữ path **tồn tại trên source** |
| `preset:suite` | **Không** — tránh nhầm; dùng `suite:name` |

Ví dụ `suite:zccnslkdhtpnc` → thử lần lượt (bỏ path không có trên source):

```text
App_Data/Controllers/Filter/{name}.xml
App_Data/Controllers/Filter/{name}Form.xml
App_Data/Controllers/Grid/{name}.xml
App_Data/Controllers/Grid/{name}Grid.xml
Main/{name}.aspx
App_Data/Controllers/Templates/Mail/{name}.html
App_Data/Controllers/Templates/Mail/zmail{Name}.html   # optional variants — chỉ nếu document rõ; v1 có thể bỏ variant phức tạp
```

**v1 tối thiểu (bắt buộc):** 6 path đầu (`Filter`, `FilterForm`, `Grid`, `GridGrid`, `Main` aspx, `Templates/Mail/{name}.html`).  
Path không tồn tại source → không đưa vào planned (hoặc `missing_on_source` từng cái — ưu tiên **bỏ im** khỏi expand để gọn).

Cho phép union: `suite:zccnslkdhtpnc,bin/fsdMail.dll`.

Parse: cùng token-first như type=3 (`suite:` prefix bắt buộc để khỏi nhầm relative).

### AC

- [x] AC-SUITE-1: `suite:zccnslkdhtpnc` source=AIH → planned/will có Filter+Grid+Form+aspx (+ html nếu có)
- [x] AC-SUITE-2: tên không tồn tại → planned rỗng + `invalid_object` hoặc warning `suite_empty`
- [x] AC-SUITE-3: union suite + 1 dll path hoạt động
- [x] AC-SUITE-4: **Không** thay đổi / yêu cầu thay đổi `query_radar` schema

---

## P2-3 — Hint path Options / App_Data

### Quan sát

`object=Options/EmailConfig.xml` → `missing_on_source` trong khi file thật ở `App_Data/Controllers/Options/EmailConfig.xml`.

### Hành vi

Khi `missing_on_source` và relative trông như Options/Web.config/Templates ngắn:

`warnings` gợi ý thử prefix `App_Data/Controllers/` (và/hoặc `App_Data/`).

Không tự đổi path im lặng (tránh copy nhầm). Optional: `suggestions: ["App_Data/Controllers/Options/EmailConfig.xml"]` nếu file đó **tồn tại** trên source.

### AC

- [x] AC-PATH-1: `Options/EmailConfig.xml` missing → có suggestion/warning trỏ `App_Data/Controllers/Options/...` nếu tồn tại
- [x] AC-PATH-2: path đúng sẵn → không spam suggestion

---

## P2-4 — `user_prompt` truncated dấu `..`

### Quan sát

`… đã ẩn (truncated). Xem summary_counts… tên.. Bạn có muốn` — hai dấu chấm trước “Bạn”.

### Fix

Nối câu bằng một khoảng / một dấu `.` — không `..`.

### AC

- [x] AC-PROMPT-1: truncated user_prompt không chứa `.. Bạn` / `...` lỗi chính tả kép

---

## P2-5 — `seed` / inventory substring quá rộng

### Quan sát

`seed=zccn` dính cả `zccnthxldtcth` lẫn `zccnslkdhtpnc`.

### Thiết kế (chọn một)

| Cách | Mô tả |
|------|-------|
| A | Param `seed_mode`: `contains` (default, giữ cũ) \| `prefix` \| `token` (boundary / `_{seed}_` / exact segment) |
| B | Document only — agent dùng seed dài hơn |

Ưu tiên **A** nếu sửa code `compare_things` folder/inventory.

### AC (nếu làm A)

- [x] AC-SEED-1: `seed=zccnslkdhtpnc` / `seed_mode=prefix` không ra `zccnthxldtcth`
- [x] AC-SEED-2: default `contains` không regress case cũ

---

## P2-6 — Optional list / alias project (thấp)

Nếu còn capacity:

- Config MCP: map alias → UNC abs (`aih_sp228` → `\\...\AIH\SP228`)
- Hoặc tool nhẹ `list_projects` đọc từ config (không scan cả CustomerPro)

**Không** bắt buộc v1 convenience này nếu P1 chưa xong.

---

## P3 — Tạo file ≠ Clone — chỉ document (không tool mới)

### Phân biệt

| | **Tạo (create)** | **Clone type=3** |
|--|------------------|------------------|
| Nguồn | Không có / nội dung mới | File đã có ở `project_source` |
| Tool | Cursor **Write** / **StrReplace** trên workspace | `clone_things` type=3 |
| Ví dụ | Soạn mới XML trong project đang UR | Copy `jAjax.js` HungThinh → AIH |

### Cấm implement trong MCP (scope file này)

- `create_file` / `delete_file` / `rename_file` trên UNC tùy ý

### Việc Gemini / Cursor doc

Cập nhật skill agent (vd. `fbo-fastbusiness-mcp` anti-pattern + 1 đoạn ngắn):

```text
MCP không tạo/xóa/đổi tên file tùy ý trên FBO.
- Sửa/tạo nội dung trong workspace đang UR → Write / StrReplace (IDE).
- Mang file có sẵn giữa 2 project → clone_things type=3.
- Xóa/rename trên UNC → hỏi user xử lý tay.
```

**Không** mở issue code MCP cho P3 trừ khi user yêu cầu riêng sau.

---

## Ngoài phạm vi (nhắc lại)

- **Không** index thêm `Main/*.aspx` / `Templates/Mail` vào `query_radar` / Kùzu.
- Agent cần suite ngoài Controllers: dùng `compare_things` `kind=folder` + `seed` trên **project root**, hoặc `suite:{name}` (P1-2).

---

## Phạm vi code

| Module | Việc |
|--------|------|
| `clone_things` type=3 | P1-1 message; P1-2 `suite:`; P2-3 suggestions; P2-4 prompt |
| `compare_things` folder/inventory | P2-5 `seed_mode` (optional) |
| Config / optional tool | P2-6 |
| Skill markdown (Cursor) | P3 document — Gemini được phép ghi note trong PR; Cursor thường sửa skill |

---

## Prompt Gemini (copy-paste)

```text
Implement docs/doc/gemini/GEMINI-mcp-agent-convenience.md.

P1 bắt buộc:
1) copy_filter=different + overwrite=false → warning/agent_message rõ cần overwrite+confirm_overwrite (will_copy vẫn rỗng).
2) type=3 object suite:{controller_name} expand Filter/Grid/Form/Main aspx/Mail html nếu có trên source; union với path khác OK.
   KHÔNG đụng query_radar / không index Main hay Templates vào graph.

P2: hint App_Data/Controllers khi Options path miss; fix user_prompt ".."; optional seed_mode.

P3: chỉ document tạo≠clone — KHÔNG thêm MCP create/delete/rename.

Tests AC-CF-*, AC-SUITE-*, AC-PATH-*, AC-PROMPT-*.
```

---

## Checklist BA / Tester

- [x] different + overwrite false → có warning rõ
- [x] different + overwrite + confirm dry-run → will_copy có file
- [x] `suite:zccnslkdhtpnc` trên AIH ra đủ file chính
- [x] Options sai path → có gợi ý App_Data/Controllers
- [x] user_prompt truncated không `.. Bạn`
- [x] Radar / graph **không** đổi vì spec này
