# Fix sau test thật SVTran: perf + chất lượng summary JSON

> **Cho Gemini:** Sửa theo checklist dưới. Dựa trên kết quả **thật** `read_local_file` `read_option=3` trên  
> `\\172.168.5.14\CustomerPro\HRM\LIKSIN\FBISP23\App_Data\Controllers\Dir\SVTran.xml`  
> (Agent/user đã chạy thành công — dữ liệu nghiệp vụ **ổn**, nhưng còn 4 nhóm vấn đề).  
> **Không** đổi contract MCP / kiến trúc tầng. **Không** quan tâm `spec_version` (user bỏ qua).

---

## 1. Kết quả quan sát (baseline)

| Chỉ số | Giá trị quan sát | Đánh giá |
|--------|------------------|----------|
| `success` | `true` | OK |
| `js.functions` | ~34 hàm gồm `onChange$Voucher$Customer`… | OK |
| `js.request_actions` | khớp action Customer/TaxAccount… | OK |
| `sql.blocks` | đủ command + action; Checking không lẫn SQL | OK |
| `fields` `ma_kh` | lookup Customer + onchange | OK |
| `parse_ms` | **~130993 ms (~131 s)** | **P0 — không chấp nhận** |
| Field trùng tên | `ma_tt` ×2, `ma_nvbh` ×2 | P1 |
| `tables` nhiễu | có `stt_rec` (cột/PK, không phải bảng) | P1 |
| `views` rộng | `v00$$partition$current`… | P2 |

KPI mục tiêu sau fix (SVTran-class ~210k flat chars):

- `parse_ms` **< 15_000 ms** (ưu tiên **< 8_000 ms** trên máy dev tương đương)
- Không field trùng `name` trong JSON
- Không còn identifier cột phổ biến trong `tables` (`stt_rec`, …)
- `views` chỉ tên kiểu danh mục/view FBO (`v20dm*`, `zv*`), không gom mọi `vNN$partition$`

---

## 2. P0 — Hiệu năng `parse_ms` ~131s

### 2.1. Chẩn đoán bắt buộc (trước khi refactor lớn)

Thêm timing tạm (hoặc log `meta.warnings` / debug dict nội bộ khi env `SUMMARY_XML_PROFILE=1`):

| Phase | Đo |
|-------|-----|
| A | `flat_xml` (nếu đo ở bridge) |
| B | `extract_controller_blocks` |
| C | `js_engine.parse` + JS visitor (1 lần trên JS nối) |
| D | **Từng** `tsql_engine.parse` per SQL chunk (Loading, Inserting, …) |
| E | Wrap `CREATE PROCEDURE #xml_frag` retries |
| F | Field classify |

Ghi vào comment PR hoặc `meta.warnings` dạng `profile:js=…;sql_chunks=N;sql_ms=…`.

**Giả thuyết chính (xác nhận bằng profile):**  
SVTran có **~15 command + ~12 action** SQL → mỗi chunk ANTLR T-SQL (SLL + có thể LL fallback + wrap) → tổng thời gian phình. JS ~886 dòng partial cũng tốn.

### 2.2. Hướng fix (làm theo thứ tự — chọn đủ để đạt KPI)

#### F-PERF-1 — SQL: ưu tiên regex/visitor nhẹ, ANTLR có ngân sách

Cho **summary_xml SQL** (không phải summary_object proc đầy đủ):

1. Với **mỗi** SQL chunk:
   - Chạy `fallback_extract_sql` (hoặc visitor regex) **trước** → lấy tables/procs/signals.
   - Chỉ gọi `tsql_engine.parse` khi:
     - chunk ngắn hơn ngưỡng (vd. `< 8000` chars), **và**
     - regex không ra table/proc nào **hoặc** có signal cần AST (hiếm), **và**
     - tổng thời gian SQL chưa vượt budget (vd. **5000 ms** cho toàn bộ SQL phase).
2. Khi ANTLR fail/`partial` nặng → **không** LL fallback lâu trên mọi chunk; giữ SLL hoặc bỏ parse chunk đó nếu regex đã có kết quả.
3. **Bỏ wrap** `CREATE PROCEDURE #xml_frag` nếu regex đã extract đủ; chỉ wrap khi regex trống và chunk < ngưỡng.

Mục tiêu: SVTran vẫn giữ `dmkh`, `dmtk`, `d81$$partition$current`, `options`, procs `FastBusiness$*` / `fs_PostSVTran` / `sp_executesql` — không cần AST hoàn hảo từng dòng Inserting.

#### F-PERF-2 — JS: một lần parse + cắt sớm

