# FIX — `compare_things` `kind=folder`: bỏ nit wording “xem hunks ranges” trong `message`

> **File ĐỘC LẬP cho Gemini fix**  
> **Ngày:** 2026-09-11  
> **Mức:** nit / P2 (không fail chức năng; sửa wording)  
> **Phạm vi:** [`compare_things/folder_compare.py`](../../../compare_things/folder_compare.py) (+ test message nếu có)  
> **Không đụng:** `sql_compare.py` / `xml_compare.py` / `service.py` kind=file — cụm “xem hunks ranges” **vẫn đúng** với text/SQL/XML.  
> **Sau:** [`FIX-compare_things-folder-summary-vs-detail.md`](./FIX-compare_things-folder-summary-vs-detail.md) đã OK live.

---

## 0. Prompt Gemini (copy-paste)

```text
Fix nit wording compare_things folder theo docs/doc/doc_fix/FIX-compare_things-folder-message-no-hunks.md

P0:
1) folder_compare.py: khi ghép message phần different_content, BỎ cụm "(xem hunks ranges, không dán code)".
   Hiện ~:
     f"khác nội dung: {n} file (xem hunks ranges, không dán code),"
   Đổi thành:
     f"khác nội dung: {n} file,"
   (giữ dấu phẩy / cấu trúc msg_parts như các phần missing/meta khác)

2) Không thêm “xem hunks” cho folder dù detail=true — folder binary/DLL không có text hunk; agent dùng summary list tên hoặc compared meta / kind=file.

3) Test: assert message folder KHÔNG chứa "hunks ranges" khi có different_content (mock 1–2 file khác hash). Có thể gắn vào test_folder_detail hiện có.

4) pytest tests/compare_things/ pass. Không đổi sql/xml/file message.
```

---

## 1. Vấn đề

Live `kind=folder` `bin/*.dll` `detail=false`:

```text
... khác nội dung: 34 file (xem hunks ranges, không dán code), khác metadata: 68 file ...
```

Với folder/DLL:

- `detail=false` → `compared=[]`, **không có hunk**.
- `detail=true` → `compared` chỉ meta/sha — **vẫn không có text hunk**.

Cụm “xem hunks ranges” copy từ contract text → agent dễ hiểu nhầm còn có line ranges.

**Không** sai bucket / hash / `detail` — chỉ wording.

---

## 2. Chỗ sửa (code hiện tại)

[`folder_compare.py`](../../../compare_things/folder_compare.py) (~line 374):

```python
msg_parts.append(f"khác nội dung: {len(different_content_names)} file (xem hunks ranges, không dán code),")
```

### Fix bắt buộc

```python
msg_parts.append(f"khác nội dung: {len(different_content_names)} file,")
```

Tuỳ chọn (không bắt buộc): nếu muốn rõ hơn cho binary inventory:

```python
msg_parts.append(f"khác nội dung (hash/size): {len(different_content_names)} file,")
```

Ưu tiên bản **ngắn** (chỉ bỏ ngoặc hunks) cho đồng bộ với các phần `thiếu N file`, `khác metadata: N file`.

---

## 3. Không làm

| Không | Lý do |
|-------|--------|
| Đổi message sql/xml/file có “xem hunks ranges” | Đúng với text diff |
| Đổi `next_actions` / `detail` / summary buckets | Ngoài scope |
| Thêm unified_diff vào folder message | Trái diff-only |

---

## 4. Acceptance

- [ ] Call folder có `different_content` → `message` **không** chứa `hunks` / `hunks ranges`.
- [ ] Vẫn có: `khác nội dung: N file` (hoặc variant hash/size nếu chọn).
- [ ] sql/xml regression: message vẫn được phép có “xem hunks ranges”.
- [ ] pytest `tests/compare_things/` pass.

---

## 5. Acceptance one-liner (sau fix)

```text
compare_things(kind=folder, folder_a=...\bin, folder_b=...\bin, include_glob=*.dll, compare_content=true)
→ message không còn "(xem hunks ranges, không dán code)"
```
