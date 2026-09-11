# 13 — `kind=xml`: `xml_view` = `original` | `flat` (bổ sung cho Gemini)

> **File ĐỘC LẬP** — Gemini chỉ cần đọc **file này** để bổ sung option so XML original/flat.  
> **CẤM** sửa các doc cũ `01`…`12`, `README.md` trong `docs/doc/compare_things/` vì task này.  
> Mọi contract param / JSON / test / prompt nằm gọn trong file này.

> **Mục đích:** Bổ sung option so XML **original (raw)** hoặc **flat** (đã resolve ENTITY/Include) trước khi diff.  
> **Không** đổi hành vi default hiện tại: mặc định vẫn `original` (tương thích v1 đã ship).

---

## 1. Vấn đề

Hiện `kind=xml` chỉ so **raw file** trên đĩa (`compare_files`). Hai controller có thể:

| Tình huống | original | flat (mong muốn) |
|------------|----------|------------------|
| Text controller giống, Include entity khác nội dung | identical (sai nghiệp vụ) | **different** |
| Text controller khác ENTITY path nhưng flat ra giống | different (nhiễu) | **identical** |
| Chỉ khác CRLF trên file gốc | only_line_ending (như file) | normalize sau flat |

Agent FBO thường cần so **sau khi expand** giống `read_local_file(..., read_option=2)`.

---

## 2. Param mới

| Param | Type | Default | Scope | Mô tả |
|-------|------|---------|-------|--------|
| `xml_view` | `str` | `"original"` | **Chỉ `kind=xml`** | `original` \| `flat` (alias chấp nhận: `raw`→`original`, `expanded`→`flat`) |

- `kind` khác xml: **bỏ qua** `xml_view` (không lỗi).
- Giá trị không thuộc enum (sau alias) → `error_code=invalid_xml_view`.

### Ý nghĩa

| `xml_view` | Nguồn text để diff |
|-----------|---------------------|
| `original` (default) | Bytes/text file `.xml` trên đĩa — **giữ behavior hiện tại** |
| `flat` | `find_entity_by_xml.facade.flat_xml(abs_path)` — expand ENTITY/Include giống `read_local_file` option=2 |

Metadata file (`size`, `sha256`, `mtime`, `created`, `line_ending` của **file gốc**) vẫn lấy từ path gốc để agent biết file vật lý; thêm field cho rõ đang so view nào (xem §4).

---

## 3. Pipeline khi `xml_view=flat`

Giữ nguyên resolve Controllers + relative path như [08_kind_xml.md](./08_kind_xml.md).

Với mỗi cặp `path_source` / `path_target` đã tồn tại:

```text
1. meta_stat(path) — luôn từ file gốc trên đĩa
2. if xml_view == "original":
       text = read file (như file_compare hiện tại)
   else:  # flat
       try:
           text = flat_xml(abs_path)   # find_entity_by_xml.facade.flat_xml
       except / empty / encrypted:
           status=error hoặc encrypted/skip — message rõ; KHÔNG silent fallback sang original
           (được phép: warnings += "flat_failed: ..." và status=error cho item đó)
3. Diff hai text bằng shared line_diff (ignore_line_endings, context_lines, mode, …)
4. Hunk line numbers = dòng trên **text đang so** (flat text nếu xml_view=flat)
   → ghi rõ trong JSON: content.line_basis = "original" | "flat"
```

### CẤM

- Tự viết lại expander ENTITY (phải reuse `flat_xml`).
- Khi flat fail: **không** im lặng so raw rồi báo identical.
- Dump full flat XML vào JSON (vẫn truncate theo `mode` / `max_diff_lines`).
- Flat cho `.f` mã hóa nếu `flat_xml` không hỗ trợ → item `error` / skip với message (giống read_local_file).

### Reuse bắt buộc

```python
from find_entity_by_xml.facade import flat_xml
# Cùng stack với xml_fbograph.mcp_tools.mcp_read_local_file read_option=2
```

Xem thêm [10_reuse_existing.md](./10_reuse_existing.md).

### Gợi ý implement (không nhét vào `file_compare` path-only)

Trong `xml_compare.py` (hoặc helper `xml_text_load.py`):

- Hàm `load_xml_text_for_compare(path, xml_view) -> tuple[str, str]`  
  trả `(text, line_basis)` với `line_basis` ∈ `{original, flat}`.
