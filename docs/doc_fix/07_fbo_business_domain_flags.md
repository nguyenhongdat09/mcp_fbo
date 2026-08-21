# Doc Fix 07 — Domain FBO nghiệp vụ: Post / APV / Lifecycle / HDDT / HDDV / Discount / Balance

> **Nguồn:** User domain knowledge + quét `VINHQUANG_FBISP242_A` (2026-08-20)  
> **Mục tiêu:** Bổ sung domain flags cho nhóm proc **không phải báo cáo `rs_*`**, Agent nhận đúng nghiệp vụ mà **không hardcode từng tên proc**.  
> **Nguyên tắc:** Pattern trên `object_name` (+ body nhẹ); ladder ưu tiên rõ; tách `EInvoice` vs `InputInvoice`.

---

## 1. Số liệu quét DB (để Gemini biết scale)

| Nhóm | Pattern | Số proc (ước) |
|------|---------|---------------|
| Post sổ | `fs_Post%` | **44** |
| APV | `%$APV$%` | **33** |
| Approval (tên rộng) | `%Approval%` / `%Approve%` | **39** |
| AfterUpdate | `%AfterUpdate%` | **57** |
| BeforeUpdate/Insert | `%BeforeUpdate%` / `%BeforeInsert%` | **52** |
| InputInvoice (HDDV) | `%InputInvoice%` | **28** |
| EInvoice (HDDT, exclude Input) | `%EInvoice%` AND NOT `%InputInvoice%` | **115** |
| Discount | `%Discount%` | **21** |
| Balance | `%Balance%` | **89** |

---

## 2. Domain flags mới (Expected)

| Flag | Nghiệp vụ | Detect (ưu tiên `object_name`) |
|------|-----------|--------------------------------|
| `post_related` | Post sổ kho / ghi sổ tồn | `fs_Post%`, chứa `$Post$` (cẩn thận không overlap `AfterUpdate`) |
| `approval_related` | Duyệt chứng từ | `%$APV$%`, `%Approval%`, `%Approve%` |
| `voucher_lifecycle_related` | Hook lưu/nhận phiếu — lưu vết nguồn | `%AfterUpdate%`, `%BeforeUpdate%`, `%AfterInsert%`, `%BeforeInsert%`, `%AfterDelete%`, `%BeforeDelete%` |
| `input_invoice_related` | Hóa đơn **đầu vào** (HDDV) | `%InputInvoice%` |
| `einvoice_related` | Phát hành HĐĐT (**HDDT**) | `%EInvoice%` **AND NOT** `%InputInvoice%` |
| `discount_related` | Chiết khấu / giảm giá | `%Discount%`, `Discount$` |
| `balance_related` | Tồn / dư (helper Balance) | `%$Balance$%`, `FastBusiness$Balance$%`, hoặc body/`calls` chứa `Balance$` |

**Notes gợi ý Agent:**

| Flag | `note` |
|------|--------|
| `post_related` | `Inventory/GL post procedure (fs_Post*); inspect tables_write, site/item qty updates` |
| `approval_related` | `Voucher approval flow (APV/Approval); inspect status/role/process approve` |
| `voucher_lifecycle_related` | `Voucher lifecycle hook (After/Before Update); updates source tracking/qty after retrieve or save; snippet @stt_rec, sl_*, link tables` |
| `input_invoice_related` | `Input invoice (HDDV/II); import/map XML or create voucher from inbound invoice` |
| `einvoice_related` | `E-invoice issuance (HDDT); publish/process outbound electronic invoice` |
| `discount_related` | `Discount/rebate calculation or posting; inspect period allocation rules` |
| `balance_related` | `Balance helper (tồn/dư Account/Item/Lot/Contract); not the same as fs_Post` |

---

## 3. Domain ladder — thứ tự ưu tiên (bắt buộc)

Chèn **sau** `interest` / `bctc` / `stock` (nếu giữ stock hẹp), **trước** `custom_*` / `report_generic`:

