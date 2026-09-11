# FIX — `compare_things`: so **mọi loại file** (`.ent`, `.txt`, …), **ngoại trừ `.f`**

> **File ĐỘC LẬP cho Gemini** — bổ sung/chốt scope đuôi file. Không bắt buộc sửa `01`…`12`.  
> **Ngày:** 2026-09-11  
> **Liên quan:** `kind=file` / `kind=folder` (và path abs khi so Include). `kind=xml` vẫn tiện cho relative Controllers `Dir|Grid|Filter/*.xml` nhưng **không** giới hạn tool chỉ XML.

---

## 0. Yêu cầu user

1. Compare **không riêng XML** — mọi thể loại file text/config thường dùng FBO đều so được: ví dụ `.ent`, `.txt`, `.sql`, `.js`, `.config`, `.aspx`, `.cs`, …  
2. **Ngoại lệ bắt buộc:** file đuôi **`.f`** (mã hóa FBO) — **không so nội dung**, không cố decrypt.  
3. Agent sau này: cần so 2 file Include / entity / script → `kind=file` (2 abs path) hoặc `kind=folder` (lọc glob), không nghĩ “compare_things chỉ XML”.

---

## 1. Phân vai kind (chốt)

| `kind` | Phạm vi file |
|--------|----------------|
| **`file`** | **So tổng quát 2 absolute/UNC path** — **mọi đuôi trừ `.f`**. Đây là entry chính cho `.ent`, `.txt`, … |
| **`folder`** | Walk thư mục; so mọi file khớp glob **trừ `.f`** (exclude mặc định) |
| **`xml`** | Convenience: relative dưới Controllers + optional `xml_view` flat — chủ yếu `.xml` controller. **Không** chặn agent dùng `kind=file` cho `.xml` abs path |
| `sql` / `table` | Object DB — không đổi |

**CẤM** trong code/docs MCP docstring: ngôn ngữ kiểu “chỉ so XML controller”. Docstring tool phải nói rõ: file bất kỳ (trừ `.f`).

---

## 2. Quy tắc đuôi `.f`

### Detect

- Path ends with `.f` (case-insensitive), kể cả `.F`.
- Áp dụng `file_a` / `file_b` / từng entry trong `folder` / nếu ai đó đưa path `.f` vào nhầm.

### Hành vi (chốt)

| Tình huống | Kết quả |
|------------|---------|
| `kind=file` một hoặc hai bên là `.f` | `success=false` hoặc item `status=skipped_encrypted_ext` / error_code **`unsupported_extension_f`** — message: không so file `.f` (mã hóa). **Không** đọc bytes để diff text |
| `kind=folder` gặp `*.f` | **Bỏ qua** file đó (như exclude); có thể đếm `skipped_f_count` trong summary; **không** đưa vào missing/different vì “không đọc được” |
| Default `exclude_glob` folder | Thêm `*.f` vào exclude mặc định (cộng với exclude user truyền) |

**CẤM:** gọi decrypt / flat / decode `.f` trong compare_things.

---

## 3. `kind=file` — mọi đuôi còn lại

Pipeline hiện có (meta + text/binary detect) **giữ**, bổ sung:

1. **Gate `.f`** trước khi `get_file_meta_and_bytes`.
2. Text (utf-8-sig → … → latin-1): áp dụng cho `.ent`, `.txt`, `.sql`, `.xml`, `.js`, … như hiện tại.
3. Binary thật (null byte): vẫn so meta/hash — **không** cấm đuôi `.dll` khi user cố ý `kind=file`; folder `bin` mặc định `compare_content=false`.
4. Diff-only (ranges/signals): tuân [FIX-compare_things-diff-only-no-preview.md](./FIX-compare_things-diff-only-no-preview.md) nếu đã/đang làm — không preview.

### Ví dụ gọi (Gemini ghi vào docstring / skill note)

