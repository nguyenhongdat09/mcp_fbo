# Doc Fix — Generic hints cho proc custom `zc_*` (không hardcode từng param)

> **Nguồn:** JSON thực tế `dbo.zc_ttdmtb` (2026-08-20)  
> **Vấn đề:** Proc không khớp domain `interest_related` / `stock_related` / `bctc_form_related` → `logic_hints` trống; param custom như `@tao_yn`, `@loai`, `@Source` không vào top 5 `param_effects` vì thua `@Admin`, `@Customer`…  
> **Nguyên tắc:** **Pattern generic + trích từ proc thật** — **KHÔNG** hardcode riêng `@tao_yn` trừ khi sau này lặp ≥ 5 proc cùng semantics.

---

## 1. Tóm tắt vấn đề (`zc_ttdmtb`)

| Hạng mục | JSON hiện tại | Vấn đề |
|----------|---------------|--------|
| `logic_hints` | `{}` (trống) | Agent không biết domain / snippet keyword |
| `param_effects` | `@Admin`, `@VCFrom`, `@Customer`… | Thiếu `@tao_yn`, `@loai`, `@Source`, `@phan_loai` |
| `tables_read` | có `information_schema` | System catalog — nên gắn flag hoặc lọc khỏi `impacted_tables` chính |
| `has_dynamic_sql` | `true` | OK — nhưng `calls_direct` không có `sp_executesql` (EXEC động khác) — chấp nhận |

**Mục tiêu:** Proc custom `zc_*` vẫn có `logic_hints` + param business được ưu tiên **mà không thêm rule cứng cho từng tên param**.

---

## 2. Nguyên tắc thiết kế (bắt buộc Gemini tuân theo)

1. **Domain cứng** chỉ cho pattern **lặp lại toàn FBO** (lãi, kho, BCTC) — giữ nguyên doc 01–03.
2. **Proc custom** dùng domain mới: `custom_listing_related` — detect bằng **bảng `zc*` / temp `#$*` / partition CT**, không bằng tên proc.
3. **`keywords_suggested`**: ưu tiên auto từ **param name pattern** + **temp_tables** + **tables zc_***, không list tay trong code.
4. **`param_effects`**: thêm **Tier 2 generic** theo regex tên param (`*_yn`, `@loai`, `@source`…) — **không** rule `"param": "@tao_yn"`.
5. Chỉ promote lên rule **hardcode tên param** khi có bằng chứng lặp nhiều proc (ngoài scope ticket này).

---

## 3. P1 — Domain hint: `custom_listing_related`

### Fix — File: `sql_object_summary/visitors/summary_visitor.py`

Trong `_compute_logic_hints()`, thêm nhánh **sau** stock, **trước** pivot (thứ tự ưu tiên: interest → bctc → stock → **custom** → pivot):

```python
# 4. Custom zc_* listing / transfer / DM sync (generic)
custom_listing_related = bool(
    re.search(r"\bzc[a-z0-9_]+\b", txt_lower)          # table zcdmtb0, zc...
    or re.search(r"#\$[a-z0-9_]+", txt_lower)           # #$da_tao, #$dl_goc
    or (
        re.search(r"\bd\d\d\$", txt_lower)             # d31$, d91$ partition detail
        and re.search(r"\bm\d\d\$", txt_lower)         # m31$, m91$ partition master
        and "dmkh" in txt_lower
    )
)
```

**Không** set `custom_listing_related` nếu đã match `interest_related`, `bctc_form_related`, hoặc `stock_related`.

**Note generic (không diễn giải nghĩa @tao_yn cụ thể):**

```python
hints["custom_listing_related"] = True
hints["note"] = (
    "Custom listing/report (zc_* tables or voucher partitions); "
    "check *_yn flags and filter params; "
    "use mode=snippet with keywords_suggested or zones=['key_filter','result_set']"
)
```

---

## 4. P1 — `keywords_suggested` auto (không hardcode `@tao_yn`)

### Fix — File: `sql_object_summary/visitors/summary_visitor.py`

Thêm helper (cùng file hoặc `sql_object_summary/hints.py` mới nếu muốn tách):

```python
import re
from sql_object_summary.models import ParamInfo

# Param name patterns — business/custom, không phải infra chuẩn FBO report
CUSTOM_PARAM_NAME_PATTERNS = [
    re.compile(r"^@\w+_yn$", re.I),       # @tao_yn, @duyet_yn, @huy_yn
    re.compile(r"^@(loai|source|phan_loai|ticket)$", re.I),
    re.compile(r"^@(vcfrom|vcto)$", re.I),  # voucher range — thường custom listing
]

def build_custom_keywords(
    full_text: str,
    params: list[ParamInfo],
    temp_tables: list[str],
    tables_read: list[str],
) -> list[str]:
    txt_lower = full_text.lower()
    out: list[str] = []

    def add(kw: str) -> None:
        if kw not in out:
            out.append(kw)

    # A) Params: chỉ thêm nếu tên khớp pattern VÀ xuất hiện trong body
    for p in params:
        name = p.name
        if any(pat.match(name) for pat in CUSTOM_PARAM_NAME_PATTERNS):
            if name.lower() in txt_lower:
                add(name)

    # B) Temp tables đặc trưng custom (#$...)
    for t in temp_tables:
        if t.startswith("#$") or t.startswith("#zc"):
            add(t)

    # C) Bảng zc_* từ tables_read
    for t in tables_read:
        if t.startswith("zc"):
            add(t)

    # D) Biến key hay gặp listing custom (chỉ nếu có trong text)
    for kw in ["@KeyPO", "@Key", "@q", "Partition$Execute", "WHILE"]:
        if kw.lower() in txt_lower:
            add(kw)

    return out
```

