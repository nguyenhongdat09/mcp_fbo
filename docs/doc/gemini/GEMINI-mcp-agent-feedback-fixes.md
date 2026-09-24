# GEMINI — Fix 3 issue từ feedback agent thực tế (mode_read truncate / search_files hint / paste artifacts)

> **Vai trò:** BA + Tester — file spec để **Gemini implement**.
> **Nguồn:** feedback agent làm UR `\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Dir\DDVTran.xml` (proc `FastBusiness$APV$PostAuthorize`, `FastBusiness$APV$UnPostAuthorize`, `zc_ReloadDDVTranSanh`), đã verify lại bằng code + call log + reproduce trực tiếp.
> **Phạm vi code:** [`clone_things/type1_flow.py`](../../../clone_things/type1_flow.py), [`clone_things/db_ops.py`](../../../clone_things/db_ops.py), [`clone_things/file_manager.py`](../../../clone_things/file_manager.py), [`clone_things/type0_flow.py`](../../../clone_things/type0_flow.py), [`search_files/service.py`](../../../search_files/service.py), `config.yaml`.

---

## 0. Kết luận một câu

3 việc: **(A)** propagate cờ `truncated` của `summary_object` + bật `mode_read_full_max_chars` để spill definition lớn ra file; **(B)** warning `max_files` của `search_files` thêm gợi ý thu hẹp **cụ thể**; **(C)** strip marker `-- clone_things` cũ trong script fetch về + tạo section `USE [sys]` **lazy** chỉ khi có object sys.

---

## 1. Bằng chứng đã verify (đừng fix sai chỗ)

| # | Agent báo | Kết quả kiểm chứng |
|---|-----------|--------------------|
| A | `mode_read=3` cắt giữa proc dài — PostAuthorize 11k chars mất ~10k | **Server KHÔNG cắt.** Reproduce trực tiếp trả đủ `chars: 11337`, kết thúc `END`, không `definition_truncated`. Log `mcp-20260918.jsonl` 08:37: response ~25k < `response_guard.max_chars` 60000. `mode_read_full_max_chars` default `0` (không cap) và không config nào set. → Vết cắt là **client-side** (host agent truncate tool result). Server không biết được — fix đúng là mục A dưới đây (spill sớm + propagate flag), **không phải** "nâng cap". |
| B | `search_files` folder 5.276 file chạm `max_files=200` → truncate | **Đúng.** Log 08:35:39: `max_files=200`, `files_candidate=5276`, `scanned=200`, `truncated=true`. Warning đã có 2 dòng ("Narrow root/include_glob or raise max_files" + "do not conclude not found") — thiếu gợi ý **cụ thể**. |
| C | Paste lặp `-- clone_things type=1:` 3 dòng liên tiếp + đuôi `USE [HAOHOA_FBISP2421_S]` | **Đúng cả hai.** `E:\SQL Temp\haohoa_apv_tmp.sql` (call 08:39, `pasted_n=2`, `skipped=0`): `UnPostAuthorize` có 2 dòng marker liên tiếp → marker cũ đã **baked vào `sys.sql_modules.definition`** khi user F5 file paste trước, fetch lại mang theo → prepend thêm → cộng dồn +1 mỗi chu kỳ. Đuôi file luôn có `USE [<sys_db>]\nGO` kể cả khi 0 object sys. |

---

## 2. Issue A — definition bị cắt LẶNG khi > 50k (bug thật ẩn sau report của agent)

### Hiện trạng code

- `clone_things/db_ops.py` `fetch_object_script` (nhánh routine ~L248-260): gọi `svc.summary_object(mode="full")` **không truyền `max_full_chars`** → default **50.000** trong `summary_bridge.summary_object`. Response có `truncated`, `truncated_at_char`, `meta.estimated_full_chars` nhưng `fetch_object_script` chỉ lấy `res["definition"]` → **bỏ cờ truncated**.
- `type1_flow.py`:
  - `mode_read=3` (~L428-457): cap riêng `mode_read_full_max_chars` (default `0` = tắt) + đã có cơ chế spill ra `definition_path` khi cap bật — **nhưng** không hề biết script đã bị cắt từ upstream (50k).
  - `mode_read=0` (~L487-535): ghi `out_script` vào `.sql` — proc > 50k → **file .sql chứa ALTER bị cụt**, user F5 → proc chết. Đây là hậu quả nặng nhất.

