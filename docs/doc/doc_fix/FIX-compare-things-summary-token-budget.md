# FIX — `compare_things`: `mode=summary` quá nặng token (XML flat ~7k)

> **SUPERSEDED:** Làm theo [`FIX-compare_things-diff-only-no-preview.md`](./FIX-compare_things-diff-only-no-preview.md) — CẤM preview, chỉ báo điểm khác biệt; không chỉ cắt số hunk.

> **Mục đích (lịch sử):** Siết JSON `mode=summary` về **~1–3k token**. Evidence Customer flat ~7.3k vì 30×preview.

---

## 1. Vì sao tốn (không phải “flat tính toán” tốn token chat)

| Thành phần | Customer flat summary (đo thật) |
|------------|----------------------------------|
| Envelope + summary counts | nhỏ (~0.1–0.2k tok) |
| `file_a` / `file_b` meta đầy đủ (path, sha, dates…) | vừa |
| **30 hunks × `preview[]` (mỗi hunk tới ~8 dòng)** | **phần lớn** (~11k chars preview) |
| `unified_diff` | 0 ở summary (OK) |

Flat làm file dài hơn → **nhiều hunk hơn** (20→30) → summary càng phình vì **đang trả hết hunk + preview**.

Thử cắt lean (5 hunk, **chỉ line ranges, bỏ preview**, vẫn indent):

| Biến thể | ~chars | ~token (/4) |
|----------|--------|-------------|
| summary hiện tại | 29 077 | **~7.3k** |
| lean 5 hunks ranges-only | 3 341 | **~0.8k** |
| lean compact (no indent) | 2 241 | **~0.6k** |

→ Mục tiêu **1–3k hoàn toàn khả thi** nếu đổi contract `summary`.

---

## 2. Hành vi mới (chốt)

### `mode=summary` (default) — **lean**

1. Luôn có: `status`, counts, `message`, `next_actions`, `xml_view` / `line_basis` / `diff_reason` nếu có.
2. Hunks trong JSON:
   - Tối đa **`max_hunks_summary`** (default **5**; param MCP optional, hoặc constant).
   - Mỗi hunk **chỉ** fields: `id`, `change_type`, `a_line_start/end`, `b_line_start/end` (sql: `source_*` / `target_*`), `lines_added`, `lines_removed`.
   - **`preview` = [] hoặc omit** ở summary.
3. `content.hunk_count` = **tổng thật** (vd 30).
4. `content.hunks_omitted` = `hunk_count - len(hunks)`.
5. `content.diff_truncated` = true nếu omitted > 0.
6. Meta file: slim — `path`, `size`, `modified`, `sha256` (8–16 hex đầu cũng được), `line_ending`, `is_binary`. Bỏ field thừa nếu có.
7. Formatter: giữ `indent=2` OK nếu đã lean (~1k); không bắt buộc compact.

**Agent vẫn biết lệch dòng X–Y** (5 vùng đầu); muốn xem chữ → gọi lại `mode=hunks` hoặc `body` **scoped** (xem §3).

### `mode=hunks`

- Cho phép preview + `unified_diff` truncate (`max_diff_lines`).
- Vẫn cap hunks trả về: default **`max_hunks_detail=15`** (hoặc giữ 30 nhưng param cắt). Mục tiêu hunks ~3–10k tùy file — chấp nhận >3k.

### `mode=body`

- Chỉ dùng khi agent đã biết hunk id / line range; khuyến nghị thêm (P1) `hunk_id` hoặc `line_start/line_end` filter — không bắt buộc P0 nếu siết summary đủ.

### Áp dụng mọi kind text

Không chỉ xml: `file`, `sql`, `folder` compare_content — cùng luật summary lean.

---

## 3. Param (optional, default an toàn)

| Param | Default | Ý nghĩa |
|-------|---------|---------|
| `max_hunks_summary` | `5` | Số hunk trả trong `mode=summary` |
| `max_hunks_detail` | `15` | Cap hunk khi `mode=hunks`/`body` |
| `summary_include_preview` | `false` | Nếu true: preview tối đa 2 dòng/hunk (vẫn dễ vượt 3k nếu nhiều hunk — không khuyến nghị default) |

Wire MCP + `service.py`.

---

## 4. Acceptance

| Case | Kỳ vọng |
|------|---------|
| Customer.xml flat + summary | JSON **≤ ~12 000 chars** (~**≤ 3k token**/4) — lý tưởng ≤ 2.5k tok |
| Customer.xml original + summary | tương tự hoặc nhỏ hơn |
| summary vẫn có `a_line_start/end` trên hunks trả về | bắt buộc |
| `hunk_count` đầy đủ + `hunks_omitted` | bắt buộc |
| mode=hunks vẫn có preview | bắt buộc |
| pytest compare_things | update assert nếu test kỳ vọng full preview ở summary |

---

## 5. Prompt Gemini

```text
Fix compare_things token budget theo docs/doc/doc_fix/FIX-compare_things-summary-token-budget.md

mode=summary: mặc định chỉ trả tối đa 5 hunks, CHỈ line ranges (không preview / không unified_diff);
giữ hunk_count thật + hunks_omitted + diff_truncated.
Slim file meta. Áp dụng file/xml/sql/folder-text.
Optional params max_hunks_summary=5, max_hunks_detail=15, summary_include_preview=false.
Acceptance: Dir/Customer.xml flat summary JSON <= ~12KB (~3k token).
Cập nhật tests. Không regress mode=hunks có preview.
```

---

## 6. Gợi ý agent habit (sau khi fix)

1. Lần 1: `mode=summary` (+ `xml_view=flat` nếu cần) → đọc ranges.  
2. Lần 2: `mode=hunks` chỉ khi cần xem chữ đoạn lệch.  
3. Tránh `body` mặc định.
