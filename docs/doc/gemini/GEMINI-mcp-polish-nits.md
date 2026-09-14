# GEMINI — MCP polish nits (warning + user_prompt)

> **File độc lập** — gửi Gemini chỉ cần file này.  
> **Repo:** `E:\PythonProject\mcp_fbo\`  
> **Bối cảnh:** Residual DX ([`GEMINI-mcp-dx-residual.md`](./GEMINI-mcp-dx-residual.md)) **đã PASS**.  
> Spec này chỉ **polish 2 nits** (không chặn dùng) sau verify 2026-09-14.

**Không** đổi priority scan / `planned` sample / `confirm_overwrite` / inventory.  
**Không** regress type=0/1. **Không** Shell.

---

## Nit 1 — `search_files`: warning truncated đủ thông tin

### Quan sát

Khi `truncated=true`, `truncated_reason=max_files`, response đã có:

- `files_scanned`, `files_candidate` (vd. 100 / 2378)
- `warnings: ["Reached max_files limit (100)"]`

Agent / user **không** thấy ngay “còn bao nhiêu chưa mở” và “nên làm gì”.

### Hành vi đúng

Khi `truncated_reason == "max_files"`:

```text
Reached max_files ({files_scanned}); {not_opened} candidates not opened (files_candidate={files_candidate}). Narrow root/include_glob or raise max_files.
```

Trong đó `not_opened = max(0, files_candidate - files_scanned)`.

Bổ sung (khuyến nghị) khi **đồng thời** `matches` rỗng:

```text
No matches in scanned files; remaining candidates were not opened — do not conclude "not found" without narrowing root/glob or increasing max_files.
```

Khi `truncated_reason == "max_total_matches"`: giữ/đổi message tương ứng (đã đủ matches; truncated vì cap matches) — không bắt buộc câu “not opened” nếu đã scan hết candidate.

### AC

- [ ] AC-NIT-SF-1: Controllers + `acceptSendMail` + max_files=100 → warning chứa `candidates not opened` **và** số = `files_candidate - files_scanned` (vd. 2278)
- [ ] AC-NIT-SF-2: ClientScript hẹp không truncated → warnings `[]` như cũ
- [ ] AC-NIT-SF-3: truncated + matches rỗng → có câu cảnh báo không kết luận "not found"

---

## Nit 2 — type=3: `user_prompt` truncate theo sample (giống `planned`)

### Quan sát

`bin/**/*.dll`, `max_files=20`, `planned` đã sample **10** + `planned_omitted=10`, nhưng `user_prompt` vẫn liệt kê **dài** hầu hết file `exists_on_target` (19+ tên) → token / chat phình dù planned đã gọn.

### Hành vi đúng

Khi `truncated=true` **hoặc** `meta.planned_omitted > 0`:

1. `user_prompt` chỉ liệt kê file exists nằm trong **planned sample** (cùng tập đã trả trong `planned[]` / sample exists), **không** dump đủ processed/`max_files` names.
2. Cuối prompt thêm 1 câu summary:

```text
… và N file exists khác đã ẩn (truncated). Xem summary_counts / gọi lại với object hẹp hoặc tăng planned_sample_size nếu cần xem đủ tên.
```

`N` = số exists bị ẩn khỏi prompt (processed exists − số exists hiện trong prompt).

3. Khi **không** truncated: `user_prompt` giữ như hiện tại (liệt kê đủ exists cần confirm).

Optional cùng rule cho `agent_message` nếu đang nhúng list dài (thường chỉ `user_prompt`).

### Không đổi

- `summary_counts` vẫn full trên tập processed (≤ `max_files`).
- `confirm_overwrite` flow không đổi.
- `exists_on_target[]` trong JSON: **được** truncate theo cùng sample như `planned` khi truncated (khuyến nghị đồng bộ với planned sample để JSON gọn); nếu giữ full array thì **ít nhất** `user_prompt` phải ngắn.

Khuyến nghị: truncate **cả** `exists_on_target` / `skipped_exists` trong JSON khi truncated (đã có `summary_counts`), đồng bộ `planned_omitted` semantics.

### AC

- [ ] AC-NIT-T3-1: glob `bin/**/*.dll` max_files=20 → `len(planned)≤10` (đã có) **và** `user_prompt` không liệt kê > ~sample exists (không còn 15–20 tên); có câu “N file exists khác đã ẩn”
- [ ] AC-NIT-T3-2: Mail `*.html` không truncated → `user_prompt` vẫn liệt kê đủ exists (vd. 1 file) như cũ
- [ ] AC-NIT-T3-3: `summary_counts` không đổi sai vì truncate prompt

---

## Phạm vi code

| Module | Việc |
|--------|------|
| `search_files` | Format `warnings[]` khi truncated |
| `clone_things` type=3 | Rút `user_prompt` (+ optional `exists_on_target` JSON) khi truncated |
| `tests/` | AC-NIT-SF-* , AC-NIT-T3-* |

---

## Prompt Gemini (copy-paste)

```text
Implement docs/doc/gemini/GEMINI-mcp-polish-nits.md only.

1) search_files: when truncated_reason=max_files, warning must include
   "{not_opened} candidates not opened (files_candidate=…)" and suggest narrow root/glob.
   If also matches empty, warn not to conclude not-found.

2) clone_things type=3: when planned is truncated, user_prompt must NOT list all exists
   — only sample (aligned with planned) + "N file exists khác đã ẩn".
   Prefer also truncate exists_on_target JSON to sample; keep summary_counts.

No regress residual DX / gaps. Tests AC-NIT-*.
```

---

## Checklist BA / Tester

- [ ] Warning search Controllers truncated có số candidates not opened
- [ ] user_prompt bin glob truncated ngắn + có N ẩn
- [ ] Case không truncated không đổi hành vi cũ
