# FIX — `compare_things` `kind=folder`: summary gọn (chỉ list tên); `compared[]` chỉ khi `detail`

> **File ĐỘC LẬP cho Gemini fix**  
> **Ngày:** 2026-09-11  
> **Phạm vi:** response `kind=folder` (đặc biệt `bin` / `*.dll`); param MCP + tests + docstring tool  
> **Bối cảnh live:** FAHASA `FBISP24\bin` vs AIH `SP228\bin`, `include_glob=*.dll`, `compare_content=true` → JSON ~50KB / 1700+ dòng; phần hữu dụng cho agent gần như chỉ block `summary` (~160 dòng tên file).  
> **Liên quan:** [`FIX-compare-things-diff-only-no-preview.md`](./FIX-compare_things-diff-only-no-preview.md) (tiết kiệm token / chỉ báo lệch).

---

## 0. Prompt Gemini (copy-paste)

```text
Fix compare_things theo docs/doc/doc_fix/FIX-compare_things-folder-summary-vs-detail.md

P0:
1) Thêm param MCP riêng (KHÔNG nhét vào mode=summary|hunks|body):
   - detail: bool, default False cho kind=folder
   - hoặc alias include_compared (cùng nghĩa; chọn 1 tên chính trong schema, alias optional)
2) kind=folder + detail=false (mặc định):
   - Trả đủ summary: files_a/b, missing_on_a/b, different_meta, different_content,
     identical_meta_count / omitted_identical_count, skipped_f_count, truncated, errors
   - Trả message + next_actions top-level
   - compared = [] (hoặc omit field compared — ưu tiên compared=[] để schema ổn định)
3) kind=folder + detail=true:
   - Giữ behavior hiện tại: compared[] per-file (meta size/sha/dates, status, next_actions)
   - max_objects CHỈ cắt compared[], KHÔNG cắt list tên trong summary.*
4) summary.* list tên phải đủ (hoặc nếu quá dài mới cắt + ghi *_omitted / truncated_names rõ ràng).
   Hiện truncated=true vì max_objects=80 trong khi summary vẫn liệt kê nhiều tên — contract phải tách rõ:
   - truncated_compared: so với max_objects khi detail=true
   - truncated_summary_names: chỉ khi list tên bị cắt (nếu có limit riêng)

P1:
5) Optional detail_status (string, default ""): khi detail=true, chỉ emit compared cho status khớp
   (vd "different_content" hoặc "missing_on_b,different_content"). Rỗng = mọi status như hiện tại.
6) Binary DLL trong compared: next_actions KHÔNG dùng review_hunks; dùng investigate_version_dll / noop.
7) Tests: folder mock 5 file missing + 3 different_content + 2 different_meta;
   detail=false → compared rỗng, summary đủ tên; detail=true → len(compared) đúng; max_objects=2 → truncated_compared.
8) Cập nhật docstring MCP compare_things + (nếu có) docs/doc/compare_things README/reference.
9) pytest tests/compare_things/ pass.
```

---

## 1. Vấn đề (repro live)

Call:

```text
compare_things(
  kind="folder",
  folder_a=\\...\FBISP24\bin,
  folder_b=\\...\SP228\bin,
  include_glob="*.dll",
  compare_content=true,
  hash_max_bytes=10485760,
  max_objects=80,
  mode="summary"
)
```

Quan sát:

| Phần response | ~Kích thước | Agent cần để quyết định? |
|---------------|-------------|---------------------------|
| `summary` (list tên `missing_on_*`, `different_meta`, `different_content`) | ~2–4KB / ~160 dòng | **Có** — đủ inventory |
| `compared[]` (mỗi DLL 1 object size/sha/date) | ~45KB+ / 1500+ dòng | **Không** trừ khi đào 1 file |

`mode=summary` hiện vẫn dump full `compared[]` → chat/agent spill file tạm, tốn token, không đúng “chỉ báo lệch”.

Nhiệm vụ “chỉ Flow” không nên buộc so cả `bin`; nhưng **khi** user/agent cố ý so cả folder, mặc định vẫn phải **gọn**.

---

## 2. Tư duy chốt

1. `mode` (`summary|hunks|body`) = độ sâu **diff text** (sql/xml/file text) — **không** dùng lại để bật/tắt `compared` folder.
2. Folder inventory = **2 tầng**:
   - **Tầng 1 (mặc định):** tên file theo bucket trong `summary`.
   - **Tầng 2 (`detail=true`):** per-file meta trong `compared[]`.
3. Cần size/sha **một** DLL → khuyến nghị `kind=file`, không bắt buộc `detail=true` cả bin.

---

## 3. Param mới

| Param | Type | Default | Áp dụng |
|-------|------|---------|---------|
| `detail` | bool | **`false` khi `kind=folder`**; với kind khác: giữ behavior hiện tại (không đổi trừ khi đồng bộ optional) | Bật `compared[]` chi tiết |
| `detail_status` | string | `""` | Chỉ khi `detail=true`: filter status (CSV). Ví dụ `different_content` hoặc `missing_on_b,different_content` |

Alias (optional, không bắt buộc cả hai trong schema): `include_compared` ≡ `detail`.

**Không** đổi default `compare_content` / `hash_max_bytes` trong task này.

---

## 4. Contract response `kind=folder`

