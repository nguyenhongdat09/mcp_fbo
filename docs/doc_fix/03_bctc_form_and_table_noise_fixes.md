# Doc Fix — BCTC tạo mẫu + lọc nhiễu table (từ JSON `zc_bckqkdtda`)

> **Nguồn:** JSON thực tế user cung cấp (2026-08-20)  
> **Object:** `dbo.zc_bckqkdtda` (`line_count=426`, `parse_status=partial`, heuristic)  
> **Bối cảnh:** Proc lãi vay / tồn kho đã sạch sau doc `02`; proc **báo cáo KQKD theo dự án (BCTC/NS tạo mẫu)** vẫn nhiễu và thiếu domain hints.

---

## 1. Tóm tắt vấn đề

| Hạng mục | JSON hiện tại | Vấn đề |
|----------|---------------|--------|
| `tables_read` | có `"3"` | False positive (literal / TOP / index) |
| `tables_write` | `["res"]` | Alias/biến, không phải bảng DB |
| `logic_hints` | chỉ `WHILE` | Thiếu gợi ý domain BCTC/form |
| `param_effects` | không có `@form`, `@mau_bc`, `@ma_vv` | Param then chốt không được highlight |
| `result_sets` | `[]` | Chấp nhận — cần snippet zone `result_set` |

**Mục tiêu:** Agent nhận ra đây là **báo cáo tạo mẫu / chỉ tiêu NS theo dự án**, biết snippet keyword/zone, không bị nhiễu `"3"`/`res"`.

---

## 2. P0 — Lọc nhiễu table name (số thuần + alias `res`)

### 2.1. `tables_read` chứa số thuần `"3"`

**Actual:**

```json
"tables_read": ["3", "bcnsky", "dmctns", "dmvv", "glns", ...]
```

**Expected:** Không có identifier chỉ gồm chữ số.

**Fix — File:** `sql_object_summary/visitors/summary_visitor.py`

Trong `_normalize_table_name()` (sau khi lowercase), thêm:

```python
# Pure numeric tokens are not table names (TOP 3, array index, literal)
if clean_name.isdigit():
    return None
```

**Test:**

```python
def test_tables_read_rejects_pure_numeric():
    # fixture có "FROM 3" hoặc "JOIN 3" hoặc proc zc_bckqkdtda mock
    assert "3" not in summary.tables_read
```

---

### 2.2. `tables_write` chứa `"res"`

**Actual:**

```json
"tables_write": ["res"]
```

**Nguyên nhân khả dĩ:** Regex `UPDATE res SET ...` hoặc alias `#result res` / biến bảng.

**Expected:** `tables_write: []` (proc báo cáo read-only, không ghi bảng thật).

**Fix — File:** `sql_object_summary/visitors/summary_visitor.py`

Mở rộng `KNOWN_ALIAS_NOISE` hoặc `RESERVED_WORDS`:

```python
TABLE_NAME_NOISE = {
    "set", "res", "result", "tmp", "temp", "data", "fact",
    # ... giữ list reserved words hiện có
}
```

Áp dụng cho **cả** `tables_read_set` và `tables_write_set` trong `_normalize_table_name()`.

**Lưu ý:** `#result`, `#fact` đã nằm `temp_tables` — không cần `"res"` / `"fact"` trong tables_write.

**Test:**

```python
assert "res" not in summary.tables_write
```

---

## 3. P1 — Domain hints: `bctc_form_related` (tương tự `interest_related`)

### Hiện tại

```json
"logic_hints": {
  "keywords_suggested": ["WHILE"],
  "options_keys": ["m_round_tl"]
}
```

Agent **không** biết đây là báo cáo tạo mẫu / NS theo dự án.

### Expected

```json
"logic_hints": {
  "bctc_form_related": true,
  "keywords_suggested": [
    "@form", "@mau_bc", "@kieu_xem", "@kieu_dt", "@ma_vv",
    "bcnsky", "glns", "dmctns", "CheckFormula", "JobCalcXStruct",
    "#fact", "cach_tinh", "WHILE"
  ],
  "options_keys": ["m_round_tl"],
  "note": "Form/template report (bcnsky/glns); formula in CheckFormula + JobCalcXStruct; use mode=snippet with keywords_suggested or zones=['processing','result_set']"
}
```

