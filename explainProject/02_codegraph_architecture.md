# Phân Hệ 02: Kiến Trúc CodeGraph (`xml_codegraph/`)

Phân hệ CodeGraph được xây dựng với mục tiêu phân tích tĩnh toàn bộ mã nguồn của dự án FastBusiness để cung cấp cái nhìn toàn diện về mối quan hệ giữa các tệp cấu hình XML, SQL động, và logic Client Javascript.

## 💾 Công nghệ Lưu trữ: Kùzu Graph DB
Thay vì sử dụng Neo4j (đòi hỏi cài đặt dịch vụ độc lập khá nặng), dự án sử dụng **Kùzu Graph DB** (`kuzu`) — một Graph Database dạng nhúng cực kỳ mạnh mẽ viết bằng C++ và có binding Python, tương tự như SQLite nhưng tối ưu cho cấu trúc đồ thị.
* Dữ liệu đồ thị được lưu trữ tại `.fbograph/kuzu/` ngay tại thư mục làm việc của dự án FBO.

---

## 🏗️ Quy Trình Xây Dựng Đồ Thị (Graph Building)

Được quản lý bởi lớp `GraphBuilder` trong [graph_builder.py](file:///e:/mcp_fbo/xml_codegraph/builder/graph_builder.py):

### Bước 1: Quét file trên đĩa
* Sử dụng cấu hình từ `ProjectPathHelper` để tìm thư mục `App_Data/Controllers/`.
* Quét tất cả các tệp có đuôi `.xml`, `.ent` (DTD Entity), `.txt`, `.f` nằm trong 6 thư mục quy định: `Dir`, `Grid`, `Filter`, `Report`, `Lookup`, `Form`.
* Loại bỏ trùng lặp: Nếu tồn tại cả tệp nguồn `.xml` và tệp đã biên dịch/mã hóa `.f` cùng tên, chương trình sẽ chỉ phân tích tệp `.xml`.

### Bước 2: Phân tích tăng dần (Incremental Cache)
* Để tăng tốc độ xây dựng đồ thị đối với các dự án lớn có hàng nghìn file XML:
  * Đọc thời gian sửa đổi gần nhất (`mtime`) và kích thước (`file_size`) của từng file.
  * So sánh với các thuộc tính tương ứng đã được lưu trong đồ thị Kùzu cũ.
  * Chỉ phân tích lại các tệp mới thêm hoặc mới bị sửa đổi. Các tệp khác được giữ nguyên thông tin Node cũ.

### Bước 3: Phân tích tệp (Parser Execution)
* Chạy bộ phân tích XML để lấy cấu trúc dữ liệu, định nghĩa thẻ chính (dir/grid/filter...), tên bảng tương ứng (`table="d31$000000"`).
* Sử dụng ThreadPoolExecutor để phân tích đa luồng, tối ưu hóa tốc độ xử lý CPU đa nhân.

### Bước 4: Thiết lập các mối quan hệ (Edges Generation)
* Dựa trên các luật liên kết được định nghĩa sẵn, tạo ra các cạnh nối giữa các node và lưu trữ xuống Kùzu DB.