### Spec fix

| Rule | Chi tiết |
|------|----------|
| A1 | Trong `fetch_object_script` (nhánh routine): sau `summary_object(mode="full")`, nếu `res.get("truncated")` → **fallback** fetch `OBJECT_DEFINITION(OBJECT_ID(...))` trực tiếp (dùng lại pattern nhánh Trigger ~L227-246: `get_connection_config` + `execute_query`, không cap). Ưu tiên fallback thay vì truyền `max_full_chars` lớn — `OBJECT_DEFINITION` trả nvarchar(max) đủ mọi độ dài, không phụ thuộc ngưỡng. |
| A2 | Nếu fallback cũng fail → giữ script cụt nhưng **bắt buộc** trả kèm flag: đổi signature `fetch_object_script` trả `(script, meta)` hoặc dict `{script, truncated_upstream: bool}` — chọn 1 kiểu, cập nhật mọi call site (`type0_flow`, `type1_flow` cả 3 mode). |
| A3 | `type1_flow`: khi `truncated_upstream` → `warnings.append(f"definition_truncated_upstream: {full_item_name} (>{n} chars, xem definition_path/mode_read=0)")`; `mode_read=3` set `analyzed_item["definition_truncated"]=True` + spill `definition_path` nếu spill được (tái dùng block spill hiện có). |
| A4 | Bật spill sẵn cho definition lớn: thêm `mode_read_full_max_chars: 15000` vào `clone_things` section của `config.yaml` (comment rõ: vượt ngưỡng → spill full body ra `definition_path`, agent đọc bằng `read_local_file` — né client-side truncation). Rebuild exe sau khi đổi config/code. |
| A5 | `agent_message` `mode_read=3`: khi có item `definition_truncated`/`definition_path` → nói rõ "definition đầy đủ nằm ở `definition_path`, đọc tiếp bằng read_local_file; hoặc dùng mode_read=0". |

### Acceptance

| ID | Given | Then |
|----|-------|------|
| AC-A1 | Proc 11k (PostAuthorize) `mode_read=3` | `definition` đủ ~11.3k chars, không truncated (giữ nguyên hành vi hiện tại) |
| AC-A2 | Proc > 50k `mode_read=0` | File .sql chứa đủ body (OBJECT_DEFINITION fallback), `line_end` khớp, không cụt giữa chừng |
| AC-A3 | Proc > 50k `mode_read=3` | `definition_truncated` + `definition_path` trỏ file full body + warnings nêu rõ |
| AC-A4 | `mode_read_full_max_chars: 15000` + proc ~11k | Không spill (dưới ngưỡng); proc > 15k → spill + `definition_path` |

---

## 3. Issue B — `search_files` truncated: warning thêm gợi ý thu hẹp cụ thể

### Hiện trạng code

`search_files/service.py` — 3 nhánh warning khi `truncated_reason == "max_files"`:

- content: ~L679-689
- definition: ~L475-485
- references: ~L570-576

Warning hiện chỉ nói generic: `"Reached max_files (N); M candidates not opened (files_candidate=K). Narrow root/include_glob or raise max_files."` — agent phải tự đoán hẹp thế nào.

### Spec fix

| Rule | Chi tiết |
|------|----------|
| B1 | Thêm helper `_narrow_hint(candidates, scanned_rel_paths, pattern_or_symbol) -> str`: (a) group candidates **chưa mở** theo top-level dir (segment đầu của `rel_path`), lấy top 3 kèm count; (b) nếu pattern/symbol trông giống identifier (`^[A-Za-z_][A-Za-z0-9_$]*$`, vd `DDVTran`) → gợi ý filename glob `*<token>*`. |
| B2 | Append hint vào warning `max_files` hiện có (cả 3 mode), vd: `"hint: 4.2k/5.1k unopened candidates nam trong 'App_Data/Controllers' (top: Controllers 4.2k, bin 0.6k) — thu root='.../Controllers/Filter' hoac include_glob='*DDVTran*'"`. Giữ nguyên 2 warning cũ, hint là dòng thứ 3 hoặc nối tiếp — chốt: **1 warning mới `narrow_hint`** để dễ test. |
| B3 | Không tính lại file — `candidates` list đã có sẵn trong RAM (đã enumerate + sort), chỉ group + count. O(n) duyệt list. |