### Fix — File: `sql_object_summary/visitors/summary_visitor.py`

Trong `_compute_logic_hints()`, bổ sung detect (heuristic, không cần ANTLR):

```python
bctc_form_related = bool(
    "bcnsky" in txt_lower
    or "glns" in txt_lower
    or "dmctns" in txt_lower
    or "checkformula" in txt_lower
    or "jobcalcxstruct" in txt_lower
    or ("@form" in txt_lower and "@mau_bc" in txt_lower)
)
```

**Candidate keywords** (chỉ thêm vào list nếu có trong text):

```python
BCTC_CANDIDATE_KEYWORDS = [
    "@form", "@mau_bc", "@kieu_xem", "@kieu_dt", "@ma_vv", "@ma_bp",
    "bcnsky", "glns", "dmctns", "dmvv", "#fact", "#glns",
    "CheckFormula", "JobCalcXStruct", "cach_tinh", "ty_trong",
    "fs20_JobCalcXStruct", "WHILE"
]
```

**Note priority** (sau interest, trước pivot):

```python
if interest_related:
    hints["note"] = "..."
elif bctc_form_related:
    hints["bctc_form_related"] = True
    hints["note"] = "Form/template report ..."
elif stock_related:  # xem mục 5 (optional)
    ...
elif "pivot" in self.zones_detected_set:
    ...
```

**Test:** Fixture proc có `bcnsky` + `@form` → `logic_hints.bctc_form_related is True` và `keywords_suggested` chứa `@mau_bc`.

---

## 4. P1 — `param_effects` cho param BCTC then chốt

### Hiện tại

Có `@Language`, `@thang_tu`, `@nam_tu`… nhưng **thiếu** `@form`, `@mau_bc`, `@ma_vv`, `@kieu_xem`.

Rule `@mau_bc` đã có trong `param_effects.py` nhưng pattern chỉ match pivot (`#pivot`, `xpivot`) — **không match** proc BCTC NS.

### Fix — File: `sql_object_summary/visitors/param_effects.py`

Bổ sung / mở rộng `SPECIFIC_PARAM_RULES`:

```python
{
    "param": r"^@form$",
    "patterns": [
        r"@form\s*=",
        r"dmctns",
        r"bcnsky",
        r"glns",
    ],
    "role": "branching",
    "effect": "Selects report form template / chỉ tiêu structure (dmctns, bcnsky)",
    "confidence": "high",
},
{
    "param": r"^@mau_bc$",
    "patterns": [
        r"@mau_bc\s*=",
        r"bcnsky",
        r"glns",
        r"#pivot",
        r"xpivot",
    ],
    "role": "branching",
    "effect": "Controls report template / layout / pivot or NS structure",
    "confidence": "high",
},
{
    "param": r"^@ma_vv$",
    "patterns": [
        r"@ma_vv\s*=",
        r"dmvv",
        r"#dmvv",
        r"JobCalcXStruct",
    ],
    "role": "filter",
    "effect": "Filters by job/project (vụ việc / dự án)",
    "confidence": "medium",
},
{
    "param": r"^@kieu_xem$",
    "patterns": [r"@kieu_xem\s*="],
    "role": "branching",
    "effect": "Controls view mode / report display type",
    "confidence": "medium",
},
```

**Giới hạn:** Vẫn max **5** `param_effects` — ưu tiên sort:

1. `confidence`: high > medium > low  
2. Rule Tier 2 (specific) trước Tier 1 generic  
3. Param domain: `@form`, `@mau_bc`, `@ma_vv` trước `@thang_tu` generic  

**Test:** Mock proc `zc_bckqkdtda` → `param_effects` chứa ít nhất `@form` hoặc `@mau_bc` với confidence high/medium.

