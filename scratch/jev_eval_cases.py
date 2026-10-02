"""Golden cases cho Jev requirement_type + step task_type evaluation.

Mỗi case:
    id             : mã case
    ur             : task_requirement nguyên văn (tiếng Việt)
    expected       : requirement_type mong đợi
    steps          : plan steps (optional — default DEFAULT_STEPS)
    expected_steps : task_type mong đợi cho TỪNG step (optional, cùng độ dài
                     steps); None = bỏ qua, không chấm step đó
"""

DEFAULT_STEPS = [
    "Khảo sát chứng từ mẫu tương thích trong project",
    "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
    "Viết SQL đăng ký SYS/APP + tạo bảng vật lý",
]

CASES = [
    # --- voucher: approval + currency ---
    {"id": "A1",
     "ur": "Tạo chứng từ mới PLH phiếu đề nghị thanh toán, có chức năng "
           "duyệt và có mã ngoại tệ",
     "expected": "voucher_approval_currency"},
    {"id": "A2",
     "ur": "Thêm voucher mới có luồng trình duyệt, hỗ trợ tỷ giá ngoại tệ",
     "expected": "voucher_approval_currency"},
    {"id": "A3",
     "ur": "Chứng từ mới đa tiền tệ và cần phê duyệt nhiều cấp",
     "expected": "voucher_approval_currency"},
    # --- voucher: approval, no currency ---
    {"id": "B1",
     "ur": "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
     "expected": "voucher_approval_no_currency"},
    {"id": "B2",
     "ur": "Tạo voucher mới có duyệt (kiểu duyệt 01501)",
     "expected": "voucher_approval_no_currency"},
    {"id": "B3",
     "ur": "Chứng từ mới cần qua bước ký duyệt trước khi hạch toán",
     "expected": "voucher_approval_no_currency"},
    # --- voucher: normal + currency ---
    {"id": "C1",
     "ur": "Tạo chứng từ mới không duyệt, có mã ngoại tệ và tỷ giá",
     "expected": "voucher_normal_currency"},
    {"id": "C2",
     "ur": "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
     "expected": "voucher_normal_currency"},
    {"id": "C3",
     "ur": "Chứng từ mới có ngoại tệ",
     "expected": "voucher_normal_currency"},
    # --- voucher: normal, no currency ---
    {"id": "D1",
     "ur": "Tạo chứng từ mới đơn giản, không duyệt, không ngoại tệ",
     "expected": "voucher_normal_no_currency"},
    {"id": "D2",
     "ur": "Chứng từ mới bình thường, không duyệt không ngoại tệ",
     "expected": "voucher_normal_no_currency"},
    # --- unclear → generic voucher ---
    {"id": "E1", "ur": "Tạo chứng từ mới PLH", "expected": "voucher"},
    {"id": "E2",
     "ur": "Tạo voucher mới cho nghiệp vụ ký gửi",
     "expected": "voucher"},
    # --- NOT new-creation ---
    {"id": "F1",
     "ur": "Sửa chứng từ DDVTran thêm cột mã dự án vào grid chi tiết",
     "expected": "none"},
    {"id": "F2",
     "ur": "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
     "expected": "retrieve_flow_parition_table"},
    # --- report ---
    {"id": "G1",
     "ur": "Tạo báo cáo danh sách phiếu nhập kho theo điều kiện lọc",
     "expected": "report_normal"},
    {"id": "G2",
     "ur": "Báo cáo có cột tick chọn dòng, nút in chỉ in các dòng đã chọn",
     "expected": "report_check"},
    {"id": "G3",
     "ur": "Báo cáo pivot doanh thu theo tháng x khách hàng",
     "expected": "report_pivot"},
    # --- category ---
    {"id": "H1",
     "ur": "Thêm danh mục mới loại phí, chỉ có mã + tên",
     "expected": "category_1_key"},
    {"id": "H2",
     "ur": "Tạo danh mục mới có khóa ghép theo đơn vị và năm",
     "expected": "category_multi_key"},
    # --- step routing sanity (db_run_sql vs clone_data vs paste_sql) ---
    {"id": "S1",
     "ur": "Kiểm tra dữ liệu và tạo dữ liệu mẫu test",
     "expected": "none",
     "steps": [
         "Kiểm tra dữ liệu thực tế trong bảng dmvt và tồn kho",
         "Clone dữ liệu mẫu từ phiếu có sẵn ra file .sql",
         "Sửa proc rs_test thêm điều kiện lọc",
     ],
     "expected_steps": ["db_run_sql", "clone_data", "paste_sql"]},
]
