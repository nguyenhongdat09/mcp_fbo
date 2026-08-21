# Review & Fix List — Tool MCP `summary_object` (sau Gemini implement)

> **Người review:** Cursor (test kỹ 2026-08-20)  
> **Mục đích:** Gửi Gemini sửa theo thứ tự ưu tiên.  
> **Spec tham chiếu:** `docs/doc/` (đặc biệt `02_tool_api.md`, `05_integration.md`, `06_implementation_checklist.md`)

---

## 1. Tóm tắt executive

| Hạng mục | Kết quả |
|----------|---------|
| `scripts/check_imports.py` | **PASS** |
| `pytest tests/` | **15/15 PASS** (~26–29s) |
| Import MCP server | **PASS** |
| **`summary_object` trên DB thật** | **FAIL** — 2 blocker trong `object_catalog/fetcher.py` |
| Phase F FBISP242 (checklist `06`) | **Chưa chạy** — không có integration test |

**Kết luận:** Unit test pure-layer (ANTLR, analyze, snippet) **ổn**. Lớp catalog DB **sai contract** với `execute_query` hiện có → tool **không chạy được end-to-end** khi nối SQL Server thật. Mock test che lỗi này.

Script tái hiện lỗi: `scripts/verify_summary_object_edges.py` (11 findings tự động + mục bổ sung dưới đây).

---

## 2. Blocker — sửa TRƯỚC, không merge production

### B1. Đảo tham số `execute_query` trong fetcher

| | |
|---|---|
| **File** | `queryDatabase/object_catalog/fetcher.py` |
| **Dòng** | 42, 89, 121, 137, 168 |
| **Expected** | `execute_query(self._parsed, sql)` — signature `executor.py:120-124`, `service.py:69` |
| **Actual** | `execute_query(sql, self._parsed)` |
| **Hậu quả live** | `AttributeError: 'dict' object has no attribute 'strip'` tại `executor.py:128` |
| **Fix** | Đổi **5 call site** thành `execute_query(self._parsed, sql)` |
| **Test hiện tại** | **Không bắt** — `test_object_catalog.py` mock không kiểm tra thứ tự arg |

**Chứng minh nhanh:**

```powershell
python -c "from queryDatabase.executor import execute_query; execute_query('SELECT 1', {'server':'x','database':'y','user':'u','password':'p'})"
# → AttributeError
```

---

### B2. Fetcher đọc `res["data"]` — executor trả `result_sets`

| | |
|---|---|
| **File** | `queryDatabase/object_catalog/fetcher.py` |
| **Dòng** | 46, 93, 122-123, 138-139, 173 |
| **Expected** | Parse `result_sets[0].columns` + `rows` → list dict (giống `query_resolver.parse_object_lookup_result`) |
| **Actual** | `rows = res.get("data") or []` → luôn rỗng với response thật |
| **Hậu quả** | Sau khi sửa B1, vẫn `object_not_found` dù object tồn tại trên DB |
| **Fix** | Thêm helper ví dụ `_rows_from_result(res) -> list[dict]`; dùng ở mọi method fetch |

**Gợi ý helper:**

```python
def _rows_from_result(res: dict) -> list[dict]:
    if not res.get("success"):
        return []
    result_sets = res.get("result_sets") or []
    if not result_sets:
        return []
    rs = result_sets[0]
    columns = [str(c).lower() for c in rs.get("columns", [])]
    rows = rs.get("rows") or []
    out = []
    for row in rows:
        out.append({columns[i]: row[i] for i in range(min(len(columns), len(row)))})
    return out
```

**Test cần thêm:** `test_object_catalog.py` mock **`result_sets`** (không dùng `data`), assert arg order `(parsed, sql)`.

---

## 3. Major — sửa sau blocker, trước Phase F

### M1. `exclude_like=None` từ bridge không merge default

| | |
|---|---|
| **File** | `queryDatabase/bridges/summary_bridge.py:239-245, 287` |
| **Expected** | Doc `02` §2.2: khi Agent không truyền → `DEFAULT_EXCLUDE_LIKE` |
| **Actual** | `AnalyzeOptions(exclude_like=None)` — explicit None ghi đè default dataclass |
| **Fix** | Trong bridge: `exclude_patterns = exclude_like if exclude_like is not None else list(DEFAULT_EXCLUDE_LIKE)`; truyền `exclude_patterns` vào `AnalyzeOptions` và `build_call_graph` |

---

### M2. `max_depth=2|3` không đệ quy fetch

| | |
|---|---|
| **File** | `queryDatabase/bridges/summary_bridge.py:255-289` |
| **Expected** | Doc `02` §7: đệ quy đến `max_depth` / `max_objects` |
| **Actual** | Chỉ **1 lần** `fetch_many` cho direct calls; `dbo.grand` không fetch khi `max_depth=2` |
| **Fix** | Implement `_collect_definitions(fetcher, calls, depth, visited, ...)` loop theo pseudo-code trong `05_integration.md` |

---

### M3. `expand` bare name không khớp infra call