### Acceptance

| ID | Given | Then |
|----|-------|------|
| AC-B1 | root=project (5.2k file), `max_files=200`, pattern `DDVTran` | `truncated=true` + warnings chứa `narrow_hint` với top dir + `include_glob='*DDVTran*'` |
| AC-B2 | Không truncated | Không có `narrow_hint` |
| AC-B3 | pattern không phải identifier (có space/ký tự lạ) | hint chỉ có top-dir, không có filename-glob |

---

## 4. Issue C — `clone_things` paste: lặp marker header + đuôi `USE [sys]` thừa

### C1. Marker `-- clone_things` cộng dồn vào definition

**Root cause:** `append_script_block` (`file_manager.py` ~L475-482) ghi `-- clone_things type=1: <obj> | ...` **trước** `ALTER PROC`. User F5 file → SQL Server lưu comment đó **vào `sys.sql_modules.definition`** (comment trước ALTER thuộc batch text). Lần paste sau `fetch_object_script` trả definition **đã chứa marker cũ** → prepend thêm marker mới → +1 dòng mỗi chu kỳ paste→F5 (user thấy 3 = 2 stored + 1 mới).

**Spec fix:**

| Rule | Chi tiết |
|------|----------|
| C1.1 | Trong `append_script_block`, sau khi `clean_script` normalize newline, strip mọi dòng khớp `^[ \t]*--[ \t]*clone_things([ \t]+type=1)?[ \t]*:[^\n]*$` (multiline, case-insensitive) trước khi build `body`/prepend `header_line`. Marker là artifact do chính tool sinh → strip toàn bộ occurrence là an toàn (giữ comment banner của user như `-- ====` nguyên vẹn). |
| C1.2 | Idempotent: paste cùng object N lần (kể cả sau khi def đã chứa marker) → file luôn chỉ **1** dòng marker mới nhất. |

### C2. `USE [sys_db]` treo cuối file dù không có object sys

**Root cause:** `ensure_use_db_sections` được gọi **eager** với cả `app_db_name` + `sys_db_name`:

- `type1_flow.py` ~L100-101 (upfront, trước vòng lặp object)
- `type0_flow.py` ~L111 (upfront)
- `file_manager.py` `append_script_block` ~L461-462 (mỗi object, truyền cả hai tên)

→ file nào cũng kết thúc `USE [<sys_db>]\nGO`. Script không sai (mọi ALTER app đã chạy trước) nhưng sau F5 context tab SSMS = DB sys → query tay tiếp theo nhầm DB.

**Spec fix (lazy sys section):**

| Rule | Chi tiết |
|------|----------|
| C2.1 | Upfront call chỉ ensure **app**: `type1_flow` → `ensure_use_db_sections(output_file, app_db_name=source_app_db)`; `type0_flow` → chỉ `app_db_name=target_app_db`. |
| C2.2 | `append_script_block`: tính `is_sys = (str(db).lower() == "sys")` **trước** đoạn ensure; gọi `ensure_use_db_sections(file_path, app_db_name=app_db_name, sys_db_name=(sys_db_name if is_sys else ""))`. → Object sys đầu tiên mới tạo section `USE [sys]`; app-only run → file sạch, không đuôi thừa. |
| C2.3 | Giữ nguyên logic insert sys section **trước** dòng `-- not found in 2 project:` (`ensure_use_db_sections` ~L366-375) và logic insert block app trước `USE sys` / sys sau `USE sys` — chỉ đổi **thời điểm tạo** section. |
| C2.4 | File chỉ có object sys: `USE [app]` vẫn ở top (default section), `USE [sys]` tạo khi append object sys đầu tiên — hành vi giống hiện tại, chỉ khác app-only case. |

### Acceptance

| ID | Given | Then |
|----|-------|------|
| AC-C1 | Def trên DB đã chứa `-- clone_things type=1:` | Paste `mode_read=0` → file chỉ 1 marker mới; marker cũ biến mất khỏi block |
| AC-C2 | Paste 2 object app | File kết thúc sau `GO` cuối block — **không** có `USE [<sys_db>]` |
| AC-C3 | Paste object app + sys | `USE [app]` top, `USE [sys]` xuất hiện đúng 1 lần trước block sys đầu tiên |
| AC-C4 | File đã có `USE [sys]` từ run trước + paste thêm app | Không duplicate `USE [sys]`; block app vẫn chèn trước marker sys |

