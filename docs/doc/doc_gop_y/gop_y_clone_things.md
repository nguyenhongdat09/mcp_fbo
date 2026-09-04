# Góp Ý & Đánh Giá Chi Tiết Bộ Thiết Kế MCP `clone_things` (Cập nhật lần 2)

> **Tài liệu tham chiếu:** [`docs/doc/clone_things/`](file:///e:/PythonProject/mcp_fbo/docs/doc/clone_things)  
> **Người đánh giá:** AI Assistant (Antigravity)  
> **Ngày cập nhật:** 2026-09-04  

---

## 1. Đánh giá sau khi cập nhật

Bộ tài liệu sau khi bạn cập nhật đã **vá hoàn toàn các lỗ hổng kỹ thuật quan trọng nhất**:
1. ✅ **Đã loại bỏ `ObjectCatalogFetcher.fetch_one` cho bước exists của Bảng:** Quy định tra cứu trực tiếp qua `sys.objects`, tránh được lỗi hiểu nhầm Bảng không tồn tại.
2. ✅ **Đã làm rõ cách lấy DDL Table:** Nêu rõ Table trả về cột `val` trong `result_sets[0]["rows"]` thay vì tìm field `definition`.
3. ✅ **Đã bổ sung chuẩn phân cách `GO`:** Phân cách `\n\nGO\n\n` đảm bảo file `.sql` hợp lệ cú pháp T-SQL của SQL Server.
4. ✅ **Đồng bộ mã giả comment `not_found_both`:** Đã sửa mã giả ở Mục 1 thống nhất với Mục 7 (chỉ gom vào list và ghi 1 dòng tổng hợp cuối file).
5. ✅ **Chuẩn hóa set `visited` & Lọc bỏ bảng tạm/biến:** Dùng key `dbo.<name_lower>` và loại trừ các token bắt đầu bằng `#` hoặc `@`.
6. ✅ **Bộ Test Cases được bổ sung đầy đủ:** Đã thêm `TC-CORE-02b`, `TC-CORE-04`, `TC-CORE-04b`, `TC-CORE-06`, `TC-DEP-04b` phủ kín các kịch bản vừa điều chỉnh.

---

## 2. Các điểm tinh chỉnh nhỏ (Minor Implementation Tips) để code mượt hơn

Hiện tại tài liệu đã **rất chặt chẽ và không còn lỗ hổng kiến trúc nào**. Chỉ còn 2 lưu ý nhỏ ở tầng mã nguồn khi Gemini/dev bắt tay vào code:

### 2.1. Khuyến nghị import trực tiếp `summary_xml` thay vì gọi wrapper MCP
- Tại [`06_reuse_existing.md`](file:///e:/PythonProject/mcp_fbo/docs/doc/clone_things/06_reuse_existing.md#L20), khi cần seed từ XML:
- Nên import trực tiếp hàm nội bộ:
  ```python
  from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
  result_dict = summary_xml(xml_file_path)
  ```
- **Lý do:** Hàm này trả về thẳng Python `dict` chứa `sql.procs`, `sql.tables`, `sql.views`, `controller.db_table`. Tránh gọi qua `mcp_read_local_file` vì wrapper đó format kết quả thành chuỗi text/markdown, code lại phải mất công parse ngược lại.

### 2.2. Nhịp ngắt dòng giữa các batch `GO` khi Append
- Định dạng chuẩn và đẹp nhất cho file script SQL Server là:
  ```sql
  -- block 1
  CREATE PROCEDURE dbo.p1 AS ...
  GO

  -- block 2
  CREATE PROCEDURE dbo.p2 AS ...
  GO
  ```
- Thuật toán ở Mục 7 của [`03_resolution_and_flow.md`](file:///e:/PythonProject/mcp_fbo/docs/doc/clone_things/03_resolution_and_flow.md#L181-L202) đã kiểm tra `last_meaningful_line is not "GO"` để tránh bị đúp 2 lệnh `GO` liên tiếp. Khi code thực tế, chỉ cần bảo đảm trước mỗi `CREATE...` mới có đúng 1 dòng trống sau lệnh `GO` trước là file script sẽ rất sạch sẽ.

---

## 3. Kết luận

Bộ tài liệu [`docs/doc/clone_things/`](file:///e:/PythonProject/mcp_fbo/docs/doc/clone_things) hiện tại đã **đạt độ hoàn thiện cao, nhất quán và sẵn sàng 100% để triển khai (Ready for Implementation)**. Bạn hoàn toàn có thể copy phần Prompt trong [`08_implementation_checklist.md`](file:///e:/PythonProject/mcp_fbo/docs/doc/clone_things/08_implementation_checklist.md#L62-L89) để bắt đầu phase code.