| | |
|---|---|
| **File** | `queryDatabase/bridges/summary_bridge.py:271` |
| **Expected** | `expand=['FastBusiness$Balance$BContract']` khớp call `dbo.FastBusiness$Balance$BContract` (doc + `mcp_app.py` tool description) |
| **Actual** | `call.name in expand_set` — so sánh literal; bare name **không** match schema-qualified |
| **Fix** | Normalize: `def _expand_key(name): return name.split('.')[-1]` cho cả `expand_set` và `call.name`; hoặc resolve cả hai về `(schema, bare)` |

**Lưu ý:** Business child (`zc_child`) vẫn fetch vì `call.kind == "business"` — bug chỉ ảnh hưởng **infra + expand**.

---

### M4. `include_called_by=True` mất khi root không có EXEC

| | |
|---|---|
| **File** | `queryDatabase/bridges/summary_bridge.py:291-298` |
| **Expected** | Checklist F7: `called_by` có dữ liệu hoặc warning |
| **Actual** | `fetch_callers` **được gọi** nhưng gán vào `pure_summary.call_graph.called_by` chỉ khi `call_graph is not None`. Proc không gọi ai → `call_graph=None` → **mất callers** |
| **Fix** | Tạo `CallGraph` tối thiểu (root only) khi `include_called_by`; hoặc đặt `called_by` ở top-level response |

---

### M5. `exclude_patterns` trong `build_call_graph` — dead code

| | |
|---|---|
| **File** | `sql_object_summary/call_graph.py:23` |
| **Expected** | `exclude_like` lọc object khỏi expansion |
| **Actual** | Gán `exclude_patterns = ...` nhưng **không dùng** trong body |
| **Fix** | Áp dụng khi build nodes / quyết định fetch; hoặc bỏ param nếu filter chỉ ở bridge |

---

### M6. Cache snippet không phân biệt `keywords` / `zones`

| | |
|---|---|
| **File** | `queryDatabase/bridges/summary_bridge.py:48, 187` |
| **Expected** | Keywords khác → snippet khác |
| **Actual** | Key `(server, db, object_id, modify_date, mode, max_depth)` — request snippet thứ 2 trả cache request đầu |
| **Fix** | Với `mode='snippet'`: thêm `tuple(keywords or [])`, `tuple(zones or [])`, `max_snippet_lines` vào key; hoặc **tắt cache** cho snippet |

---

### M7. `query_timeout` catalog không enforce

| | |
|---|---|
| **File** | `queryDatabase/object_catalog/fetcher.py:18-20` |
| **Expected** | Doc `02` §12: 10s/fetch |
| **Actual** | `_query_timeout` lưu nhưng không truyền `execute_query`, không check `perf_counter` sau fetch |
| **Fix** | Phase 1: check elapsed sau `execute_query`, warning nếu vượt; Phase 2: timeout pyodbc |

---

### M8. Tổng timeout 30s/request chưa có

| | |
|---|---|
| **File** | `queryDatabase/bridges/summary_bridge.py` — toàn hàm `summary_object` |
| **Expected** | Doc `02` §12 |
| **Actual** | Không deadline |
| **Fix** | `deadline = time.perf_counter() + 30`; check trước mỗi fetch đệ quy; trả partial + warning |

---

### M9. Không có cycle detection khi thu thập call graph

| | |
|---|---|
| **File** | `queryDatabase/bridges/summary_bridge.py:255-289` |
| **Expected** | Doc `02` §7: `visited: set[(schema, name)]` |
| **Actual** | Không có `visited`; proc đệ quy có thể fetch lặp (chỉ giới hạn lỏng bởi `max_objects` trên direct calls) |
| **Fix** | Thêm `visited` trong `_collect_definitions` |

---

### M10. Mock test catalog sai contract → che blocker

| | |
|---|---|
| **File** | `tests/queryDatabase/test_object_catalog.py` |
| **Expected** | Mock giống `execute_query` thật |
| **Actual** | `{"success": True, "data": [...]}` — key không tồn tại trong production |
| **Fix** | Refactor mock dùng `result_sets`; assert `(parsed, sql)` qua `call_args` |

---

## 4. Minor — polish sau MVP

### N1. Definition rỗng / encrypted im lặng

- **File:** `fetcher.py:54`, `summary_bridge.py`, `analyze.py`
- **Actual:** `definition or ""` → `success=True`, summary rỗng
- **Fix:** Sau fetch, nếu không `definition.strip()` → `error: encrypted` hoặc `meta.warnings`

### N2. `called_by` JSON shape lệch doc

- **File:** `summary_bridge.py:296`
- **Actual:** `[{"name": "dbo.caller"}]`
- **Doc:** `called_by: []` (list string)
- **Fix:** Chọn một format; cập nhật code + `03_json_schema.md` cho khớp

### N3. Snippet không match → không warning

- **File:** `sql_object_summary/snippet.py`
- **Actual:** `success=True`, `snippets=[]`
- **Fix:** `meta.warnings.append("no_snippet_matches")`

### N4. Cache key thiếu `expand`, `max_objects`, `include_called_by`, `exclude_like`, `max_full_chars`

- **File:** `summary_bridge.py:48`
- **Fix:** Mở rộng key hoặc ghi rõ trong doc là intentional

