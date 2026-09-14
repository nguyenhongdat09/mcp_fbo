# GEMINI — MCP agent gaps (sau type=3)

> **File độc lập** — gửi Gemini chỉ cần file này (+ tùy chọn đọc type=3 đã ship).  
> **Repo:** `E:\PythonProject\mcp_fbo\`  
> **Bối cảnh:** Smoke test agent Cursor 2026-09-14 trên UNC FBO (HungThinh ↔ AIH SP228).  
> **type=3 đã ship** — không re-implement copy file; chỉ **lấp gap** làm agent tiện hơn / ít mù hơn khi **cấm Shell UNC**.

---

## Mục tiêu

Sau khi có `clone_things` type=3 + policy no-Shell, agent vẫn vướng các case sau. Spec này yêu cầu Gemini **implement / tinh chỉnh MCP** theo ưu tiên.

| Ưu tiên | Gap | Hướng xử lý |
|---------|-----|-------------|
| **P0** | Không **list** được file trong **1** thư mục | Mở rộng `compare_things` |
| **P0** | Không **grep/search** nội dung trên UNC ngoài workspace | Tool mới hoặc mở rộng tool sẵn |
| **P0** | `object=bin` (dir) báo sai `missing_on_source`; glob rộng phình token | Sửa `clone_things` type=3 |
| **P1** | Error type=3 mỏng; overwrite không soft-gate; thiếu preset registry | Sửa type=3 + DX |
| **P1** | `read_local_file` abs path vẫn bắt `reference_file` khó hiểu | Sửa `read_local_file` |
| **P2** | xml seed chỉ Controllers; thiếu filter copy; summary counts | Tiện ích |

**Không** đụng semantics type=0/1 SQL clone (trừ khi ghi chú rõ).  
**Không** thêm Shell vào agent policy.

---

## P0-1 — `compare_things`: inventory / list 1 folder

### Vấn đề quan sát

`kind=folder`, `folder_a == folder_b`, `include_glob=*Mail*`:

- `identical_meta_count: 7`, `omitted_identical_count: 7`
- `detail=true` vẫn `compared: []` — **không trả tên file**

Agent cần thay `Get-ChildItem` → hiện **mù**.

### Thiết kế

Thêm một trong hai (ưu tiên A):

#### A) Param `inventory` (khuyến nghị)

| Param | Default | Ý nghĩa |
|-------|---------|---------|
| `inventory` | `false` | `true` → chế độ **liệt kê 1 thư mục**, không so 2 bên |

Khi `inventory=true`:

- Bắt buộc: `folder_a` (hoặc `folder_b`; nếu cả hai → dùng `folder_a`)
- `folder_b` **không bắt buộc**
- Vẫn dùng `include_glob` / `exclude_glob` / `seed` / `recursive`
- **Không** hash nội dung mặc định (`compare_content` bỏ qua trừ khi user bật)

JSON gợi ý:

```json
{
  "success": true,
  "kind": "folder",
  "mode": "inventory",
  "folder": "\\\\...\\bin",
  "files": [
    {"relative": "fsdMail.dll", "size": 41984, "modified": "...", "is_dir": false}
  ],
  "summary": {"file_count": 7, "dir_count": 0, "truncated": false},
  "warnings": []
}
```

`relative` = path POSIX relative tới folder root. `max_objects` áp dụng; vượt → `truncated=true`.

#### B) Fallback nếu không muốn param mới

Khi `detail=true` **hoặc** `list_identical=true`: **luôn** trả tên trong `summary.identical` / `compared[]` (kể cả A≡B), **không** omit.

### AC

- [ ] AC-INV-1: `inventory=true`, 1 folder bin + `include_glob=*Mail*` → trả đủ tên DLL khớp (không `omitted` hết)
- [ ] AC-INV-2: `inventory=true` thiếu folder → `error_code=invalid_folder`
- [ ] AC-INV-3: Self-compare A=B + `list_identical=true` (nếu chọn B) → có tên file
- [ ] AC-INV-4: Không regress summary 2-folder khi `inventory=false` (vẫn được omit identical để gọn)

---

## P0-2 — Search nội dung file trên UNC (`search_files` hoặc tương đương)

### Vấn đề

Agent cần tìm `acceptSendMail` / chuỗi trong HungThinh `Main/`, `ClientScript/`, Controllers… Workspace Cursor Grep **không** cover cross-project UNC ổn định; Shell UNC cấm.

### Thiết kế (tool mới `search_files` — khuyến nghị)

| Param | Required | Default | Ý nghĩa |
|-------|----------|---------|---------|
| `root` | **có** | | Abs folder hoặc project root |
| `pattern` | **có** | | Regex hoặc literal (param `regex` bool) |
| `include_glob` | | `*.{xml,aspx,js,html,config,ent,txt,sql}` | |
| `exclude_glob` | | `**/*.f,**/*.dll,**/*.pdb,**/bin/**` (dll optional) | |
| `recursive` | | `true` | |
| `case_sensitive` | | `false` | |
| `max_files` | | `50` | |
| `max_matches_per_file` | | `5` | |
| `max_total_matches` | | `100` | |
| `context_lines` | | `0` | 0 = chỉ path:line |

**Deny:** không đọc `*.f`; skip binary (NUL / không decode utf-8/cp1258).

JSON:

```json
{
  "success": true,
  "root": "...",
  "pattern": "acceptSendMail",
  "matches": [
    {"path": "ClientScript/jAjax.js", "line": 42, "preview": "...acceptSendMail..."}
  ],
  "files_scanned": 120,
  "truncated": false,
  "warnings": []
}
```

Path trả về POSIX relative tới `root` nếu `root` là project; abs nếu cần.

### Phương án B (không tool mới)

Mở rộng `compare_things` **không** phù hợp (so 2 bên). Có thể gắn `read_local_file` batch — **không đủ**. Ưu tiên tool mới.

### AC

- [ ] AC-SF-1: Search `acceptSendMail` dưới HungThinh `ClientScript` hoặc project root → ≥1 hit
- [ ] AC-SF-2: `*.f` không bị đọc
- [ ] AC-SF-3: Vượt `max_total_matches` → `truncated=true`, không nổ token
- [ ] AC-SF-4: `root` ngoài / không tồn tại → error rõ

---

## P0-3 — `clone_things` type=3: directory + glob guard

### 3a. Token là thư mục

**Quan sát:** `object=bin` → `planned[].status=missing_on_source` dù `bin/` tồn tại trên source.

**Hành vi đúng:**

| Tình huống | Kết quả |
|------------|---------|
| Token trỏ tới **directory** trên source, `expand_dirs=false` (default) | `success=false` hoặc item `status=is_directory` + `error_code=is_directory` + message gợi ý `bin/*` hoặc `bin/**/*` hoặc `expand_dirs=true` |
| `expand_dirs=true` | Expand **file** dưới dir (recursive theo `recursive_dirs` default true), áp `max_files` |

**Không** copy cả cây như 1 “file” `bin`.

### 3b. Giới hạn glob / expand

| Param | Default | Ý nghĩa |
|-------|---------|---------|
| `max_files` | `100` | Sau expand+dedupe, nếu > max → **không** copy; `truncated=true`; trả `file_count`, sample 20 path đầu; `error_code` optional `too_many_files` khi `execute=true` |
| Dry-run vượt max | | `success=true` vẫn OK nhưng `warnings: ["truncated_max_files"]` + `planned` chỉ sample **hoặc** planned đầy đủ nếu ≤ 2×max — chọn: **planned truncated + truncated=true** (tiết kiệm token) |

Khuyến nghị dry-run: trả `summary_counts` (mục P2) + `planned` tối đa `max_files` entries.

### AC

- [ ] AC-T3-DIR-1: `object=bin` không còn `missing_on_source` giả
- [ ] AC-T3-DIR-2: `expand_dirs=true` trên thư mục nhỏ → danh sách file con
- [ ] AC-T3-GLOB-1: `bin/**/*.dll` vượt `max_files=100` → truncated / warn; `execute=true` không copy hàng trăm trừ khi user tăng `max_files`
- [ ] AC-T3-GLOB-2: Glob hẹp (`Templates/Mail/*.html`) không bị ảnh hưởng

---

## P1-4 — type=3 error chi tiết + overwrite soft-gate + presets

### 4a. Error message

Hiện: `"Failed to expand object: unknown_preset"`.

Bắt buộc kèm:

- `error_code`
- `message` tiếng Việt/Anh ngắn **có token/path**
- Optional `detail: { "token": "preset:foobar" }`

Ví dụ: `unknown_preset: token 'foobar' (from 'preset:foobar')`.

### 4b. Overwrite soft-gate (MCP)

**Quan sát:** `execute=true&overwrite=true` ghi đè ngay, không cần confirm token — agent dễ quên hỏi user.

Thêm một lớp **mềm** (không phá API cũ hoàn toàn):

| Cách | Mô tả |
|------|-------|
| **A (khuyến nghị)** | Khi `overwrite=true` và có file `exists_on_target` với `content=different` **hoặc** `same`: vẫn cho copy, nhưng nếu thiếu `confirm_overwrite=true` → **không** copy exists; trả `needs_user_confirm=true` + `user_prompt` giống dry-run |
| **B** | Chỉ yêu cầu `confirm_overwrite` khi `content=different` |

Param mới: `confirm_overwrite: bool = false`.

Flow:

```
execute=true, overwrite=true, confirm_overwrite=false
  → missing_on_target: copy OK
  → exists_on_target: SKIP + needs_user_confirm + user_prompt
execute=true, overwrite=true, confirm_overwrite=true
  → copy cả missing + exists (ghi đè)
```

Cập nhật skill: Agent chỉ set `confirm_overwrite=true` **sau khi user đồng ý**.

### 4c. Preset registry

- Endpoint nhẹ: `object="preset:?"` hoặc `list_presets=true` (param riêng trên type=3) → JSON `presets: [{ "name": "mail", "paths": [...] }]`
- Thêm preset tùy chọn (không bắt buộc v1 gaps): `ajax` = `Main/Uploads/AjaxWeb.aspx`, `ClientScript/jAjax.js` (không DLL)

### AC

- [ ] AC-T3-ERR-1: `preset:foobar` → message có `foobar`
- [ ] AC-T3-OW-1: `overwrite=true` không `confirm_overwrite` → không đè exists
- [ ] AC-T3-OW-2: cả hai true → đè được
- [ ] AC-T3-PRE-1: list presets trả `mail` (+ ajax nếu có)

---

## P1-5 — `read_local_file`: abs path tự resolve

### Vấn đề

`file_path` abs đầy đủ + `reference_file=""` → lỗi kiểu “đường dẫn nằm ngoài thư mục dự án” — khó hiểu.

### Thiết kế

1. Nếu `file_path` là absolute và tồn tại:
   - Tự `get_project_root_from_path(file_path)` (cùng resolver type=3)
   - **Không bắt buộc** `reference_file`
2. Nếu `file_path` relative → vẫn **bắt buộc** `reference_file` abs
3. Message lỗi khi fail: nêu rõ thiếu ref vs ngoài root vs không tồn tại

### AC

- [ ] AC-RLF-1: Abs `Main/zccnslkdhtpnc.aspx` không cần `reference_file` → đọc OK
- [ ] AC-RLF-2: Relative `Filter/x.xml` thiếu ref → error `reference_file_required`
- [ ] AC-RLF-3: Không regress `read_option` 1/2/3

---

## P2 — Tiện ích thêm

### 5a. `summary_counts` trên type=3 response

Luôn có:

```json
"summary_counts": {
  "missing_on_target": 1,
  "missing_on_source": 0,
  "exists_same": 4,
  "exists_different": 2,
  "denied": 0,
  "will_copy": 1
}
```

Agent đọc counts trước, tránh dump hết `planned` ra chat.

### 5b. `copy_filter` type=3

| Value | Khi execute |
|-------|-------------|
| `missing` (default nếu overwrite=false) | Chỉ `missing_on_target` |
| `different` | Chỉ exists + `content=different` (cần overwrite+confirm) |
| `all` | missing + exists (cần overwrite+confirm cho exists) |

### 5c. Seed / discover ngoài Controllers

`compare_things` `kind=xml` seed chỉ Controllers — không thấy `Main/*.aspx`, `Templates/Mail`.

Mở rộng **hoặc** document rõ: dùng `kind=folder` + `seed` trên `App_Data` / `Main`.  
Nếu code: thêm `kind=path_seed` quét `App_Data/**`, `Main/**`, `ClientScript/**` theo keyword (max 50 hits).

### 5d. File > 32MB

Unit test + 1 dòng trong response warning `hash_skipped_large_file` khi size > `hash_max_bytes` (đã spec type=3 — **bổ sung test nếu thiếu**).

---

## Phạm vi code (Gemini)

| Module | Việc |
|--------|------|
| `compare_things/` | `inventory` / `list_identical` |
| `clone_things/type3_file_clone.py` (+ service) | dir detect, `expand_dirs`, `max_files`, `confirm_overwrite`, `summary_counts`, `copy_filter`, list presets, error detail |
| `fastbusiness_mcp/mcp_app.py` | Expose params mới |
| Tool mới `search_files` (hoặc tên `grep_files`) | P0-2 |
| `read_local_file` | Abs path resolve |
| `tests/` | AC ở trên |

**Không** đổi mặc định omit identical của folder compare 2 bên (trừ khi bật flag).  
**Không** bắt buộc sửa `docs/doc/clone_things/01`–`14` trước — cập nhật index **sau** khi ship (optional).

---

## Anti-patterns

- Dùng lại Shell `Get-ChildItem` / `Select-String` trên UNC trong skill thay vì inventory/search
- `execute=true` + glob `bin/**` không `max_files`
- Coi directory token như file thiếu
- Dump toàn bộ `planned[]` hàng trăm DLL ra chat agent (dùng `summary_counts` + truncate)

---

## Prompt Gemini (copy-paste)

```text
Implement MCP agent gaps theo docs/doc/gemini/GEMINI-mcp-agent-gaps.md.

P0 bắt buộc:
1) compare_things: inventory=true list 1 folder (tên file, size, mtime) — hết omitted khi list.
2) Tool search_files: grep pattern trên UNC root + glob + max_matches + deny *.f.
3) clone_things type=3: object=dir không báo missing_on_source giả; expand_dirs; max_files default 100 truncate.

P1:
4) error message có token; confirm_overwrite soft-gate; list_presets.
5) read_local_file: absolute file_path tự resolve project root, reference_file optional.

P2 nếu còn thời gian: summary_counts, copy_filter, test file >32MB.

Không regress type=0/1. Không Shell. Tests AC-* trong file spec.
```

---

## Checklist BA / Tester sau khi Gemini xong

- [ ] Inventory `bin` + glob Mail trên AIH — thấy tên DLL
- [ ] Search `acceptSendMail` HungThinh — có hit js/aspx
- [ ] type=3 `object=bin` → lỗi/gợi ý rõ, không missing giả
- [ ] type=3 glob lớn → truncated, không copy ầm
- [ ] overwrite cần `confirm_overwrite` sau khi user OK
- [ ] Đọc abs aspx không cần reference_file
- [ ] Skill `fbo-clone-things` / no-shell: bổ sung map list→inventory, grep→search_files (Gemini hoặc Cursor cập nhật skill sau)