### 4.1 `detail=false` (default) — chỉ bản đồ tên

```json
{
  "success": true,
  "kind": "folder",
  "role_a": "reference_clone_from",
  "role_b": "editing",
  "folder_a": "...\\bin",
  "folder_b": "...\\bin",
  "mode": "summary",
  "detail": false,
  "summary": {
    "files_a": 129,
    "files_b": 107,
    "missing_on_b": ["BarcodeLib.dll", "..."],
    "missing_on_a": ["Provider.dll", "..."],
    "different_meta": ["Flow.dll", "..."],
    "different_content": ["Export.dll", "..."],
    "identical_meta_count": 0,
    "omitted_identical_count": 0,
    "skipped_f_count": 0,
    "errors": [],
    "truncated": false,
    "truncated_compared": false,
    "truncated_summary_names": false
  },
  "compared": [],
  "message": "So thư mục B: bin (đang sửa) với thư mục A: bin (nguồn clone): bin thiếu 27 file, khác nội dung: 34 file, khác metadata: 68 file, thiếu ở nguồn A: 5 file.",
  "next_actions": ["copy_missing_to_b", "copy_missing_to_a", "investigate_version_dll"],
  "warnings": [],
  "error_code": null,
  "error": null
}
```

**Bắt buộc:**

- `compared` rỗng (hoặc omit — ưu tiên `[]`).
- `summary.missing_on_*` / `different_*` vẫn là **list tên đầy đủ** (trừ khi có limit tên riêng và `truncated_summary_names=true`).
- `message` + `next_actions` top-level vẫn có.

### 4.2 `detail=true` — thêm `compared[]`

Giữ shape per-item hiện tại (relative_path, status, a/b meta, next_actions, content nếu có).

`max_objects`:

- Chỉ giới hạn **số phần tử `compared`**.
- Khi cắt: `summary.truncated_compared=true` (và/hoặc `truncated=true` tương thích ngược — ghi rõ trong docstring).
- **Không** vì `max_objects` mà cắt list tên trong `summary`.

`detail_status` (P1):

- Parse CSV, trim, case-insensitive match `status`.
- Chỉ những item khớp mới vào `compared`; summary vẫn full buckets.

### 4.3 Binary / DLL

Trong `compared` (khi detail):

| Tình huống | `next_actions` khuyến nghị |
|------------|----------------------------|
| missing_on_b / missing_on_a | `copy_missing_to_b` / `copy_missing_to_a` |
| different_content + `is_binary` | `investigate_version_dll` (cấm `review_hunks`) |
| different_meta only (cùng sha) | `noop` hoặc `investigate_version_dll` nhẹ |

---

## 5. Scope kind khác

| Kind | Task này |
|------|----------|
| `folder` | **P0 bắt buộc** đổi default |
| `file` / `sql` / `table` / `xml` | Không bắt buộc đổi; `detail` có thể ignore hoặc no-op. Không phá contract `compared` hiện có của sql/xml. |

Nếu muốn đồng bộ sau (out of scope P0): sql/xml `mode=summary` chỉ list + counts, `detail=true` mới có hunk ranges — **không** làm trong FIX này trừ khi còn bandwidth.

---

## 6. Tests (bắt buộc)

File gợi ý: `tests/compare_things/test_folder_detail.py` (hoặc mở rộng test folder hiện có).

1. **default detail=false:** `compared == []`; `summary.missing_on_b` chứa đủ tên mock; response size nhỏ (assert không có key sha256 trong body… hoặc assert `"sha256"` không xuất hiện ngoài summary nếu summary không chứa hash — hiện summary chỉ tên, OK).
2. **detail=true:** `len(compared)` = số file non-identical (hoặc đúng filter).
3. **detail=true + max_objects=2:** `len(compared) <= 2`, `truncated_compared` / `truncated` true; `len(summary.missing_on_b)` vẫn full.
4. **detail=true + detail_status=different_content:** mọi item `compared[].status == different_content`.
5. Binary mock: `next_actions` không chứa `review_hunks`.

---

## 7. Docstring / docs

Cập nhật mô tả tool `compare_things`:

- `detail` (folder): mặc định false — chỉ summary list tên; true — kèm `compared[]`.
- Agent: so `bin` lần đầu luôn `detail=false`; cần meta 1 DLL → `kind=file` hoặc `detail=true` + `include_glob` hẹp.

---

## 8. Acceptance

- [ ] Call live `bin` + `*.dll` + `compare_content=true` + **không** truyền `detail` → JSON gọn (cùng lượng thông tin list tên như `summary` hiện tại), `compared=[]`.
- [ ] Cùng call + `detail=true` → có `compared` như behavior cũ (có truncate theo `max_objects`).
- [ ] `max_objects` không cắt `summary.missing_on_*` / `different_*`.
- [ ] pytest `tests/compare_things/` pass.
- [ ] Không phá `kind=sql|xml|file|table` regression.

---

## 9. Non-goals

- Không đổi semantics `missing_on_a` / `missing_on_b` / role_a/b.
- Không disassemble DLL / so assembly version PE.
- Không bắt buộc đổi `mode`.
- Không giảm độ chính xác hash khi `compare_content=true` (vẫn hash khi cần phân loại `different_meta` vs `different_content` để **điền tên vào summary** — chỉ **không serialize** per-file vào `compared` khi `detail=false`).
