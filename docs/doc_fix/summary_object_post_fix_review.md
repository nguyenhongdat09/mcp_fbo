# Post-Fix Review — `summary_object` (sau Gemini fix theo review lần 1)

> **Người review:** Cursor — 2026-08-20  
> **Trạng thái:** **Gần OK / sẵn sàng dùng** — blocker đã sửa; còn vài điểm cải thiện & smoke test DB thật trên máy có VPN.

---

## 1. Kết quả test (Cursor chạy lại)

| Kiểm tra | Kết quả |
|----------|---------|
| `scripts/check_imports.py` | **PASS** |
| `scripts/verify_summary_object_edges.py` | **0 findings** |
| `pytest tests/` | **24/24 PASS** (~32s) |
| Fetcher + `result_sets` shape (mock) | **PASS** — `fetch_one` trả metadata đúng |
| `max_depth=2` đệ quy grandchild | **PASS** |
| `expand` infra bare name (`FastBusiness$...`) | **PASS** (script `scripts/verify_expand_infra.py`) |
| Live FBISP242 E2E | **Chưa chạy được** tại môi trường review (network path / Web.config không resolve) |

**Kết luận:** Các blocker B1/B2 **đã sửa đúng**. Logic bridge/call_graph **cải thiện rõ** so với bản trước. Có thể coi **MVP đạt** nếu user smoke test 1 proc trên DB thật.

---

## 2. Xác nhận các fix Gemini (đúng spec)

| ID | Mô tả | Xác nhận |
|----|--------|----------|
| B1 | `execute_query(self._parsed, sql)` | OK — 5 call site |
| B2 | `_rows_from_result()` | OK — test catalog assert arg order + `result_sets` |
| M1 | `exclude_like` default | OK — bridge + `AnalyzeOptions.__post_init__` |
| M2/M9 | Đệ quy + `visited` + deadline 30s | OK — verified grandchild fetch |
| M3 | `expand` bare name | OK — verified infra expand |
| M4 | `called_by` khi không EXEC | OK — `CallGraph` tối thiểu + `list[str]` |
| M5/N9 | `_matches_exclude` + leaf nodes | OK — trong `call_graph.py` |
| M6/N4 | Cache key mở rộng | **Phần lớn OK** — xem R3 bên dưới |
| M10 | Mock test catalog | OK |
| N1/N3/N7 | Warnings / parse_status | OK — bridge + analyze + snippet |

---

## 3. Điểm cần lưu ý (không blocker)

### R1. Phase F “integration” thực chất là mock test

**File:** `tests/integration/test_summary_fbisp242.py`

- Tất cả test dùng `fetcher_override=MagicMock()` — **không** nối SQL Server / FBISP242.
- Tên folder `integration` + walkthrough Gemini dễ hiểu nhầm là đã test DB thật.

**Khuyến nghị:**

- Đổi tên → `tests/summary_object/test_phase_f_scenarios.py` hoặc giữ path nhưng thêm marker `@pytest.mark.skipif(not os.getenv("FBISP242_XML"))` cho 1–2 test live.
- Thêm **1 test live optional** (skip khi không có network):

```python
FBISP242_XML = r"\\172.168.5.14\CustomerPro\FBI\SHOWA\FBISP242\App_Data\Controllers\Dir\LoanContract.xml"

@pytest.mark.skipif(not Path(FBISP242_XML).exists(), reason="FBISP242 share unavailable")
def test_live_rs_rpt_interest_summary():
    res = summary_object(file_path=FBISP242_XML, object_name="rs_rptInterestDetailedByLoanContract", use_cache=False)
    assert res["success"] and res["object_type"] == "PROCEDURE"
```

- User **bắt buộc** chạy smoke test thủ công 1 lần trên máy có VPN trước khi deploy MCP exe.

---

### R2. F8 thiếu — regression `query_database`

Checklist `06` Phase F8 (`query_database` type 0/1/2 không regression) **chưa có test** trong suite mới.

**Khuyến nghị:** Thêm 1 test nhẹ gọi `query_database` mock connection hoặc smoke manual sau deploy.

---

### R3. Cache key thiếu `max_objects`

**File:** `summary_bridge.py` — `_make_cache_key`

- Đã có: `keywords`, `zones`, `expand`, `exclude_like`, `include_called_by`, `max_snippet_lines`, `max_full_chars`
- **Chưa có:** `max_objects`