```
1. interest_related
2. bctc_form_related
3. einvoice_related          # trước InputInvoice? → EINVOICE trước, rồi Input (tên InputInvoice chứa "Invoice" nhưng check InputInvoice trước EInvoice nếu dùng CONTAINS)
4. input_invoice_related     # PHẢI check InputInvoice TRƯỚC khi match EInvoice chung
5. approval_related
6. post_related
7. voucher_lifecycle_related
8. discount_related
9. balance_related           # rộng hơn stock; hoặc merge với stock
10. stock_related            # giữ báo cáo tồn Lot (có thể gộp vào balance_related — xem §3.1)
11. custom_action / custom_report / custom_related
12. report_generic
13. pivot note
```

### 3.1. Quan hệ `stock_related` vs `balance_related`

| Option | Cách làm |
|--------|----------|
| **A (khuyến nghị)** | Nếu `balance_related` → set `balance_related=true`; nếu thêm `Balance$Lot` / `dmvt`+`dmlo` thì **cũng** set `stock_related=true` (hoặc chỉ note “inventory subset”) |
| **B** | Gộp: bỏ `stock_related` riêng, chỉ `balance_related` + keywords Lot/Item |

Khuyến nghị **A**: giữ `stock_related` cho báo cáo tồn; `balance_related` cover Account/Customer/Contract dư.

### 3.2. EInvoice vs InputInvoice — **cấm nhầm**

```python
obj = object_name.lower()
if "inputinvoice" in obj.replace("$", "").replace("_", "") or "inputinvoice" in obj:
    # FastBusiness$InputInvoice$..., ...InputInvoice...
    input_invoice_related = True
elif "einvoice" in obj.replace("$", "").lower() or "$einvoice$" in obj:
    einvoice_related = True
```

An toàn hơn:

```python
if "inputinvoice" in obj_bare.replace("$", "").lower():
    input_invoice_related = True
elif "einvoice" in obj_bare.replace("$", "").lower():
    einvoice_related = True
```

`FastBusiness$EInvoice$GetInvoiceInputInvoice` → **input** (vì chứa InputInvoice) hoặc check **InputInvoice trước**.

### 3.3. `post_related` vs `voucher_lifecycle`

- `fs_PostAdjustmentInventory` → `post_related`
- `FastBusiness$Voucher$AfterUpdate$PO` → `voucher_lifecycle_related` (**không** gọi là post sổ)
- Không classify `AfterUpdate` là `post_related` chỉ vì có chữ “Post” trong body

```python
post_related = bool(
    obj_bare.startswith("fs_post")
    or re.search(r"(^|\$)post\$", obj_bare)  # cẩn thận
    or obj_bare.startswith("ds_post")  # discount post? → ưu tiên discount nếu có Discount trong tên
)
# Nếu tên có Discount + Post → discount_related trước (ladder)
```

Thứ tự: **`discount_related` trước `post_related`** nếu tên chứa cả hai (`ds_PostDiscount`).

---

## 4. Keywords seeds (qua `keyword_builder.py`)

Thêm vào `DOMAIN_SEEDS`:

```python
"post_related": ["@Site", "@Item", "sl_", "ton_", "Partition$Execute", "INSERT", "UPDATE"],
"approval_related": ["@Status", "Approve", "APV", "LoadApproval", "GetApprovalRole"],
"voucher_lifecycle_related": ["@stt_rec", "stt_rec_", "sl_", "AfterUpdate", "BeforeUpdate", "fsdSttRecRef"],
"input_invoice_related": ["InputInvoice", "ImportXml", "IIInsert", "@ticket"],
"einvoice_related": ["EInvoice", "hddt", "Publish", "GetInvoice"],
"discount_related": ["Discount", "ck_", "ty_le", "Allocation"],
"balance_related": ["Balance$", "#$bal", "so_du", "ton_"],
```

Chỉ add keyword nếu có trong body (giống rule hiện tại).

---

## 5. Batch scan script

**File:** `scripts/batch_scan_summary.py`

Mở rộng `domain_counts` keys:

```python
"einvoice_related", "input_invoice_related", "approval_related",
"post_related", "voucher_lifecycle_related", "discount_related",
"balance_related",
# giữ các key cũ
```