### N5. `DirectCall.expanded` luôn `false`

- **File:** `summary_visitor.py:250`; bridge không cập nhật sau fetch
- **Fix:** Set `expanded=True` cho call đã fetch definition

### N6. `meta.objects_fetched` luôn default `1`

- **File:** `models.py`; bridge không set
- **Fix:** `len(definitions_dict)` trước return

### N7. Visitor exception bị nuốt

- **File:** `sql_object_summary/analyze.py:41-44` — `except Exception: pass`
- **Fix:** Ghi `meta.warnings`; set `parse_status=partial`

### N8. `resolve_object_ref` — tên nhiều dấu chấm

- **File:** `summary_bridge.py:95` — `partition(".")` lấy phần đầu
- **Actual:** `dbo.proc.extra` → schema=`dbo`, name=`proc` (sai)
- **Fix:** Validate tối đa 1 dấu chấm; hoặc document reject

### N9. `build_call_graph` child depth luôn `1`

- **File:** `call_graph.py:81`
- **Actual:** `max_depth=2` chỉ set `expanded=True`, không thêm grandchild vào `nodes`
- **Fix:** Recurse hoặc document “shallow graph only”

---

## 5. Phase F — chưa làm (checklist `06`)

Chưa có `tests/integration/test_summary_fbisp242.py`. Sau khi sửa B1+B2, chạy manual:

| # | Object | Assert |
|---|--------|--------|
| F1 | `rs_rptInterestDetailedByLoanContract` | `@Status`, `ctdmku`, cursor, `spec_version` |
| F2 | `zc_bcthlv` | pivot, `#pivot` (nếu có trên DB) |
| F3 | snippet `tl_th`, `@Status` | < 150 lines |
| F4 | `ff_GetStartDateOfCycle` | infra, depth 0 |
| F5 | VIEW bất kỳ | `object_type=VIEW`, không expand graph |
| F6 | `max_objects=2` | `truncated: true` |
| F7 | `include_called_by` | có data hoặc warning |
| F8 | `query_database` 0/1/2 | không regression |
| F9 | `dbo.zc_x` vs `zc_x` + `schema=dbo` | cùng kết quả |
| F10 | snippet không keywords/zones | `snippet_params_required` |

**Path gợi ý FBISP242:**  
`\\172.168.5.14\CustomerPro\FBI\SHOWA\FBISP242\App_Data\Controllers\Dir\LoanContract.xml`

*(Môi trường review Cursor: network path không resolve — cần chạy trên máy có VPN/share.)*

---

## 6. Thứ tự fix đề xuất cho Gemini

```
1. B1 + B2  (fetcher — bắt buộc để tool sống)
2. M10      (sửa test catalog — tránh regression)
3. M1, M3, M4, M6  (bridge behavior doc đã ghi)
4. M2, M9   (call graph đệ quy + visited)
5. M5, M7, M8  (call_graph exclude + timeout)
6. N1–N9    (polish)
7. Phase F integration test + chạy FBISP242
```

---

## 7. Acceptance sau fix

- [ ] `summary_object(mode=summary)` trên `rs_rptInterestDetailedByLoanContract` + file_path FBISP242 → JSON có params/tables/signals
- [ ] `pytest tests/` pass (≥ 18 tests nếu thêm catalog + integration smoke)
- [ ] `scripts/verify_summary_object_edges.py` → **0 blocker, 0 major** (hoặc chỉ còn M7/M8 nếu defer timeout)
- [ ] `scripts/check_imports.py` pass
- [ ] Không break 5 tools cũ

---

## 8. File liên quan cần sửa (tóm tắt)

| File | Blocker | Major | Minor |
|------|---------|-------|-------|
| `queryDatabase/object_catalog/fetcher.py` | B1, B2 | M7 | N1 |
| `queryDatabase/bridges/summary_bridge.py` | — | M1,M2,M3,M4,M6,M8,M9 | N2,N4,N5,N6,N8 |
| `sql_object_summary/call_graph.py` | — | M5 | N9 |
| `sql_object_summary/analyze.py` | — | — | N7 |
| `sql_object_summary/snippet.py` | — | — | N3 |
| `tests/queryDatabase/test_object_catalog.py` | — | M10 | — |
| `tests/integration/test_summary_fbisp242.py` | — | (mới) | — |

---

## 9. Log test review (Cursor)

```text
scripts/check_imports.py          → [OK]
pytest tests/ -v                  → 15 passed in ~26-29s
fastbusiness_mcp.mcp_app import   → OK (server name: fastbusiness-mcp-server)
execute_query(reversed args)      → AttributeError (confirms B1)
fetcher + result_sets mock        → meta is None (confirms B2)
verify_summary_object_edges.py    → 11 findings (2 blocker, 4 major, 5 minor)
include_called_by, no EXEC        → call_graph=None, callers dropped (M4)
FBISP242 live                     → conn resolve failed (network); chưa test E2E
```

---

*Tài liệu này bổ sung cho `docs/doc/08_review_changelog.md` — ghi thêm mục "lần review 4 (post-implement Gemini)".*
