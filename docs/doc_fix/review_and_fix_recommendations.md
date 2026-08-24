# Góp ý & Đề xuất hoàn thiện Thiết kế Chrome CDP Debug MCP

> **Mục đích:** Tài liệu tổng hợp các nhận xét, đánh giá chuyên sâu và đề xuất khắc phục (fix/improvements) cho bộ tài liệu thiết kế tại `docs/doc_chrome_debug/` trước và trong quá trình triển khai mã nguồn.

---

## 1. Đánh giá chung (Overall Assessment)

Bộ tài liệu thiết kế tại `docs/doc_chrome_debug/` được xây dựng **rất bài bản, chi tiết và có tầm nhìn thực tế cao**:
- **Đúng trọng tâm nghiệp vụ:** Bổ sung lớp runtime verification (console, HTTP error, DOM tương tác) để hoàn thiện mắt xích còn thiếu của 5 tool phân tích tĩnh hiện có.
- **Kiến trúc rõ ràng:** Tách package `fastbusiness_mcp/chrome_debug/`, cơ chế Lazy Connect, và Import Guard cho `playwright` giúp đảm bảo tính tương thích ngược và an toàn cho hệ thống.
- **Tiết kiệm Token tối ưu:** Không dump raw HTML, dùng snapshot cấu trúc gọn (`ref="e0"`, label rút gọn, ring buffer console/network).

Dưới đây là **7 điểm kỹ thuật then chốt** cần Cursor Agent lưu ý và tinh chỉnh khi triển khai code thực tế.

---

## 2. Các điểm cần lưu ý & Đề xuất cải tiến (Key Technical Considerations)

### ⚠️ Điểm 1: Xử lý Event Loop & Threading giữa MCPServer và `playwright.sync_api`

* **Vấn đề:** 
  `mcp.server.MCPServer` (FastMCP pattern) có thể chạy trên một async event loop ngầm định (`asyncio`/`anyio`). Khi gọi `playwright.sync_api` từ một luồng đang có running event loop, Playwright sẽ quăng exception:
  `PlaywrightError: It looks like you are using Playwright Sync API inside the asyncio loop.`
* **Giải pháp đề xuất:**
  1. Trong `session.py`, đảm bảo Playwright sync được khởi tạo và thực thi trong một dedicated worker thread riêng (nếu cần), HOẶC:
  2. Bọc Playwright call qua `asyncio.to_thread(...)` hoặc `concurrent.futures.ThreadPoolExecutor(max_workers=1)`.
  3. Quản lý singleton session an toàn qua `threading.Lock`.

---

### ⚠️ Điểm 2: Vấn đề "Miss Event" của Console & Network Buffer

* **Vấn đề:**
  Trong thiết kế `02_architecture_layers.md`, buffer console/network được bắt qua event listener (`page.on("console")`, `page.on("response")`).
  Tuy nhiên, listener **chỉ bắt đầu ghi nhận sau khi session attach thành công vào tab**. Nếu người dùng gặp lỗi JS / 500 trước khi Agent gọi tool MCP, buffer sẽ **rỗng (0 log)**.
* **Giải pháp đề xuất:**
  1. **CDP Log Fetching:** Xem xét kích hoạt `Runtime.enable` / `Log.enable` qua CDP session để kéo lại các console entry đã xuất hiện trước đó trong session DevTools.
  2. **Rule cho Agent:** Nếu `chrome_debug(type=2)` trả lỗi rỗng nhưng user vẫn báo lỗi → gợi ý reload tab / reproduce thao tác.

---

### ⚠️ Điểm 3: Tương thích với DOM ExtJS & Trigger Sự kiện FBO

* **Vấn đề:**
  Các trường nhập liệu trên FastBusiness (FBO) thường được quản lý bởi ExtJS hoặc custom script:
  - Giá trị thật có thể nằm ở hidden input hoặc custom widget.
  - Event `onChange$Voucher$...` thường chỉ kích hoạt khi có sự kiện `blur`, `change`, hoặc `keydown` (Enter/Tab).
  - Sử dụng `.fill(value)` đơn thuần của Playwright đôi khi không kích hoạt được logic tính toán phụ thuộc trong FBO.
* **Giải pháp đề xuất:**
  1. Trong `actions.py` (`fill_fields`), sau khi `.fill()`, nên dispatch thêm event `blur` hoặc `change` (`el.dispatch_event('blur')`, `el.press('Tab')`).
  2. Cung cấp fallback thông minh: Nếu form có đối tượng FBO controller toàn cục (`f` / `g`), cho phép tùy chọn set trực tiếp qua `f.setItemValue(fieldName, value)` trong trường hợp selector DOM bị che khuất/không kích hoạt được handler.

---

### ⚠️ Điểm 4: Quản lý Vòng đời Kết nối (Connection Lifecycle & Auto-Reconnect)