Khi đếm flag: ưu tiên flag “chính” trong ladder (một proc một domain chính), giống hiện tại.

---

## 6. Unit tests (bắt buộc)

```python
def test_fs_post_is_post_related():
    res = analyze_definition("CREATE PROC dbo.fs_PostAdjustmentInventory AS SELECT 1",
                             object_name="dbo.fs_PostAdjustmentInventory")
    assert res.summary.logic_hints.get("post_related") is True

def test_apv_is_approval_related():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$APV$LoadApproval AS SELECT 1",
                             object_name="dbo.FastBusiness$APV$LoadApproval")
    assert res.summary.logic_hints.get("approval_related") is True

def test_afterupdate_is_lifecycle_not_post():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$Voucher$AfterUpdate$PO AS SELECT 1",
                             object_name="dbo.FastBusiness$Voucher$AfterUpdate$PO")
    assert res.summary.logic_hints.get("voucher_lifecycle_related") is True
    assert res.summary.logic_hints.get("post_related") is not True

def test_inputinvoice_not_einvoice():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$InputInvoice$UpdateStatus AS SELECT 1",
                             object_name="dbo.FastBusiness$InputInvoice$UpdateStatus")
    assert res.summary.logic_hints.get("input_invoice_related") is True
    assert res.summary.logic_hints.get("einvoice_related") is not True

def test_einvoice_publish():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$EInvoice$Publish AS SELECT 1",
                             object_name="dbo.FastBusiness$EInvoice$Publish")
    assert res.summary.logic_hints.get("einvoice_related") is True

def test_discount():
    res = analyze_definition("CREATE PROC dbo.ds_PostDiscount AS SELECT 1",
                             object_name="dbo.ds_PostDiscount")
    assert res.summary.logic_hints.get("discount_related") is True

def test_balance_account():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$Balance$Account AS SELECT 1",
                             object_name="dbo.FastBusiness$Balance$Account")
    assert res.summary.logic_hints.get("balance_related") is True
```

Regression: `rs_rpt*` + `dmkh` vẫn `report_generic`; `zc_*` custom không đổi.

---

## 7. Validation

```powershell
cd E:\PythonProject\mcp_fbo
python scripts\batch_scan_summary.py `
  --file-path "\\172.168.5.14\CustomerPro\FBI\VINHQUANG\FBISP242\App_Data\Controllers\\Grid\\zcbcthlv.xml" `
  --limit 0 `
  --output "docs\doc_fix\scan_results_VINHQUANG_FBISP242_A_after_07.json"
```

**Target (ước):**

| Flag | Kỳ vọng count (không chính xác tuyệt đối) |
|------|-------------------------------------------|
| `post_related` | ~40+ |
| `approval_related` | ~30+ |
| `voucher_lifecycle_related` | ~50+ |
| `einvoice_related` | ~100+ |
| `input_invoice_related` | ~25+ |
| `discount_related` | ~20+ |
| `balance_related` | ~80+ (hoặc một phần đã bị interest/stock lấy trước) |
| `none` | giảm so với trước doc 07 |

---

## 8. Checklist PASS

- [ ] 7 unit tests trên PASS
- [ ] `InputInvoice` không bao giờ `einvoice_related`
- [ ] `AfterUpdate` không bao giờ chỉ vì lifecycle mà thành `post_related`
- [ ] `ds_PostDiscount` → `discount_related` (không `post_related`)
- [ ] `pytest tests/` PASS
- [ ] Batch full hoặc sample prefix `fs_Post`, `FastBusiness$APV`, `EInvoice` có domain đúng

---

## 9. Explicit NON-GOALS

- ❌ Không hardcode từng `ma_ct` (`AfterUpdate$PO`, `$IR`…)
- ❌ Không đổi sâu `kind: infra` classification (FastBusiness$ vẫn infra; **logic_hints** mới là điểm Agent đọc)
- ❌ Không parse full semantics post/approval vào summary — chỉ domain + keywords + note

---

*Tham chiếu:* [05_master_fix_from_db_scan.md](./05_master_fix_from_db_scan.md), [06_custom_listing_rs_overlap.md](./06_custom_listing_rs_overlap.md)
