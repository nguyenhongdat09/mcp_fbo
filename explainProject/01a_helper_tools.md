# Phân Hệ 01-A: Helper Tools Chuyên Sâu (`fastbusiness_mcp/tools/`)

Thư mục `tools` của phân hệ `fastbusiness_mcp` chứa các công cụ hỗ trợ AI Agent và lập trình viên thao tác viết mã XML/JS nhanh chóng và chính xác theo chuẩn FastBusiness FBO.

## 📝 1. Bộ Hỗ Trợ Chèn Mã XML/JS (`xml_snippet_tool.py`)

Lớp `XMLSnippetTool` cung cấp các giải pháp hoàn toàn tự động trên máy chủ để sửa đổi tệp XML của FastBusiness mà không cần AI tự biên soạn, giảm thiểu 100% lỗi cú pháp XML do AI tự suy luận.

### Chức năng 1: `add_clientscript_to_field`
* **Mục tiêu**: Thêm thuộc tính hoặc thẻ `<clientScript>` vào bên trong thẻ `<field>` chỉ định.
* **Cơ chế xử lý**:
  1. Nhận chuỗi XML của field hiện tại (`field_xml`), loại handler (`onchange` hoặc `onfocus`), và tên hàm Javascript cần gọi (`function_name`).
  2. **Trường hợp 1**: Nếu field chưa có thẻ `<clientScript>`, chương trình tự động phân giải cấu trúc XML. Nếu thẻ đóng dạng tự kết thúc (`<field ... />`), nó chuyển đổi thành cặp thẻ `<field> ... </field>` và chèn thẻ con `<clientScript><![CDATA[onchange="tên_hàm(this);"]]></clientScript>`.
  3. **Trường hợp 2**: Nếu đã tồn tại thẻ `<clientScript>` nhưng khác loại sự kiện, nó nối thêm sự kiện mới vào CDATA (ví dụ: `onchange="..." onfocus="..."`).
  4. **Trường hợp 3**: Nếu đã tồn tại sự kiện cùng loại, nó nối tiếp lệnh gọi hàm phân cách bằng dấu chấm phẩy (ví dụ: `onchange="ham1(this);ham2(this);"`).
* **Kết quả trả về**: Trả về khối XML của trường đã sửa đổi (`modified_field`) để client thay thế trực tiếp vào tệp nguồn.

### Chức năng 2: `add_function_to_script`
* **Mục tiêu**: Đóng gói mã JavaScript thô vào thẻ CDATA XML chuẩn hóa và chèn vào thẻ `<script>` ở cuối file.
* **Cơ chế xử lý**:
  - Nhận đoạn mã JS thô.
  - Sinh chuỗi định dạng chèn:
    ```xml
    <![CDATA[
    [Hàm Javascript thô]
    ]]>
        </text>
    </script>
    ```
  - Trả về mã snippet cùng vị trí chuỗi tìm kiếm (`    </text>\n</script>`) để công cụ editor của client dễ dàng thực hiện thay thế (replace) an toàn.

---

## 🤖 2. Trợ Lý Lập Trình Thông Minh (`code_assistant_tool.py`)

Lớp `CodeAssistantTool` tích hợp sâu với cơ sở tri thức (Knowledge Base) của FastBusiness được lưu trữ trong mã nguồn dự án.

### Chức năng 1: Dò tìm ngữ cảnh (`detect_context`)
* Sử dụng bộ phát hiện ngữ cảnh `ContextDetector` để đọc file XML hoặc nội dung chuỗi XML nhằm xác định phân hệ (ví dụ: Dir - danh mục nhập liệu, Grid - bảng chi tiết chứng từ, Filter - bảng lọc dữ liệu...).
* Trích xuất các thuộc tính chính và trả về tóm tắt ngữ cảnh kèm các gợi ý phát triển liên quan.

### Chức năng 2: Tra cứu trợ giúp API (`get_api_help`)
* Truy vấn các định nghĩa hàm API có sẵn của Client FastBusiness tương ứng với Form hoặc Grid.
* Trả về chi tiết tham số, kiểu dữ liệu, giải thích và mã mẫu trực quan cho từng hàm API (ví dụ: API `setItemValue`, `request`, `g.setItemValue`).

### Chức năng 3: Sinh code từ Pattern mẫu (`generate_code` & `generate_function_skeleton`)
* Dựa trên ngữ cảnh hiện tại và Pattern mong muốn (ví dụ: khởi tạo form mới, kiểm tra logic lưu trữ), tự động sinh ra mã khung xương (skeleton) của hàm JavaScript hoặc cấu trúc XML chuẩn của FastBusiness.
* Điền sẵn các biến môi trường vào các hàm mẫu để lập trình viên chỉ việc điền logic nghiệp vụ.
