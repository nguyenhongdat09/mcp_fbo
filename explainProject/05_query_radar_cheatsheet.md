# KùzuDB Cypher Query Principles & CodeGraph Schema Guide

> **Tài liệu quy tắc tổng quát & Bộ Template chuẩn tra cứu CodeGraph (Cypher / KùzuDB) cho Cursor AI Agent**
> **Mục đích:** Cung cấp quy tắc bắt buộc, chỉ thị nghiêm ngặt và 10 Template Cypher chuẩn hóa bao phủ 100% ngữ cảnh tra cứu CodeGraph. AI Agent BẮT BUỘC dùng đúng Template, tuyệt đối KHÔNG tự sáng tác câu lệnh Cypher phức tạp để tránh mọi lỗi Syntax / Parser Exception.

---

## 1. BẢN NGHĨA VÀ NGUYÊN TẮC CÚ PHÁP TỔNG QUÁT (CYPHER SYNTAX PRINCIPLES)

### ⚠️ CHỈ THỊ NGHIÊM NGẶT DÀNH CHO CURSOR AI AGENT (STRICT AGENT DIRECTIVE)

> [!IMPORTANT]
> 1. **KHÔNG BAO GIỜ** tự ghép chuỗi code JS/SQL nguyên bản chứa dấu nháy lồng (`\''`, `\'`, `""`) vào câu lệnh Cypher `query_radar`.
> 2. **KHÔNG BAO GIỜ** tự sáng tác cú pháp Cypher ngoài 10 Template bên dưới.
> 3. **BẮT BUỘC** chọn 1 trong 10 Template bên dưới và CHỈ ĐƯỢC thay thế tham số dạng `<PARAM>` bằng chuỗi ký tự đơn giản (Alphanumeric, Underscore).
> 4. **NẾU BẮT BUỘC** phải tìm kiếm chuỗi chứa dấu nháy đơn `'` $\rightarrow$ Dùng nháy kép `"` bao quanh giá trị trong Cypher, hoặc tốt nhất là **tách thành 2 từ khóa ngắn không chứa dấu nháy kết hợp `AND`**.

---

### 1.1. Nguyên Tắc Vỏ Bọc Nháy & Escape Chuỗi (Universal Quote & Escaping Rules)

1. **Dùng nháy chéo (Alternate Quote Wrapping):**
   - Chuỗi tìm kiếm có chứa nháy đơn `'` $\rightarrow$ Dùng nháy kép `"` bao ngoài chuỗi Cypher.
   - Chuỗi tìm kiếm có chứa nháy kép `"` $\rightarrow$ Dùng nháy đơn `'` bao ngoài chuỗi Cypher.
2. **Kỹ thuật tách từ khóa ngắn (Keyword Decomposition):**
   - ❌ **CẤM:** Viết câu Cypher chứa cả đoạn mã dài có nháy lồng: `a.js_text CONTAINS "validFields('ma_kh', 'ngay_ct')"` (Dễ lỗi syntax).
   - ✅ **BẮT BUỘC:** Tách thành các từ khóa ngắn độc lập kết hợp `AND`:
     `a.js_text CONTAINS 'validFields' AND a.js_text CONTAINS 'ma_kh' AND a.js_text CONTAINS 'ngay_ct'`
