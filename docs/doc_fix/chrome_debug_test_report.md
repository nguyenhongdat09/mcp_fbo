# Chrome CDP Debug — Báo cáo test & hướng dẫn sửa (Gemini)

> **Ngày test:** 2026-08-23  
> **Người test:** Cursor Agent (review code Gemini trong `fastbusiness_mcp/chrome_debug/`)  
> **Spec tham chiếu:** `docs/doc_chrome_debug/04_tool_api.md`, `02_architecture_layers.md` §8–9  
> **Góp ý trước đó:** `docs/doc_fix/review_and_fix_recommendations.md` §2.1

---

## 1. Tóm tắt

| Hạng mục | Kết quả |
|----------|---------|
| Smoke test offline (`scripts/test_chrome_debug_smoke.py`) | **PASS** |
| Đăng ký MCP tool `chrome_debug` | **PASS** — có trong danh sách tool |
| `type=1` khi Chrome chưa bật | **PASS** — `available=false`, `hint` đầy đủ |
| Validation `type=3`, `type=4`, `type` invalid | **PASS** |
| `type=2/3/4` trong asyncio loop (mô phỏng MCP thật) | **FAIL** — lỗi Playwright Sync API |
| E2E với Chrome `:9222` | **Chưa test** — máy test không bật Chrome debug |

**Kết luận:** Code cấu trúc ổn, smoke test pass, nhưng **chưa sẵn sàng dùng trong Cursor MCP** cho `type≥2` vì lỗi event loop. Cần Gemini sửa trước khi agent gọi runtime.

---

## 2. Kết quả test đã chạy

### 2.1. Smoke test (PASS)

```powershell
E:\PythonProject\mcp_fbo\.venv\Scripts\python.exe E:\PythonProject\mcp_fbo\scripts\test_chrome_debug_smoke.py
```

Output: tất cả bước 1–4 PASS.

### 2.2. Import MCP server (PASS)

```powershell
E:\PythonProject\mcp_fbo\.venv\Scripts\python.exe -c "from fastbusiness_mcp.mcp_app import server; ..."
```

Tool list: `query_database`, `get_xml_entities`, `query_radar`, `read_local_file`, `search_qlyc`, **`chrome_debug`**.

### 2.3. Mô phỏng MCP async — type=2 (FAIL — P0)

`mcp_app.py` bọc `server.call_tool` bằng `async def _safe_call_tool` → MCP chạy trên **asyncio event loop**.

```python
import asyncio, sys
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.service import dispatch_chrome_debug

async def main():
    cfg = load_chrome_debug_config()
    dispatch_chrome_debug(cfg, type=2, tab_keyword="test")

asyncio.run(main())
```

**Lỗi:**

```
Error: It looks like you are using Playwright Sync API inside the asyncio loop.
Please use the Async API instead.
```

Stack: `service.handle_type_2_inspect` → `session.resolve_page` → `session.connect` → `sync_playwright().start()`.

### 2.4. type=2 khi CDP tắt, không asyncio (FAIL UX — P1)

Gọi trực tiếp `dispatch_chrome_debug(cfg, type=2)` (sync script):

```
RuntimeError: Lỗi khi kết nối Playwright tới http://localhost:9222: BrowserType.connect_over_cdp: connect ECONNREFUSED ...
```

Trong khi `type=1` trả JSON gọn với `hint` hướng dẫn mở Chrome debug. Agent gọi `type=2` trước khi bật Chrome sẽ nhận lỗi Playwright khó đọc (dù `tools.py` bọc `format_execution_error`).

---

## 3. Lỗi cần sửa — chi tiết cho Gemini

### P0 — Blocking: Sync Playwright trong asyncio loop

