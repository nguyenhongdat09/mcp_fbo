# Master Fix — `summary_object` (quét toàn DB `VINHQUANG_FBISP242_A`)

> **Ngày quét:** 2026-08-20  
> **Database:** `VINHQUANG_FBISP242_A` @ `172.168.5.14\SQL2016`  
> **Resolve từ:** `\\172.168.5.14\CustomerPro\FBI\VINHQUANG\FBISP242\App_Data\Controllers\Grid\zcbcthlv.xml`  
> **Mục tiêu:** **Một lần implement** — không fix từng proc / từng JSON nữa.  
> **Thay thế / gom:** doc `02`, `03`, `04` → implement theo doc này (doc cũ giữ làm lịch sử).

---

## 1. Executive summary — số liệu quét DB

| Metric | Giá trị | Ý nghĩa |
|--------|---------|---------|
| Tổng proc `dbo` | **2.192** | Toàn bộ phạm vi |
| Proc **> 150 dòng** (heuristic) | **482** (22%) | Nhánh fast scan — phải đủ thông minh |
| `sp_executesql` trong body | **1.634** (75%) | `has_dynamic_sql` phải luôn đúng |
| `WHILE` | 731 | Signal OK |
| `CURSOR` | 236 | Signal OK |
| `EXEC(@q)` | 71 | Cần detect ngoài `sp_executesql` |
| `information_schema` | **62** | Lọc khỏi `tables_read` |
| Proc có param `*_yn` | **13** | Dùng **pattern** `^@\w+_yn$`, không hardcode `@tao_yn` |

### Phân bố prefix

| Prefix | Số proc |
|--------|---------|
| `rs_*` | 873 |
| other | 649 |
| `FastBusiness$*` | 511 |
| `fs*` | 189 |
| `zc_*` | 47 |
| `fsd_*` | 18 |

### Phân bố độ dài

| Dòng | Số proc |
|------|---------|
| ≤ 50 | 608 |
| 51–150 | 1.102 |
| 151–300 | 374 |
| 301–500 | 81 |
| > 500 | 27 |

### Coverage domain hiện tại (keyword SQL — có overlap)

| Signal | Proc match |
|--------|------------|
| custom (`zc_*`, `#$`, `zcd*`) | 353 |
| bctc_form | 82 |
| stock | 66 |
| pivot | 38 |
| interest | 19 |

### Gap lớn nhất — vì sao user mệt fix từng proc

| Nhóm | Tổng | Không khớp 4 domain cứng | Ghi chú |
|------|------|---------------------------|---------|
| `rs_*` | 869 | **556** (64%) | Đa số báo cáo chuẩn FBO |
| `rs_*` + `#report` + `Partition$Execute` + không lãi/kho/BCTC | — | **199** | Pattern **report generic** |
| `zc_*` | 47 | 0 (theo tên) | Cần `custom_listing_related` + keyword auto |
| `other` | 1.074 | **925** (86%) | `ff_*`, helper, listing… |

**Kết luận:** 4 domain cứng (`interest`, `stock`, `bctc`, `pivot`) chỉ cover ~20–25% proc. **Phải thêm tầng generic** + **keyword/param auto** từ catalog.

---

## 2. Nguyên tắc thiết kế (bắt buộc)

1. **Không hardcode tên proc** (`zc_ttdmtb`, `rs_rptStock…`).
2. **Không hardcode từng param** trừ Tier-2 FBO chuẩn lặp hàng trăm lần (`@Language`, `@Admin`, `@Status`, `@mau_bc`, `@form`).
3. **Pattern + catalog-driven:**
   - Param: regex tên + `sys.parameters` của proc đó
   - Table noise: denylist universal
   - Domain: thang ưu tiên (§4)
4. **`logic_hints` không được trống** với proc báo cáo (`rs_*`, `zc_*`, `#report`) — fallback `report_generic`.
5. **`param_effects` max 5:** ưu tiên param **nghiệp vụ** proc đó, không để `@Admin`/`@Language` chiếm hết slot.
6. Một PR — một lần test batch (§9).

---