---

## 5. Test cases (gợi ý thêm vào `tests/`)

| ID | File | Mô tả |
|----|------|-------|
| TC-A1 | `tests/clone_things/` | Mock `summary_object` trả `truncated=True` → `fetch_object_script` fallback `OBJECT_DEFINITION` (assert gọi execute_query đúng SQL) |
| TC-A2 | `tests/clone_things/` | `mode_read=3` + `mode_read_full_max_chars` nhỏ → `definition_path` tồn tại, file chứa full body, `definition_truncated=True` |
| TC-B1 | `tests/test_search_files.py` | Fake candidate list nhiều dir → `narrow_hint` có top dir + filename glob từ pattern identifier |
| TC-C1 | `tests/clone_things/test_type1_paste_for_edit.py` | Script input chứa sẵn 2 dòng `-- clone_things` marker → append xong file chỉ 1 marker |
| TC-C2 | `tests/clone_things/test_type1_paste_for_edit.py` | Paste app-only → EOF không có `USE [sys]`; paste app+sys → `USE [sys]` đúng vị trí trước block sys |

---

## 6. Implementation checklist (Gemini)

- [ ] `db_ops.fetch_object_script`: detect `truncated` → fallback `OBJECT_DEFINITION`; signature trả kèm `truncated_upstream` (cập nhật call sites type0/type1)
- [ ] `type1_flow` mode_read=3 + mode_read=0: propagate `definition_truncated` + warnings + spill reuse
- [ ] `config.yaml`: thêm `clone_things.mode_read_full_max_chars: 15000`
- [ ] `search_files/service.py`: helper `_narrow_hint` + gọi ở 3 nhánh truncated `max_files`
- [ ] `file_manager.append_script_block`: strip marker `clone_things` khỏi script trước khi prepend
- [ ] `type1_flow` / `type0_flow` / `append_script_block`: lazy `USE [sys]` (chỉ khi object sys)
- [ ] Unit tests TC-A/B/C
- [ ] Rebuild exe (`build_onedir.bat`) + deploy `E:\fastbusiness_mcp\` để config mới có hiệu lực

## 7. Ngoài phạm vi

- **Không** "nâng cap" mode_read=3 cho client-side truncation — server đã trả đủ; cách né là spill `definition_path` (A4).
- Không đổi `response_guard.max_chars` 60k.
- Không đổi priority sort `prefer_name_match` của `search_files`.
- Không bỏ marker `-- clone_things` mới (vẫn cần để `object_already_in_sql_file`/`old_pat` nhận diện block) — chỉ strip marker **cũ trong script fetch về**.

---

## 8. Prompt Gemini (copy-paste)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

Implement theo docs/doc/gemini/GEMINI-mcp-agent-feedback-fixes.md — 3 issue:

A) clone_things: definition >50k bị cắt lặng vì fetch_object_script bỏ flag
   truncated của summary_object(mode="full"). Fallback OBJECT_DEFINITION khi
   truncated; propagate definition_truncated/warnings; thêm
   clone_things.mode_read_full_max_chars: 15000 vào config.yaml để spill
   definition lớn ra definition_path (cơ chế spill đã có sẵn trong type1_flow).

B) search_files: khi truncated do max_files, thêm warning narrow_hint cụ thể —
   top-level dir của candidates chưa mở + include_glob filename từ pattern
   identifier. Không enumerate lại file, group trên list candidates có sẵn.

C) clone_things paste:
   - append_script_block strip mọi dòng '-- clone_things...' có sẵn trong script
     fetch về trước khi prepend header mới (marker cũ bị baked vào
     sys.sql_modules.definition sau khi user F5 → cộng dồn mỗi chu kỳ).
   - USE [sys_db] chỉ tạo lazy khi append object db='sys' (sửa upfront call ở
     type1_flow + type0_flow chỉ còn app_db_name; append_script_block truyền
     sys_db_name có điều kiện).

Yêu cầu: unit tests TC-A/B/C trong file spec; giữ nguyên warning cũ, hint là
warning mới; không đổi response_guard; rebuild exe sau khi xong.
```
