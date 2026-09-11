# FIX — `compare_things`: signals 2 phía + PK order noise + message meta (live AIH/FAHASA 2026-09-11)

> **File ĐỘC LẬP cho Gemini fix** — không sửa `01`…`13` spec trừ khi Gemini tự cập nhật docstring MCP.  
> **Ngày:** 2026-09-11  
> **Phạm vi:** [`compare_things/`](../../../compare_things/) (signals, table PK compare, file/xml message), tests [`tests/compare_things/`](../../../tests/compare_things/)  
> **Spec liên quan:** [`../compare_things/`](../compare_things/), [`FIX-compare_things-diff-only-no-preview.md`](./FIX-compare_things-diff-only-no-preview.md)  
> **Context nghiệm thu:** case ủy quyền duyệt FAHASA `FBISP24` (source) ↔ AIH `SP228` (target) — seed `dmuqduyet,vdmduyetuq,ma_quyen_uq`.

---

## 0. Prompt Gemini (copy-paste)

```text
Fix compare_things theo docs/doc/doc_fix/FIX-compare_things-signals-pk-message.md

Ưu tiên P0:
1) SQL signals: báo CẢ HAI phía (source_refs_* VÀ target_refs_*), không chỉ source.
   Khi source dùng vdmduyetuq mà target dùng dmduyet → phải có cặp signal rõ (vd source_refs_vdmduyetuq + target_refs_dmduyet).
   Khi CẢ HAI đã refs cùng view nhưng fingerprint vẫn different → đừng chỉ ghi source_refs_*; thêm signal kiểu both_refs_same_view / refs_equal_body_diff hoặc liệt kê refs_source vs refs_target trong fingerprint JSON.
2) Table PK: pk_diff=true chỉ vì khác THỨ TỰ cột cùng tập PK → KHÔNG coi different (hoặc tách pk_order_only=true, status identical/schema_noise). Cùng tập cột PK = identical về PK.
3) kind=file / xml: message không được nói "giống metadata" / "hoàn toàn giống metadata" khi meta_diff còn phần tử (vd created). Message phải khớp meta_diff.

P1:
4) Thêm/giữ fingerprint field refs_table / refs_view (sorted list) trên compared[] SQL để agent đọc không đoán từ signals.
5) Tests cho 1–3. pytest tests/compare_things/ pass; không regress clone_things.
```

---

## 1. [P0] Signals SQL chỉ một phía — agent đoán sai

### Repro (live)

```text
compare_things(
  kind="sql",
  project_source=\\172.168.5.14\CustomerPro\FBI\FAHASAKHANHHOA\FBISP24,
  project_target=\\172.168.5.14\CustomerPro\FBO\AIH\SP228,
  seed="dmuqduyet,vdmduyetuq,ma_quyen_uq",
  mode="summary"
)
```

Object ví dụ `dbo.FastBusiness$App$GetApprovalRole` / `dbo.ff_PRAuthorize` status=`different`, `signals` chỉ có:

```json
["source_refs_vdmduyetuq"]
```

**Không** có `target_refs_dmduyet` / `target_refs_vdmduyetuq`.

Trong khi nghiệp vụ ủy quyền cần biết nhanh:

| Source (FAH) | Target (AIH) | Signal kỳ vọng |
|--------------|--------------|----------------|
| `vdmduyetuq` | `dmduyet` | `source_refs_vdmduyetuq` + `target_refs_dmduyet` (+ ideally `delegation_view_mismatch`) |
| `vdmduyetuq` | `vdmduyetuq` nhưng body khác | `source_refs_vdmduyetuq` + `target_refs_vdmduyetuq` + `refs_match_body_diff` (hoặc tương đương) |
| có `dmuqduyet` Delegation block | không có | `source_refs_dmuqduyet` / `target_missing_dmuqduyet` (nếu đã scan) |

### Vì sao quan trọng

Agent/user đọc signal một phía sẽ nghĩ “chỉ source có uq” — không biết target đã chuyển `vdmduyetuq` hay còn `dmduyet`. Case live 2026-09-11: vài proc AIH **đã** `vdmduyetuq` nhưng vẫn `different` (lệch khác Delegation/whitespace) → signal hiện tại **gây hiểu nhầm**.

### Fix bắt buộc

1. Build `refs_view` / `refs_table` (sorted unique) **cho từng phía** từ definition (cùng pipeline fingerprint đang dùng).
2. Emit signals theo **cặp / từng phía**, ví dụ:
   - `source_refs_vdmduyetuq`, `target_refs_dmduyet`
   - hoặc structured:

```json
"refs": {
  "source": { "views": ["dbo.vdmduyetuq"], "tables": ["dbo.dmquyen", "dbo.dmuqduyet"] },
  "target": { "views": [], "tables": ["dbo.dmduyet", "dbo.dmquyen"] }
},
"signals": [
  "source_refs_vdmduyetuq",
  "target_refs_dmduyet",
  "delegation_view_mismatch"
]
```

3. Heuristic FBO tối thiểu (giữ mở rộng được):

| Pattern trong definition | Signal token |
|--------------------------|--------------|
| `vdmduyetuq` / `vgndmduyetuq` / `vsodmduyetuq` | `*_refs_vdmduyetuq` (hoặc đúng tên view) |
| `\bdmduyet\b` (không nhầm `dmuqduyet` / `gndmduyet` nếu tách word-boundary) | `*_refs_dmduyet` |
| `dmuqduyet` / `gndmuqduyet` / `sodmuqduyet` | `*_refs_dmuqduyet` |

