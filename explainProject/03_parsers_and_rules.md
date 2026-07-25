# Phân Hệ 03: Bộ Phân Tích Cú Pháp & Quy Tắc Thiết Lập Quan Hệ

Tài liệu này đi sâu vào chi tiết kỹ thuật của các bộ phân tích cú pháp (Parsers) và cách thức tạo lập các mối quan hệ (Edges) trong đồ thị.

## 🔍 Bộ Phân Tích Cú Pháp (Parsers)

Nằm trong thư mục [xml_codegraph/parsers/](file:///e:/mcp_fbo/xml_codegraph/parsers/):

### 1. Bộ Phân Tích XML (`xml_parser.py`)
* **Hỗ trợ DTD Entity**: Các file XML trong FastBusiness sử dụng rất nhiều tệp khai báo thực thể thực tế như `<!ENTITY % Control.xml SYSTEM "..\..\Control.ent">`. Bộ phân tích sử dụng thư viện `lxml.etree` kết hợp lớp tự chế `FboResolver` để phân giải động các tệp tham chiếu này, đưa XML về dạng phẳng (flat XML) trước khi phân tích thẻ.
* **Giải Mã Mã Hóa Cổ (Encoding Handler)**: Rất nhiều tệp XML cũ của FastBusiness chứa văn bản hiển thị Tiếng Việt dạng `Windows-1258` (chứ không phải UTF-8). Bộ parser tự động dò tìm thẻ `encoding` trong XML header để giải mã đúng định dạng font, tránh lỗi vỡ font hoặc crash khi lưu trữ vào DB.

### 2. Bộ Phân Tích SQL (`sql_parser.py`)
* Quét tìm các khối lệnh chứa trong thẻ `<query>` hoặc các thuộc tính liên quan đến lệnh SQL.
* Phân tích các câu lệnh SELECT/INSERT/UPDATE để tìm ra các bảng dữ liệu liên quan.

### 3. Bộ Phân Tích JS (`js_parser.py`)
* Tìm thẻ `<script>` ở cuối các file điều khiển, trích xuất mã JS.
* Sử dụng regex để phát hiện các tên hàm onChange/onFocus và các lời gọi API của hệ thống (ví dụ: `setItemValue`, `getItemValue`, `request`, `g.request`).

---

## 📐 Quy Tắc Thiết Lập Cạnh (Relationship Rules)

Nằm tại [xml_codegraph/rules/edges_rules.py](file:///e:/mcp_fbo/xml_codegraph/rules/edges_rules.py). Đồ thị Kùzu chỉ sử dụng một nhãn quan hệ duy nhất là `:Rel`, với thuộc tính `edge_type` để phân loại.

Các loại liên kết chính bao gồm:
1. **`GRID_MASTER_DETAIL`**:
   - Xác định khi một Form XML (thuộc thư mục `Dir`) chứa thẻ `<fields>` khai báo một trường lưới chi tiết dẫn đến một file XML khác nằm trong `Grid`.
2. **`LOOKUP_REFERENCE`**:
   - Khi một trường dữ liệu định nghĩa một thuộc tính tự động hoàn thành (AutoComplete) hoặc chọn từ danh mục (Lookup) dẫn đến một controller danh mục (ví dụ: `ma_kh` tham chiếu đến danh mục `Customer`).
3. **`COMPANION_FILE`**:
   - Các file có cấu trúc cùng tên nhưng phục vụ các giai đoạn hiển thị khác nhau. Ví dụ: `Dir/SVTran.xml` (dữ liệu nhập voucher) và `Grid/SVTran.xml` (lưới hiển thị danh sách voucher).
4. **`SHARED_INCLUDE`**:
   - Các file đóng vai trò thực thể mẫu dùng chung, được include vào qua DTD entity (Ví dụ: `Control.ent`, `fields.ent`). Số lượng quan hệ này rất lớn (~99% tổng số cạnh) nên mặc định các công cụ truy vấn sẽ loại bỏ cạnh này để tránh làm ngập ngữ cảnh (context window) của AI Agent.
5. **`ENTITY_INCLUDE` / `PARAM_ENTITY_USE`**:
   - Các liên kết thể hiện mối quan hệ kế thừa và sử dụng định nghĩa DTD Entity.