Hệ quả: cùng object, `max_objects=2` vs `max_objects=30` có thể trả cache cũ (truncated vs full graph).

**Fix:** Thêm `max_objects` vào tuple cache key.

---

### R4. `query_timeout` catalog — chưa enforce

**File:** `fetcher.py:60-62`

- Có `start` / `elapsed` nhưng **không** so với `self._query_timeout`, không warning.

**Fix (nice-to-have):** Nếu `elapsed > self._query_timeout` → log warning hoặc append vào meta (defer nếu MVP ổn).

---

### R5. Definition rỗng / encrypted — `success=True`

**File:** `summary_bridge.py:298-317`

- Trả `success=True`, `parse_status="failed"`, warning `encrypted_or_empty_definition`.
- Doc gốc `02` §10 gợi ý error code `encrypted` (ToolError).

**Đánh giá:** Chấp nhận được cho Agent (có warning); nếu muốn khớp doc strict → đổi `success=False`, `error=encrypted`.

---

### R6. Call graph con vẫn dùng regex `_extract_shallow_calls`

Đệ quy fetch dùng regex EXEC, không re-parse ANTLR cho child. Đủ cho MVP shallow graph; có thể miss `INSERT #x EXEC proc` phức tạp.

**Không cần sửa v1** — ghi known limitation trong tool description nếu muốn.

---

### R7. F4 test yếu

`test_f4_infra_proc_depth_zero` chỉ assert `success=True`, **không** assert `fetch_many` không gọi / infra không expand.

**Khuyến nghị:** `mock_fetcher.fetch_many.assert_not_called()` khi proc chỉ gọi infra.

---

## 4. Smoke test thủ công (user có VPN)

```powershell
cd E:\PythonProject\mcp_fbo
$xml = "\\172.168.5.14\CustomerPro\FBI\SHOWA\FBISP242\App_Data\Controllers\Dir\LoanContract.xml"

python -c "
from queryDatabase.bridges.summary_bridge import summary_object
r = summary_object(file_path=r'$xml', object_name='rs_rptInterestDetailedByLoanContract', mode='summary', use_cache=False)
print('success', r.get('success'), 'object', r.get('object'))
print('parse', r.get('parse_status'))
s = r.get('summary', {})
print('@Status', any(p.get('name')=='@Status' for p in s.get('params',[])))
print('ctdmku', 'ctdmku' in s.get('tables_read',[]))
print('cursor', s.get('signals',{}).get('has_cursor'))
"
```

Kỳ vọng: `success True`, có `@Status`, `ctdmku`, `has_cursor True`.

---

## 5. Verdict cuối

| Tiêu chí | Trạng thái |
|----------|------------|
| Blocker B1/B2 | **Đã fix** |
| Review doc lần 1 (M1–M10, N*) | **~95%** |
| Sẵn sàng merge / build exe | **Có** (sau smoke DB trên máy user) |
| “100% hoàn tất Phase F FBISP242” | **Chưa** — test F* là mock, chưa live DB |

**Không cần vòng fix lớn tiếp theo** trừ R3 (cache `max_objects`) và R1 (1 live test optional). Phần còn lại là polish / documentation accuracy.

---

## 6. Ticket từ JSON / quét DB (doc fix)

| Doc | Trạng thái | Nội dung |
|-----|------------|----------|
| `02` … `04` | **Đã fix / gom** | Lịch sử |
| [05_master_fix_from_db_scan.md](./05_master_fix_from_db_scan.md) | **Done** | Domain ladder + batch scan |
| [06_custom_listing_rs_overlap.md](./06_custom_listing_rs_overlap.md) | **Done** | rs_* không gán nhầm custom |
| [07_fbo_business_domain_flags.md](./07_fbo_business_domain_flags.md) | **Done** | Post / APV / AfterUpdate / HDDT / HDDV / Discount / Balance |
| **[08_print_inquiry_cte_options_pivot.md](./08_print_inquiry_cte_options_pivot.md)** | **Cần Gemini xử lý** | `zc_*` print vs action; CTE noise; options đa dòng; SQL PIVOT; result_sets in phiếu |

**Case:** `zc_dxtlccdc` — summary gọi action nhưng thực tế in 3 RS + chữ ký/PIVOT.

---

*Tham chiếu review lần 1:* [summary_object_implementation_review_fixes.md](./summary_object_implementation_review_fixes.md)
