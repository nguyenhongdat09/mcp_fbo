import re

# 1. Các mẫu Regex dùng cho SQL
SQL_PATTERNS = {
    # Phát hiện lệnh gọi store procedure: exec name, execute name
    "stored_procedures": re.compile(
        r"\b(?:exec|execute)\s+([a-zA-Z0-9_\$]+(?:\$[a-zA-Z0-9_\$]+)*)", 
        re.IGNORECASE
    ),
    
    # Phát hiện các bảng đích trong câu lệnh SELECT, INSERT, UPDATE, DELETE
    # Nhận diện các bảng đặc thù như d81$$partition$current hoặc m81$$partition$previous
    "tables": re.compile(
        r"\b(?:from|join|into|update)\s+([a-zA-Z0-9_\$]+(?:\$\$[a-zA-Z0-9_\$]+)*(?:\$[a-zA-Z0-9_\$]+)*)", 
        re.IGNORECASE
    ),
    
    # Phát hiện các biến khai báo/sử dụng trong SQL
    "variables": re.compile(r"(@[a-zA-Z0-9_]+)\b"),
}

# 2. Các mẫu Regex dùng cho Javascript
JS_PATTERNS = {
    # Phát hiện khai báo hàm: function name(...) hoặc onChange$Voucher(this)
    "functions": re.compile(r"\bfunction\s+([a-zA-Z0-9_\$]+)\s*\("),
    
    # Phát hiện các hàm tiện ích FBO hay dùng (ví dụ: g.validExpression, g.onChange...)
    "fbo_helper_calls": re.compile(r"\bg\s*\.\s*([a-zA-Z0-9_\$]+)\b"),
    
    # Phát hiện các biến trường dữ liệu Client: g.$a.field_name
    "client_fields": re.compile(r"\bg\s*\.\s*\$a\s*\.\s*([a-zA-Z0-9_]+)\b"),
}
