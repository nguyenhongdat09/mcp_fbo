# GEMINI — MCP DX residual (sau gaps P0/P1)

> **File độc lập** — gửi Gemini chỉ cần file này.  
> **Repo:** `E:\PythonProject\mcp_fbo\`  
> **Bối cảnh:** Smoke verify 2026-09-14 — gaps P0/P1 trong [`GEMINI-mcp-agent-gaps.md`](./GEMINI-mcp-agent-gaps.md) **đã ship OK**.  
> Spec này chỉ fix **điểm DX còn sót** làm agent “grep miss” / token phình khi truncated.

**Không** re-implement inventory / search_files / type=3 core / confirm_overwrite / read abs.  
**Không** đổi semantics type=0/1.  
**Không** Shell UNC.

---

## Quan sát từ verify (PASS vs sót)

| Hạng mục | Trạng thái |
|----------|------------|
| `compare_things` `inventory=true` | PASS |
| `search_files` khi root/glob **hẹp** | PASS (vd. `ClientScript` → `sendMail`; glob `*zccnslkdhtpnc*` → `acceptSendMail`) |
| type=3 `is_directory` / `expand_dirs` / `max_files` / `confirm_overwrite` / `list_presets` / `summary_counts` | PASS |
| `read_local_file` abs không cần `reference_file` | PASS |
| **`search_files` root = cả project** + `max_files=100..200` | **SÓT** — `truncated=true`, `matches=[]` dù chuỗi **có** trong Filter/Grid sâu hơn |
| type=3 glob lớn `truncated=true` | **SÓT DX** — `planned[]` vẫn ~`max_files` entries (vd. 20) → token nặng; agent nên nhìn `summary_counts` nhưng JSON vẫn dài |

---

## P0 — `search_files`: không miss hit vì hết quota scan sớm

### Vấn đề

Hiện scan theo thứ tự filesystem / glob → cắt khi `files_scanned >= max_files`.

Ví dụ fail:

- `root=...\AIH\SP228\App_Data\Controllers`, `pattern=acceptSendMail`, `max_files=100`  
  → `matches=[]`, `truncated=true`  
- Cùng pattern + `include_glob=*zccnslkdhtpnc*` → **có hit** `Grid/zccnslkdhtpnc.xml`

→ Agent “grep cả Controllers” **sai kết luận không có**.

### Thiết kế (bắt buộc kết hợp A + B; C optional)

#### A) Ưu tiên file “có khả năng khớp tên” trước khi scan body

Trước khi đọc nội dung theo thứ tự mặc định:

1. Thu thập candidate paths (sau include/exclude, recursive).
2. **Sort priority** (cao → thấp), rồi mới đọc lần lượt đến khi đủ `max_total_matches` **hoặc** hết candidate (không chỉ cắt mù theo `max_files` trên list unsorted):

| Priority | Điều kiện |
|----------|-----------|
| 0 (cao nhất) | Tên file / relative path **chứa** substring literal của `pattern` (case theo `case_sensitive`) — bỏ ký tự regex đặc biệt nếu `regex=true` (chỉ dùng phần alphanumeric / token đầu) |
| 1 | Extension “nóng” agent hay grep: `.js`, `.xml`, `.aspx`, `.html`, `.txt`, `.ent` trước `.sql`/khác |
| 2 | Path chứa `Filter/`, `Grid/`, `Dir/`, `ClientScript/`, `Main/`, `Templates/` trước thư mục sâu khác |
| 3 | Còn lại — ổn định theo relative path POSIX |

`max_files` = số file **được mở đọc nội dung** tối đa (không đổi nghĩa), nhưng thứ tự phải theo priority ở trên.

#### B) Phân biệt truncated scan vs truncated matches

JSON bổ sung (giữ field cũ):

```json
{
  "success": true,
  "matches": [],
  "files_scanned": 100,
  "files_candidate": 3500,
  "truncated": true,
  "truncated_reason": "max_files",
  "warnings": [
    "Reached max_files (100); 3400 candidates not opened. Narrow root/include_glob or raise max_files. Prefer filename-matching candidates were scanned first."
  ]
}
```

| Field | Ý nghĩa |
|-------|---------|
| `files_candidate` | Số path sau filter glob (trước đọc) |
| `truncated_reason` | `max_files` \| `max_total_matches` \| `null` |
| `warnings` | Bắt buộc có khi `truncated && matches rỗng` — nhắc hẹp root/glob |

#### C) Optional — `prefer_name_match: bool = true`

Default **true**. `false` = thứ tự cũ (chỉ để regress test).

### Không làm

- Không bỏ `max_files` / không scan vô hạn.
- Không đọc `*.f` / binary.
- Không đổi default `include_glob` trừ khi cần document.

### AC

- [ ] AC-SF2-1: `root=...\App_Data\Controllers` (AIH SP228), `pattern=acceptSendMail`, `include_glob=*.{xml,js,aspx,html}`, `max_files=100` → **≥1 match** (Grid/Filter `zccnslkdhtpnc*`) nhờ priority tên/path — **không** còn `matches=[]` chỉ vì scan alphabet sớm
- [ ] AC-SF2-2: Cùng case nếu vẫn truncated → `files_candidate` > `files_scanned`, `truncated_reason=max_files`, warning rõ
- [ ] AC-SF2-3: Root hẹp `ClientScript` + `sendMail` không regress
- [ ] AC-SF2-4: `prefer_name_match=false` + max nhỏ có thể miss (cho phép) — chỉ để chứng minh flag hoạt động
- [ ] AC-SF2-5: `*.f` vẫn không đọc

---

## P1 — type=3: khi `truncated_max_files`, rút gọn `planned[]`

### Vấn đề

`object=bin/**/*.dll`, `max_files=20`:

- `truncated=true`, `total_expanded=90`, `summary_counts` OK  
- Nhưng `planned[]` vẫn **20 object đầy hash** → response ~token lớn; agent dễ dump hết ra chat

### Thiết kế

Khi `truncated=true` (vượt `max_files` sau expand):

| Param | Default | Ý nghĩa |
|-------|---------|---------|
| `planned_sample_size` | `10` | Số phần tử tối đa trong `planned[]` khi truncated |
| (giữ) `max_files` | `100` | Số file tối đa **đưa vào xử lý/copy** |

Hành vi:

1. Expand đầy đủ → `total_expanded` (meta).
2. Cắt list xử lý theo `max_files` (như hiện tại).
3. Nếu `truncated`:
   - `planned[]` chỉ giữ **sample** ≤ `planned_sample_size`:
     - ưu tiên: vài `missing_on_target`, vài `exists_different`, vài `exists_same` (round-robin), không chỉ 20 file đầu alphabet
   - `will_copy` / `exists_on_target` / `skipped_*`: cũng truncate theo cùng sample **hoặc** chỉ giữ counts trong `summary_counts` + sample paths trong `planned`
4. `summary_counts` **luôn** tính trên tập đã đưa vào xử lý (≤ `max_files`), không đổi.
5. `warnings` thêm: `"planned_truncated: showing N of M processed (total_expanded=X)"`
6. `meta.planned_omitted` = số planned bị ẩn

Khi `truncated=false`: `planned[]` đầy đủ như hiện tại (không sample).

### AC

- [ ] AC-T3-SAMP-1: glob lớn + `max_files=20` + default sample → `len(planned) ≤ 10` (hoặc `planned_sample_size`), có `summary_counts`, `meta.total_expanded`
- [ ] AC-T3-SAMP-2: dry-run hẹp (`Templates/Mail/*.html`, không truncate) → `planned` đủ mọi file
- [ ] AC-T3-SAMP-3: `execute=true` vẫn chỉ copy trong budget `max_files` (không copy phần omitted vì truncate expand)

---

## P2 (optional) — DX nhỏ

1. **Skill** `fbo-clone-things` / no-shell: map  
   - list 1 folder → `compare_things(inventory=true)`  
   - grep UNC → `search_files` (nhắc hẹp `root` / glob)  
   - overwrite → cần `confirm_overwrite=true` sau user OK  
   *(Có thể Cursor cập nhật skill; Gemini chỉ cần ghi chú trong PR MCP nếu đụng docs.)*

2. Document tool description `search_files`:  
   “Root rộng dễ truncated — ưu tiên `Filter/`, `ClientScript/`, hoặc glob tên controller; tool đã ưu tiên filename match.”

---

## Phạm vi code

| Module | Việc |
|--------|------|
| `search_files` (module/tool mới đã ship) | Priority sort + `files_candidate` + `truncated_reason` + warning |
| `clone_things/type3_*.py` | `planned_sample_size` khi truncated |
| `mcp_app.py` | Expose param mới nếu có |
| `tests/` | AC-SF2-* , AC-T3-SAMP-* |

---

## Anti-patterns

- Tăng `max_files` default lên hàng nghìn để “che” miss — **không**; phải sort priority.
- Trả full `planned` 100 hash khi truncated.
- Đổi nghĩa `confirm_overwrite` / inventory.

---

## Prompt Gemini (copy-paste)

```text
Implement docs/doc/gemini/GEMINI-mcp-dx-residual.md only.

1) search_files: khi scan, ưu tiên file/path có tên gần pattern + Filter/Grid/Dir/ClientScript/Main trước; thêm files_candidate, truncated_reason; warning khi truncated && matches rỗng.
   AC: root=App_Data/Controllers pattern=acceptSendMail max_files=100 phải ra hit (AIH SP228).

2) clone_things type=3: khi truncated_max_files, planned[] sample (default 10) + summary_counts đủ; không dump đủ max_files hash.

Không regress gaps P0/P1 đã ship. Không đụng type=0/1. Tests AC-SF2-* và AC-T3-SAMP-*.
```

---

## Checklist BA / Tester

- [ ] Controllers + `acceptSendMail` + max_files=100 → có hit (không cần glob tên)
- [ ] ClientScript + `sendMail` vẫn OK
- [ ] `bin/**/*.dll` max_files=20 → planned ngắn, có summary_counts + total_expanded
- [ ] Mail html glob nhỏ → planned đầy đủ
