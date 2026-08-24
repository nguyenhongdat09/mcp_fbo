# 09 — Implementation Checklist

## 1. Tổng quan phases

| Phase | Nội dung | Trạng thái doc |
|-------|----------|----------------|
| **0** | Tài liệu thiết kế + config spec | Done (folder này) |
| **1** | MVP read-only Chrome tools | Chưa code |
| **2** | Interaction tools | Chưa code |
| **3** | Launch helper + FBO extensions | Chưa code |
| **4** | Rules + README + PyInstaller | Chưa code |

---

## 2. Phase 0 — Documentation (hoàn thành)

- [x] `docs/doc_chrome_debug/README.md`
- [x] `01_overview.md` — bối cảnh, scope, non-goals
- [x] `02_architecture_layers.md` — module map, mermaid, lazy connect
- [x] `03_config.md` — `chrome_debug.yaml`, env, Chrome shortcut
- [x] `04_tool_api.md` — **1 tool** `chrome_debug` + `type` 1–4
- [x] `05_agent_workflow.md` — workflow, ví dụ SVTran
- [x] `06_token_budget.md` — giới hạn token
- [x] `07_integration.md` — thin register `mcp_app.py`
- [x] `08_dev_test_guide.md` — 3 tầng test
- [x] `09_implementation_checklist.md` — file này
- [x] `10_fbo_sp2263_runtime_profile.md` — review FBO SP2263 Controllers

---

## 3. Phase 1 — MVP (read-only)

### 3.1 Scaffold package

- [ ] Tạo `fastbusiness_mcp/chrome_debug/` theo [02_architecture_layers.md](02_architecture_layers.md)
- [ ] `constants.py` — defaults
- [ ] `config_loader.py` + `fastbusiness_mcp/chrome_debug.yaml`
- [ ] `buffers.py` — `TabBuffers`
- [ ] `session.py` — ping, connect, resolve_page, hooks
- [ ] `snapshot.py` — interactive snapshot JS
- [ ] `service.py` — `dispatch(type)` → status, inspect, interact, execute
- [ ] `tools.py` — **một** `@server.tool` `chrome_debug`
- [ ] `__init__.py` — public exports

### 3.2 MCP integration

- [ ] `register_chrome_tools(server, get_config)` trong `mcp_app.py`
- [ ] Import guard playwright
- [ ] `format_execution_error` cho mọi tool

### 3.3 Tool Phase 1–2 (một entry point)

- [ ] `chrome_debug` type **1** — status + tabs
- [ ] `chrome_debug` type **2** — errors + inspect
- [ ] `chrome_debug` type **3** — interact (click + fill)
- [ ] `chrome_debug` type **4** — execute_js

### 3.4 Test Phase 1

- [ ] `scripts/test_chrome_debug_smoke.py`
- [ ] Manual: Chrome debug + tab FBO + 4 tools qua Cursor
- [ ] Static tools vẫn chạy khi CDP off

### 3.5 Dependencies

- [ ] `requirements.txt` thêm `playwright>=1.40.0`

---

### 4. Phase 2 — Interaction (trong cùng tool)

- [ ] `actions.py` — interact + execute
- [ ] Validation param theo `type`
- [ ] Test: type=3 fill `ma_kh` → type=4 verify readonly

---

## 5. Phase 3 — Extensions

- [ ] `chrome_launch_debug` (Windows shortcut helper)
- [ ] Config `launch.auto_launch`
- [ ] `inspect` mode `fields_only`
- [ ] iframe / frame picker (nếu FBO cần)
- [ ] `fbo_helpers.py` — grid readonly verify (optional)

---

## 6. Phase 4 — Polish

- [ ] Append section Chrome vào [.cursorrules](../../.cursorrules) (nội dung từ [05_agent_workflow.md](05_agent_workflow.md))
- [ ] Cập nhật [README.md](../../README.md) — tool count + link doc
- [ ] PyInstaller: bundle `chrome_debug.yaml`, hiddenimports playwright (nếu cần exe)
- [ ] Metric log output size (optional)

---

## 7. Definition of Done (MVP = Phase 1+2)

| Tiêu chí | Pass |
|----------|------|
| Agent `chrome_debug(type=1)` khi CDP off → message tiếng Việt + shortcut | |
| Agent type=2 trên tab FBO → thấy `ma_kh`, nút Lưu | |
| Agent type=3 + type=4 — user thấy Chrome đổi | |
| `query_database` / `read_local_file` không bị ảnh hưởng khi thiếu playwright | |
| Không tool nào trả raw HTML | |
| Output inspect ≤ config `max_nodes` | |

---

## 8. Rủi ro & mitigation

| Rủi ro | Mitigation |
|--------|------------|
| FBO grid ảo | Phase 2 `execute_js`; Phase 3 fbo_helpers |
| Token cao | [06_token_budget.md](06_token_budget.md) + cap trong service |
| Chrome không debug | `chrome_debug(type=1)` + rule agent dừng sớm |
| Playwright nặng | Optional dep, lazy import |
| iframe popup | inspect multi-frame (đã spec); frame picker phase 3 |

---

## 9. Liên kết

- [README.md](README.md) — mục lục doc
- [07_integration.md](07_integration.md) — code hook points
- [08_dev_test_guide.md](08_dev_test_guide.md) — cách test từng phase
