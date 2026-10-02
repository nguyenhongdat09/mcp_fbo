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
    (r"(clone|copy|kéo|đưa).*(dòng|data|row|dữ liệu).*(ra|vào|sang|"
     r"\.sql|file|db|database)|clone.*(dòng|data|row|dữ liệu)|"
     r"delete.*insert|"
     r"(dump|export|viết|ghi).*(dữ liệu|data|rows?|dòng).*"
     r"(vào|ra|into|to).*(file|\.sql)|dữ liệu.*(mẫu|test).*\.sql",
     "clone_data"),
    (r"(tạo|new|mở|xin).{0,25}(file|tệp)?\s*\.?\s*sql.{0,20}"
     r"(mới|trống|rỗng|temp|scratch|để viết)|"
     r"(file|tệp)\s*\.?\s*sql\s*(mới|trống|rỗng)|"
     r"(tạo|new)\s+(?:(?:file|tệp)\s+)?[^\s]*\.sql\b|"
     r"new\s+(empty\s+)?sql\s+file|sql_temp",
     "new_sql_file"),
    (r"save[\s_-]*as|"
     r"(copy|clone)\s+(theo|từ|giống|tương tự|dựa\s+trên)\s+"
     r"(chức năng|báo cáo|màn hình|controller|phiếu|chứng từ)|"
     r"(làm|tạo|thêm)\s+(?:\w+\s+){0,3}?(giống|tương tự|dựa\s+trên)\s+"
     r"(chức năng|báo cáo|màn hình|controller|phiếu|chứng từ)",
     "save_as_existing"),
    # đọc/trích ĐOẠN proc (có cue đoạn/block/phần/cách tính) → db_snippet;
    # đặt TRƯỚC paste_sql vì paste_sql bắt cả "đọc proc" (toàn bộ).
    (r"(đọc|xem|trích).*(đoạn|block|phần|cách\s*tính|khu\s*vực).*(proc|"
     r"procedure|func(tion)?)|"
     r"(proc|procedure|func(tion)?)\b.*(đoạn|block|phần|cách\s*tính|"
     r"khu\s*vực)",
     "db_snippet"),
    (r"(lấy|xuất|paste).*(proc|func|view).*(ra|sửa|edit)|"
     r"paste.?for.?edit|"
     r"(sửa|chỉnh|edit|xem|đọc|viết lại|dump).*(nội dung |source |body )?"
     r"(proc|procedure|func(tion)?)\b", "paste_sql"),
    (r"(tạo|thêm).*(bộ|suite|template).*(controller|báo cáo|danh mục|"
     r"lấy dữ liệu|chứng từ|voucher)|chức năng lấy dữ liệu|"
     r"retrieve.*(flow|suite)|"
     r"(tạo|thêm).*(chứng từ|voucher).*(mới|suite|bộ|template)|"
     r"chứng từ mới|voucher.*(suite|mới)", "clone_template"),
    (r"(copy|clone).*(bộ|suite|controller|file)", "copy_files"),
    (r"(clone|mang|kéo).*(proc|sql|object|thiếu)", "clone_sql"),
    # --- query_database ---
    (r"(tính|lấy|xác định|hạch toán).{0,30}(số dư|dư đầu|dư cuối|"
     r"tồn đầu|tồn cuối|công nợ|dư nợ|dư có)|"
     r"(số dư|dư|tồn)\s*(đầu|cuối)\s*kỳ|tồn kho|dư nợ|dư có|công nợ|"
     r"tồn\s*(theo\s+)?(kho|mã kho|vị trí|lô|vật tư|site|location|lot|"
     r"item)|đáo hạn|maturity|balance\$|openingbalance|opening\s+balance|"
     r"số dư (theo )?(tk|tài khoản|khách hàng|kho|lô|vị trí|khế ước|"
     r"hợp đồng|vụ việc|công trình|nhân viên|nvbh|sale)|"
     r"dư (khế ước|hợp đồng|vụ việc|nhân viên|nvbh)",
     "db_balance"),
    (r"(thêm|add|bổ sung).*(trường|cột|field|column).*(bảng|table|vào|cho)|"
     r"fsd_addfields|alter\s+table", "db_add_field"),
    (r"(check|kiểm tra).*(syntax|cú pháp).*\.sql|parseonly",
     "db_check_syntax"),
    (r"(chạy|execute|run).*(file|script).*\.sql", "db_run_file"),
    (r"(proc|object|function).*(dùng|use|reference).*(bảng|table|field)|"
     r"tìm.*(proc|object).*(trong db|database)", "db_search"),
    (r"(trích|extract).*(block|đoạn|vùng).*(proc|code)|snippet.*proc",
     "db_snippet"),
    (r"(xem|inspect|schema|cấu trúc).*(bảng|table|proc|view)|"
     r"create table|cột.*của bảng", "db_object"),
    (r"(kiểm tra|check|xem).*(dữ liệu|data|tồn|rows?|dòng).*(bảng|table|"
     r"database|trong db)|exec.*proc|chạy.*proc.*test", "db_run_sql"),
    (r"(chạy|run|select|query).*\b(sql|select|proc)\b", "db_run_sql"),
    # --- query_radar ---
    (r"(tìm|find|search|xác định|locate).*(title|tiêu đề|tên hiển thị)|"
     r"(theo|qua|bằng)\s*(title|tiêu đề|tên hiển thị)", "find_by_title"),
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