**Cẩn thận word-boundary:** `gndmduyet` chứa substring `dmduyet` — phải match token SQL identifier, không `LIKE '%dmduyet%'`.

4. Khi `refs.source.views == refs.target.views` (và tables quan trọng giống) nhưng `status=different` → thêm `refs_match_body_diff` (body/fingerprint khác, refs không giải thích đủ).

### Test

- Fixture 2 definition: source `FROM vdmduyetuq`, target `FROM dmduyet` → signals có **cả hai** phía.
- Cả hai `FROM vdmduyetuq` nhưng thêm 1 dòng khác → `refs_match_body_diff` (hoặc cả hai `*_refs_vdmduyetuq`) + status different.
- Không match nhầm `dmuqduyet` thành `dmduyet`.

---

## 2. [P0] Table `pk_diff` chỉ vì thứ tự cột PK — nhiễu

### Repro (live)

```text
compare_things(
  kind="table",
  project_source=...FBISP24,
  project_target=...SP228,
  object="dmuqduyet,dmquyen"
)
```

`dbo.dmuqduyet` → `status=different`, `schema_diff.pk_diff=true`:

```json
"pk_source": ["loai_duyet", "u_id4", "ngay_hl"],
"pk_target": ["loai_duyet", "ngay_hl", "u_id4"]
```

Cùng 3 cột PK, **chỉ khác order** trong constraint. Cột/type không lệch. `dmquyen` identical.

### Kỳ vọng

- Coi PK **giống** nếu **tập cột** (set) bằng nhau — order trong `sys.index_columns` / constraint không làm `status=different`.
- Nếu muốn vẫn báo: `pk_order_diff=true` / đưa vào `schema_noise` hoặc `warnings`, **không** đẩy object vào `summary.different` chỉ vì order.
- `next_actions`: không `review_pk` khi chỉ order khác.

### Fix

So PK bằng `set(columns)` (và kiểu cột nếu cần). So sánh order chỉ optional flag `pk_column_order_diff`.

### Test

- Cùng PK columns khác ordinal → status identical (hoặc different=false cho PK), `pk_diff=false`, optional `pk_column_order_diff=true`.
- Thiếu 1 cột PK → `pk_diff=true`, status different.

---

## 3. [P0] Message file/xml mâu thuẫn `meta_diff`

### Repro (live)

```text
compare_things(
  kind="file",
  file_a=...FBISP24\Main\kbuqd.aspx,
  file_b=...SP228\Main\kbuqd.aspx
)
```

- `identical_content=true`
- `meta_diff: ["created"]`
- `message` dạng: *“Hai file hoàn toàn giống nhau về nội dung và metadata.”* ← **sai** (còn lệch created).

Tương tự `kind=xml` PUDelegationApproval: content identical, `meta_diff: ["created"]` — message phải nói rõ chỉ lệch meta (created), không “giống hết metadata”.

### Fix

Quy tắc message:

| identical_content | meta_diff | Message |
|-------------------|-----------|---------|
| true | `[]` | Giống nội dung + metadata |
| true | non-empty | Giống nội dung; khác metadata: liệt kê keys (`created`, …) |
| true + only_line_ending | … | Giống nội dung (bỏ qua CRLF/LF); … |
| false | … | Khác nội dung (kèm counts hunks) — không khẳng định giống meta nếu meta cũng lệch |

Áp dụng đồng nhất `kind=file` và `kind=xml` (mỗi compared item + message tổng nếu có).

### Test

- Content same, `created` khác → message **không** chứa “giống … metadata” / “hoàn toàn giống metadata”; phải mention `created` hoặc “khác metadata”.

---

## 4. [P1] Fingerprint SQL đủ để agent khỏi đoán

Trên mỗi `compared[]` khi kind=sql (summary cũng được):

```json
"fingerprint": {
  "source": { "sha_norm": "...", "refs_view": ["dbo.vdmduyetuq"], "refs_table": ["dbo.dmquyen"] },
  "target": { "sha_norm": "...", "refs_view": [], "refs_table": ["dbo.dmduyet", "dbo.dmquyen"] }
}
```

(Tên field có thể giữ `fingerprint_source` sha hiện tại + thêm object `refs` — miễn agent đọc được 2 phía.)

Không dump definition.

---

## 5. Việc không làm trong fix này

- Đổi semantics `project_source` / `project_target`
- Bật lại preview / unified_diff mặc định (giữ FIX diff-only)
- So data rows
- Tự ALTER / clone

---

## 6. Tiêu chí xong

1. Seed ủy quyền FAH↔AIH: object `different` vì `dmduyet` vs `vdmduyetuq` → signals/refs **2 phía** nhìn là biết ngay.
2. `dmuqduyet` chỉ khác order PK → **không** nằm `summary.different` chỉ vì PK order.
3. `kbuqd.aspx` identical content + `meta_diff=["created"]` → message khớp, không nói giống metadata.
4. `pytest tests/compare_things/` pass.

---

## 7. Gợi ý file code (Gemini tự tìm đúng path)

- `compare_things/signals.py` (hoặc tương đương) — emit 2 phía + word-boundary
- `compare_things/table_compare.py` — PK set vs order
- `compare_things/file_diff.py` / formatter message file+xml
- `compare_things/sql_compare.py` — gắn refs vào fingerprint