---

## 5. P2 (optional) — Domain hints tồn kho `stock_related`

JSON `rs_rptStockSummaryByLotItem` sau fix v2 vẫn chỉ có:

```json
"logic_hints": { "options_keys": ["m_instock_split"] }
```

**Detect khi:**

```python
stock_related = bool(
    "balance$lot" in txt_lower
    or "m_instock_split" in txt_lower
    or ("dmvt" in txt_lower and "dmlo" in txt_lower)
)
```

**Keywords gợi ý:** `@CalculateTransfer`, `@Key`, `Balance$Lot`, `@ReportType`, `@DataType`, `ton_`, `sl_`

Không blocker — làm cùng PR với BCTC nếu tiện.

---

## 6. JSON mục tiêu (`zc_bckqkdtda` sau fix)

```json
{
  "object": "dbo.zc_bckqkdtda",
  "summary": {
    "tables_read": ["bcnsky", "dmctns", "dmvv", "glns", "options", "r00$", "wrkcolumns"],
    "tables_write": [],
    "signals": {
      "has_dynamic_sql": true,
      "uses_partition_execute": true
    },
    "param_effects": [
      {
        "param": "@form",
        "role": "branching",
        "effect": "Selects report form template / chỉ tiêu structure (dmctns, bcnsky)",
        "confidence": "high"
      },
      {
        "param": "@mau_bc",
        "role": "branching",
        "effect": "Controls report template / layout / NS structure",
        "confidence": "high"
      },
      {
        "param": "@ma_vv",
        "role": "filter",
        "effect": "Filters by job/project (vụ việc / dự án)",
        "confidence": "medium"
      }
    ],
    "logic_hints": {
      "bctc_form_related": true,
      "keywords_suggested": ["@form", "@mau_bc", "bcnsky", "glns", "CheckFormula", "JobCalcXStruct", "WHILE"],
      "note": "Form/template report; use mode=snippet with keywords_suggested"
    }
  }
}
```

---

## 7. Thứ tự implement (Gemini)

| # | Việc | File | Ưu tiên |
|---|------|------|---------|
| 1 | Lọc `isdigit()` khỏi table names | `summary_visitor.py` | P0 |
| 2 | Lọc `res`, `fact`, `result` khỏi tables_write/read | `summary_visitor.py` | P0 |
| 3 | `bctc_form_related` + keywords + note | `summary_visitor.py` | P1 |
| 4 | Rules `@form`, `@mau_bc`, `@ma_vv`, `@kieu_xem` | `param_effects.py` | P1 |
| 5 | `stock_related` (optional) | `summary_visitor.py` | P2 |
| 6 | Unit tests 3 case | `test_analyze_proc.py` | P1 |

---

## 8. Checklist PASS trước khi báo xong

- [ ] `zc_bckqkdtda` summary: `"3" not in tables_read`
- [ ] `zc_bckqkdtda` summary: `"res" not in tables_write`
- [ ] `logic_hints.bctc_form_related == true`
- [ ] `keywords_suggested` chứa `@form` và `@mau_bc`
- [ ] `param_effects` có `@form` hoặc `@mau_bc` (high/medium)
- [ ] Regression: proc lãi vay vẫn có `interest_related`, không mất `@Status` effect
- [ ] Regression: proc tồn kho vẫn sạch `nvarchar`/`set`, `has_dynamic_sql=true`
- [ ] `pytest tests/sql_object_summary/` PASS

---

## 9. Known limitation (không sửa v1)

- `result_sets: []` với proc 426 dòng heuristic — **OK**; Agent dùng `snippet_index.result_set` [372, 392].
- Không parse công thức `cach_tinh` vào summary — thuộc snippet/full.
- `processing` zone [86, 375] vẫn rộng — chấp nhận; ưu tiên `result_set` + keywords.

---

*Tham chiếu:* [01_improve_summary_for_agent.md](./01_improve_summary_for_agent.md), [02_additional_fixes_from_real_json.md](./02_additional_fixes_from_real_json.md)
