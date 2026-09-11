# FIX — `compare_things`: bugs / lệch spec sau live + extra cases

> **Mục đích:** Doc gửi **Gemini fix** — các lỗi / lệch hành vi phát hiện khi nghiệm thu LIVE FAHASA↔AIH và suite case tự tạo.  
> **Ngày:** 2026-09-10  
> **Phạm vi:** package [`compare_things/`](../../../compare_things/), tests [`tests/compare_things/`](../../../tests/compare_things/), MCP wire [`fastbusiness_mcp/mcp_app.py`](../../../fastbusiness_mcp/mcp_app.py)  
> **Spec gốc:** [`../compare_things/`](../compare_things/)  
> **Feature bổ sung XML flat (cùng đợt):** [`../compare_things/13_xml_view_original_or_flat.md`](../compare_things/13_xml_view_original_or_flat.md) — implement `xml_view` **trong cùng PR/fix nếu tiện**.

---

## 0. Prompt Gemini (copy-paste)

```text
Fix compare_things theo docs/doc/doc_fix/FIX-compare_things-live-findings.md
VÀ bổ sung xml_view theo docs/doc/compare_things/13_xml_view_original_or_flat.md

Ưu tiên P0:
1) ignore_line_endings=false phải so được CRLF vs LF là different (bug text_normalize.splitlines nuốt \r)
2) only_line_ending_diff / message: đừng gọi BOM-only hoặc whitespace-only là "chỉ khác xuống dòng" — tách flag/message
3) xml_view=original|flat (default original) dùng find_entity_by_xml.facade.flat_xml
4) SQL seed quá rộng (LIKE '%Authorize%' bắt cs_CF*) — ưu tiên match tên object / word-boundary; rank name trước
5) Object/table không có cả 2 bên: status rõ (missing_both) thay vì chỉ errors count
6) (P1) Strip noise header clone_things / USE khi fingerprint+diff SQL definition

Thêm/sửa tests cho từng bug. pytest tests/compare_things/ phải pass; không regress clone_things.
```

---

## 1. [P0] `ignore_line_endings=false` không có tác dụng với CRLF vs LF

### Repro

Extra case `S-FILE CRLF vs LF ignore_line_endings=false → different`:

- File A: `aaa\nbbb\nccc\n` (LF)
- File B: `aaa\r\nbbb\r\nccc\r\n` (CRLF)
- Gọi `ignore_line_endings=False`

**Kỳ vọng (spec 05):** `identical_content=false`, có hunks (hoặc ít nhất khác bytes-as-lines có `\r`).

**Thực tế:** `identical_content=true`, `only_line_ending_diff=true` — giống khi `ignore_line_endings=True`.

### Root cause

[`compare_things/text_normalize.py`](../../../compare_things/text_normalize.py) — `normalize_text_lines`:

```python
if ignore_line_endings:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
lines = text.splitlines()  # LUÔN gọi — splitlines() coi \r\n là boundary và BỎ \r
```

→ dù không replace, `splitlines()` vẫn làm mất khác biệt CRLF/LF.

### Fix bắt buộc

Khi `ignore_line_endings=False`:

- **Không** dùng `splitlines()`.
- Tách dòng theo `\n` only (sau khi không convert), **giữ `\r` cuối dòng** nếu có (CRLF → line content `...\r`), hoặc so với `keepends=True` rồi compare raw line chunks.
- Khi `ignore_line_endings=True`: giữ normalize `\r\n`/`\r` → `\n` rồi split (như hiện tại sau fix rõ ràng).

Xóa dead code `raw_lines = text.split("\n")` không dùng.

### Test

- `ignore_line_endings=False` + CRLF vs LF → **different** (assert not identical_content).
- `ignore_line_endings=True` + CRLF vs LF → identical_content + only_line_ending_diff (regression).

---

## 2. [P0] `only_line_ending_diff` / message gây hiểu nhầm (BOM, whitespace)

### Repro

| Case | Thực tế tool | Vấn đề |
|------|--------------|--------|
| BOM vs no-BOM cùng text | `only_line_ending_diff=true`, message “chỉ khác định dạng xuống dòng” | Không phải line ending — là BOM/bytes |
| `ignore_whitespace=True`, `"  hello  \n"` vs `"hello\n"` | `only_line_ending_diff=true` + message CRLF | Sai nhãn — khác whitespace đã được ignore; sha256 raw khác |

Công thức hiện tại (`file_compare.py`):

```text
only_line_ending_diff = identical_content and (sha256_a != sha256_b)
```

đúng theo doc “byte khác sau normalize giống”, nhưng **tên flag + message tiếng Việt** gắn “CRLF/LF” → agent hiểu sai.

### Fix

1. Đổi semantics rõ trong JSON (chọn một, **chốt A**):

**Option A (khuyến nghị, ít breaking):**

- Giữ `only_line_ending_diff` = true **chỉ khi** `line_ending` meta khác (crlf vs lf) và identical_content.
- Thêm `only_normalized_bytes_diff` hoặc `content_same_bytes_differ=true` khi identical_content và sha256 khác (BOM / whitespace strip / khác encoding decode path).
- `message` phân nhánh:
  - chỉ line ending → “chỉ khác CRLF/LF”
  - chỉ BOM → “nội dung giống sau normalize; khác BOM/bytes gốc”
  - whitespace ignore → “giống sau strip whitespace; bytes gốc khác”

**Option B:** đổi tên flag thành `only_byte_diff_after_normalize` và deprecate tên cũ (alias cả hai trong 1 version).

2. Cập nhật tests TC-FILE-02 / BOM / whitespace assert message hoặc flag mới. (**Ưu tiên sửa code + test; không bắt buộc sửa doc `05` cũ.**)