| | |
|---|---|
| **File** | `fastbusiness_mcp/chrome_debug/service.py`, có thể thêm `fastbusiness_mcp/chrome_debug/runtime.py` |
| **Triệu chứng** | `type=2`, `type=3`, `type=4` fail khi gọi từ Cursor MCP |
| **Nguyên nhân** | `session.connect()` gọi `sync_playwright()` trên thread đang có running asyncio loop |
| **Spec** | `02_architecture_layers.md` §8, `review_and_fix_recommendations.md` §2.1 |

**Đề xuất sửa (chọn 1, ưu tiên A):**

**A. ThreadPoolExecutor singleton (khuyến nghị — giữ sync_api):**

```python
# runtime.py (mới) hoặc đầu service.py
from concurrent.futures import ThreadPoolExecutor
import asyncio

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chrome_cdp")

def run_playwright_sync(fn, *args, **kwargs):
    try:
        asyncio.get_running_loop()
        in_async = True
    except RuntimeError:
        in_async = False
    if not in_async:
        return fn(*args, **kwargs)
    future = _EXECUTOR.submit(fn, *args, **kwargs)
    return future.result(timeout=120)
```

Bọc **toàn bộ** nhánh Playwright trong `dispatch_chrome_debug`:

- `handle_type_2_inspect`
- `handle_type_3_interact`
- `handle_type_4_execute`

Ví dụ:

```python
def dispatch_chrome_debug(...):
    ...
    elif type == 2:
        res = run_playwright_sync(
            handle_type_2_inspect, cfg, tab_keyword=tab_keyword, ...
        )
```

**B. Hoặc** chuyển sang `playwright.async_api` + `await` — thay đổi lớn hơn, không khuyến nghị trừ khi refactor toàn package.

**Test lại sau sửa:**

```python
asyncio.run(main())  # type=2 phải không còn lỗi Sync API
# (CDP tắt → trả hint hoặc RuntimeError có hint, không crash loop)
```

---

### P1 — `playwright` thiếu trong `requirements.txt`

| | |
|---|---|
| **File** | `requirements.txt` |
| **Triệu chứng** | Cài mới `.venv` → `type≥2` raise `Thiếu thư viện 'playwright'` |
| **Hiện trạng** | Package có trong `.venv` hiện tại nhưng **không** khai báo dependency |

**Sửa:**

```text
playwright>=1.40.0
```

Ghi chú trong `08_dev_test_guide.md`: `connect_over_cdp` **không** cần `playwright install chromium` (attach Chrome có sẵn), nhưng vẫn cần `pip install playwright`.

---

### P1 — type≥2 không pre-check CDP trước khi connect Playwright

| | |
|---|---|
| **File** | `fastbusiness_mcp/chrome_debug/service.py` — `handle_type_2_inspect`, `handle_type_3_interact`, `handle_type_4_execute` |
| **Triệu chứng** | CDP tắt → lỗi Playwright `ECONNREFUSED` thay vì JSON giống `type=1` |
| **Spec** | `04_tool_api.md` §4 — type 1 dùng ping HTTP; agent habit: type 1 trước, nhưng type 2 vẫn nên graceful |

**Đề xuất:**

```python
def _ensure_cdp_available(cfg: dict) -> None:
    available, _, _, hint = ping_cdp(cfg.get("cdp_url", DEFAULT_CDP_URL))
    if not available:
        raise RuntimeError(hint)  # hoặc return dict JSON { "available": false, "hint": ... }
```

Gọi đầu mỗi handler type 2/3/4 **trước** `session.connect()`.

Hoặc trả JSON structured (không raise):

```json
{
  "type": 2,
  "available": false,
  "hint": "... shortcut Chrome debug ..."
}
```

---

### P1 — Thiếu auto-reconnect / stale browser cleanup

| | |
|---|---|
| **File** | `fastbusiness_mcp/chrome_debug/session.py` — `resolve_page()`, `connect()` |
| **Triệu chứng** | Đóng tab / restart Chrome giữa 2 lần gọi → `Target closed` |
| **Spec** | `02_architecture_layers.md` §9, `review_and_fix_recommendations.md` §2.4 |

**Đề xuất:**

