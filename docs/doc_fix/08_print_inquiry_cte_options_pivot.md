# Doc Fix 08 — Print/inquiry `zc_*` + CTE noise + options/PIVOT + result_sets

> **Nguồn:** Đối chiếu MCP definition thật vs JSON `summary_object`  
> **Object:** `dbo.zc_dxtlccdc` (VINHQUANG_FBISP242_A, 2026-08-20)  
> **Vấn đề:** Summary định vị đúng loại phiếu CCDC, nhưng **domain note sai** (gọi là action/manipulation), **thiếu 3 result sets in**, **thiếu option key + PIVOT**, **nhiễu CTE** trong `tables_read`.

---

## 1. Evidence — JSON vs proc thật

| Hạng mục | JSON summary | Proc thật (MCP) | Cần sửa |
|----------|--------------|-----------------|---------|
| Mục đích | `custom_action_related` + note manipulation | **In phiếu** — 3 SELECT output, `tables_write: []` | Domain print/inquiry |
| `result_sets` | `[]` | RS1 master `#m89`, RS2 detail `#d89`, RS3 chữ ký PIVOT | Heuristic RS |
| `options_keys` | `[]` | `zc_7_cd_tl` từ `options` | Regex options |
| `uses_pivot_pattern` | `false` | Có SQL `PIVOT (... FOR cap IN ...)` | Detect `PIVOT` |
| `tables_read` | có `ranked`, `max_reset`, `nguoi_duyet`, `media` | CTE / comment — không phải bảng | Noise filter |
| Partition suffix | `a89$000000`, `m89$000000` | Nên gộp `a89$`, `m89$` | Normalize |
| `uses_partition_execute` | `true` | Chỉ `EXEC(@q)` + `m89$`+parti — **không** gọi `Partition$Execute` | Signal tách (P2) |

**Comment trong proc:** `--C-KHANHTD save as zc_dxct` — đây là proc **lấy dữ liệu in**, không post/update chứng từ.

---

## 2. P0 — Phân loại `custom_action` vs `custom_report` (print/inquiry)

### Hiện tại (bug)

`custom_is_action` match quá rộng:

```python
custom_is_action = bool(
    is_custom
    and (
        any(obj_bare.startswith(p) for p in ["zc_post", "zc_insert", ...])
        or len(self.tables_write_set) > 0
        or "@stt_rec" in txt_lower   # ← BUG: gần như mọi phiếu in đều có @stt_rec
        or "@action" in txt_lower
    )
)
```

→ `zc_dxtlccdc` có `@stt_rec` → bị gán **action** dù `tables_write: []`.

### Expected

| Điều kiện | Domain |
|-----------|--------|
| `zc_*` + (`tables_write` thật **hoặc** tên `zc_post/insert/update/...` **hoặc** `@action`) | `custom_action_related` |
| `zc_*` + `@stt_rec` + `tables_write` rỗng + ≥1 SELECT cuối không INTO | `custom_report_related` (print/inquiry) |
| `zc_*` còn lại | `custom_related` |

### Fix — File: `summary_visitor.py`

```python
has_real_write = bool(self.tables_write_set)  # sau khi filter #temp (đã đúng)

custom_is_action = bool(
    is_custom
    and (
        any(obj_bare.startswith(p) for p in [
            "zc_post", "zc_insert", "zc_update", "zc_delete", "zc_del",
            "zc_save", "zc_check", "zc_import", "zc_convert", "zc_create", "zc_auto"
        ])
        or has_real_write
        or re.search(r"@action\b", txt_lower)
        # KHÔNG dùng "@stt_rec" alone làm action
    )
)

# Đếm SELECT output (không INTO, không gán @var) — dùng cho report/print
output_select_count = len(re.findall(
    r"(?im)^\s*SELECT\b(?![^\n]*@\w+\s*=)(?![^\n]*\bINTO\b)",
    self.full_text,
))
# Đơn giản hơn: nếu đã có result_sets heuristic sau bước §5 thì dùng len(result_sets)

custom_is_report = bool(
    is_custom
    and not custom_is_action
    and (
        any(obj_bare.startswith(p) for p in ["zc_bc", "zc_rpt", "zc_list", "zc_view", "zc_dx", "zc_in"])
        or "#report" in txt_lower
        or "@datefrom" in txt_lower
        or (
            "@stt_rec" in txt_lower
            and not has_real_write
            and output_select_count >= 1
        )
    )
)
```

**Note khi `custom_report_related`:**

```text
"Custom print/inquiry procedure; multiple result sets for form/report; use snippet result_set / processing"
```

**Keywords seed** thêm cho `custom_report_related`: `@stt_rec`, `#cap_duyet`, `zcdmsignature`, `chu_ky`, `PIVOT` (nếu có trong text).

### Test

```python
def test_zc_dxtlccdc_is_custom_report_not_action():
    # fixture rút gọn: @stt_rec, tables_write empty, 2 SELECT FROM #m89 / #d89
    assert hints.get("custom_report_related") is True
    assert hints.get("custom_action_related") is not True
    assert "print/inquiry" in hints.get("note", "").lower() or "inquiry" in hints.get("note", "").lower()
```

