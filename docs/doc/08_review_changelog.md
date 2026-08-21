# 08 — Changelog review doc (sau Gemini + chỉnh lần 2)

> Tài liệu nội bộ — ghi các sửa đổi quan trọng để implementer không lặp lại lỗi doc cũ.

## Đã sửa (lần review 2)

| # | Vấn đề | Sửa |
|---|--------|-----|
| 1 | `called_by` dùng nhầm `dm_sql_referenced_entities` (outbound) | Primary: `sys.sql_expression_dependencies` theo `referenced_id` / `object_id` |
| 2 | View depth theo tên `V*` | Depth=0 theo `sys.objects.type = 'V'` |
| 3 | Sót tên `definition_loader.py` | → `object_catalog/fetcher.py` |
| 4 | Security “cấm f-string” mâu thuẫn `query_resolver` | v1: sanitize + `N'{safe_name}'` giống code hiện tại; params là phase 2 |
| 5 | Tiêu đề “Circuit Breaker” | → “Timeout & graceful degradation”; ghi rõ không có circuit breaker v1 |
| 6 | Formatter lẫn lộn | `result_to_dict` → `sql_object_summary`; `format_summary_result` → `bridges/summary_format.py` |
| 7 | `max_depth` không thống nhất | Mặc định 1, max 3 (README + `02`) |
| 8 | `spec_version` | Required trong schema + ví dụ JSON |
| 9 | Cache TTL | `modify_date` là invalidate chính; TTL 3600s optional |
| 10 | Batch fetch SQL | Pattern OR an toàn + ghi phase 2 TVP/params |
| 11 | Checklist | Thêm test VIEW, truncated, called_by; MVP vs nice-to-have; `check_imports` bắt buộc |
| 12 | Doc lẻch (Claude review) | `07` PyInstaller + `object_catalog.fetcher`; `param_effects.role` + `evidence_lines` khớp schema trong ví dụ `03` |
| 13 | Thiếu grammar `.g4` | Thêm `tsql_engine/grammar/*.g4` vào repo + `09_tsql_grammar.md` + `download_grammar.py` |

## Đã sửa (lần review 3 — Cursor)

| # | Vấn đề | Sửa |
|---|--------|-----|
| 13 | Parse `object_name` có schema | `02` §2.1: `resolve_object_ref`, split dấu `.` đầu; ghi khác biệt với `query_database type=0` |
| 14 | Mapping `sys.objects.type` | `02` §2.3 + `03` bảng map → `PROCEDURE`/`FUNCTION`/`VIEW`; `TR`/`U` → `unsupported_type` |
| 15 | `exclude_like` thiếu default + flow | `02` §2.2 + `05` flow truyền `exclude_like` vào `AnalyzeOptions` / `build_call_graph` |
| 16 | MCP registration generic | `02` §1: pattern `MCPServer` + `Annotated`/`Field` như code hiện tại |
| 17 | ANTLR jar path mơ hồ | `04` §3: `tsql_engine/tools/antlr-4.13.2-complete.jar`, commit jar + `generated/` |
| 18 | `build_call_graph` thiếu `truncated_objects` | `07` public API đồng bộ với `05`/`06` |
| 19 | Snippet mode không validate | `02` error `snippet_params_required`; `05` check trước fetch DB |
| 20 | Checklist thiếu `.cursorrules` / requirements | `06` Phase E3 mở rộng |

## File đã cập nhật (lần 2)

- `README.md`
- `01_overview.md`
- `02_tool_api.md`
- `03_json_schema.md`
- `04_antlr4_parser.md`
- `05_integration.md`
- `06_implementation_checklist.md`
- `07_architecture_layers.md`

## File đã cập nhật (lần review 3)

- `README.md`
- `01_overview.md`
- `02_tool_api.md`
- `03_json_schema.md`
- `04_antlr4_parser.md`
- `05_integration.md`
- `06_implementation_checklist.md`
- `07_architecture_layers.md`
- `08_review_changelog.md`

## Đã sửa (lần review 4 — Fix sau Cursor review & Edge tests)

| # | Vấn đề | Sửa |
|---|--------|-----|
| 21 | **Blocker B1:** Đảo tham số `execute_query(sql, self._parsed)` | Đổi thành `execute_query(self._parsed, sql)` across all 5 call sites |
| 22 | **Blocker B2:** Đọc `res["data"]` thay vì `res["result_sets"]` | Thêm helper `_rows_from_result(res)` parse `result_sets` columns/rows thành dicts |
| 23 | **Major M1:** `exclude_like=None` override default | Thêm `__post_init__` trong `AnalyzeOptions` & merge default trong bridge |
| 24 | **Major M2 & M9:** `max_depth >= 2` & cycle detection | Implement vòng lặp đệ quy `_collect_definitions` với `visited: set` & deadline 30s |
| 25 | **Major M3:** `expand` bare name không khớp | Chuẩn hóa `expand_normalized` khớp cả bare name và schema-qualified |
| 26 | **Major M4:** `include_called_by` mất khi root không có EXEC | Luôn khởi tạo `CallGraph` tối thiểu khi `include_called_by=True` |
| 27 | **Major M5 & N9:** `exclude_patterns` dead code & leaf nodes | Áp dụng `_matches_exclude` và bổ sung unexpanded leaf nodes |
| 28 | **Major M6 & N4:** Cache key snippet & options | Mở rộng tuple cache key với keywords, zones, expand, exclude_like, lines, chars |
| 29 | **Major M10:** Mock test che blocker | Cập nhật `test_object_catalog.py` mock `result_sets` và assert thứ tự `(parsed, sql)` |
| 30 | **Minor N1-N8:** Warnings, empty def, parse_status | Bổ sung warning `no_snippet_matches`, `encrypted_or_empty_definition`, `parse_status="failed"` |
| 31 | **Phase F:** Thiếu integration test suite | Tạo `tests/integration/test_summary_fbisp242.py` (9 tests F1–F10, 24/24 tests pass) |