- Diff in-memory: tái dụng `line_diff.build_line_hunks` / logic đã tách khỏi đọc file — **không** bắt buộc ghi temp file flat ra đĩa (tránh side effect). Nếu hiện `compare_files` chỉ nhận path: tách hàm `compare_text_pair(text_a, text_b, meta_a, meta_b, ...)` và để `file_compare` gọi lại.

---

## 4. JSON — field bổ sung

Trên envelope và/hoặc mỗi `compared[]` item:

```json
{
  "kind": "xml",
  "xml_view": "flat",
  "compared": [
    {
      "relative_path": "Dir/PUDelegationApproval.xml",
      "xml_view": "flat",
      "content": {
        "line_basis": "flat",
        "hunks": [ { "a_line_start": 120, "a_line_end": 140, "...": "..." } ]
      },
      "file_a_meta": { "path": "...", "size": 1234, "sha256": "..." },
      "next_actions": ["review_hunks"]
    }
  ],
  "message": "So XML ở chế độ flat (đã expand entity)."
}
```

- `xml_view` trên envelope = param đã resolve (sau alias).
- `line_basis` trên `content` = cơ sở số dòng hunk (phải khớp `xml_view` khi success).

`next_actions` gợi ý thêm (optional catalog):

| Code | Khi nào |
|------|---------|
| `retry_xml_view_flat` | original identical nhưng nghi ngờ Include khác |
| `retry_xml_view_original` | flat lỗi / muốn so raw |

---

## 5. MCP wiring

Trong `fastbusiness_mcp/mcp_app.py` thêm param:

```text
xml_view: Annotated[str, Field(default="original", description="Chỉ kind=xml: original=so file gốc; flat=so sau expand ENTITY/Include (giống read_local_file option=2).")] = "original"
```

Truyền xuống `compare_things(..., xml_view=xml_view)` → `service` → `xml_compare`.

Docstring tool: nhắc khi so controller FBO nên thử `xml_view=flat` nếu nghi entity/Include.

---

## 6. Tests (bắt buộc)

Thêm vào `tests/compare_things/` (fixture temp + entity Include tối giản):

| ID | Case | Expected |
|----|------|----------|
| TC-XML-VIEW-01 | `xml_view=original` (default) — regression PU/identical raw | như trước |
| TC-XML-VIEW-02 | `xml_view=flat`: 2 XML raw khác ENTITY nhưng Include cùng nội dung → sau flat **identical** (hoặc hunks ít hơn raw) | identical_content hoặc different giảm nhiễu ENTITY |
| TC-XML-VIEW-03 | `xml_view=flat`: cùng raw controller, Include file khác nội dung → **different** + hunks trên flat | status different, line_basis=flat |
| TC-XML-VIEW-04 | `xml_view=raw` alias → original | OK |
| TC-XML-VIEW-05 | `xml_view=nope` | `invalid_xml_view` |
| TC-XML-VIEW-06 | `kind=file` + truyền `xml_view=flat` | bỏ qua, không lỗi |
| TC-XML-VIEW-07 | flat fail (path giả / mock) | item/error rõ, không silent original |

Live (optional): FAH vs AIH `Dir/Customer.xml` với `original` vs `flat` — so sánh `hunk_count` (ghi vào report, không bắt flake CI).

---

## 7. Checklist Gemini

- [ ] Param `xml_view` trong `service.py` validate + alias
- [ ] Wire MCP `mcp_app.py`
- [ ] `xml_compare.py`: nhánh flat dùng `flat_xml`; original giữ path
- [ ] Tách/reuse `compare_text_pair` nếu cần (architecture sạch)
- [ ] JSON: `xml_view`, `line_basis`
- [ ] Tests TC-XML-VIEW-*
- [ ] Cập nhật docstring; không regress default `original`
- [ ] Chạy `pytest tests/compare_things/` + không gãy `clone_things`

---

## 8. Prompt Gemini (copy-paste)

```text
Bổ sung compare_things kind=xml theo docs/doc/compare_things/13_xml_view_original_or_flat.md

Thêm param xml_view default "original"; giá trị "original"|"flat" (alias raw→original, expanded→flat).
Khi flat: dùng find_entity_by_xml.facade.flat_xml(abs_path) giống read_local_file option=2; diff text đã flat; hunk line_basis="flat".
Khi original: giữ behavior hiện tại.
Meta size/sha256/mtime vẫn từ file gốc. JSON có xml_view + content.line_basis.
CẤM tự viết expander; CẤM silent fallback original khi flat fail.
Wire mcp_app.py; tests TC-XML-VIEW-* trong 13; pytest tests/compare_things/ phải pass; default original không regress.
```