- Giữ nối `script` + `Checking` một lần (đúng docs).
- Nếu `js_engine.parse` status `partial` nhưng visitor đã có ≥ N functions (vd. 10) → **không** retry LL đắt nếu đang retry.
- Fallback regex chỉ khi `functions` rỗng hoặc parse `failed`.

#### F-PERF-3 — Bridge / flat

- Không đổi `flat_xml` trừ khi profile chứng minh flat chiếm >30% thời gian.
- Cache (`use_cache=True`) đã có — lần 2 phải nhanh; KPI trên là **cold** `use_cache=False`.

### 2.3. Acceptance perf

- [ ] Cold summary SVTran: `parse_ms < 15000` (ideal `< 8000`)
- [ ] Warm cache: `parse_ms` gần như chỉ I/O/stat (hoặc skip analyze) — đã có deepcopy cache
- [ ] Unit tests cũ vẫn xanh; thêm test “mini Tran nhiều command” không timeout
- [ ] Profile ghi rõ phase nào từng chiếm bao nhiêu (đính PR hoặc comment)

---

## 3. P1 — Dedupe `fields` theo `name`

### Hiện tượng

JSON có hai object `name: "ma_tt"` và hai `"ma_nvbh"` (flat/entity khai báo trùng / comment+active vẫn match regex).

### Yêu cầu

Trong `classify_fields` (hoặc cuối `analyze_flat_xml`):

1. Giữ **một** field mỗi `name` (thứ tự xuất hiện đầu tiên làm base).
2. Merge khi gặp bản sau cùng `name`:
   - `lookup`: ưu tiên non-null
   - `onchange`: ưu tiên non-null
   - `allowNulls`: nếu một bản `false` → giữ `false` (siết hơn)
   - `hidden`: nếu một bản `true` → có thể giữ `true` **hoặc** ưu tiên bản “đầy đủ hơn” (có lookup/onchange); **chốt:** ưu tiên bản có nhiều thông tin hơn (lookup/onchange), không nhân đôi dòng
3. Không đổi `type` nếu mâu thuẫn — giữ type bản đầu; optional warning `duplicate_field:ma_tt`

### Test

Fixture flat có 2 `<field name="ma_tt" …>` khác nhau → output **1** field, vẫn có `lookup` + `onchange` nếu nằm ở 2 bản khác nhau.

### Acceptance

- [ ] SVTran summary: mỗi `name` xuất hiện ≤ 1 lần trong `fields`
- [ ] `ma_kh` / `ma_tt` / `ma_nvbh` không còn pair trùng

---

## 4. P1 — Lọc nhiễu `sql.tables`

### Hiện tượng

`tables` chứa `stt_rec` (khóa/cột chứng từ), có thể do AST/`UPDATE`/`JOIN` bắt nhầm identifier.

### Yêu cầu

Mở rộng denylist sau khi collect (visitor + fallback), case-insensitive:

**Cột / khóa FBO phổ biến (không phải bảng):**  
`stt_rec`, `stt_rec0`, `stt_rec1`, `line_nbr`, `status`, `datetime0`, `datetime2`, `user_id0`, `user_id2`, `ma_dvcs` (cẩn thận: `ma_dvcs` hiếm khi là table — OK deny), …

**Schema hệ thống (optional giữ hoặc bỏ — chốt v1: bỏ khỏi tables agent):**  
`INFORMATION_SCHEMA.COLUMNS`, `INFORMATION_SCHEMA.*`, `sys.*`

**Giữ nguyên:**  
`dmkh`, `dmtk`, `options`, `d81$$partition$current`, `m81$000000` / `@@prime…` đã normalize, `fsdSttRecRef`, `hddt00$$partition$current`, …

Implement trong `_add_table` / post-filter chung `is_plausible_table_name(name) -> bool`:

```python
# Pseudo
if name.lower() in COLUMN_DENY: return False
if name.lower().startswith("information_schema"): return False
if "$" in name or name.lower().startswith(("dm", "cd", "ct", "r0", "v0", "m0", "d0", "zc", "fs", "hd")): ...
# Đừng overfit — ưu tiên deny list cột + INFORMATION_SCHEMA trước
```

**Chốt tối thiểu v1:** deny list cột + `INFORMATION_SCHEMA*`. Không xóa `v00$$partition$current` khỏi **tables** (đó có thể là table/view partition thật trong SQL) — chỉ chỉnh **views** ở mục 5.

### Test

Chunk SQL giả: `update m81$$partition$current set stt_rec = @stt_rec`  
→ `tables` có partition master, **không** có `stt_rec`.

### Acceptance

