# GEMINI — Nâng cấp `clone_things` type=3 (clone file bất kỳ)

> **File độc lập** — gửi Gemini chỉ cần file này.  
> **Không** bắt buộc sửa `01`–`14` / `README` clone_things **trước** khi code. Sau khi ship xong, Gemini **được phép** cập nhật index/`02_tool_api` cho khớp (optional follow-up).  
> **Repo:** `E:\PythonProject\mcp_fbo\`  
> **Không** nhầm với **`mode_read=3`** (thuộc type=1 — full SQL definition JSON).

---

## Mục tiêu

Thêm `clone_things(type=3)`: copy **file bất kỳ** từ `project_source` → `project_target` (relative path / list / glob / preset).

- Default **dry-run** (`execute=false`)
- `execute=true` → chỉ **copy file chưa có** trên target (`overwrite=false` mặc định)
- File đã có → **không đè**; JSON `user_prompt` để Agent hỏi user; chỉ `overwrite=true` sau confirm
- Thay Shell Cursor trên UNC (hay “no exit”)
- **Không** chỉ DLL mail — mọi file trong project (trừ deny list)

---

## So sánh type

| | type=0 | type=1 | **type=3** |
|--|--------|--------|------------|
| Việc | SQL thiếu → `.sql` | Paste ALTER 1 project | **Copy file** |
| `project_target` | Bắt buộc | Rỗng OK | **Bắt buộc** |
| DB | Có | Có | **Không** query SQL — chỉ resolve project root |
| `path_to_pasted` / `mode_*` | Có / N/A | Có | **Bỏ qua** |
| Ghi đích | `.sql` temp | `.sql` | Tree **project_target** |
| Execute | Config DDL | Force false | Param **`execute`** default **false** |

---

## Params

| Param | Required | Default | Ý nghĩa |
|-------|----------|---------|---------|
| `type` | | `0` | **`3`** = file clone |
| `object` | **có** | | Path / list / glob / preset (§ dưới) |
| `project_source` | **có** | | Abs project nguồn |
| `project_target` | **có** | | Abs project đích |
| `execute` | | `false` | `true` = copy thật. Alias: `execute_clone` (chỉ type=3) |
| `overwrite` | | `false` | **`false` (mặc định):** chỉ copy file **chưa có** trên target. **`true`:** mới được ghi đè file đã tồn tại — **chỉ sau khi user xác nhận** (Agent đọc `exists_on_target` / `user_prompt` rồi hỏi lại) |

`path_to_pasted`, `mode_get`, `mode_recursion`, `mode_read` → type=3 **bỏ qua**.

### Parse `object` (token-first — tránh lệch union)

**Không** kiểm tra preset trên cả chuỗi rồi mới `else` split (sẽ làm `mail,App_Data/...` mất preset).

Flow bắt buộc:

```
1. Split object theo `,`  `;`  hoặc newline `\n` → danh sách token (strip từng token; bỏ token rỗng)
2. Với mỗi token:
     a. Bắt đầu bằng `preset:`  → tên = phần sau tiền tố
        - Khớp whitelist preset → bung paths của preset
        - Không khớp → error `unknown_preset` (lập tức)
     b. Token ∈ tên preset tường minh (vd. `mail`) → bung whitelist preset
     c. Token chứa `*` hoặc `?` → glob dưới root_source (relative từ root)
     d. Ngược lại → relative path