## 3. P0 — Universal table / signal fixes (áp dụng 100% proc)

**File:** `sql_object_summary/visitors/summary_visitor.py`

### 3.1. Denylist table name (`_normalize_table_name`)

Loại bỏ **trước khi** add vào `tables_read` / `tables_write`:

```python
TABLE_NAME_DENY = {
    # SQL keywords (đã có — mở rộng)
    "set", "select", "where", "from", "join", "order", "group", "into",
    "values", "exec", "execute", "begin", "end", "declare", "return",
    # Alias / biến hay nhiễu
    "res", "result", "fact", "data", "tmp", "temp", "cur", "re", "sl",
    # SQL types
    "nvarchar", "varchar", "char", "nchar", "int", "bigint", "smallint",
    "tinyint", "bit", "decimal", "numeric", "float", "real", "money",
    "datetime", "smalldatetime", "date", "time", "sysname",
    # System catalog
    "information_schema", "sys", "sysobjects", "syscolumns", "sysindexes",
}
# + if clean_name.isdigit(): return None
# + KNOWN_ALIAS_NOISE (a,b,c,g,gl...) — giữ
```

**PASS toàn DB:** không còn `"3"`, `"set"`, `"res"`, `"nvarchar"`, `"information_schema"` trong output.

### 3.2. `has_dynamic_sql` universal (`finalize`)

```python
if re.search(r"\bsp_executesql\b", text, re.I):
    signals.has_dynamic_sql = True
if re.search(r"\bEXEC\s*\(\s*@q\s*\)", text, re.I):
    signals.has_dynamic_sql = True
if re.search(r"\bSET\s+@q\s*=", text, re.I) and re.search(r"\bEXEC\b", text, re.I):
    signals.has_dynamic_sql = True
```

---

## 4. P1 — Domain ladder (logic_hints) — **core fix**

**File:** `summary_visitor.py` → `_compute_logic_hints()`

Thứ tự **elif** (chỉ một domain chính):

| # | Flag | Detect (heuristic) | Note gợi ý snippet |
|---|------|---------------------|-------------------|
| 1 | `interest_related` | Giữ doc 01 | cursor/WHILE + `tl_th`… |
| 2 | `bctc_form_related` | Giữ doc 03 | `@form`, `bcnsky`, `CheckFormula` |
| 3 | `stock_related` | Giữ doc 03 | `Balance$Lot`, `dmvt`+`dmlo` |
| 4 | `custom_listing_related` | doc 04 | `zc*`, `#$*`, partition `dNN$`+`mNN$`+`dmkh` |
| 5 | **`report_generic`** **(MỚI)** | `rs_*` **HOẶC** `#report` + (`Partition$Execute` hoặc `sp_executesql`) | Báo cáo FBO chuẩn không thuộc 1–4 |
| 6 | pivot zone | `#pivot` / `xpivot` | zones pivot |

### 4.1. `report_generic` — cover ~199–556 proc `rs_*`

```python
report_generic = bool(
    re.search(r"\brs_", object_name or "", re.I)  # truyền object_name vào visitor nếu chưa có
    or (
        "#report" in txt_lower
        and (
            "partition$execute" in txt_lower
            or "sp_executesql" in txt_lower
            or re.search(r"\bEXEC\s*\(\s*@q", txt_lower)
        )
    )
)
```

Note:

```text
"Standard FBO report (rs_* / #report); use snippet key_filter + result_set; keywords from params in this proc"
```

### 4.2. Keywords — **auto build, không list tay từng proc**

**File mới (khuyến nghị):** `sql_object_summary/keyword_builder.py`

