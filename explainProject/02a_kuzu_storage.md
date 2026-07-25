# Phân Hệ 02-A: Cơ Chế Lưu Trữ Kùzu Graph DB (`xml_codegraph/storage/`)

Thư mục `storage` chứa giao thức tương tác trực tiếp với cơ sở dữ liệu đồ thị nhúng **Kùzu DB** (viết bằng C++ mang lại tốc độ cực nhanh mà không cần daemon service như Neo4j).

## 🗃️ 1. Lớp Quản Lý Kùzu DB (`kuzu_index.py`)

Lớp `KuzuIndexStore` đóng vai trò là tầng truy cập dữ liệu (DAL) cho toàn bộ đồ thị CodeGraph.

### A. Khởi tạo và Cache Singleton Connection
* **Vấn Đề**: Do Kùzu DB là cơ sở dữ liệu nhúng, nó sẽ khóa tệp tin cơ sở dữ liệu khi có một kết nối mở. Nếu mở nhiều kết nối song song trong cùng một tiến trình Python, ứng dụng sẽ bị crash do tranh chấp khóa.
* **Giải Pháp**: Sử dụng biến cache toàn cục `_db_instances` để lưu lại thực thể `Database` và `Connection` dưới dạng Singleton theo đường dẫn file:
  ```python
  cache_key = str(self.db_path).replace("\\", "/").lower()
  if cache_key not in _db_instances:
      db = kuzu.Database(str(self.db_path), read_only=read_only)
      conn = kuzu.Connection(db)
      _db_instances[cache_key] = (db, conn)
  ```

### B. Giải pháp Đọc từ xa (Remote Read-only Cache)
* Khi `read_only=True` và đường dẫn cơ sở dữ liệu nằm trên một thư mục mạng UNC (bắt đầu bằng `\\` hoặc `//`), lớp này sẽ tự động hash đường dẫn thành một chuỗi duy nhất, tạo thư mục cache tạm thời trên ổ đĩa máy cục bộ (`tempfile.gettempdir()`), sao chép Kùzu DB và tệp WAL (Write-Ahead Log) về máy cục bộ để truy vấn đọc. 
* Cơ chế này giúp tránh tắc nghẽn băng thông mạng và khóa file từ xa.

### C. Khởi Tạo Cấu Trúc (Database Schema)
Bảng Node chính `XmlFile` và bảng quan hệ `Rel` được khởi tạo như sau:
* **Node Table `XmlFile`**: Lưu trữ các siêu dữ liệu của tệp tin XML như đường dẫn (`relative_path`), loại controller (`controller_type`), bảng CSDL tương ứng (`db_table`), văn bản mã nguồn SQL (`sql_text`), văn bản mã JavaScript (`js_text`), và mảng các trường dữ liệu (`fields_names STRING[]`).
* **Relationship Table `Rel`**: Cạnh đa hướng nối từ `XmlFile` đến `XmlFile` có thuộc tính phân loại cạnh `edge_type` và metadata bổ sung.

### D. Đồng Bộ Hóa Đồ Thị Lớn (Bulk Import)
* Khi khởi tạo đồ thị lần đầu, thay vì chạy hàng nghìn lệnh `INSERT` riêng lẻ (gây nghẽn đĩa), `sync_graph` tạo ra các tệp dữ liệu CSV tạm thời (`nodes.csv` và `edges.csv`).
* Sau đó, nó gọi lệnh `COPY FROM` hiệu năng cao của Kùzu để nhập đồng thời hàng nghìn node và cạnh vào cơ sở dữ liệu trong chưa đầy 1 giây.
