# Phân Hệ 04-A: Giám Sát Thay Đổi File Thời Gian Thực (`xml_codegraph/service/`)

Thư mục `service` quản lý dịch vụ nền giám sát các tệp tin cấu hình XML của FastBusiness nhằm đảm bảo đồ thị Kùzu Graph DB luôn phản ánh đúng trạng thái thực tế của dự án.

## 🕒 1. Dịch Vụ Theo Dõi File (`watcher.py`)

File này cung cấp lớp `GraphUpdateHandler` kế thừa từ `watchdog.events.FileSystemEventHandler` và hàm chạy chính `start_watcher`.

### A. Cơ Chế Lọc Sự Kiện (Event Filtering)
Hệ thống tránh cập nhật vô tội vạ bằng cách lọc sự kiện qua 3 tầng bảo vệ:
1. **Lọc Thư Mục**: Bỏ qua các sự kiện thay đổi xảy ra trên thư mục (`event.is_directory == True`).
2. **Lọc Phạm Vi**: Gọi `is_graph_scope_file` để kiểm tra tệp tin có thuộc 6 thư mục quy định (`Dir`, `Grid`, `Filter`, `Report`, `Lookup`, `Templates/Upload`) hay không.
3. **Lọc Định Dạng**: Chỉ chấp nhận tệp tin có đuôi mở rộng `.xml`, `.ent` (DTD entity) hoặc `.txt`.
4. **Tránh Vòng Lặp Vô Hạn**: Bỏ qua các thay đổi xảy ra bên trong thư mục `.fbograph/kuzu` (chính là nơi Graph DB ghi dữ liệu).

### B. Cơ Chế Chống Rung (Debounce Mechanism)
* **Vấn Đề**: Khi người dùng hoặc một trình soạn thảo lưu file (Save), hệ điều hành có thể phát ra liên tiếp nhiều sự kiện thay đổi (`Modified`) trong vài mili giây. Nếu hệ thống lập tức parser file và cập nhật DB cho từng sự kiện sẽ gây lãng phí CPU và gây nghẽn đĩa.
* **Giải Pháp**: Thuật toán Debounce bằng biến `last_triggered`:
  ```python
  now = time.time()
  if now - self.last_triggered < self.debounce_seconds: # debounce_seconds = 1.0 giây
      return
  self.last_triggered = now
  ```
  Nếu có sự kiện trùng lắp trong vòng 1 giây, watcher sẽ bỏ qua một cách an toàn.

### C. Cập Nhật Gia Tăng (Incremental Update)
* Khi sự kiện hợp lệ đi qua bộ lọc, watcher gọi hàm `incremental_update_file` trong [graph_builder.py](file:///e:/mcp_fbo/xml_codegraph/builder/graph_builder.py).
* Hàm này sẽ:
  1. Parse duy nhất tệp tin vừa thay đổi thành một đối tượng `GraphNode` mới.
  2. Xóa Node cũ có cùng `node_id` và các Cạnh (`Rel`) liên quan của Node đó trong Kùzu DB.
  3. Ghi Node mới cùng các Cạnh mới được phân tích vào Kùzu DB.
  4. Kích hoạt hàm gọi ngược `on_node_updated` để cập nhật RAM Cache của MCP Server ngay lập tức.