```python
INFRA_KEYWORDS = {"Partition$Execute", "sp_executesql", "WHILE", "CURSOR", "#report"}

# Param names xuất hiện trong ≥ N proc toàn DB (từ scan 2026-08-20) — dùng làm gợi ý khi có trong body
COMMON_REPORT_PARAMS = {
    "@DateFrom", "@DateTo", "@Unit", "@Customer", "@Item", "@Site", "@Account",
    "@Language", "@Form", "@mau_bc", "@Status", "@CalculateTransfer",
    "@ReportType", "@DataType", "@Controller", "@DynamicKeyTable", "@Key",
}

PARAM_PATTERNS = [
    re.compile(r"^@\w+_yn$", re.I),
    re.compile(r"^@(loai|source|phan_loai|ticket|Type|Action|status)$", re.I),
]

def build_keywords_suggested(full_text, params, temp_tables, tables_read, calls_direct, domain_flag):
    txt = full_text.lower()
    out = []
    def add(k):
        if k not in out: out.append(k)

    # A) Params: common + pattern + có mặt trong body
    for p in params:
        name = p.name
        if name in COMMON_REPORT_PARAMS or any(r.match(name) for r in PARAM_PATTERNS):
            if name.lower() in txt:
                add(name)

    # B) Temp tables #... và #$
    for t in temp_tables:
        if t.startswith("#"):
            add(t)

    # C) Tables đặc trưng (partition rNN$, dNN$, zc*)
    for t in tables_read:
        if re.match(r"^[rdcm]\d\d\$", t) or t.startswith("zc"):
            add(t)

    # D) Infra calls (bare name)
    for c in calls_direct:
        bare = c.name.split(".")[-1]
        if bare in ("FastBusiness$Balance$Lot", "FastBusiness$Balance$BContract",
                    "FastBusiness$Report$CheckFormula", "FastBusiness$Report$GetDynamicKey"):
            add(bare)

    # E) Domain-specific seed (chỉ thêm nếu có trong text)
    DOMAIN_SEEDS = {
        "interest_related": ["tl_th", "@Status", "@days", "ctdmku", "m_kieu_ls"],
        "stock_related": ["Balance$Lot", "@CalculateTransfer", "m_instock_split", "ton_", "sl_"],
        "bctc_form_related": ["@form", "@mau_bc", "bcnsky", "glns", "cach_tinh"],
        "custom_listing_related": ["@KeyPO", "#$da_tao", "zcdmtb0"],
        "report_generic": ["@DateFrom", "@DateTo", "@Key", "@q"],
    }
    for kw in DOMAIN_SEEDS.get(domain_flag, []):
        if kw.lower() in txt:
            add(kw)

    return out[:20]  # cap token
```

Gọi từ `_compute_logic_hints()` sau khi chọn domain flag.

**Không** hardcode `@tao_yn` — param `*_yn` tự lọt qua `PARAM_PATTERNS`.

---

## 5. P1 — `param_effects` — slot 5 cho param nghiệp vụ proc

**File:** `sql_object_summary/visitors/param_effects.py`

### 5.1. Tier 2 — giữ + bổ sung pattern (doc 03 + 04)

- `@Status`, `@form`, `@mau_bc`, `@Language`, `@Admin` (giữ)
- **`^@\w+_yn$`** — generic Y/N
- **`^@(loai|source|phan_loai|ticket|Type|Action|status)$`** — generic branching

### 5.2. Deprioritize infra params trong top 5

```python
INFRA_PARAMS = {"@UserID", "@Admin", "@Language", "@SysDB", "@sysDatabaseName", "@cLan"}

def _effect_sort_key(e):
    is_infra = e.param in INFRA_PARAMS
    is_generic_tier1 = e.effect.startswith("Parameter ") and "used in" in e.effect
    is_pattern_business = bool(re.match(r"^@\w+_yn$", e.param, re.I)) or e.param in (
        "@form", "@mau_bc", "@Status", "@CalculateTransfer", "@ReportType", "@loai", "@source"
    )
    return (
        0 if e.confidence == "high" else 1,
        1 if is_infra else 0,           # infra sau business
        1 if is_generic_tier1 else 0,
        0 if is_pattern_business else 1,
        e.param,
    )
```

**Quy tắc:** Nếu proc có `@tao_yn` / `@loai` / `@Status` / `@CalculateTransfer` matched → **ít nhất 1** phải nằm top 5 (trước `@Customer` generic).

---

## 6. P2 — Truyền `object_name` vào SummaryVisitor

Hiện `_compute_logic_hints` không biết `rs_*` vs `zc_*` nếu body không có keyword.

