# Phân Hệ 01: FastBusiness MCP Server (`fastbusiness_mcp/`)

Phân hệ này đảm nhận việc giao tiếp trực tiếp với cơ sở dữ liệu SQL Server của dự án FastBusiness và các chức năng tự động hóa viết mã XML (code generation/field snippet).

## 📁 Cấu Trúc Thư Mục
* `fastbusiness_mcp/server.py`: Điểm bắt đầu của MCP Server. Đăng ký các công cụ như `query_database`, `get_xml_entities`.
* `fastbusiness_mcp/core/`: Chứa mã nguồn kết nối CSDL, đọc file Web.config.
* `fastbusiness_mcp/tools/`:
  - `xml_snippet_tool.py`: Hỗ trợ thêm các đoạn XML cho field và views.
  - `code_assistant_tool.py`: Hỗ trợ chèn xử lý JavaScript onChange, onFocus vào XML đúng chuẩn định dạng (CDATA, DTD entities).

---

## 🔌 Chi Tiết Cơ Chế Hoạt Động Của Các Công Cụ

### 1. Công cụ `query_database` (Dò Connection String tự động)
* **Ý tưởng**: Khi nhà phát triển chạy một câu lệnh SQL từ môi trường làm việc, MCP cần biết nó phải kết nối tới DB nào mà không yêu cầu cấu hình cứng.
* **Cách thực hiện**:
  1. Khi nhận được một file nguồn kèm theo yêu cầu (ví dụ: `e:\FBO\App_Data\Controllers\Dir\SI2Tran.xml`).
  2. Hệ thống tìm ngược lên thư mục cha để định vị file `Web.config`.
  3. Phân tích cú pháp XML của file `Web.config` để đọc connection string tại khóa `<connectionStrings>` hoặc `<appSettings>`.
  4. Mở kết nối SQL Server (sử dụng thư viện như `pyodbc` hoặc `pymssql`) và thực thi câu lệnh SQL động do LLM yêu cầu, trả về kết quả định dạng JSON.

### 2. Công cụ Trợ Lý ClientScript (`code_assistant_tool.py`)
Khi cần thêm logic onChange (ví dụ: khi chọn mã khách hàng thì tự động điền tên khách hàng):
* Bộ sinh mã của FastBusiness yêu cầu các hàm JS phải nằm trong thẻ `<script>` ở cuối file, bọc trong thẻ `<![CDATA[ ... ]]>`.
* Trường dữ liệu XML `<field>` thì phải khai báo thuộc tính `<clientScript>` tham chiếu đến hàm JS đó.
* Tool `code_assistant_tool.py` tự động đọc file XML hiện tại, phân tích vị trí đặt thẻ, chèn an toàn JavaScript mà không phá hỏng định dạng DTD của tệp XML.