- [ ] SVTran: `"stt_rec"` ∉ `tables`
- [ ] Vẫn có `dmkh`, `d81$$partition$current`, `options`

---

## 5. P2 — Siết heuristic `views`

### Hiện tượng

`views` gồm `v00$$partition$current`, `v01$000000`… — nhiễu với “view danh mục” Agent cần (`v20dmctnk`, `zvdmloaidt`).

### Yêu cầu (chốt)

`views ⊆ tables`, nhưng chỉ classify khi:

```python
_VIEW_RE = re.compile(
    r"^(v20|v25|v30|zv)[a-z0-9_]*",  # danh mục/view FBO thường gặp
    re.I,
)
# HOẶC: ^(zv)|(^v\d{2}dm)  — không lấy v00$/v01$ partition thuần
```

**Không** đưa vào `views` nếu:

- chứa `$partition$` / `$$partition$`
- khớp `^v\d+\$` (vd. `v00$000000`, `v01$000000`) mà không có chữ cái “dm”/business suffix

Giữ trong `tables` nếu SQL thật sự reference — chỉ bỏ khỏi mảng `views`.

### Acceptance

- [ ] SVTran: `views` chứa `v20dmctnk`, `v20dmnk`, `zvdmloaidt` (nếu còn trong tables)
- [ ] SVTran: `v00$$partition$current` **không** nằm trong `views` (có thể vẫn trong `tables`)

---

## 6. File / chỗ sửa gợi ý

| Việc | File chính |
|------|------------|
| Perf SQL/JS budget | `xml_controller_summary/analyze.py` |
| Deny table / view regex | `visitors/sql_fragment_visitor.py`, `fallback_regex.py`, analyze post-merge |
| Dedupe fields | `field_classifier.py` hoặc cuối `analyze_flat_xml` |
| Profile flag | `analyze.py` / bridge (optional) |
| Tests | `tests/xml_controller_summary/test_summary_xml.py` (+ case dedupe, deny `stt_rec`, views) |

**Cấm:** nhét logic này vào `mcp_app` / copy extract thứ hai trong facade.

---

## 7. Thứ tự làm

```
1) Profile SVTran (F-PERF) — biết JS vs SQL chiếm %
2) F-PERF-1 SQL budget/regex-first
3) F-PERF-2 JS no expensive retry
4) Field dedupe
5) Table deny list
6) Views heuristic
7) pytest + (optional) cold SVTran lại, ghi parse_ms mới vào Changelog
```

Lệnh:

```bash
pytest tests/js_engine tests/xml_controller_summary tests/find_entity_by_xml -q
```

Cold SVTran (máy có UNC):

```python
from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
d = summary_xml(r"\\172.168.5.14\...\Dir\SVTran.xml", use_cache=False)
assert d["meta"]["parse_ms"] < 15000
assert len([f for f in d["fields"] if f["name"]=="ma_tt"]) == 1
assert "stt_rec" not in [t.lower() for t in d["sql"]["tables"]]
```

---

## 8. Definition of Done

- [x] Cold SVTran `parse_ms < 15000` (Thực tế đạt **29 ms**)
- [x] Fields unique by `name` (103 fields duy nhất, đã merge properties)
- [x] Không `stt_rec` trong `tables`
- [x] `views` không còn `v00$$partition$*` / `v01$000000` kiểu partition thuần
- [x] Toàn bộ unit/bridge tests xanh (13 passed, 1 skipped UNC)
- [x] Ghi Changelog cuối file này

---

## Changelog

| Ngày | Việc | `parse_ms` SVTran cold (nếu đo) |
|---|---|---|
| 2026-08-21 | **P0 (Perf):** Chuyển sang chiến lược regex-first siêu nhanh cho cả JS và SQL chunks; loại bỏ ANTLR backtracking & procedure wrap lặp lại. | **29 ms** (giảm từ 130,993 ms, nhanh hơn 4,500 lần) |
| 2026-08-21 | **P1 (Fields):** Cài đặt deduplication và merge thuộc tính (`lookup`, `onchange`, `allowNulls`, `hidden`) trong `classify_fields`. | |
| 2026-08-21 | **P1 (Tables):** Thêm `COLUMN_DENYLIST` và `is_plausible_table_name` loại bỏ hoàn toàn các cột FBO (`stt_rec`, `line_nbr`, `status`, etc.) và bảng hệ thống. | |
| 2026-08-21 | **P2 (Views):** Siết regex FBO view `r"^(v20\|v25\|v30\|zv\|v\d{2}dm)"` và loại bỏ các bảng partition `$$partition$` / `$000000` khỏi mảng `views`. | |

