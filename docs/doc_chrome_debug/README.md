# Chrome CDP Debug MCP — Tài liệu thiết kế

Bộ tài liệu mô tả tính năng **Chrome CDP Debug** tích hợp vào FastBusiness MCP Server: attach Chrome thật qua CDP (`localhost:9222`), snapshot UI gọn, bắt console/network, tương tác form — phục vụ Cursor Agent debug runtime FBO.

> **Phạm vi tài liệu:** thiết kế / spec / workflow. Chưa triển khai code Python (xem [09_implementation_checklist.md](09_implementation_checklist.md)).

---

## Mục lục

| # | File | Nội dung |
|---|------|----------|
| 1 | [01_overview.md](01_overview.md) | Bối cảnh, mục tiêu, phạm vi, non-goals |
| 2 | [02_architecture_layers.md](02_architecture_layers.md) | Kiến trúc module, tách file, lazy connect |
| 3 | [03_config.md](03_config.md) | `chrome_debug.yaml`, env vars, Chrome shortcut |
| 4 | [04_tool_api.md](04_tool_api.md) | Spec **1 tool** `chrome_debug` — `type` 1·2·3·4 |
| 5 | [05_agent_workflow.md](05_agent_workflow.md) | Rule agent, workflow, ví dụ FBO |
| 6 | [06_token_budget.md](06_token_budget.md) | Chiến lược tiết kiệm token |
| 7 | [07_integration.md](07_integration.md) | Gắn vào `mcp_app.py` (thin layer) |
| 8 | [08_dev_test_guide.md](08_dev_test_guide.md) | Debug Python, Cursor source, Chrome debug |
| 9 | [09_implementation_checklist.md](09_implementation_checklist.md) | Roadmap MVP → full |
| 10 | [10_fbo_sp2263_runtime_profile.md](10_fbo_sp2263_runtime_profile.md) | **Review FBO SP2263** — DOM, JS, grid, lookup, tab_keyword |
| 11 | [11_fbo_showform_flowmulti_patterns.md](11_fbo_showform_flowmulti_patterns.md) | **`g.showForm` / FlowMulti / FlowForm** — 8 kiểu, deferred request, TransferData, checklist Chrome + fbo_js_skill |
| 12 | [12_fbo_webforms_mainreport_runtime.md](12_fbo_webforms_mainreport_runtime.md) | **MainReport runtime** — `$find`, `_type`, lookup lọc báo cáo, `_getItemValue` grid (probe BinhDienMK) |
| 13 | [13_fbo_runtime_agent_architecture.md](13_fbo_runtime_agent_architecture.md) | **Kiến trúc Gemini** — module/API để agent tự lookup/CRUD/grid dynamic |

---

## Quick start (khi đã triển khai code)

1. Cài dependency: `pip install playwright` (trong cùng `.venv` MCP).
2. Bật Chrome debug (profile riêng, xem [03_config.md](03_config.md)).
3. Cursor trỏ MCP source: `python -m fastbusiness_mcp.server` (không cần `dist`).
4. Agent gọi `chrome_debug(type=1)` → nếu OK → `type=2` / `type=3` / `type=4`.

---

## Quan hệ với MCP hiện tại

```
fastbusiness-mcp (1 server)
├── Static (design-time): query_database, read_local_file, query_radar, get_xml_entities, search_qlyc
└── Runtime (run-time):   chrome_debug (type 1–4)  ← tài liệu này
```

Chrome MCP **bổ sung**, không thay thế 5 tool static. Agent kết hợp cả hai: đọc XML/SQL trước, verify trên browser sau (khi cần).

**Project FBO tham chiếu:** [10_fbo_sp2263_runtime_profile.md](10_fbo_sp2263_runtime_profile.md) (SP2263 `f`/`g`); [12_fbo_webforms_mainreport_runtime.md](12_fbo_webforms_mainreport_runtime.md) (MainReport `$find` — probe BinhDienMK); [13_fbo_runtime_agent_architecture.md](13_fbo_runtime_agent_architecture.md) (**Gemini implement — agent dynamic**).

---

## Folder code (future)

Module runtime dự kiến: `fastbusiness_mcp/chrome_debug/` — tách biệt hoàn toàn khỏi SQL/XML/Graph. Chi tiết: [02_architecture_layers.md](02_architecture_layers.md).

Config riêng: `fastbusiness_mcp/chrome_debug.yaml` — chi tiết: [03_config.md](03_config.md).

---

## Tài liệu liên quan

- [docs/doc_summary_xml/](../doc_summary_xml/) — pattern tài liệu feature tách folder (summary_xml).
- [README.md](../../README.md) — MCP server root.
- [docs/doc_fix/review_and_fix_recommendations.md](../doc_fix/review_and_fix_recommendations.md) — góp ý triển khai (Gemini review).