Trong `_compute_logic_hints()` khi `custom_listing_related`:

```python
custom_kws = build_custom_keywords(
    self.full_text, self.params, sorted(self.temp_tables_set), sorted(self.tables_read_set)
)
for kw in custom_kws:
    if kw not in keywords_suggested:
        keywords_suggested.append(kw)
```

**Kỳ vọng với `zc_ttdmtb`:**

```json
"logic_hints": {
  "custom_listing_related": true,
  "keywords_suggested": [
    "@tao_yn", "@loai", "@Source", "@phan_loai", "@ticket",
    "@VCFrom", "@VCTo", "#$da_tao", "#$dl_goc", "zcdmtb0", "@KeyPO", "WHILE"
  ],
  "note": "Custom listing/report ..."
}
```

> `@tao_yn` xuất hiện vì **pattern `*_yn`**, không vì hardcode tên.

---

## 5. P1 — `param_effects`: Tier 2 generic theo pattern tên

### Fix — File: `sql_object_summary/visitors/param_effects.py`

Thêm vào `SPECIFIC_PARAM_RULES` **trước** rule `@Admin` / sau rule `@kieu_xem` — dùng **regex param**, không tên cố định:

```python
{
    "param": r"^@\w+_yn$",
    "patterns": [
        r"@\w+_yn\s*=\s*'[01]'",
        r"@\w+_yn\s*=\s*'[YNyn]'",
        r"IF\s+[^\n;]*@\w+_yn",
    ],
    "role": "branching",
    "effect": "Yes/no flag controls filter or processing branch",
    "confidence": "medium",
},
{
    "param": r"^@(loai|source|phan_loai)$",
    "patterns": [r"@(loai|source|phan_loai)\s*="],
    "role": "branching",
    "effect": "Controls report/listing type or data source branch",
    "confidence": "medium",
},
{
    "param": r"^@ticket$",
    "patterns": [r"@ticket\s*="],
    "role": "filter",
    "effect": "Filters or scopes by ticket / batch identifier",
    "confidence": "medium",
},
```

### Ưu tiên khi cắt max 5 effects

Sửa sort cuối `detect_param_effects()`:

```python
PRIORITY_ORDER = {
    "high": 0,
    "medium": 1,
}

def _effect_sort_key(e: ParamEffect) -> tuple:
    # Tier 2 generic yn/loai/source trước generic Tier 1 "Parameter @Customer used..."
    is_generic_tier1 = e.effect.startswith("Parameter ") and "used in" in e.effect
    is_yn_or_custom = bool(re.match(r"^@\w+_yn$", e.param, re.I)) or re.match(
        r"^@(loai|source|phan_loai|ticket)$", e.param, re.I
    )
    return (
        PRIORITY_ORDER.get(e.confidence, 2),
        1 if is_generic_tier1 else 0,           # business rule trước generic scan
        0 if is_yn_or_custom else 1,            # *_yn / loai trước @Customer
        e.param,
    )

filtered.sort(key=_effect_sort_key)
return filtered[:5]
```

**Kỳ vọng `zc_ttdmtb`:** top 5 có **`@tao_yn`** (medium) và ít nhất một trong `@loai` / `@Source` / `@phan_loai` nếu có trong body.

---

## 6. P2 — Lọc / gắn nhãn `information_schema`

### Actual

```json
"tables_read": [..., "information_schema", ...]
```

### Expected (chọn 1 — ưu tiên A)

**A) Lọc khỏi `tables_read` / `impacted_tables`:**

Trong `_normalize_table_name()`:

```python
if clean_name in ("information_schema", "sys", "sysobjects", "syscolumns"):
    return None
```

**B) Hoặc** giữ nhưng thêm signal (nếu muốn Agent biết proc check metadata):

```json
"signals": { "uses_information_schema": true }
```

Khuyến nghị **A** — đơn giản, giảm nhiễu `impacted_tables`.

---

## 7. P2 — `has_dynamic_sql` khi không có `sp_executesql` trong calls

Proc `zc_ttdmtb`: `has_dynamic_sql: true` nhưng `calls_direct` chỉ `Partition$Execute`.

Trong `finalize()` (đã có scan `sp_executesql`), **bổ sung**:

```python
if re.search(r"\bEXEC\s*\(\s*@q\s*\)", self.full_text, re.IGNORECASE):
    self.signals.has_dynamic_sql = True
if re.search(r"\bSET\s+@q\s*=", self.full_text, re.IGNORECASE) and "EXEC" in self.full_text.upper():
    self.signals.has_dynamic_sql = True
```

Không cần thêm `EXEC @q` vào `calls_direct`.

---

## 8. JSON mục tiêu (`zc_ttdmtb` sau fix)

```json
{
  "object": "dbo.zc_ttdmtb",
  "summary": {
    "tables_read": [
      "d31$", "d71$", "d91$", "d94$", "dmbp", "dmkh", "dmvt",
      "m31$", "m71$", "m91$", "m94$", "tbdmbp", "vsysuserinfo", "zcdmtb0"
    ],
    "param_effects": [
      {
        "param": "@tao_yn",
        "role": "branching",
        "effect": "Yes/no flag controls filter or processing branch",
        "confidence": "medium"
      },
      {
        "param": "@loai",
        "role": "branching",
        "effect": "Controls report/listing type or data source branch",
        "confidence": "medium"
      },
      {
        "param": "@Admin",
        "role": "branching",
        "effect": "Bypasses or enforces user rights / data security filters",
        "confidence": "high"
      }
    ],
    "logic_hints": {
      "custom_listing_related": true,
      "keywords_suggested": [
        "@tao_yn", "@loai", "@Source", "@phan_loai",
        "#$da_tao", "#$dl_goc", "zcdmtb0", "@KeyPO", "WHILE"
      ],
      "note": "Custom listing/report (zc_* tables or voucher partitions); check *_yn flags..."
    }
  }
}
```

---

## 9. Thứ tự implement

| # | Việc | File | Ưu tiên |
|---|------|------|---------|
| 1 | `custom_listing_related` + note | `summary_visitor.py` | P1 |
| 2 | `build_custom_keywords()` | `summary_visitor.py` hoặc `hints.py` | P1 |
| 3 | Tier 2 rules `*_yn`, `@loai`, `@source`, `@phan_loai`, `@ticket` | `param_effects.py` | P1 |
| 4 | Sort ưu tiên param custom trong top 5 | `param_effects.py` | P1 |
| 5 | Lọc `information_schema` | `summary_visitor.py` | P2 |
| 6 | `has_dynamic_sql` cho `EXEC(@q)` | `summary_visitor.py` | P2 |
| 7 | Unit tests | `test_analyze_proc.py` | P1 |

---

## 10. Test cases (bắt buộc)

### T1 — `zc_ttdmtb` mock fixture (~30 dòng đủ pattern)

```python
def test_custom_listing_hints_zc_ttdmtb():
    sql = """
    CREATE PROC dbo.zc_ttdmtb @tao_yn char(1), @loai char(1), @Source char(1) AS
    IF @tao_yn = '1' INSERT INTO #$da_tao SELECT * FROM zcdmtb0
    IF @loai = '2' SELECT * FROM d91$ JOIN m91$ ON ...
    WHILE @num > 0 BEGIN SET @q = N'SELECT ...' EXEC(@q) END
    """
    res = analyze_definition(sql, ...)
    h = res.summary.logic_hints
    assert h.get("custom_listing_related") is True
    assert "@tao_yn" in h.get("keywords_suggested", [])
    assert "zcdmtb0" in h.get("keywords_suggested", []) or "#$da_tao" in h.get("keywords_suggested", [])
    effects = [e.param for e in res.summary.param_effects]
    assert "@tao_yn" in effects
```

### T2 — Regression interest / stock / bctc

- `rs_rptInterestDetailedByLoanContract` mock → vẫn `interest_related`, **không** `custom_listing_related`
- `rs_rptStockSummaryByLotItem` mock → vẫn `stock_related`
- `zc_bckqkdtda` mock → vẫn `bctc_form_related`

### T3 — `information_schema` filtered

```python
assert "information_schema" not in summary.tables_read
```

---

## 11. Checklist PASS

- [ ] `zc_ttdmtb`: `logic_hints.custom_listing_related == true`
- [ ] `keywords_suggested` chứa `@tao_yn` (via pattern, không hardcode list)
- [ ] `param_effects` chứa `@tao_yn` (medium+)
- [ ] `information_schema` không còn trong `tables_read` (nếu chọn P2-A)
- [ ] Regression 3 domain cũ PASS
- [ ] `pytest tests/sql_object_summary/` PASS

---

## 12. Explicit NON-GOALS (Gemini không làm)

- ❌ Hardcode `"param": "@tao_yn"` với effect mô tả nghiệp vụ cụ thể (“đã tạo DM thiết bị”)
- ❌ Parse semantic từ tên proc `zc_ttdmtb`
- ❌ Thêm domain cứng cho từng module UR
- ❌ Fill `result_sets` bằng đoán — vẫn `[]` + snippet zone

---

*Tham chiếu:* [01_improve_summary_for_agent.md](./01_improve_summary_for_agent.md), [03_bctc_form_and_table_noise_fixes.md](./03_bctc_form_and_table_noise_fixes.md)