3. Union danh sách path → chuẩn hóa `/` (POSIX) → dedupe giữ thứ tự lần đầu xuất hiện
```

Cho phép union: `mail,App_Data/Controllers/Templates/Mail/foo.html`  
tương đương `preset:mail,App_Data/Controllers/Templates/Mail/foo.html`.

**Preset `mail` (v1):**

- `bin/fsdMail.dll`
- `bin/callMailXS.dll`
- `bin/clsFileUpload.dll`
- `bin/zcCallMail.dll` (optional — thiếu source → `missing_on_source`, không fail cả batch)
- `Main/Uploads/AjaxWeb.aspx`
- `Main/Uploads/AjaxWeb_Core.aspx`
- `ClientScript/jAjax.js`

### Tiêu chí `unknown_preset` vs relative path

| Trường hợp | Kết quả |
|------------|---------|
| Token `preset:<tên>` mà `<tên>` không trong registry | **`unknown_preset`** (fail ngay) |
| Token là tên preset đã đăng ký (`mail`, …) | Expand preset |
| Token có `/` hoặc `\` hoặc có phần mở rộng file (`.dll`, `.xml`, `.aspx`, `.js`, `.html`, …) | Luôn coi **relative path** (không phải preset) |
| Token từ đơn (không slash, không extension), **không** khớp preset, và **không** tồn tại file/dir dưới `root_source` | Coi **`unknown_preset`** nếu sau expand **không còn** path hợp lệ nào khác trong `object` |
| Token từ đơn không khớp preset nhưng **tồn tại** trên source disk | Coi **relative path** |

- Absolute ngoài project / `..` thoát root → `path_outside_project`
- List rỗng sau expand → `invalid_object`

### Resolve root (+ fallback unit test)

1. Reuse `find_connect_by_path.path_resolver.get_project_root_from_path(p)`.
2. **Fallback (bắt buộc cho pytest `tmp_path`):** nếu hàm trả `None` nhưng `Path(p).is_dir()` → dùng `str(Path(p).resolve())` làm project root.
3. Không bắt buộc mở SQL connection.

Fixture test chỉ cần tạo cây `bin/`… dưới `tmp_path` — **không** bắt buộc có `Web.config` / `App_Data`.

### `execute` coercion

`false` / `"false"` / `0` / thiếu → dry-run  
`true` / `"true"` / `1` → copy

Ưu tiên: nếu `execute_clone` được truyền (không `None`) → dùng giá trị đó; không thì dùng `execute`.

### Signature service (mở rộng)

`clone_things/service.py` — thêm tham số tương thích `mcp_app` + config cũ:

```python
def clone_things(
    ...,
    execute: bool | str = False,
    execute_clone: bool | str | None = None,
    ...
) -> dict:
    ...
```

- Type=0/1: `execute` / `execute_clone` **không** dùng để bật copy file (giữ semantics cũ / force false DDL như hiện tại).
- Type=3: coerce như trên → truyền vào `run_type3(...)`.

---

## Flow

### Quy tắc ghi đè (BẮT BUỘC — BA)

| Tình huống | Hành vi |
|------------|---------|
| Target **chưa có** file (`missing_on_target`) | `execute=true` → **được** `copy2` |
| Target **đã có** file (`exists_on_target`) | **Không đè** khi `overwrite=false` (default). Đưa vào `exists_on_target[]` + `needs_user_confirm=true` + `user_prompt` / `agent_message` để **Agent hỏi user** |
| User đồng ý ghi đè | Gọi lại `execute=true`, **`overwrite=true`** (có thể kèm `object` chỉ các path user chọn) → lúc đó mới `copy2` đè |
| Content giống hay khác | Vẫn so `same` / `different` **để thông tin** trong `planned` / `exists_on_target[].content` — **không** tự đè chỉ vì `different` |

```
1. Validate type=3, object, project_source, project_target (absolute)
2. Resolve root_source, root_target (kèm fallback dir)
3. Expand object → unique relative list (POSIX `/`)
4. For each rel:
     src = root_source/rel ; dst = root_target/rel
     missing_on_source | missing_on_target | exists_on_target (+ content same|different) | denied
5. execute=false → return planned[]; KHÔNG ghi target
6. execute=true + overwrite=false (default):
     - chỉ copy missing_on_target → copied[]
     - exists_on_target → KHÔNG copy; điền exists_on_target[] + needs_user_confirm + user_prompt
7. execute=true + overwrite=true (sau user xác nhận):
     - copy missing_on_target và exists_on_target (ghi đè)
