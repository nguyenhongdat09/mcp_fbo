# FastBusiness FBO MCP & XML CodeGraph - Hướng Dẫn Kiến Trúc Tổng Quan

Chào mừng bạn đến với tài liệu hướng dẫn kỹ thuật chi tiết của dự án **`mcp_fbo`**. Hệ thống được thiết kế để hỗ trợ nhà phát triển (hoặc AI Agent) đọc hiểu, tìm kiếm, sửa đổi và kiểm tra các màn hình khai báo dạng XML (Dir, Grid, Filter, Report, Lookup) và thao tác cơ sở dữ liệu trên hệ thống FastBusiness ERP/FBO.

## 📌 Các Thành Phần Tài Liệu Khác
Chúng tôi đã chia nhỏ tài liệu giải thích dự án thành các tệp tin chuyên đề riêng biệt nằm trong thư mục `explainProject/` để bạn dễ dàng theo dõi:
1. [01_mcp_server.md](file:///e:/mcp_fbo/explainProject/01_mcp_server.md): Giải thích phân hệ **FastBusiness MCP Server** tác vụ trực tiếp với CSDL và XML field generator.
2. [02_codegraph_architecture.md](file:///e:/mcp_fbo/explainProject/02_codegraph_architecture.md): Cấu trúc bộ phân tích tĩnh và cơ chế xây dựng đồ thị Kùzu Graph DB (`xml_codegraph/`).
3. [03_parsers_and_rules.md](file:///e:/mcp_fbo/explainProject/03_parsers_and_rules.md): Chi tiết cách phân tích XML (có DTD & mã hóa font 1258), SQL, JS và các quy tắc sinh Cạnh (Relationship Rules).
4. [04_query_and_watcher.md](file:///e:/mcp_fbo/explainProject/04_query_and_watcher.md): Cơ chế tìm kiếm đồng nghĩa (Synonyms) và cơ chế tự động đồng bộ thay đổi file (Watcher).

---

## 🛠️ Luồng Khởi Chạy & Deploy MCP

Dự án có thể chạy trực tiếp bằng python hoặc đóng gói thành file `.exe` độc lập.

### 1. File mcp_server.py (FboCodeGraph MCP)
Được cấu hình làm MCP Server để LLM Client (như Cursor/VS Code) kết nối.
* **Đường dẫn**: `mcp_server.py`
* **Cách hoạt động**:
  - Nhận các câu lệnh gọi Tool từ Client.
  - Phân tích `reference_file` được gửi kèm để tìm root của dự án Client đang thao tác qua `ProjectPathHelper`.
  - Khởi tạo kết nối Kùzu DB nhúng ở thư mục dự án đó (`.fbograph/kuzu`).
  - Nếu Kùzu DB chưa tồn tại hoặc bị lỗi, tự động kích hoạt `GraphBuilder` để tạo mới đồ thị toàn bộ các controller trước khi trả lời.
  - Khởi chạy một Background Thread để chạy file `watcher.py` nhằm bắt các sự thay đổi của file XML trên máy khách.

### 2. File fastbusiness_mcp/server.py (FastBusiness MCP)
Tập trung vào cơ sở dữ liệu và hỗ trợ công việc viết code.
* **Đường dẫn**: `fastbusiness_mcp/server.py`
* **Cách hoạt động**:
  - Tích hợp `query_database` giúp thực hiện SQL từ xa mà không cần cài SQL Management Studio (tự động dò Web.config).
  - Tích hợp `code_assistant_tool.py` và `xml_snippet_tool.py` hỗ trợ sinh nhanh cấu trúc XML clientScript/onChange, tạo nhanh cột hiển thị hoặc lưu trữ.

---

## 🔄 Quy trình Đồng bộ hóa Tệp

```
[XML File Thay Đổi] ──► [Watcher Thread] ──► [Cập nhật Node vào Kùzu DB]
                                                   │
[LLM Client] ◄─────── [Đọc Đồ Thị Kùzu] ────────────┘
```

Tất cả các tệp cấu hình đồ thị đều nằm ẩn trong thư mục `.fbograph/` của mỗi dự án FastBusiness, do đó không gây ô nhiễm mã nguồn chính.
