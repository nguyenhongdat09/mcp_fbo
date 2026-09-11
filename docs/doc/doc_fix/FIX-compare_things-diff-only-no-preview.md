# FIX — `compare_things`: chỉ báo **điểm khác biệt**, CẤM preview / dump nội dung

> **File ĐỘC LẬP cho Gemini** — không sửa `01`…`12` vì task này (trừ khi Gemini tự cập nhật docstring MCP).  
> **Ngày:** 2026-09-10  
> **Thay thế tư duy** doc token-budget trước đó: không chỉ “cắt 5 hunk”, mà **đổi contract** — tool tồn tại để **chỉ ra lệch**, không phải để agent đọc lại cả file/proc.

---

## 0. Tư duy user (bắt buộc hiểu)

1. So 2 project / 2 file / 2 proc là để **tìm điểm khác biệt**.
2. Nếu trả `preview` / unified_diff / body dài = bắt agent **đọc gần như cả file** → **phá mục đích** tool.
3. Ví dụ nghiệp vụ:
   - Project **đang sửa** = AIH (`SP228`)
   - Project **nguồn muốn clone về** = FAHASA (`FBISP24`)
   - Agent cần biết: trên AIH **thiếu gì / lệch gì** so với FAH — **cụ thể** (tên object, dòng X–Y, cột/type/PK…), không cần đoạn XML/SQL dán vào chat.
4. Áp dụng **đồng nhất** cho: file, xml (original/flat), folder, **proc / func / view**, table.

---

## 1. Vai trò 2 project (chốt semantics JSON)

Giữ param MCP hiện có:

| Param | Vai trò nghiệp vụ |
|-------|-------------------|
| `project_source` | **Nguồn tham chiếu / nguồn clone** (vd FAHASA) |
| `project_target` | **Project đang sửa / đích nhận** (vd AIH) |

JSON phải nói rõ bằng field + `message` tiếng Việt, không để agent đoán:

```json
{
  "role_source": "reference_clone_from",
  "role_target": "editing",
  "project_source": "\\\\...\\FBISP24",
  "project_target": "\\\\...\\SP228",
  "message": "So AIH (đang sửa) với FAHASA (nguồn clone): AIH thiếu 1 XML; 1 XML khác ở 3 vùng dòng (xem hunks ranges)."
}
```

Mapping list:

| Summary key | Ý nghĩa với agent |
|-------------|-------------------|
| `missing_on_target` | **Có trên source (FAH), không có trên target (AIH)** → ứng viên `clone_things` / copy XML |
| `missing_on_source` | Có trên AIH, không có trên FAH → không clone từ FAH; có thể AIH custom |
| `different` | Có cả hai nhưng **lệch** (ranges / schema_diff / signals) |
| `identical` | Giống (sau normalize / flat tùy mode) |
| `missing_both` | Sai tên / không có ở đâu |

Alias trong message: luôn nhắc `(source=FAH…)` / `(target=AIH…)` ngắn nếu path dài thì dùng basename project.

**File/folder** (`file_a`/`file_b`, `folder_a`/`folder_b`):  
- Convention khuyến nghị: **A = source/reference**, **B = editing/target** (cùng chiều source→target).  
- JSON: `role_a=reference_clone_from`, `role_b=editing` + message tương ứng (`missing_on_b` = thiếu phía đang sửa).

---

## 2. CẤM trong response (mọi `mode`, mọi kind text)

| CẤM | Lý do |
|-----|--------|
| `preview[]` chứa dòng code/XML/SQL | Agent đọc lại file |
| `unified_diff` dài mặc định | Như trên |
| `body_a` / `body_b` / `body_source` / `body_target` mặc định | Dump cửa sổ nội dung |
| Trả full / gần full definition proc | Đúng việc của `clone_things` type1 mode_read=0/3 khi user **cần sửa** |
| Liệt kê hàng trăm path identical | Noise |

**Cho phép (và bắt buộc khi khác):**

- **Khoảng dòng**: `a_line_start/end`, `b_line_start/end` hoặc `source_line_*` / `target_line_*`
- **Đếm**: `hunk_count`, `lines_added` / `lines_removed` (số, không kèm text)
- **Signals** SQL: `target_refs_dmduyet`, `source_refs_vdmduyetuq`, `signals_in_hunk` (mã, không đoạn code)
- **schema_diff** table: tên cột / type / PK / index / trigger
- **meta_diff** folder/file: `size`, `modified`, `created`, `sha256` ngắn
- **`change_type`**: insert/delete/replace
- **`next_actions`**: `clone_things_type0`, `clone_things_type1_mode_read_0`, `review_hunks` (review = mở file đúng dòng, không đọc dump)

---

## 3. Contract theo `mode` (sau fix)

### `mode=summary` (default) — chỉ bản đồ lệch