8. lỗi I/O → failed[] chi tiết
```

- Copy **binary** — không đổi encoding/CRLF
- Mọi trường `relative` trong JSON → **chuẩn hóa POSIX `/`** (không trả `\`)

### So sánh `same` / hash

| Điều kiện | Cách so |
|-----------|---------|
| File ≤ 32MB (`hash_max_bytes`, default 33554432) | SHA-256; `same` khi hash bằng nhau |
| File **> 32MB** | **Không** hash; warning `hash_skipped_large_file` |

**Tiêu chí `status = "same"` khi > 32MB:**

- `size_source == size_target` **và**
- `abs(mtime_source - mtime_target) < 1.0` giây

Trong `planned[]` cho case này: `hash_source: null`, `hash_target: null` (có thể thêm `mtime_source` / `mtime_target` optional).

Nếu size khác **hoặc** |Δmtime| ≥ 1.0s → `different`.

### Deny

| Rule | Hành vi |
|------|---------|
| `*.f` | `skipped_denied` / `denied` |
| Preset `mail` | **Không** gồm `EmailConfig.xml` |
| User chỉ đúng `Options/EmailConfig.xml` | Cho phép |
| User chỉ đúng `Web.config` | Cho phép; preset không include |

---

## JSON response

```json
{
  "success": true,
  "spec_version": "1.0",
  "type": 3,
  "mode": "file_clone",
  "project_source": "...",
  "project_target": "...",
  "object": "...",
  "execute": false,
  "overwrite": false,
  "needs_user_confirm": true,
  "planned": [
    {
      "relative": "bin/fsdMail.dll",
      "status": "missing_on_target",
      "size_source": 12345,
      "size_target": null,
      "hash_source": "...",
      "hash_target": null
    },
    {
      "relative": "ClientScript/jAjax.js",
      "status": "exists_on_target",
      "content": "different",
      "size_source": 100,
      "size_target": 90,
      "hash_source": "...",
      "hash_target": "..."
    }
  ],
  "will_copy": ["bin/fsdMail.dll"],
  "exists_on_target": [
    {
      "relative": "ClientScript/jAjax.js",
      "content": "different",
      "size_source": 100,
      "size_target": 90
    }
  ],
  "copied": [],
  "skipped_exists": ["ClientScript/jAjax.js"],
  "skipped_denied": [],
  "missing_on_source": [],
  "failed": [],
  "warnings": [],
  "user_prompt": "Các file sau ĐÃ CÓ trên project đích (không tự ghi đè): ClientScript/jAjax.js (content=different). Bạn có muốn ghi đè không? Nếu có, Agent gọi lại clone_things type=3 với execute=true và overwrite=true (object có thể chỉ các path được chọn).",
  "agent_message": "Dry-run/execute xong phần thiếu. Có file đã tồn tại → PHẢI hỏi user trước khi overwrite=true. Không tự đè.",
  "meta": {
    "execute": false,
    "overwrite": false,
    "file_count": 0,
    "hash_max_bytes": 33554432,
    "elapsed_ms": 0
  }
}
```

`status` trong `planned[]`: `missing_on_source` | `missing_on_target` | `exists_on_target` | `denied`  
`content` (khi `exists_on_target`): `same` | `different` (theo hash hoặc size+mtime >32MB).

| Field | Ý nghĩa |
|-------|---------|
| `will_copy` | Path sẽ (hoặc đã) copy khi `execute` — chỉ **chưa có** trên target trừ khi `overwrite=true` |
| `exists_on_target` | File đích **đã có** — **không** copy khi `overwrite=false` |
| `skipped_exists` | Relative đã bỏ qua vì tồn tại (alias list string từ `exists_on_target`) |
| `needs_user_confirm` | `true` nếu `exists_on_target` không rỗng và chưa `overwrite` |
| `user_prompt` | **Câu hỏi tiếng Việt** Agent **phải** đưa ra hỏi user (không tự quyết ghi đè) |
| `agent_message` | Hướng dẫn ngắn cho Agent |

Khi `execute=true`, `overwrite=false`: chỉ điền `copied[]` cho `missing_on_target`; mọi file đã có → `skipped_exists` / `exists_on_target` + `user_prompt`.  
Khi `execute=true`, `overwrite=true`: copy cả missing + exists (ghi đè); `needs_user_confirm=false`.

### `failed[]` (bắt buộc khi copy lỗi)

Mỗi phần tử là object, không chỉ string path:

```json
"failed": [
  { "relative": "bin/fsdMail.dll", "error": "Permission denied" }
]
```

Ví dụ nguyên nhân: DLL bị IIS khóa, Permission denied UNC, disk full, path quá dài Windows.  
`error` = message ngắn từ exception / OS (`str(exc)` hoặc tương đương); Agent dùng để báo user xử lý.

`copied` / `will_copy` / `skipped_exists` / `missing_on_source` / `skipped_denied`: **ưu tiên list string** (POSIX); `exists_on_target` = list object; **`failed` luôn object** `{relative, error}`.

### Error codes

| Điều kiện | `error_code` |
|-----------|--------------|
| `type` ∉ `{0,1,3}` | `unsupported_type` |
| Thiếu object / project_* | `invalid_object` / `invalid_project_*` |
| Path escape | `path_outside_project` |
| Preset lạ (`preset:x` hoặc từ đơn không path) | `unknown_preset` |

---

## Code phạm vi (Gemini)

| File | Việc |
|------|------|
| `clone_things/type3_file_clone.py` | **Mới** — expand (token-first), plan, copy, failed[] |
| `clone_things/service.py` | `if type == 3: return run_type3(...)`; signature + `execute` / `execute_clone` |
| `fastbusiness_mcp/mcp_app.py` | `type` + `execute: bool = False` + `overwrite: bool = False`; validate `{0,1,3}` |
| `tests/clone_things/test_type3_file_clone.py` | **Mới** — tmp_path (không bắt buộc Web.config) |

**CẤM** nhét logic vào `type0_flow.py` / `type1_flow.py`.  
**CẤM** Shell / subprocess copy.  
**CẤM** query SQL chỉ để copy file.  
**CẤM** regress type=0/1.

---

## Anti-patterns

1. Default `execute=true`
2. **Tự ghi đè** file đã có khi `different` / không hỏi user
3. `overwrite=true` mặc định hoặc Agent tự bật không có xác nhận user
4. Shell `Copy-Item` / `xcopy`
5. Trả base64/binary trong JSON
6. Hash cả `bin/` không filter `object`
7. Preset tự kéo `EmailConfig.xml`
8. Đổi line ending khi copy
9. Nhầm `mode_read=3` ↔ `type=3`
10. Parse preset **trước** split (làm hỏng `mail,path/...`)
11. Trả `relative` dạng `\` trên Windows
12. Thiếu `user_prompt` / `needs_user_confirm` khi còn `exists_on_target`

---

## AC / Tests

| ID | Expected |
|----|----------|
| AC-T3-01 | dry-run thiếu target → `missing_on_target`; disk đích không đổi |
| AC-T3-02 | `execute=true` chỉ tạo file **thiếu**; `copied` |
| AC-T3-03 | file đã có target + `overwrite=false` → **không** đè; `exists_on_target` + `needs_user_confirm` + `user_prompt` |
| AC-T3-03b | `overwrite=true` sau confirm → mới ghi đè; `copied` gồm path đó |
| AC-T3-04 | missing source → `missing_on_source` |
| AC-T3-05 | glob chỉ match |
| AC-T3-06 | preset `mail` đúng whitelist |
| AC-T3-07 | `../` → `path_outside_project` |
| AC-T3-08 | `*.f` denied |
| AC-T3-09 | type=0/1 regression pass |
| AC-T3-10 | UNC optional — không Shell |
| AC-T3-11 | `mail,App_Data/.../foo.html` → preset expand **+** path thêm |
| AC-T3-12 | `preset:unknown` → `unknown_preset` |
| AC-T3-13 | tmp_path chỉ có `bin/` (không Web.config) → resolve root OK qua fallback |
| AC-T3-14 | file > 32MB: `same` theo size + \|Δmtime\| < 1s; hash null + warning |
| AC-T3-15 | copy Permission denied → `failed: [{relative, error}]` |
| AC-T3-16 | mọi `relative` trong JSON dùng `/` |
| AC-T3-17 | `different` nhưng đã có target + không overwrite → vẫn **không** copy; có `user_prompt` |

Pytest: `tmp_path` 2 fake projects — không bắt buộc `\\172.168.5.14` trong unit test.

---

## Checklist

- [ ] `type3_file_clone.py` + branch service (`execute` / `execute_clone` / `overwrite`)
- [ ] `mcp_app.py`: type ∈ {0,1,3}, `execute`, `overwrite=False`
- [ ] **Chỉ copy missing**; exists → `exists_on_target` + `user_prompt` hỏi user
- [ ] `overwrite=true` mới đè (sau confirm)
- [ ] Parse token-first; `preset:`; union; POSIX relative
- [ ] Preset `mail`; dry-run; `copy2`; deny `.f`; `failed[]` object
- [ ] Root fallback khi không có Web.config
- [ ] Large-file same = size + mtime < 1s
- [ ] JSON + tests TC-T3-* (gồm AC-T3-11…17)
- [ ] Không đổi semantics type=0/1
- [ ] (Optional sau ship) Cập nhật `02_tool_api.md` / README tool list

---

## Prompt Gemini (copy nguyên)

```text
Bạn implement MCP clone_things type=3 theo ĐÚNG file spec độc lập này:

