"""Keyword fallback khi Jev không khả dụng — regex VN+EN -> task_type.

Thứ tự trong list = thứ tự ưu tiên (rule cụ thể đặt trước rule chung).
"""
import re

# (regex, task_type) — match trên step text (case-insensitive, unicode)
KEYWORD_RULES: list[tuple[str, str]] = [
    # --- search_qlyc (đặt trước vì "tìm yêu cầu" dễ lẫn "tìm file") ---
    (r"\b(ur|yêu cầu|ticket|fcode|yc\d+)\b.*(cũ|trước|từng|lịch sử|đã làm)"
     r"|tra.*(ticket|yêu cầu|ur)|search.*(ticket|request)",
     "ur_semantic"),
    (r"\byc\d+\b|mã (yc|yêu cầu|dự án)\b|fcode1", "ur_exact"),
    # --- entity ---
    (r"entity.*(chưa khai báo|thiếu|missing|lint|check)|"
     r"undeclared.*entit", "entity_check"),
    (r"entity.*(khai báo ở|ở đâu|declared|file:line|vị trí)",
     "entity_path"),
    (r"(liệt kê|list|xem).*entit", "entity_list"),
    (r"(nội dung|content).*entit|entit.*(content|nội dung)",
     "entity_content"),
    # --- compare ---
    (r"(list|liệt kê|xem).*(file|folder|thư mục).*(có gì|có những|nào)|"
     r"inventory", "list_folder"),
    (r"(so sánh|compare|diff|đối chiếu).*(folder|thư mục|project)",
     "diff_folder"),
    (r"(so sánh|compare|diff).*(bảng|table|proc|sql|schema)",
     "diff_sql_table"),
    (r"(so sánh|compare|diff).*xml", "diff_xml"),
    (r"(so sánh|compare|diff).*file", "diff_file"),
    # --- clone ---
    (r"clone.*(dòng|data|row)|kéo.*data.*\.sql|delete.*insert",
     "clone_data"),
    (r"(lấy|xuất|paste).*(proc|func|view).*(ra|sửa|edit)|"
     r"paste.?for.?edit", "paste_sql"),
    (r"(copy|clone).*(bộ|suite|controller|file)", "copy_files"),
    (r"(clone|mang|kéo).*(proc|sql|object|thiếu)", "clone_sql"),
    # --- query_database ---
    (r"(check|kiểm tra).*(syntax|cú pháp).*\.sql|parseonly",
     "db_check_syntax"),
    (r"(chạy|execute|run).*(file|script).*\.sql", "db_run_file"),
    (r"(proc|object|function).*(dùng|use|reference).*(bảng|table|field)|"
     r"tìm.*(proc|object).*(trong db|database)", "db_search"),
    (r"(trích|extract).*(block|đoạn|vùng).*(proc|code)|snippet.*proc",
     "db_snippet"),
    (r"(xem|inspect|schema|cấu trúc).*(bảng|table|proc|view)|"
     r"create table|cột.*của bảng", "db_object"),
    (r"(chạy|run|select|query).*\b(sql|select|proc)\b", "db_run_sql"),
    # --- query_radar ---
    (r"(file|controller|chứng từ).*(nào).*(gọi|call|retrieve|dùng)|"
     r"graph|radar|quan hệ.*file", "graph_query"),
    # --- search_files ---
    (r"tìm.*(file).*(tên|name)|files?.*(matching|theo tên)|"
     r"files_only|match.*filename", "match_filename"),
    (r"(định nghĩa|definition).*(hàm|symbol|function)|"
     r"(hàm|symbol).*(định nghĩa|defined).*ở đâu", "find_definition"),
    (r"(mọi|all|tất cả).*(nơi|chỗ).*(dùng|gọi|use).*(symbol|hàm)|"
     r"references|refactor|rename", "find_references"),
    (r"tìm.*(file).*(chứa|có).*(chuỗi|string|text)|"
     r"(file|controller).*(nào).*(chứa|có)|grep|"
     r"tìm.*(trong|trên).*(dự án|project|file)", "grep_content"),
    # --- read_local_file ---
    (r"(sửa|edit|thay).*(file|code)|old_string|str_replace|"
     r"suggest.?edit", "read_suggest_edit"),
    (r"(trích|đọc|xem).*(hàm|function|block|command|field|đoạn)|"
     r"snippet", "read_snippet"),
    (r"(full|toàn bộ|expand).*(nội dung|xml|file)", "read_flat"),
    (r"đọc.*(raw|file gốc|\.sql|\.js|\.ent|template)", "read_raw"),
    (r"(đọc|xem|read).*(summary|controller|file)|summary.*xml",
     "read_summary"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE | re.UNICODE), t)
             for p, t in KEYWORD_RULES]


def keyword_route(step: str) -> str | None:
    """Trả task_type đoán theo keyword, hoặc None nếu không match."""
    for rx, task_type in _COMPILED:
        if rx.search(step or ""):
            return task_type
    return None
