# agent_messages.py

MISSING_ARG_MSG = """
[LỖI THIẾU THAM SỐ] Tool '{tool_name}' yêu cầu bắt buộc phải có tham số '{missing_key}'.
Vui lòng gọi lại tool và truyền đầy đủ tham số này.
Lưu ý: Đối với 'file_path' hoặc 'reference_file', LUÔN dùng đường dẫn TUYỆT ĐỐI (VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SRTran.xml).
"""

GENERAL_EXECUTION_ERROR_MSG = """
[LỖI THỰC THI TOOL '{tool_name}'] 
{error_detail}
Vui lòng kiểm tra lại tham số truyền vào và thử lại.
"""

VALIDATION_ERROR_MSG = """
[LỖI THAM SỐ KHÔNG HỢP LỆ] Tool '{tool_name}' — Agent cần sửa tham số rồi gọi lại.

{detail_vi}

Gợi ý:
- 'file_path' / 'reference_file': LUÔN dùng đường dẫn TUYỆT ĐỐI (VD: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SRTran.xml).
- 'db_type': chỉ 'app' hoặc 'sys'.
- 'mode' (get_xml_entities): 'content', 'path', 'list'.
- 'read_option': 1 (raw), 2 (flat), 3 (summary_xml).
- 'page', 'page_size', 'max_total': phải là số nguyên hợp lệ.
"""

PATH_HINT_FIELDS = frozenset({"file_path", "reference_file"})