3. **Nguyên tắc đường dẫn (`\` vs `/`):**
   - KHÔNG dùng so sánh bằng tuyệt đối `= 'Grid\\ARDetail.xml'`.
   - **BẮT BUỘC** dùng `ENDS WITH` hoặc `ILIKE` với đường dẫn file:
     `a.relative_path ENDS WITH 'ARDetail.xml'` hoặc `a.relative_path ILIKE '%Grid%ARDetail.xml'`

---

### 1.2. Nguyên Tắc Tra Cứu Theo Kiểu Dữ Liệu (Data-Type Driven Rules)

Schema của CodeGraph chứa 4 nhóm kiểu dữ liệu chính. AI Agent phải dùng đúng toán tử cho từng nhóm:

| Kiểu dữ liệu | Các trường đại diện trong Schema | Toán tử / Hàm BẮT BUỘC dùng | Ví dụ minh họa |
|---|---|---|---|
| **Chuỗi đơn (`STRING`)** | `relative_path`, `folder_type`, `db_table`, `title_v`, `code_field` | `ILIKE`, `CONTAINS`, `ENDS WITH`, `STARTS WITH`, `=` | `a.db_table ILIKE '%d91%'`<br>`a.relative_path ENDS WITH 'SI2Tran.xml'` |
| **Đoạn Code lớn (`STRING`)** | `js_text`, `sql_text` | `CONTAINS` (Tách nhỏ từ khóa với `AND`) | `a.js_text CONTAINS 'showForm' AND a.js_text CONTAINS 'Filter'` |
| **Mảng danh sách (`STRING[]`)** | `fields_names`, `fields_headers`, `grid_refs`, `lookup_refs`, `param_entities` | **Hàm mảng:** `list_contains(...)` hoặc `ANY x IN ...` | `list_contains(a.fields_names, 'ma_kh')`<br>`ANY x IN a.grid_refs WHERE x ILIKE '%Detail%'` |
| **Cờ / Số (`BOOLEAN`, `INT64`)** | `is_encrypted`, `file_size`, `last_modified` | So sánh logic: `=`, `>`, `<`, `IS NULL`, `IS NOT NULL` | `a.is_encrypted = false`<br>`a.db_table IS NOT NULL AND a.db_table <> ''` |

---

## 2. MÔ HÌNH SCHEMA ĐỒ THỊ TỔNG QUÁT (GRAPH DATA MODEL)

### 2.1. Node Table: `XmlFile` (Thực thể File Controller)

Tất cả tài nguyên trong dự án (Dir, Grid, Filter, Report, Templates...) đều biểu diễn dưới dạng 1 Node trong table `XmlFile`.

- **Primary Key:** `node_id` (`STRING`)
- **Metadata phân loại:** `relative_path`, `folder_type` (`Dir`\|`Grid`\|`Filter`\|`Report`\|`Templates`), `folder_subtype`, `controller_type`, `canonical_path`, `alias_of`, `is_encrypted`.
- **Dữ liệu nghiệp vụ:** `db_table` (Bảng DB chính), `code_field` (Trường khóa chính), `title_v` (Tiêu đề VN), `title_e` (Tiêu đề EN).
- **Mảng thành phần khai báo:** `fields_names` (`STRING[]`), `fields_headers` (`STRING[]`), `grid_refs` (`STRING[]`), `lookup_refs` (`STRING[]`), `param_entities` (`STRING[]`).
- **Nội dung mã nguồn CDATA:** `js_text` (`STRING`), `sql_text` (`STRING`).

---

### 2.2. Relationship Table: `Rel` (Mối Quan Hệ Giữa Các Node)

Cấu trúc tổng quát: `(source:XmlFile)-[r:Rel]->(target:XmlFile)`

- **Thuộc tính của `Rel`:**
  - `edge_type` (`STRING`): Nhãn định danh loại mối quan hệ.
  - `meta` (`STRING`): Dữ liệu bổ sung dạng JSON (dòng code, ngữ cảnh...).

#### Bảng danh mục `edge_type` chuẩn:
1. `GRID_MASTER_DETAIL`: Master Controller (Dir) $\rightarrow$ Detail Controller (Grid).
2. `LOOKUP_REFERENCE`: Form/Grid Controller $\rightarrow$ Lookup Controller được tham chiếu bởi Field.
3. `RETRIEVE_DATA_SOURCE`: Detail Controller $\rightarrow$ Filter/Grid Controller lấy nguồn dữ liệu.
4. `COMPANION_FILE`: Controller phân hệ này $\leftrightarrow$ Controller cùng tên thuộc phân hệ khác.
5. `SQL_TABLE_USE`: Controller $\rightarrow$ Bảng SQL Server tương tác.
6. `SQL_PROC_CALL`: Controller $\rightarrow$ Stored Procedure SQL Server được gọi.
7. `JS_FUNC_CALL`: Script JS $\rightarrow$ Hàm/Sự kiện JS liên quan.
8. `ENTITY_INCLUDE`: XML $\rightarrow$ File DTD SYSTEM include.
9. `PARAM_ENTITY_USE`: XML $\rightarrow$ Parameter Entity khai báo.
10. `SHARED_INCLUDE`: Controller $\rightarrow$ File tài nguyên dùng chung.

---

## 3. 10 BỘ TEMPLATE TRUY VẤN CHUẨN NGUYÊN BẢN (10 CANONICAL TEMPLATES)

Agent BẮT BUỘC chọn 1 trong 10 Template dưới đây và thay các giá trị `<...>` bằng chuỗi chữ/số đơn giản:

### Template 1: Tìm Controller theo Tên File / Đường Dẫn
```cypher
MATCH (a:XmlFile)
WHERE a.relative_path ENDS WITH '<FILE_NAME>.xml'
RETURN a.relative_path, a.folder_type, a.db_table, a.title_v, a.code_field
LIMIT 20
```

### Template 2: Tìm Controller theo Loại Thư Mục (Dir, Grid, Filter...)
```cypher
MATCH (a:XmlFile)
WHERE a.folder_type = '<FOLDER_TYPE>'
RETURN a.relative_path, a.db_table, a.title_v
LIMIT 50
```

### Template 3: Tìm Controller Chứa Từ Khóa trong Javascript (`js_text`)
```cypher
MATCH (a:XmlFile)
WHERE a.js_text CONTAINS '<KEYWORD_1>'
  AND a.js_text CONTAINS '<KEYWORD_2>'
RETURN a.relative_path, a.folder_type, a.title_v
LIMIT 20
```

### Template 4: Tìm Controller Chứa Từ Khóa trong SQL (`sql_text`)
```cypher
MATCH (a:XmlFile)
WHERE a.sql_text CONTAINS '<KEYWORD_1>'
  AND a.sql_text CONTAINS '<KEYWORD_2>'
RETURN a.relative_path, a.db_table, a.title_v
LIMIT 20
```

### Template 5: Tìm Controller Khai Báo Trường Dữ Liệu (`fields_names`)
```cypher
MATCH (a:XmlFile)
WHERE list_contains(a.fields_names, '<FIELD_NAME>')
RETURN a.relative_path, a.folder_type, a.title_v, a.db_table
LIMIT 20
```

### Template 6: Tìm Controller Thao Tác Với Bảng Database (`db_table`)
```cypher
MATCH (a:XmlFile)
WHERE a.db_table ILIKE '%<TABLE_NAME>%'
RETURN a.relative_path, a.db_table, a.title_v, a.code_field
LIMIT 20
```

### Template 7: Tra Cứu Quan Hệ 1 Chiều (Master-Detail, Field-Lookup, Data-Source)
```cypher
MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)
WHERE a.relative_path ENDS WITH '<SOURCE_FILE>.xml'
  AND r.edge_type = '<EDGE_TYPE_ENUM>'