---

## 3. P0 — Lọc CTE / alias khỏi `tables_read`

### Actual noise từ `zc_dxtlccdc`

`ranked`, `max_reset`, `nguoi_duyet`, `media` (media nằm trong comment/`#image_tmp` — nếu vẫn bắt thì lọc).

### Fix

**A) Thêm vào `SQL_TABLE_NOISE_TOKENS`:**

```python
"ranked", "max_reset", "nguoi_duyet", "media", "t", "p_comment", "p_dt", "p_img",
```

**B) (Khuyến nghị mạnh hơn)** Detect CTE names rồi deny:

```python
# ;WITH name AS (  hoặc  WITH name AS (
cte_names = re.findall(r"(?i)(?:;?\s*WITH|,)\s*([a-zA-Z_][\w]*)\s+AS\s*\(", self.full_text)
for name in cte_names:
    # không add vào tables_read; hoặc add vào deny set runtime
```

Áp dụng trong `_normalize_table_name` hoặc trước `_add_table` heuristic FROM/JOIN.

### Partition gộp

Đã có gộp `r00$000000` → `r00$`. Mở rộng cho **`a89$`, `m89$`, `d89$`, `c89$`**:

```python
# Hiện: ^([rdc]\d\d\$)\d+$
# Sửa:  ^([a-z]\d\d\$)\d+$   hoặc ^(a|r|d|c|m)\d\d\$\d+$
partition_match = re.match(r"^([ardcm]\d\d\$)\d+$", clean_name)
```

→ `a89$000000` → `a89$`, `m89$000000` → `m89$`.

### Test

```python
assert "ranked" not in tables_read
assert "max_reset" not in tables_read
assert "nguoi_duyet" not in tables_read
assert "a89$000000" not in tables_read
assert "a89$" in tables_read or "a89$000000" not in tables_read
```

---

## 4. P1 — `options_keys` bắt option cách dòng

### Actual

Proc:

```sql
FROM options a cross apply ...
WHERE name = 'zc_7_cd_tl'
```

Regex hiện tại:

```python
r"options\s+WHERE\s+name\s*=\s*'([^']+)'"
```

→ **không match** vì `WHERE` không liền sau `options`.

### Fix

```python
# 1) Giữ pattern cũ
# 2) Thêm: trong cửa sổ gần FROM options ... name = '...'
options_matches = re.findall(
    r"options\b[\s\S]{0,200}?name\s*=\s*'([^']+)'",
    self.full_text,
    re.IGNORECASE,
)
# Giới hạn 200 ký tự tránh bắt nhầm options khác
```

Hoặc:

```python
r"(?is)FROM\s+options\b.*?WHERE\s+.*?name\s*=\s*'([^']+)'"
```

**Expected JSON:**

```json
"options_keys": ["zc_7_cd_tl"]
```

### Test

Fixture có `FROM options a ... WHERE name = 'zc_7_cd_tl'` → `options_keys` chứa `zc_7_cd_tl`.

---

## 5. P1 — Detect SQL `PIVOT` (không chỉ `#pivot`)

### Actual

Chỉ:

```python
if "#pivot" in text or "xpivot" in text or "xsearch" in text:
```

Proc `zc_dxtlccdc` dùng `PIVOT (MAX(comment) FOR cap IN (...))` → miss.

### Fix

```python
if (
    "#pivot" in txt
    or "xpivot" in txt
    or "xsearch" in txt
    or re.search(r"\bPIVOT\s*\(", self.full_text, re.IGNORECASE)
):
    self.signals.uses_pivot_pattern = True
    self.zones_detected_set.add("pivot")
```

### Test

```python
assert signals.uses_pivot_pattern is True  # trên fixture có PIVOT (
```

---

## 6. P1 — Heuristic `result_sets` cho SELECT cuối (print form)

### Actual

AST + heuristic line-based bỏ SELECT nhiều dòng / CTE trước SELECT → `result_sets: []` dù có 3 RS.

### Expected cho `zc_dxtlccdc` (confidence medium, không cần đủ cột)

```json
"result_sets": [
  {"ordinal": 1, "hint": "master", "confidence": "medium", "columns_hint": ["so_ct", "nguoi_de_xuat", "ly_do_thanh_ly"]},
  {"ordinal": 2, "hint": "detail", "confidence": "medium", "columns_hint": ["ma_tb", "ten_tb", "so_luong"]},
  {"ordinal": 3, "hint": "signature", "confidence": "low", "columns_hint": ["ten_ng_duyet_1", "chu_ky_1"]}
]
```

Nếu extract cột khó (SELECT nhiều dòng): vẫn trả **ordinal + hint**, `columns_hint` có thể `[]` hoặc vài cột nhận diện được — **không để `[]` hoàn toàn** khi rõ ràng có ≥1 SELECT output.

### Fix gợi ý

Sau khi normalize lines, tìm các khối:

1. Bỏ `SELECT ... INTO #`
2. Bỏ `SELECT @x =`
3. Bỏ SELECT trong `DECLARE CURSOR`
4. Các `SELECT` còn lại **sau nửa sau của proc** (hoặc sau comment `-- BẢNG` / không theo sau bởi chỉ INSERT temp) → coi là result set

Hoặc đơn giản hơn cho print procs:

```python
# Đếm top-level SELECT không INTO trong nửa cuối file
# Cap max 5 result_sets
# hint: ordinal==1 -> "master" nếu có @stt_rec; else "listing"
```

**Ưu tiên:** đúng **số lượng RS** (3) quan trọng hơn đủ `columns_hint`.

### Test

```python
assert len(summary.result_sets) >= 2  # master + detail tối thiểu
```

---

## 7. P2 — Signal partition (optional)

`uses_partition_execute: true` khi chỉ có bảng `m89$` + `EXEC(@q)` gây hiểu nhầm Agent nghĩ gọi `FastBusiness$Partition$Execute`.

**Option A:** Đổi tên signal (breaking) — tránh trong v1.

**Option B (khuyến nghị):** Chỉ set `uses_partition_execute` khi **thật sự** gọi `Partition$Execute`; thêm:

```python
signals.uses_partition_tables = True  # khi thấy [ardcm]\d\d$
```

Nếu chưa muốn thêm field: giữ nguyên + ghi known limitation trong tool description.

---

## 8. JSON mục tiêu (`zc_dxtlccdc` sau fix)

```json
{
  "object": "dbo.zc_dxtlccdc",
  "summary": {
    "tables_read": ["a89$", "c89$", "d89$", "dmbp", "fsdgalleryimage", "m89$", "options", "tbdmnv", "tbtttb", "vsysuserinfo", "zcdmsignature"],
    "tables_write": [],
    "signals": {
      "has_dynamic_sql": true,
      "uses_pivot_pattern": true,
      "options_keys": ["zc_7_cd_tl"]
    },
    "result_sets": [
      {"ordinal": 1, "hint": "master", "confidence": "medium", "columns_hint": ["so_ct", "nguoi_de_xuat", "ly_do_thanh_ly"]},
      {"ordinal": 2, "hint": "detail", "confidence": "medium", "columns_hint": ["ma_tb", "ten_tb", "so_luong"]},
      {"ordinal": 3, "hint": "signature", "confidence": "low", "columns_hint": ["ten_ng_duyet_1", "chu_ky_1"]}
    ],
    "logic_hints": {
      "custom_report_related": true,
      "custom_related": true,
      "note": "Custom print/inquiry procedure; multiple result sets for form/report; use snippet result_set / processing",
      "keywords_suggested": ["@stt_rec", "#cap_duyet", "zcdmsignature", "m89$", "d89$", "PIVOT"],
      "options_keys": ["zc_7_cd_tl"]
    }
  }
}
```

---

## 9. Thứ tự implement

| # | Việc | File | Ưu tiên |
|---|------|------|---------|
| 1 | Bỏ `@stt_rec` khỏi `custom_is_action`; print → `custom_report` | `summary_visitor.py` | P0 |
| 2 | CTE deny + partition `[ardcm]\d\d$` | `summary_visitor.py` | P0 |
| 3 | Options regex đa dòng | `summary_visitor.py` | P1 |
| 4 | Detect `\bPIVOT\s*\(` | `summary_visitor.py` | P1 |
| 5 | Heuristic result_sets số lượng / hint | `summary_visitor.py` | P1 |
| 6 | Keyword seeds print | `keyword_builder.py` | P1 |
| 7 | Unit tests + fixture `zc_dxtlccdc` rút gọn | `test_analyze_proc.py` | P1 |
| 8 | Partition signal tách (optional) | models + visitor | P2 |

---

## 10. Checklist PASS

- [ ] `zc_dxtlccdc` (hoặc fixture tương đương): `custom_report_related`, **không** `custom_action_related`
- [ ] `ranked` / `max_reset` / `nguoi_duyet` **không** trong `tables_read`
- [ ] `a89$000000` không còn; có `a89$` hoặc tương đương gộp
- [ ] `options_keys` chứa `zc_7_cd_tl`
- [ ] `uses_pivot_pattern: true`
- [ ] `len(result_sets) >= 2`
- [ ] Regression: `zc_Post*` / proc có `tables_write` thật vẫn `custom_action`
- [ ] Regression: lãi / kho / BCTC / doc 07 flags không đổi
- [ ] `pytest tests/` PASS

---

## 11. Explicit NON-GOALS

- ❌ Không hardcode tên `zc_dxtlccdc`
- ❌ Không yêu cầu columns_hint đầy đủ 30 cột master
- ❌ Không đổi `kind: business` của proc
- ❌ Không bắt buộc rename `uses_partition_execute` trong cùng PR (P2)

---

*Tham chiếu:* case JSON user + MCP `query_database type=0` object `zc_dxtlccdc`; [07_fbo_business_domain_flags.md](./07_fbo_business_domain_flags.md)