```json
{
  "kind": "xml",
  "xml_view": "flat",
  "role_source": "reference_clone_from",
  "role_target": "editing",
  "summary": {
    "missing_on_target": [],
    "missing_on_source": [],
    "different": ["Dir/Customer.xml"],
    "identical": [],
    "counts": { "different": 1, "hunk_total": 30 }
  },
  "compared": [
    {
      "relative_path": "Dir/Customer.xml",
      "status": "different",
      "content": {
        "line_basis": "flat",
        "lines_source": 1593,
        "lines_target": 1085,
        "hunk_count": 30,
        "hunks": [
          {
            "id": 1,
            "change_type": "replace",
            "source_line_start": 40,
            "source_line_end": 55,
            "target_line_start": 40,
            "target_line_end": 48,
            "lines_added": 2,
            "lines_removed": 9
          }
        ],
        "hunks_omitted": 25,
        "diff_truncated": true
      },
      "next_actions": ["open_target_at_lines", "clone_things_type0_if_missing"]
    }
  ],
  "message": "AIH (đang sửa) khác FAHASA (nguồn) tại Dir/Customer.xml: 30 vùng dòng; JSON liệt kê 5 vùng đầu (chỉ số dòng)."
}
```

Quy tắc summary:

- Max **5** hunks ranges-only (`max_hunks_summary`, default 5).
- **Không** `preview`, **không** `unified_diff`.
- Ngân sách mục tiêu: **~1–3k token / object** (Customer flat summary lean).

### `mode=hunks`

- Vẫn **không** preview code mặc định.
- Cho phép **nhiều ranges hơn** (vd max 30) + optional `signals_in_hunk`.
- `unified_diff` **default tắt**. Chỉ bật nếu param mới `include_unified_diff=true` (default **false**) — user/agent chủ động xin.

### `mode=body`

- **Đổi nghĩa hoặc hạn chế mạnh:** không dump body quanh hunk mặc định.
- Khuyến nghị: `mode=body` = “ranges đầy đủ mọi hunk + signals”, vẫn **không** text — hoặc deprecate body text; nếu giữ text thì bắt buộc `include_text_snippets=true` (default false) và cap rất chặt (vd 2 hunk × 3 dòng).

**Chốt P0 Gemini:**  
`include_unified_diff=false`, `include_text_snippets=false` mặc định; xóa/omit mọi `preview` khỏi builder.

---

## 4. Theo kind — “khác cái gì thì ghi cái đó”

### XML / file

| Lệch | Ghi |
|------|-----|
| Thiếu file phía đang sửa | `missing_on_target` + relative_path |
| Thiếu phía nguồn | `missing_on_source` |
| Khác nội dung | hunks **chỉ line ranges** + hunk_count; `xml_view` / `line_basis` |
| Chỉ CRLF/BOM | `diff_reason` + flag, **không** hunk giả |

### SQL proc/func/view

| Lệch | Ghi |
|------|-----|
| Thiếu trên target (AIH) | `missing_on_target` → `next_actions: ["clone_things_type0"]` |
| Khác definition | ranges source/target + `signals` (vd dmduyet vs vdmduyetuq) — **không** dán SQL |
| Encrypted | `encrypted_skip` |
| missing_both | tên sai |

### Table

Chỉ `schema_diff` (cột/type/PK/index/trigger) — không DDL text.

### Folder

`missing_on_b` / `missing_on_a`, `meta_diff` (size/date), optional hash — không hex dump / không đọc DLL.

---

## 5. Code cần đụng (gợi ý)

- `line_diff.py` / `build_line_diff`: mode summary → không gắn preview; flag `include_preview=False`
- `file_compare.py`, `xml_compare.py`, `sql_compare.py`, `folder_compare.py`: bỏ ghi `preview` vào dict hunk
- `formatter.py`: không cần đổi nhiều nếu dict đã lean
- `models.py`: Hunk.preview optional / default empty
- `service.py` + `mcp_app.py`: param `include_unified_diff`, `include_text_snippets`, `max_hunks_summary`; docstring nhấn mạnh tư duy
- Tests: assert `"preview" not in hunk or hunk["preview"] == []` cho summary; Customer flat summary chars ≤ ~12k

---

## 6. Acceptance

1. `Customer.xml` flat + summary: **không** có preview text; ~**≤ 3k token**; vẫn có line ranges.
2. SQL different: có `source_line_*` / `target_line_*` + signals; **không** dòng SQL trong JSON.
3. Message nêu rõ **ai đang sửa / ai là nguồn clone** + thiếu/lệch phía nào.
4. `pytest tests/compare_things/` cập nhật (các test cũ assert preview → đổi sang assert ranges / omit preview).
5. Không regress `clone_things`.

---

## 7. Prompt Gemini (copy-paste)

```text
Fix compare_things theo docs/doc/doc_fix/FIX-compare_things-diff-only-no-preview.md

Tư duy: tool chỉ báo ĐIỂM KHÁC BIỆT — CẤM preview/unified_diff/body text mặc định (đừng bắt agent đọc file/proc).

Semantics: project_source = nguồn clone/tham chiếu; project_target = project đang sửa.
missing_on_target = thiếu trên project đang sửa (cần mang từ source).
JSON: role_source/role_target + message tiếng Việt rõ.

mode=summary: tối đa 5 hunks, CHỈ line ranges + counts/signals/schema_diff/meta_diff;
hunk_count đầy đủ + hunks_omitted; không preview.
mode=hunks: nhiều ranges hơn, vẫn không preview trừ include_text_snippets=true (default false).
Áp dụng file, xml, sql, table, folder.

Acceptance: Customer.xml flat summary ≤ ~3k token, không preview; SQL chỉ ranges+signals.
Sửa tests. Không regress clone_things.
```
