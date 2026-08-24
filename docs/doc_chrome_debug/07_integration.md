# 07 — Integration với FastBusiness MCP

## 1. Nguyên tắc integration

- **Một server** — `fastbusiness-mcp-server`, không tách MCP config Cursor.
- **Thin layer** — [fastbusiness_mcp/mcp_app.py](../../fastbusiness_mcp/mcp_app.py) chỉ register tools; zero logic CDP inline.
- **Package tách** — `fastbusiness_mcp/chrome_debug/` self-contained.
- **Backward compatible** — thiếu `playwright` hoặc `enabled: false` không ảnh hưởng 5 tool cũ.

---

## 2. Thay đổi `mcp_app.py` (future)

### Import (cuối file, trước `call_tool` intercept)

```python
from fastbusiness_mcp.chrome_debug.tools import register_chrome_tools

register_chrome_tools(server, get_config)
```

### Không làm trong `mcp_app.py`

- `connect_over_cdp`
- Playwright import
- Snapshot JS
- Buffer console

---

## 3. `tools.py` — pattern register

```python
def register_chrome_tools(server, get_config_fn) -> None:
    cfg = get_config_fn()
    chrome_cfg = load_chrome_debug_config(cfg)

    if not chrome_cfg.get("enabled", True):
        return

    @server.tool(name="chrome_debug")
    def chrome_debug_tool(
        type: Annotated[int, Field(description="1=status, 2=inspect, 3=interact, 4=execute")],
        tab_keyword: Annotated[str, Field(default="")] = "",
        ...
    ) -> str:
        return dispatch_chrome_debug(type, ...)
```

Một handler route `type` → `service.py` (`check_status`, `inspect_page`, `interact_page`, `execute_js`).

Mỗi lần gọi:

1. Validate param theo `type`
2. `try/except` → `format_execution_error("chrome_debug", e)`
3. Return JSON string

Copy pattern từ `query_database_tool` / `read_local_file_tool` (Annotated + Field + docstring tiếng Việt).

---

## 4. Config loading

### Option A — Pointer trong `config.yaml`

```yaml
# fastbusiness_mcp/config.yaml
chrome_debug_config: "chrome_debug.yaml"
```

`get_config()` đã load yaml chính → `config_loader` resolve path relative `fastbusiness_mcp/`.

### Option B — Env only

`CHROME_DEBUG_CONFIG_PATH=E:\...\chrome_debug.yaml`

### Lazy load

- Load yaml lần đầu gọi `chrome_debug` hoặc lúc `register_chrome_tools` — không block startup static tools.

---

## 5. Dependencies

### `requirements.txt`

```
playwright>=1.40.0
```

Optional install note trong README: dev cần browser debug không cần `playwright install chromium` nếu chỉ attach CDP.

### Import guard

```python
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
```

Tool trả: *"Thiếu playwright. pip install playwright"*

---

## 6. PyInstaller / `dist` (phase sau)

- MVP dev: **source + venv** only
- Bundle exe: thêm `playwright` vào hiddenimports khi cần — **không** block Phase 1
- `chrome_debug.yaml` copy vào `_internal` giống `config.yaml` (pattern [config_paths.py](../../fastbusiness_mcp/config_paths.py))

---

## 7. Logging

- Logger name: `fastbusiness_mcp.chrome_debug.session` (v.v.)
- **Không** log full snapshot/response body ra stdout (stdio MCP)
- Log level INFO: connect/disconnect, tab count

---

## 8. Error messages (Agent-friendly)

| Tình huống | Message |
|------------|---------|
| CDP không bật | Hướng dẫn shortcut Windows + profile riêng |
| Không tab | "Mở ít nhất 1 tab trong Chrome debug" |
| Tab keyword miss | Liệt kê title \| url |
| Ref hết hạn | "Gọi lại chrome_debug(type=2)" |
| playwright missing | pip install |

Reuse [agent_messages.py](../../fastbusiness_mcp/agent_messages.py) nếu thêm template constant.

---

## 9. README root update (phase implement)

Thêm section vào [README.md](../../README.md):

- MCP Tools: 5 → 5 + 7 chrome (hoặc "5 + chrome optional")
- Link `docs/doc_chrome_debug/README.md`
- Note: Chrome debug chỉ khi cần runtime

---

## 10. Liên kết

- Architecture: [02_architecture_layers.md](02_architecture_layers.md)
- Dev test: [08_dev_test_guide.md](08_dev_test_guide.md)
- Checklist: [09_implementation_checklist.md](09_implementation_checklist.md)
