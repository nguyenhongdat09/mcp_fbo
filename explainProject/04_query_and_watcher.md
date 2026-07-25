# Phân Hệ 04: Bộ Truy Vấn Đồng Nghĩa & File Watcher Động

Hệ thống cung cấp cơ chế tìm kiếm thông minh thông qua từ đồng nghĩa (Synonyms) tiếng Việt và cơ chế tự động đồng bộ hóa đồ thị theo thời gian thực (Watcher).

## 🔍 Tìm Kiếm Đồng Nghĩa (Synonyms Engine)

Được cấu hình trong tệp [xml_codegraph/query/engine.py](file:///e:/mcp_fbo/xml_codegraph/query/engine.py):

* **Vấn Đề**: Nhà phát triển/AI Agent thường tìm kiếm bằng ngôn ngữ tự nhiên (ví dụ: "giá bán", "diễn giải"), nhưng tên trường thực tế trong CSDL FBO lại là viết tắt tiếng Việt không dấu hoặc tiếng Anh (ví dụ: `gia2`, `gia_nt2`, `dien_giai`, `description`).
* **Giải Pháp**: Engine duy trì bản đồ đồng nghĩa `FBO_SYNONYMS` để tự động mở rộng từ khóa tìm kiếm:
  ```python
  FBO_SYNONYMS = {
      "gia ban": ["gia2", "gia_nt2", "gia_ban", "gia21", "price", "t_tien2"],
      "khach hang": ["ma_kh", "ten_kh", "customer"],
      "dien giai": ["dien_giai", "description", "memo"],
  }
  ```
* **Cơ Chế Khử Dấu**: Hệ thống sử dụng thuật toán chuẩn hóa Unicode để loại bỏ dấu tiếng Việt khỏi từ khóa đầu vào trước khi đối chiếu bản đồ từ điển đồng nghĩa (ví dụ: "Diễn giải" -> "dien giai" -> khớp với `dien_giai` và `description`).

---

## 🕒 Giám Sát Thay Đổi File (`watcher.py`)

Nằm tại [xml_codegraph/service/watcher.py](file:///e:/mcp_fbo/xml_codegraph/service/watcher.py):

* **Cơ chế hoạt động**:
  - Khi MCP Server khởi động, nó tạo một luồng riêng chạy ngầm (Daemon Thread) khởi tạo thư viện `watchdog` để quan sát toàn bộ thư mục `App_Data/Controllers/`.
  - Khi phát hiện sự kiện file bị sửa đổi (`Modified`), thêm mới (`Created`), hoặc bị xóa (`Deleted`):
    - Đọc file bị ảnh hưởng và gọi bộ parser riêng để tạo lại dữ liệu Node.
    - Thực thi truy vấn cập nhật nóng (Upsert / Delete) vào cơ sở dữ liệu Kùzu DB.
    - Cập nhật Ram Cache của MCP Server để các câu truy vấn tiếp theo nhận ngay dữ liệu mới nhất mà không cần tải lại toàn bộ đồ thị từ đầu.
* **Tự Động Đồng Bộ Dự Phòng**:
  - Nếu watcher bị tắt hoặc lỗi, hệ thống có cơ chế kiểm tra thời gian thay đổi file định kỳ (5 phút một lần). Khi có yêu cầu truy vấn mới từ client, hệ thống sẽ kiểm tra xem có tệp tin nào bị lệch pha so với Kùzu DB hay không và tiến hành đồng bộ hóa ngay lập tức.