```text
# Hai file Include / entity
compare_things(
  kind="file",
  file_a=r"\\...\FBISP24\App_Data\Controllers\Include\Command\WhenVoucherInit.txt",
  file_b=r"\\...\SP228\App_Data\Controllers\Include\Command\WhenVoucherInit.txt",
  mode="summary"
)

# Hai .ent
compare_things(kind="file", file_a=r"...\Something.ent", file_b=r"...\Something.ent")
```

---

## 4. `kind=folder` — quét đa đuôi, trừ `.f`

1. `include_glob` mặc định `*` → đã gồm `.ent`, `.txt`, …  
2. **Luôn** loại `.f` (hard + default exclude).  
3. User có thể `include_glob="*.ent,*.txt,*.xml"` để hẹp scope Controllers/Include.  
4. `compare_content=true` chỉ cho text; binary vẫn meta.

Ví dụ:

```text
compare_things(
  kind="folder",
  folder_a=r"\\...\FBISP24\App_Data\Controllers\Include",
  folder_b=r"\\...\SP228\App_Data\Controllers\Include",
  include_glob="*.txt,*.ent",
  recursive=true,
  compare_content=false,   # hoặc true nếu cần ranges nội dung
  mode="summary"
)
```

---

## 5. `kind=xml` — không mở rộng ép `.ent`

- Giữ resolve Controllers + relative `Dir|Grid|Filter|…/*.xml` (+ `xml_view`).
- Nếu `object` trỏ `.ent` / `.txt`:  
  - **P0:** reject `invalid_object` với message: dùng `kind=file` + abs path (hoặc folder Include).  
  - **Không** bắt buộc implement relative `.ent` trong xml kind ở P0.

---

## 6. MCP docstring / validation

- Thêm `error_code=unsupported_extension_f` khi kind=file gặp `.f`.
- Docstring `compare_things`:  
  “So file bất kỳ trên đĩa (`.xml`, `.ent`, `.txt`, …) trừ `.f` mã hóa; folder tương tự; xml = convenience controller relative.”
- Wire không cần param mới trừ khi muốn `skip_extensions=.f` configurable — **P0 hardcode `.f` đủ**.

---

## 7. Tests

| ID | Case | Expected |
|----|------|----------|
| TC-EXT-01 | `kind=file` hai `.txt` khác 1 dòng | different + line ranges |
| TC-EXT-02 | `kind=file` hai `.ent` identical | identical |
| TC-EXT-03 | `kind=file` `file_a` đuôi `.f` | `unsupported_extension_f` / không diff content |
| TC-EXT-04 | `kind=folder` có `a.f` + `b.txt` | `a.f` skipped; `b.txt` so bình thường |
| TC-EXT-05 | `kind=xml` object `Include/x.ent` | invalid_object + hướng dẫn kind=file (P0) |

---

## 8. Checklist Gemini

- [ ] Gate `.f` trong `file_compare` / `service` validation
- [ ] Folder: luôn exclude `*.f` + `skipped_f_count` (optional)
- [ ] Docstring MCP nêu rõ mọi đuôi trừ `.f`
- [ ] Không giới hạn allowlist chỉ `.xml`
- [ ] Tests TC-EXT-*
- [ ] `pytest tests/compare_things/` pass

---

## 9. Prompt Gemini (copy-paste)

```text
Bổ sung compare_things theo docs/doc/doc_fix/FIX-compare_things-all-extensions-except-f.md

kind=file: so MỌI đuôi file (ent, txt, sql, xml, js, …) trừ .f — reject/skip .f với unsupported_extension_f, không decrypt.
kind=folder: mặc định exclude *.f; include_glob vẫn quét ent/txt/xml bình thường.
kind=xml: giữ convenience Controllers xml + xml_view; không ép so .ent qua kind=xml (bảo dùng kind=file).
Cập nhật docstring MCP: không phải tool chỉ XML.
Tests TC-EXT-01..05. Không regress compare hiện có.
```