**Fix:** `analyze.py` → `SummaryVisitor(..., object_name=object_name)`  
Dùng cho `report_generic` detect `rs_` prefix.

---

## 7. P2 — Batch scan script (test 1 lần, không MCP từng proc)

**File mới:** `scripts/batch_scan_summary.py`

```python
# Chạy: python scripts/batch_scan_summary.py --file-path <xml> --limit 0
# limit=0 → all dbo procs; mặc định sample 500
```

Output JSON: `docs/doc_fix/scan_results_VINHQUANG_FBISP242_A.json` với:

- `empty_logic_hints_count`
- `noise_table_hits_by_name`
- `bad_has_dynamic_sql_count`
- `domain_flag_counts`
- `top_missing_examples` (10 proc `logic_hints` trống)

**Gemini:** implement script + chạy trước/ sau PR; **PASS** khi:

| Metric | Trước (ước lượng) | Sau (target) |
|--------|-------------------|--------------|
| `rs_*` empty hints | ~556 | **< 50** |
| `zc_*` empty hints | ~47 | **0** |
| noise table hits | > 0 | **0** |
| `has_dynamic_sql` false khi có `sp_executesql` | > 0 | **0** |

---

## 8. JSON mục tiêu — ví dụ 3 nhóm (không phải 3 proc riêng lẻ)

### A) Lãi vay — giữ (regression)

`interest_related` + `@Status` — không đổi hành vi.

### B) `rs_*` generic (proc bất kỳ trong 199 pattern)

```json
"logic_hints": {
  "report_generic": true,
  "keywords_suggested": ["@DateFrom", "@DateTo", "@Customer", "#report", "Partition$Execute", "@Key"],
  "note": "Standard FBO report ..."
}
```

### C) `zc_*` custom

```json
"logic_hints": {
  "custom_listing_related": true,
  "keywords_suggested": ["@tao_yn", "@loai", "#$da_tao", "zcdmtb0", "WHILE"],
  "note": "Custom listing/report ..."
}
```

---

## 9. Checklist implement (Gemini — một PR)

### Code

- [ ] `TABLE_NAME_DENY` + `isdigit()` — `summary_visitor.py`
- [ ] `has_dynamic_sql` universal — `summary_visitor.py`
- [ ] Domain ladder + `report_generic` — `summary_visitor.py`
- [ ] `keyword_builder.py` + integrate — `summary_visitor.py`
- [ ] `object_name` → visitor — `analyze.py`
- [ ] `param_effects` sort + pattern rules — `param_effects.py`
- [ ] `scripts/batch_scan_summary.py`

### Test

- [ ] Unit: noise filters, dynamic sql, each domain flag (mock SQL nhỏ)
- [ ] Regression: 3 proc đã PASS user (lãi, kho, `zc_bckqkdtda`)
- [ ] Batch scan full DB → attach summary stats vào PR

### SQL validation (chạy sau deploy — copy từ §1)

```sql
-- Empty hints không nên còn nhiều trên rs_*
-- (validate bằng batch script Python, không query thủ công từng proc)
```

---

## 10. Explicit NON-GOALS

- ❌ Không thêm domain cứng cho từng module UR
- ❌ Không fill `result_sets` bằng đoán trên toàn DB
- ❌ Không ANTLR full trên proc > 150 dòng
- ❌ Không yêu cầu user paste JSON từng proc nữa — dùng batch scan

---

## 11. Tham chiếu doc cũ

| Doc | Trạng thái | Ghi chú |
|-----|------------|---------|
| `01_improve_summary_for_agent.md` | Spec gốc | Vẫn valid |
| `02_additional_fixes_from_real_json.md` | ✅ Done | Gom vào §3 |
| `03_bctc_form_and_table_noise_fixes.md` | ✅ Done | Gom vào §4 |
| `04_generic_custom_proc_hints.md` | ⏳ Chưa merge | Gom vào §4–5 |
| **`05_master_fix_from_db_scan.md`** | **Implement doc này** | Master |

---

*Quét thực hiện qua MCP `query_database` trên `VINHQUANG_FBISP242_A`, 2026-08-20.*