RETURN a.relative_path AS source, r.edge_type AS relationship, b.relative_path AS target
LIMIT 50
```

### Template 8: Tra Cứu Quan Hệ Hai Chiều / Bất Kỳ Hướng Nào (Discovery)
```cypher
MATCH (a:XmlFile)-[r:Rel]-(b:XmlFile)
WHERE a.relative_path ENDS WITH '<FILE_NAME>.xml'
RETURN a.relative_path AS node_a, r.edge_type AS edge, b.relative_path AS node_b
LIMIT 50
```

### Template 9: Tra Cứu Đường Đi Đa Cấp / Chuỗi Quan Hệ (Multi-Hop Traversal)
```cypher
MATCH (a:XmlFile)-[r1:Rel]->(b:XmlFile)-[r2:Rel]->(c:XmlFile)
WHERE a.relative_path ENDS WITH '<START_FILE>.xml'
RETURN a.relative_path AS start_node, r1.edge_type AS edge1, b.relative_path AS mid_node, r2.edge_type AS edge2, c.relative_path AS end_node
LIMIT 30
```

### Template 10: Thống Kê Số Lượng Controller Theo Phân Loại (Aggregation)
```cypher
MATCH (a:XmlFile)
RETURN a.folder_type, COUNT(a) AS total_files
ORDER BY total_files DESC
```

---

## 4. QUY TẮC HIỆU NĂNG VÀ AN TOÀN KHI RETURNING

1. **KHÔNG BAO GIỜ `RETURN a` (Trả về toàn bộ Node):**
   - Node `XmlFile` chứa các cột `js_text` và `sql_text` rất dài. Trả về toàn bộ node sẽ làm tràn bộ nhớ JSON response.
   - **BẮT BUỘC** chỉ chọn các cột cần thiết: `RETURN a.relative_path, a.folder_type, a.title_v, a.db_table`
2. **Luôn có `LIMIT` ở cuối câu truy vấn:**
   - Mặc định đặt `LIMIT 20` hoặc `LIMIT 50` để tránh truy vấn quá tải.
3. **Chiến lược Chuyển Giao (Fallback Strategy):**
   - Nếu câu hỏi của người dùng đòi hỏi tìm kiếm pattern động quá phức tạp, lồng nhiều điều kiện regex:
   - **Dừng việc tự viết Raw Cypher qua `query_radar`.**
   - **Sử dụng các Tool bọc sẵn an toàn trong Python:** `search_nodes`, `get_related_nodes`, `query_node_details`.