```python
from playwright.sync_api import Error as PlaywrightError

def resolve_page(...):
    try:
        browser = self.connect(cdp_url)
        ...
        return matched_page
    except PlaywrightError as e:
        if "Target closed" in str(e) or "Browser has been closed" in str(e):
            self.disconnect()
            browser = self.connect(cdp_url)
            # retry resolve once
        raise
```

Bắt lỗi khi `page.title()`, `frame.evaluate()` trong snapshot/actions tương tự.

---

### P2 — Tham số `mode` (type=2) chưa được implement

| | |
|---|---|
| **File** | `service.py` nhận `mode`; `snapshot.py` `build_page_snapshot()` **bỏ qua** |
| **Config** | `chrome_debug.yaml` có `snapshot.mode: interactive \| fields_only` |
| **Spec** | `04_tool_api.md` §5, `chrome_debug.yaml` line 16 |

**Đề xuất:** Truyền `mode` vào `build_page_snapshot(page, mode=mode, ...)`. Khi `fields_only`: chỉ lấy `input, select, textarea` (bỏ button/link) — giảm token cho agent.

---

### P2 — `actions.py`: pattern `locator(...).first` + `count()`

| | |
|---|---|
| **File** | `fastbusiness_mcp/chrome_debug/actions.py` — `fill_fields`, `click_target` |
| **Vấn đề** | Gọi `.first` rồi `.count()` — anti-pattern Playwright; có thể luôn 0/1 không ổn định |

**Sửa gợi ý:**

```python
locator = frame.locator(sel)
if locator.count() > 0:
    target = locator.first
    ...
```

Áp dụng cho mọi nhánh fill/click/ref.

---

### P2 — `execute_page_script` truncate result sai logic

| | |
|---|---|
| **File** | `fastbusiness_mcp/chrome_debug/actions.py` ~line 137–142 |

**Hiện tại:** Cắt `res_json` rồi `json.loads(res_json)` → JSON invalid → fallback string lẫn lộn.

**Sửa:**

```python
if len(res_json) > max_result_chars:
    return {
        "ok": True,
        "result": res_json[:max_result_chars],
        "truncated": True,
    }
return {"ok": True, "result": res}
```

---

### P2 — Smoke test chưa cover MCP thật

| | |
|---|---|
| **File** | `scripts/test_chrome_debug_smoke.py` |

**Bổ sung:**

1. Test `asyncio.run(dispatch type=2)` — expect pass sau fix P0.
2. Test `type=2` khi CDP off — expect hint (sau fix P1).
3. (Optional) Skip E2E nếu `ping_cdp()` false.

---

## 4. Điểm đã OK — không cần sửa

| Hạng mục | Ghi chú |
|----------|---------|
| Cấu trúc package 9 file | Khớp `02_architecture_layers.md` |
| Tool duy nhất `chrome_debug` type 1–4 | Khớp `04_tool_api.md` |
| `type=1` ping HTTP `/json/version` + `/json/list` | Không cần Playwright |
| Import guard Playwright | `session.py` — OK |
| Ring buffer console/network | `buffers.py` — OK |
| `errors_note` khi buffer rỗng | `service.py` handle_type_2 — OK |
| Snapshot gắn `data-cdp-ref` e0.. | `snapshot.py` — OK |
| Fill dispatch `change` + `blur` | `actions.py` — đúng hướng FBO |
| `mcp_app.py` try/except register | Static tools không bị ảnh hưởng nếu chrome lỗi import |
| Validation tiếng Việt type 3/4 | OK |

---

## 5. Checklist sửa cho Gemini (thứ tự ưu tiên)

- [ ] **P0** — `run_playwright_sync` + ThreadPoolExecutor; bọc type 2/3/4
- [ ] **P1** — Thêm `playwright>=1.40.0` vào `requirements.txt`
- [ ] **P1** — Pre-check `ping_cdp()` trước connect cho type 2/3/4
- [ ] **P1** — Auto-reconnect / `disconnect()` khi Target closed
- [ ] **P2** — Implement `mode=fields_only` trong snapshot
- [ ] **P2** — Sửa locator count pattern trong `actions.py`
- [ ] **P2** — Sửa truncate logic `execute_page_script`
- [ ] **P2** — Mở rộng smoke test (asyncio + CDP off)