* **Vấn đề:**
  Người dùng có thể đóng tab, chuyển trang (navigate), mở lại Chrome hoặc tắt cổng debug giữa các lần gọi MCP tool. Khi đó instance `page` hoặc `browser` cũ sẽ trở thành stale/dead object (`Target closed`).
* **Giải pháp đề xuất:**
  1. Trong `session.py`, hàm `resolve_page()` cần bọc trong khối kiểm tra trạng thái sống của kết nối:
     ```python
     if not browser or not browser.is_connected():
         # Tự động cleanup và re-connect
     ```
  2. Mọi thao tác trên `page` cần bắt `playwright.errors.TargetClosedError` để tự động refresh lại danh sách pages và thông báo lỗi rõ ràng bằng tiếng Việt thân thiện với Agent.

---

### ⚠️ Điểm 5: Xử lý Đa khung (Iframe & Modal Dialogs trong FBO)

* **Vấn đề:**
  Hệ thống FastBusiness thường mở các form danh mục (`Dir`), chứng từ popup, hoặc màn hình tra cứu lookup trong các `<iframe>` hoặc floating dialogs tách biệt với Main Frame.
* **Giải pháp đề xuất:**
  1. Trong `snapshot.py`, tiếp tục duy trì cơ chế quét đệ quy qua `page.frames` như đã mô tả trong tài liệu.
  2. Trong **`chrome_debug(type=3)`**, truyền `frame_index` từ snapshot `type=2`.

---

### ⚠️ Điểm 6: Tránh Side-Effects dữ liệu (Data Mutation Safety)

* **Vấn đề:**
  Khi Agent tự động hóa UI (`chrome_debug type=3`), tránh click nút nhạy cảm: "Xóa", "Hủy", "Lưu".
* **Giải pháp đề xuất:**
  1. Thêm cảnh báo hoặc cơ chế confirmation trong Agent Workflow (`.cursorrules` / `05_agent_workflow.md`) đối với các action có nhãn nguy hiểm (`Xóa`, `Hủy`, `Delete`, `Drop`).
  2. Ưu tiên hướng dẫn Agent chỉ thực hiện các action verify (nhập thử, kiểm tra readonly, kiểm tra disable) trên form tạm/chế độ New, tránh submit dữ liệu thật nếu chưa có yêu cầu từ user.

---

### ⚠️ Điểm 7: Chiến lược Mocking cho Unit Test

* **Vấn đề:**
  Trong môi trường CI hoặc máy dev chưa bật Chrome debug (`localhost:9222`), bộ test MCP không được phép crash hoặc bị block.
* **Giải pháp đề xuất:**
  1. Trong `scripts/test_chrome_debug_smoke.py`, tách rõ:
     - **Offline/Unit Test:** Test `config_loader`, `constants`, `buffers`, và mock CDP response (không cần Chrome thật).
     - **Integration/E2E Test:** Chỉ chạy khi phát hiện cổng 9222 đang mở (`ping_cdp() == True`).

---

## 3. Checklist đề xuất khi triển khai Code (Implementation Action Plan)

```
[ ] BƯỚC 1: Xây dựng nền tảng (Base)
    ├── fastbusiness_mcp/chrome_debug/constants.py
    ├── fastbusiness_mcp/chrome_debug/config_loader.py
    └── fastbusiness_mcp/chrome_debug.yaml

[ ] BƯỚC 2: Quản lý Session & Buffer (Core Session)
    ├── fastbusiness_mcp/chrome_debug/buffers.py (Ring buffer)
    └── fastbusiness_mcp/chrome_debug/session.py (CDP Ping + Safe Connect + Reconnect)

[ ] BƯỚC 3: Snapshot & Service MVP (Phase 1)
    ├── fastbusiness_mcp/chrome_debug/snapshot.py (Interactive JS Scan)
    ├── fastbusiness_mcp/chrome_debug/service.py (Orchestrator)
    └── tools.py — register **chrome_debug** (dispatch type 1–4)
    └── Tích hợp vào fastbusiness_mcp/mcp_app.py

[ ] BƯỚC 4: Action Tools (Phase 2)
    ├── fastbusiness_mcp/chrome_debug/actions.py (click, fill + event blur/tab)
    └── Bổ sung chrome_debug type 3–4 vào tools.py
```

---

## 4. Cập nhật spec tool (2026-08)

Theo [04_tool_api.md](../doc_chrome_debug/04_tool_api.md): **một tool** `chrome_debug(type=1|2|3|4)` thay toàn bộ `chrome_*` cũ. Điểm 3 (fill+blur) và 5 (`frame_index`) → **type=3**.

---

*Tài liệu này được tạo để Cursor Agent tham khảo trực tiếp khi lập kế hoạch và sinh mã nguồn cho tính năng Chrome CDP Debug.*
