# agent_messages.py

QUERY_RADAR_ERROR_MSG = """
[LỖI CÚ PHÁP CYPHER KUZUDB] 
Agent chú ý:
1. BẠN PHẢI DÙNG 1 TRONG 10 TEMPLATE CYPHER chuẩn đã được quy định trong Rule hệ thống. 
2. Tuyệt đối KHÔNG tự sáng tác câu lệnh Cypher phức tạp.
3. Nếu tìm chuỗi có chứa dấu nháy đơn ('), HÃY bọc bằng dấu nháy kép (") hoặc tách thành các điều kiện AND CONTAINS ngắn gọn. VD: a.js_text CONTAINS 'validFields' AND a.js_text CONTAINS 'ma_kh'
4. Lỗi chi tiết từ hệ thống: {error_detail}
Vui lòng sửa lại câu lệnh Cypher và gọi lại tool query_radar!
"""

MISSING_ARG_MSG = """
[LỖI THIẾU THAM SỐ] Tool '{tool_name}' yêu cầu bắt buộc phải có tham số '{missing_key}'.
Vui lòng gọi lại tool và truyền đầy đủ tham số này.
Lưu ý: Đối với 'file_path' hoặc 'reference_file', LUÔN dùng đường dẫn TUYỆT ĐỐI (VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SRTran.xml).
"""

GENERAL_EXECUTION_ERROR_MSG = """
[LỖI THỰC THI TOOL '{tool_name}'] 
{error_detail}
Vui lòng kiểm tra lại tham số truyền vào và thử lại. Nếu là lỗi liên quan tới query_radar, hãy chắc chắn bạn đã dùng đúng Template.
"""

VALIDATION_ERROR_MSG = """
[LỖI THAM SỐ KHÔNG HỢP LỆ] Tool '{tool_name}' — Agent cần sửa tham số rồi gọi lại.

{detail_vi}

Gợi ý:
- 'file_path' / 'reference_file': LUÔN dùng đường dẫn TUYỆT ĐỐI (VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SRTran.xml).
- 'db_type': chỉ 'app' hoặc 'sys'.
- 'mode' (get_xml_entities): 'content', 'path', 'list'.
- 'mode' (query_radar): 'query', 'schema'.
- 'read_option': 1 hoặc 2.
- 'page', 'page_size', 'max_total': phải là số nguyên hợp lệ.
"""

PATH_HINT_FIELDS = frozenset({"file_path", "reference_file"})