E:\PythonProject\mcp_fbo\docs\doc\gemini\GEMINI-clone_things-type3-file-clone.md

Repo: E:\PythonProject\mcp_fbo\

Yêu cầu:
1. type=3 = clone FILE bất kỳ (relative/glob/preset) project_source → project_target — không chỉ mail DLL.
2. Default execute=false (dry-run). execute=true → shutil.copy2 CHỈ file chưa có trên target.
3. File ĐÃ CÓ trên target: KHÔNG ghi đè (overwrite=false mặc định). Trả exists_on_target + needs_user_confirm=true + user_prompt (tiếng Việt) để Agent hỏi user. Chỉ khi user đồng ý mới gọi lại overwrite=true.
4. Module MỚI clone_things/type3_file_clone.py — KHÔNG sửa logic trong type0_flow / type1_flow.
5. Parse object TOKEN-FIRST (split rồi mới preset/glob/path) — hỗ trợ mail,path/... và preset:mail.
6. Signature service: execute + execute_clone (alias) + overwrite=False.
7. Resolve root: get_project_root_from_path; nếu None và path.is_dir() → fallback resolve().
8. File >32MB: content same = size bằng + |Δmtime|<1s; hash null + warning hash_skipped_large_file.
9. failed[] = [{relative, error}, ...] khi copy lỗi.
10. Mọi relative trong JSON chuẩn hóa POSIX /.
11. Không Shell/subprocess. Không query SQL chỉ để copy file.
12. Không nhầm mode_read=3 (type=1) với type=3.
13. mcp_app.py: type ∈ {0,1,3}, execute=False, overwrite=False.
14. Preset "mail" theo bảng trong spec; không tự copy EmailConfig.xml.
15. Deny *.f. Chặn path .. thoát root.
16. tests/clone_things/test_type3_file_clone.py (tmp_path, không bắt buộc Web.config) — gồm case không đè + user_prompt.
17. Không regress type=0 / type=1.
18. KHÔNG bắt buộc sửa docs 01–14 trước khi code. Spec đủ trong file này.

Reuse: find_connect_by_path.path_resolver.get_project_root_from_path ; formatter pattern clone_things.

Trả lời: diff files + lệnh pytest.
```
