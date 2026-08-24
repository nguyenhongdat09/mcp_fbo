# 08 — Dev & Test Guide

## 1. Ba tầng test

| Tầng | Môi trường | Cần Cursor? | Cần `dist`? |
|------|------------|-------------|-------------|
| **1** | Python script / breakpoint | Không | Không |
| **2** | Cursor + MCP source | Có | Không |
| **3** | `fastbusiness_mcp.exe` | Có | Có (release) |

**Khuyến nghị lúc dev:** Tầng 1 → 2. Tầng 3 chỉ trước release.

---

## 2. Tầng 1 — Unit / integration trực tiếp

### Setup

```bash
cd E:\PythonProject\mcp_fbo
.venv\Scripts\activate
pip install playwright
```

Bật Chrome debug (xem [03_config.md](03_config.md)).

### Script smoke test (future)

```python
# scripts/test_chrome_debug_smoke.py
# Offline: config_loader, buffers — không cần Chrome
# E2E: chỉ chạy khi ping_cdp() == True

from fastbusiness_mcp.chrome_debug.service import check_status, list_tabs

if __name__ == "__main__":
    print(check_status())
    print(list_tabs())
```

### Breakpoint

Đặt breakpoint trong:

- `session.py` → `connect()`, `resolve_page()`
- `snapshot.py` → `build_snapshot()`
- `service.py` → orchestration

Chạy Debug F5 trên script — quan sát Chrome nhảy khi test fill/click.

---

## 3. Tầng 2 — Cursor Agent + MCP source

### Cấu hình MCP

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\PythonProject\\mcp_fbo\\.venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\PythonProject\\mcp_fbo"
    }
  }
}
```

### Reload sau sửa code

Cursor **không** hot-reload MCP process:

1. Sửa file trong `chrome_debug/`
2. Restart MCP server (Command Palette → MCP: Restart hoặc reload window)
3. Test lại tool từ Agent

### Test manual qua Agent

Prompt gợi ý:

```
chrome_debug(type=1)
(chrome mở tab FBO)
chrome_debug(type=2, tab_keyword=SVTran)
chrome_debug(type=3, fields_json={"ma_kh":"123"}, tab_keyword=SVTran)
```

---

## 4. Tầng 3 — Build exe (optional)

```bash
build_onedir.bat
```

Output: `dist/fastbusiness_mcp/fastbusiness_mcp.exe`

Chỉ cần khi:

- Máy không có Python
- Phát hành nội bộ

Dev hàng ngày **không** cần rebuild sau mỗi thay đổi chrome tool.

---

## 5. Checklist trước khi test runtime

- [ ] Chrome debug shortcut chạy (`http://localhost:9222/json/version` OK)
- [ ] Tab FBO đã login trên **profile debug** (không phải Chrome thường nếu chưa attach được)
- [ ] `playwright` installed trong `.venv` MCP
- [ ] MCP server restarted sau pull code mới

---

## 6. Kịch bản test FBO gợi ý

### A. Read-only (Phase 1 MVP)

1. Mở SVTran trên Chrome debug
2. Agent: `chrome_debug(type=1)` → available + tabs
3. Agent: `chrome_debug(type=2, tab_keyword=...)` → lỗi + `ma_kh`, nút Lưu

### B. Interaction (Phase 2)

1. `chrome_debug(type=3, fields_json={"ma_kh":"123"})` — quan sát UI
2. `chrome_debug(type=4, script=...)` verify readonly
3. Gây lỗi JS → `type=2` bắt TypeError

### C. Regression static

1. Tắt Chrome debug
2. `query_database`, `read_local_file` vẫn OK
3. `chrome_debug(type=1)` → available false

### D. MainReport runtime — BinhDienMK (2026-08-23)

Môi trường: VPN `172.168.5.14/BinhDienMK`, Chrome CDP `localhost:9222`.

| Script | Kiểm tra |
|--------|----------|
| `scripts/probe_fbo_three_screens.py` | Classify 3 URL: báo cáo / danh mục / chứng từ |
| `scripts/_test_report_lookup_ma_vt.py` | Lookup `ma_vt` → Nhận → Tìm |
| `scripts/_probe_grid_getItemValue5.py` | Chữ ký `_getItemValue(1,1)` → `"00131"` |

Chi tiết API & workflow: [12_fbo_webforms_mainreport_runtime.md](12_fbo_webforms_mainreport_runtime.md).

---

## 7. Troubleshooting

| Triệu chứng | Nguyên nhân | Xử lý |
|-------------|-------------|--------|
| Connection refused :9222 | Chrome debug chưa bật | Mở shortcut debug |
| Connect OK, 0 tabs | Chrome mới mở chưa có tab | Mở tab FBO |
| Tool không xuất hiện | Chưa register / MCP chưa restart | Restart MCP |
| Fill không trigger onChange | Cần dispatch event | Playwright fill; thử Tab blur hoặc execute_js |
| Attach Chrome thường fail | Không có debug port | Dùng profile debug riêng |

---

## 8. Liên kết

- Config Chrome: [03_config.md](03_config.md)
- Implementation phases: [09_implementation_checklist.md](09_implementation_checklist.md)