---

## 3. [P0] Thiếu `xml_view=original|flat`

Hiện chỉ so **raw**. Spec bổ sung nằm **một file mới độc lập** (không sửa `01`…`12`):

→ [`docs/doc/compare_things/13_xml_view_original_or_flat.md`](../compare_things/13_xml_view_original_or_flat.md)

Gemini **chỉ đọc file 13** cho phần này — **CẤM** patch `02_tool_api.md` / `08_kind_xml.md` / `README.md` vì task flat.

Tóm tắt (chi tiết trong 13):

- Param `xml_view` default `original`
- `flat` → `find_entity_by_xml.facade.flat_xml`
- JSON: `xml_view`, `content.line_basis`
- CẤM silent fallback; CẤM tự viết expander

---

## 4. [P0] SQL `seed` LIKE quá rộng / nhiễu

### Repro

`seed=Authorize`, `max_objects=5`, FAH→AIH:

- Trả các `dbo.cs_CFExtractData*` / `cs_CFAutoGeneration*` — **missing_on_target**
- Không phải nhóm Authorize/Approval nghiệp vụ user kỳ vọng

Nguyên nhân: `sql_seed_scan.py` chỉ:

```sql
WHERE m.definition LIKE '%' + @k + '%'
```

Substring `Authorize` nằm trong body/comment nhiều proc không liên quan; TOP N cắt sớm → lệch acceptance.

### Fix

1. **Ưu tiên match tên object:**  
   `o.name LIKE '%' + @k + '%'` xếp hạng / lấy trước.
2. Definition match: dùng word-boundary hợp lý (vd. `LIKE '%[^a-zA-Z0-9_]Authorize[^a-zA-Z0-9_]%'` hoặc filter Python `\bAuthorize\b` sau khi lấy candidate rộng hơn rồi rank).
3. Merge order: name hits trước, definition hits sau; rồi cắt `max_objects`.
4. Optional param sau (không bắt buộc P0): `seed_in=name|definition|both` default `both` với rank trên.

### Test

- Seed `Authorize` không được đưa `cs_CFExtractData*` lên đầu nếu có proc tên chứa`Authorize` / `GetApproval*`.
- Seed `vdmduyetuq` vẫn ra MailList/Role (LIVE hoặc mock).

---

## 5. [P0] Object/table không có ở cả hai bên → chỉ `errors`, agent khó đọc

### Repro

`object=dbo.ThisObjectDefinitelyDoesNotExist_XYZ_999`:

- `success=true`
- `counts.errors=1`
- `missing_on_target=0`, `missing_on_source=0`

Code (`sql_compare.py`): `"not found on source nor target"` → `errors_list`.

Tương tự table missing / sys `options` không resolve.

### Fix

- Thêm status **`missing_both`** (hoặc `not_found_both` cho đồng bộ clone_things).
- Đưa tên vào `summary.missing_both[]` + `compared[].status=missing_both`.
- `next_actions`: `["investigate_object_name"]` / `fix_paths`.
- Vẫn có thể giữ `errors` cho lỗi IO/permission thật sự — **tách** “không tồn tại cả hai” khỏi error kỹ thuật.

Cùng pattern cho `kind=table`.

---

## 6. [P1] Diff SQL bị nhiễu header `clone_things` / comment paste

### Repro

SQL-01 hunk preview dòng đầu dạng:

```text
+ -- clone_things type=1: dbo.FastBusiness$App$GetApprovalMailList | ... paste-for-edit ...
```

Fingerprint/diff đang so definition có thể đã bị wrapper/header khác giữa 2 DB hoặc tool lấy definition không cùng normalize.

### Fix (P1)

Trước fingerprint + diff:

- Strip dòng comment leading kiểu `-- clone_things type=1:` / banner paste-for-edit nếu có trong module text (hiếm trên DB thuần — kiểm tra nguồn `get definition`).
- Normalize: bỏ `\ufeff`, unify line endings (theo flag), optional bỏ `CREATE`/`ALTER` khác nhau nếu chỉ khác verb (cẩn thận — chỉ khi spec cho phép).
- Đảm bảo lấy definition cùng API cho source/target (không bên CREATE bên ALTER script).

Thêm test với 2 definition giống logic, một bên có dòng comment header → identical sau strip.

---

## 7. [P1] Folder `compare_content=true` — summary dễ tối nghĩa

Extra case `S-FOLDER compare_content text hunks`: file `sub/x.txt` khác nội dung nhưng summary in chủ yếu missing; cần đảm bảo:

- `summary.different_content` list relative path
- `compared[]` có item `status=different_content` + `content.hunks` (spec 06 / 04 §5.4.1)

Gemini: đọc lại `folder_compare.py` — nếu hunks có trong compared nhưng summary không liệt kê `different_content`, **bổ sung summary field** cho agent.

---

## 8. Checklist Gemini

- [ ] Fix `text_normalize` + test CRLF `ignore_line_endings=False`
- [ ] Tách flag/message BOM / whitespace / line ending
- [ ] Implement `xml_view` theo doc 13
- [ ] Seed scan rank name + boundary; test Authorize
- [ ] `missing_both` cho sql/table
- [ ] (P1) Strip SQL header noise; folder summary `different_content`
- [ ] `pytest tests/compare_things/` green
- [ ] `pytest tests/clone_things/` không regress
- [ ] Wire MCP param `xml_view` + docstring

---

## 9. Tham chiếu evidence

- Live report: `scripts/_clone_things_live/_compare_things_live_report.json`
- Extra cases: `scripts/_clone_things_live/_compare_things_extra_cases_report.json`
- Scripts: `_compare_things_live_fah_aih.py`, `_compare_things_extra_cases.py`