---

## 6. Test lại sau khi Gemini sửa

### Bước 1 — Offline (không cần Chrome)

```powershell
cd E:\PythonProject\mcp_fbo
.venv\Scripts\python.exe scripts\test_chrome_debug_smoke.py
.venv\Scripts\python.exe -c "import asyncio; ... dispatch type=2 trong asyncio ..."
```

Kỳ vọng: không còn lỗi *Sync API inside asyncio loop*.

### Bước 2 — CDP tắt

```powershell
.venv\Scripts\python.exe -c "dispatch_chrome_debug(..., type=2)"
```

Kỳ vọng: message/hint giống type=1, không raw Playwright stack.

### Bước 3 — E2E (bật Chrome debug)

1. Mở Chrome: `--remote-debugging-port=9222 --user-data-dir=C:\chrome-fbo-debug`
2. Mở tab FBO (vd `SVTran`)
3. Trong Cursor Agent:
   - `chrome_debug(type=1)` → `available=true`, có tab
   - `chrome_debug(type=2, tab_keyword=SVTran)` → `frames`, `elements` có `ma_kh` / nút Lưu
   - `chrome_debug(type=3, fields_json={"ma_kh":"TEST"})` → UI đổi / `filled` không NOT FOUND
   - `chrome_debug(type=4, script="document.title")` → `ok: true`

### Bước 4 — Regression static MCP

Tắt Chrome → `query_database`, `read_local_file` vẫn hoạt động.

---

## 7. File liên quan

```
fastbusiness_mcp/chrome_debug/
├── session.py      ← P0, P1 reconnect
├── service.py      ← P0 wrapper, P1 pre-ping
├── actions.py      ← P2 locator, truncate
├── snapshot.py     ← P2 mode
├── tools.py          (OK)
├── config_loader.py  (OK)
├── buffers.py        (OK)
└── constants.py      (OK)

requirements.txt      ← P1 playwright
scripts/test_chrome_debug_smoke.py  ← P2 mở rộng
docs/doc_chrome_debug/04_tool_api.md  (spec)
docs/doc_fix/review_and_fix_recommendations.md  (§2.1–2.4)
```

---

---

## 8. Xác nhận sau khi Gemini sửa (2026-08-23 21:15)

| Hạng mục | Trạng thái |
|----------|------------|
| P0 — `runtime.py` + `run_playwright_sync` | ✅ PASS — asyncio test OK |
| P1 — `playwright>=1.40.0` trong `requirements.txt` | ✅ Đã thêm |
| P1 — `_check_cdp_ready()` type 2/3/4 | ✅ PASS — graceful fallback + hint |
| P1 — Auto-reconnect `session.resolve_page` | ✅ Code có retry sau `disconnect()` |
| P2 — `mode=fields_only` snapshot | ✅ Có trong `snapshot.py` |
| P2 — Locator count pattern | ✅ Sửa trong `actions.py` |
| P2 — Truncate `execute_page_script` | ✅ Trả `truncated: true` |
| P2 — Smoke test mở rộng | ✅ 6 bước PASS 100% |
| E2E Chrome `:9222` | ⏳ Chưa test — máy không bật Chrome debug |

**Lệnh verify:**

```powershell
E:\PythonProject\mcp_fbo\.venv\Scripts\python.exe E:\PythonProject\mcp_fbo\scripts\test_chrome_debug_smoke.py
```

**Bước tiếp theo (user):** Bật Chrome debug → test `type=2/3/4` trên tab FBO thật qua Cursor Agent.

---

*Báo cáo ban đầu dành cho Gemini sửa code. Mục §8 xác nhận re-test sau fix.*
