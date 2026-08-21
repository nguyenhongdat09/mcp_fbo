# Doc Fix — `custom_listing_related` chồng lên `rs_*` (over-detect)

> **Nguồn:** Batch scan sau doc 05 — `scripts/batch_scan_summary.py`, 100 proc `rs_rpt*` trên `VINHQUANG_FBISP242_A`  
> **Ngày:** 2026-08-20  
> **Trạng thái doc 05:** ~95% — **1 bug logic domain ladder** cần sửa trước khi chốt full scan.

---

## 1. Vấn đề

### Kết quả batch scan (100 proc `rs_rpt*`)

```
custom_listing_related  : 42 (42%)   ← BẤT THƯỜNG cao trên rs_*
report_generic          : 21 (21%)
none                    : 17 (17%)   ← OK
```

Proc **`rs_*` / `rs_rpt*`** là báo cáo chuẩn FBO — đa số phải là **`report_generic`**, không phải **`custom_listing_related`**.

`custom_listing_related` chỉ dành cho **`zc_*`**, bảng `zcd*`, temp `#$*`, luồng PO/`@KeyPO`.

### Root cause

**File:** `sql_object_summary/visitors/summary_visitor.py` — `_compute_logic_hints()`

```python
custom_listing_related = bool(
    self.object_name.lower().startswith("zc_")
    or "zcdm" in txt_lower
    or "#$" in txt_lower
    or "@keypo" in txt_lower
    or ("dmkh" in txt_lower and re.search(r"[dm]\d\d\$", txt_lower))  # ← BUG
)
```

Nhánh cuối match **hầu hết báo cáo bán hàng / công nợ KH** (`dmkh` + `d91$`/`m91$`/`d71$`…) — tức **rs_rpt*** thông thường.

Vì `custom_listing_related` đứng **trước** `report_generic` trong chuỗi `elif`, proc `rs_*` bị gán domain sai → `note` và seed keywords lệch (vẫn có keywords nhưng agent hiểu nhầm loại báo cáo).

---

## 2. Expected behavior

| Proc | Domain mong muốn |
|------|------------------|
| `dbo.zc_ttdmtb`, `dbo.zc_*` + `#$*` / `zcd*` | `custom_listing_related` |
| `dbo.rs_rpt*`, `dbo.rs_*` + `#report` / partition / date filter | `report_generic` |
| `rs_*` + `tl_th` / `dmku` | `interest_related` (ưu tiên cao nhất — giữ) |
| `rs_*` + `bcnsky` / `CheckFormula` | `bctc_form_related` (giữ) |
| `rs_*` + `Balance$Lot` + `dmvt`/`dmlo` | `stock_related` (giữ) |

**Không** gán `custom_listing_related` cho proc có `object_name` bắt đầu `rs_` **chỉ vì** có `dmkh` + partition.

---

## 3. Fix spec (Gemini)

### 3.1. Thu hẹp `custom_listing_related`

**File:** `summary_visitor.py`

```python
is_rs_object = self.object_name.lower().startswith("rs_")
is_zc_object = self.object_name.lower().startswith("zc_")

custom_listing_related = bool(
    is_zc_object
    or "zcdm" in txt_lower
    or "#$" in txt_lower
    or "@keypo" in txt_lower
    or (
        not is_rs_object  # ← MỚI: rs_* không dùng nhánh dmkh+partition
        and "dmkh" in txt_lower
        and re.search(r"[dm]\d\d\$", txt_lower)
    )
)
```

**Hoặc** (rõ hơn — khuyến nghị): bỏ hẳn nhánh `dmkh + partition`; chỉ giữ:

```python
custom_listing_related = bool(
    is_zc_object
    or "zcdm" in txt_lower
    or "#$" in txt_lower
    or "@keypo" in txt_lower
)
```

Nhánh `dmkh + dNN$` **không cần** — `zc_*` đã cover qua `is_zc_object`; proc `ff_*`/other hiếm khi cần domain này.

### 3.2. Mở rộng nhẹ `report_generic` (optional)

Đảm bảo mọi `rs_rpt*` có ít nhất hint khi không match domain 1–4:

```python
report_generic = bool(
    self.object_name.lower().startswith("rs_rpt")
    or (
        self.object_name.lower().startswith("rs_")
        and (
            "#report" in txt_lower
            or "partition$execute" in txt_lower
            or "sp_executesql" in txt_lower
            or "@datefrom" in txt_lower
            or "@dateto" in txt_lower
            or "@thang_tu" in txt_lower
            or "@ngay_tu" in txt_lower
            or re.search(r"\bEXEC\s*\(\s*@q", txt_lower)
        )
    )
    or ( ... giữ block #report + partition ... )
)
```

Không bắt buộc nếu fix 3.1 đủ — sau fix, proc `rs_*` rơi xuống `report_generic` tự nhiên.

### 3.3. Test unit (bắt buộc)

**File:** `tests/sql_object_summary/test_analyze_proc.py` (hoặc file mới `test_domain_ladder.py`)

```python
def test_rs_sales_report_is_report_generic_not_custom_listing():
    """rs_rpt* with dmkh + d91$ must NOT be custom_listing."""
    sql = """
    CREATE PROC dbo.rs_rptSalesByCustomer
      @DateFrom smalldatetime, @DateTo smalldatetime, @Customer varchar(33) AS
    SELECT * INTO #report FROM d91$ a JOIN m91$ b ON ...
    JOIN dmkh k ON a.ma_kh = k.ma_kh
    EXEC FastBusiness$Partition$Execute @q
    """
    res = analyze_definition(sql, object_name="dbo.rs_rptSalesByCustomer", ...)
    hints = res.summary.logic_hints
    assert hints.get("custom_listing_related") is not True
    assert hints.get("report_generic") is True


def test_zc_proc_still_custom_listing():
    sql = """
    CREATE PROC dbo.zc_ttdmtb @tao_yn char(1) AS
    INSERT INTO #$da_tao SELECT * FROM zcdmtb0
    """
    res = analyze_definition(sql, object_name="dbo.zc_ttdmtb", ...)
    assert res.summary.logic_hints.get("custom_listing_related") is True
```

### 3.4. Regression

- Proc lãi / kho / BCTC (`interest_related`, `stock_related`, `bctc_form_related`) — **không đổi**
- `zc_ttdmtb` — vẫn `custom_listing_related` + `@tao_yn` trong keywords (via pattern)

---

## 4. Validation sau fix

Chạy lại batch scan:

```powershell
cd E:\PythonProject\mcp_fbo
python scripts/batch_scan_summary.py `
  --file-path "\\172.168.5.14\CustomerPro\FBI\VINHQUANG\FBISP242\App_Data\Controllers\Grid\zcbcthlv.xml" `
  --prefix rs_rpt `
  --limit 100
```

**Target:**

| Metric | Trước | Sau (kỳ vọng) |
|--------|-------|----------------|
| `custom_listing_related` trên `rs_rpt*` | 42% | **< 5%** (chỉ proc rs_* thật sự có `#$`/`zcdm`) |
| `report_generic` trên `rs_rpt*` | 21% | **> 50%** |
| `none` | 17% | **≤ 20%** (giữ hoặc giảm) |
| Noise table hits | 0 | 0 |
| Dynamic SQL errors | 0 | 0 |

Full scan (optional chốt release):

```powershell
python scripts/batch_scan_summary.py --file-path "..." --limit 0
```

Ghi kết quả vào `docs/doc_fix/scan_results_VINHQUANG_FBISP242_A_after_06.json`.

---

## 5. Checklist PASS

- [ ] `rs_rpt*` + `dmkh` + `d91$` → **`report_generic`**, không `custom_listing`
- [ ] `zc_*` + `#$` / `zcd*` → vẫn **`custom_listing_related`**
- [ ] Unit tests mới PASS
- [ ] `pytest tests/` PASS
- [ ] Batch 100 `rs_rpt*`: `custom_listing` < 5%

---

## 6. Phạm vi — không làm thêm

- ❌ Không thêm domain mới
- ❌ Không sửa `keyword_builder.py` (trừ khi cần đổi seed key name)
- ❌ Không đổi ngưỡng 150 dòng heuristic
- ❌ Không yêu cầu user paste JSON từng proc

---

*Liên quan:* [05_master_fix_from_db_scan.md](./05_master_fix_from_db_scan.md) §4 Domain ladder
