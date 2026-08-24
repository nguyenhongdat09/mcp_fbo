# 03 — Configuration

## 1. Tách file config

Feature Chrome Debug dùng **file riêng**, không nhét limit/CDP vào `fastbusiness_mcp/config.yaml` chính.

| File | Vai trò |
|------|---------|
| `fastbusiness_mcp/chrome_debug.yaml` | Defaults đầy đủ cho feature |
| `fastbusiness_mcp/config.yaml` | (Tuỳ chọn) 1 dòng pointer: `chrome_debug_config: chrome_debug.yaml` |
| Env `CHROME_DEBUG_CONFIG_PATH` | Override đường dẫn file yaml |
| Env `CHROME_DEBUG_CDP_URL` | Override URL nhanh (không sửa file) |

Pattern resolve path tham chiếu [fastbusiness_mcp/config_paths.py](../../fastbusiness_mcp/config_paths.py) (`resolve_config_path`, `get_exe_dir` cho PyInstaller sau này).

---

## 2. Schema `chrome_debug.yaml` (mẫu)

```yaml
# fastbusiness_mcp/chrome_debug.yaml

enabled: true

# CDP endpoint — Chrome phải bật --remote-debugging-port tương ứng
cdp_url: "http://localhost:9222"

# Tuỳ chọn: launch Chrome từ MCP (phase sau)
chrome_path: ""          # Windows: C:\Program Files\Google\Chrome\Application\chrome.exe
user_data_dir: ""        # Profile riêng; trống = %TEMP%\chrome-fbo-debug

snapshot:
  max_nodes: 120         # Số phần tử interactive tối đa / frame
  max_label_chars: 120   # Cắt text hiển thị
  mode: "interactive"    # interactive | fields_only (future)

network:
  max_response_chars: 4000
  capture_status_from: 400   # Chỉ log response status >= 400

console:
  max_lines: 200             # Ring buffer per tab

execute_js:
  max_result_chars: 2000     # Cắt JSON result trả agent

launch:
  auto_launch: false         # MVP: user mở shortcut tay
  port: 9222
  headless: false
```

---

## 3. Biến môi trường

| Biến | Mô tả |
|------|--------|
| `CHROME_DEBUG_CONFIG_PATH` | Absolute path tới yaml override |
| `CHROME_DEBUG_CDP_URL` | Override `cdp_url` (vd `http://127.0.0.1:9222`) |
| `CHROME_DEBUG_ENABLED` | `false` tắt toàn bộ tool (trả message ngắn) |

---

## 4. `config_loader.py` (future)

Trách nhiệm:

1. Resolve file yaml (env → pointer trong config.yaml → default `chrome_debug.yaml`)
2. Merge env overrides
3. Validate kiểu (Pydantic model `ChromeDebugSettings` hoặc dataclass)
4. Expose `get_chrome_debug_config() -> dict` cho `session.py` / `service.py`

**Không** load Playwright lúc import module.

---

## 5. Cursor MCP — một server, không tách project

Giữ nguyên entry point hiện tại; Chrome tools đăng ký cùng process:

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

Sau implement: reload MCP server trong Cursor khi sửa tool Chrome.

---

## 6. Bật Chrome debug mode

Chrome **bình thường** không expose CDP. Phải dùng profile debug riêng (không ảnh hưởng Chrome hàng ngày).

### Windows — Shortcut Target

```text
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-fbo-debug"
```

### Windows — PowerShell one-liner

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="$env:TEMP\chrome-fbo-debug"
```

### macOS

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/chrome-fbo-debug"
```

### Kiểm tra

Mở trình duyệt: `http://localhost:9222/json/version` — phải trả JSON (Browser, webSocketDebuggerUrl).

Tool `chrome_debug` wrap bước ping này (`type=1`).

---

## 7. Workflow profile debug

1. Lần đầu: mở Chrome debug → login FBO trên profile `chrome-fbo-debug`
2. Session giữ cookie — các lần sau chỉ mở shortcut
3. Làm việc sửa XML/SQL: **không** cần Chrome debug
4. Khi agent verify runtime: mở tab FBO trên profile debug

---

## 8. `enabled: false`

Khi tắt trong yaml hoặc env:

- Tool `chrome_debug` trả message ngắn: feature disabled
- Không import Playwright
- Zero overhead cho deployment không cần browser debug

---

## 9. Liên kết

- Tool API: [04_tool_api.md](04_tool_api.md)
- Dev test: [08_dev_test_guide.md](08_dev_test_guide.md)
