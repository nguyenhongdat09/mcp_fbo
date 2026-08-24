# 01 — Overview: Chrome CDP Debug MCP

## 1. Bối cảnh

FastBusiness MCP hiện tại mạnh ở **phân tích tĩnh** (design-time):

- Đọc controller XML (`read_local_file`, `get_xml_entities`)
- Tra cứu SQL / proc / schema (`query_database`)
- Đồ thị quan hệ controller (`query_radar`)
- Lịch sử yêu cầu (`search_qlyc`)

Các tool này trả lời: **“Code / SQL / cấu trúc nói gì?”**

Chúng **không** trả lời được khi:

- JavaScript runtime lỗi trên browser (console đỏ)
- API trả 401 / 403 / 500 khi Save / Retrieve
- UI không phản ánh đúng sau khi sửa `onChange$*` (readonly, disabled, grid ẩn)
- Lỗi chỉ xuất hiện khi user thao tác thật trên form FBO

→ Cần lớp **runtime verification** gắn vào Chrome đang chạy FBO.

---

## 2. Mục tiêu

Xây dựng **một** MCP tool `chrome_debug` (tham số `type` 1–4) cho phép Cursor Agent:

1. **Attach** Chrome thật qua CDP (`http://localhost:9222`)
2. **Liệt kê tab** và chọn tab theo URL/title (`tab_keyword`)
3. **Snapshot** phần tử tương tác (button, input, role=button) — **không** dump raw HTML
4. **Bắt** lỗi JavaScript console và request HTTP 4xx/5xx (kèm payload/response cắt ngắn)
5. **Tương tác** (fill, click, execute_js) để agent tự verify tính năng sau khi sửa code
6. **Tiết kiệm token** — output gọn, giới hạn node/char, rule agent chặt

Tích hợp vào **cùng** server `fastbusiness-mcp`, không tách project MCP riêng.

---

## 3. CDP là gì? (tóm tắt)

**CDP (Chrome DevTools Protocol)** là giao thức nội bộ mà DevTools (F12) dùng để điều khiển Chrome: DOM, console, network, thực thi JS.

MCP dùng **Playwright** `connect_over_cdp()` làm driver — Agent không gọi CDP trực tiếp.

**Lưu ý quan trọng:** Chrome bình thường **không** mở cổng CDP ra ngoài. Phải khởi động Chrome với `--remote-debugging-port=9222` (và nên dùng `--user-data-dir` profile riêng). Chi tiết: [03_config.md](03_config.md).

---

## 4. Phạm vi (In scope)

| Hạng mục | Mô tả |
|----------|--------|
| CDP attach | Chrome debug port 9222, lazy connect |
| Tab routing | `tab_keyword` match URL/title; default tab cuối |
| Snapshot | Interactive elements, ref `e0`, `e1`… |
| Console buffer | Ring buffer per tab, tích lũy từ lúc hook |
| Network errors | 4xx/5xx + requestfailed, body truncated |
| Form actions | fill theo `name`/`id`, click text/ref/selector |
| execute_js | Escape hatch cho grid FBO / API `f`/`g` |
| Config riêng | `chrome_debug.yaml` |
| Agent dynamic | Không kịch bản Playwright `.spec` cố định |

---

## 5. Non-goals (MVP)

| Hạng mục | Lý do |
|----------|--------|
| Attach Chrome **không** debug port | Chrome chặn vì bảo mật |
| Headless CI regression suite | Phase sau; MVP phục vụ Cursor agent |
| Chrome Extension bridge | Phức tạp, không cần cho MVP |
| Dump full HTML / screenshot mặc định | Tốn token, không cần cho agent |
| Thay thế 5 tool static | Chrome bổ sung, không thay thế |

---

## 6. Khi nào cần Chrome debug?

| Việc làm | Cần Chrome debug? |
|----------|-------------------|
| Sửa XML controller, proc, SQL | **Không** |
| Tra graph Kuzu, entity | **Không** |
| User báo Save fail / grid trống / console đỏ | **Có** |
| Sau sửa JS, agent tự verify readonly/click | **Có** (nếu user bật Chrome debug) |
| Chỉ accept diff, user tự test tay | **Không** (0 token Chrome) |

**Ước lượng:** ~90% công việc FBO không cần Chrome; ~10% debug runtime.

---

## 7. Agent dynamic vs kịch bản Playwright cố định

| Cách | Ai viết bước? | Dùng khi |
|------|----------------|----------|
| **MCP + Agent (hướng này)** | Agent quyết từng bước mỗi lần chat | Feature mới, debug ticket, verify 1–2 case |
| **Playwright script cố định** | Dev viết `test_*.py` | CI nightly, regression 50 case |

Playwright trong MCP là **thư viện driver**, không phải bộ test check-in sẵn.

---

## 8. Luồng tổng quát

```
User yêu cầu / báo lỗi web
        │
        ▼
┌─ Static MCP ─────────────────────┐
│ read_local_file(3), query_radar, │
│ query_database                   │
└──────────────┬───────────────────┘
               │ cần verify runtime?
               ▼
┌─ Chrome MCP ─────────────────────┐
│ chrome_debug(type=1) status/tabs │
│ chrome_debug(type=2) inspect     │
│ chrome_debug(type=3) interact    │
│ chrome_debug(type=4) execute_js  │
└──────────────────────────────────┘
```

---

## 9. Tài liệu tiếp theo

- Kiến trúc module: [02_architecture_layers.md](02_architecture_layers.md)
- Config: [03_config.md](03_config.md)
- Tool API: [04_tool_api.md](04_tool_api.md)
