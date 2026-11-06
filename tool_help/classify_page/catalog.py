"""Mô tả template Page.0xx (SP30+) cho Jev chọn, viết bằng lời thường.

Chỉ có Page.001..024 + Flow + Query (không có Page.025+). Số trang là số dòng
``<page>`` dùng template đó ở DIVN/FBISP30.
"""

PAGE_TEMPLATES: dict[str, dict] = {
    "Page.001": {
        "what": "Màn hình danh mục thông thường (thêm, sửa, xóa, import dữ "
                "liệu). Template mặc định, dùng nhiều nhất (~1650 trang)",
        "signals": "danh mục, tiện ích, màn hình không có gì đặc biệt",
        "not_for": ["chứng từ"],
    },
    "Page.002": {
        "what": "Màn hình khai báo có khung truy vấn bên cạnh để xem ngược "
                "số liệu (~11 trang)",
        "signals": "khai báo kèm truy vấn xem ngược, dự toán",
        "not_for": ["chứng từ"],
    },
    "Page.003": {
        "what": "Màn hình có dữ liệu nhạy cảm cần mã hóa, như người dùng, "
                "tài khoản hóa đơn điện tử (~28 trang)",
        "signals": "người dùng, mã hóa, tài khoản hóa đơn điện tử",
        "not_for": ["báo cáo thông thường"],
    },
    "Page.004": {
        "what": "Báo cáo có thêm nút xem đồ thị/biểu đồ (~88 trang)",
        "signals": "báo cáo có đồ thị, biểu đồ",
        "not_for": ["báo cáo không có đồ thị"],
    },
    "Page.005": {
        "what": "Màn hình dạng cây: phân quyền, quản lý menu (~10 trang)",
        "signals": "cây, phân quyền, cấu trúc phân cấp",
        "not_for": ["báo cáo", "chứng từ"],
    },
    "Page.006": {
        "what": "Màn hình cập nhật nhân sự: hợp đồng lao động, bảo hiểm "
                "(~3 trang)",
        "signals": "hợp đồng lao động, bảo hiểm, nhân sự",
        "not_for": ["báo cáo", "chứng từ kế toán"],
    },
    "Page.007": {
        "what": "Màn hình soạn mẫu thư, tin nhắn (~4 trang)",
        "signals": "mẫu thư, mail template, tin nhắn",
        "not_for": ["báo cáo", "chứng từ"],
    },
    "Page.008": {
        "what": "Màn hình thông tin nhân viên chia nhiều khung (~6 trang)",
        "signals": "thông tin nhân viên",
        "not_for": ["báo cáo", "chứng từ kế toán thông thường"],
    },
    "Page.009": {
        "what": "Màn hình khai báo máy chủ mail và mật khẩu (~2 trang)",
        "signals": "khai báo mail server, mật khẩu",
        "not_for": ["mọi trường hợp khác"],
    },
    "Page.010": {
        "what": "Màn hình nhập số dư đầu kỳ (~10 trang)",
        "signals": "số dư đầu kỳ, nhập số dư",
        "not_for": ["báo cáo"],
    },
    "Page.011": {
        "what": "Màn hình duyệt chứng từ, có ký duyệt (~26 trang)",
        "signals": "duyệt chứng từ, approval, ký duyệt",
        "not_for": ["chứng từ nhập liệu thường", "báo cáo"],
    },
    "Page.012": {
        "what": "Chứng từ nhập liệu cơ bản: không ký số, không qua duyệt "
                "(~80 trang)",
        "signals": "chứng từ mới đơn giản, không duyệt, không ký số",
        "not_for": ["chứng từ có ký số", "chứng từ có duyệt", "báo cáo"],
    },
    "Page.013": {
        "what": "Chứng từ nhập liệu có ký số, không qua duyệt: kế toán tổng "
                "hợp, thu chi tiền (~19 trang)",
        "signals": "chứng từ có ký số, không duyệt",
        "not_for": ["chứng từ có duyệt"],
    },
    "Page.014": {
        "what": "Chứng từ có quy trình duyệt và ký số, có khung soạn thảo "
                "nội dung: đơn hàng bán (~13 trang)",
        "signals": "chứng từ có duyệt và ký số, đơn hàng bán",
        "not_for": ["chứng từ không duyệt"],
    },
    "Page.015": {
        "what": "Chứng từ có quy trình duyệt và ký số: mua hàng, yêu cầu, "
                "kế hoạch (~15 trang)",
        "signals": "chứng từ có duyệt và ký số, đơn mua hàng, yêu cầu",
        "not_for": ["chứng từ không duyệt"],
    },
    "Page.016": {
        "what": "Chứng từ có ký số kèm bảng báo cáo con bên dưới: công nợ "
                "phải trả, phải thu (~13 trang)",
        "signals": "chứng từ ký số có báo cáo con",
        "not_for": ["chứng từ có duyệt"],
    },
    "Page.017": {
        "what": "Báo cáo bình thường. Chỉ có lọc dữ liệu và xem dữ liệu",
        "signals": "báo cáo thông thường chỉ lọc và xem",
        "not_for": ["báo cáo tài chính nhiều kỳ có đồ thị",
                    "báo cáo có đồ thị"],
    },
    "Page.018": {
        "what": "Chứng từ tự sinh ra từ chức năng khác: phân bổ, quyết định "
                "sử dụng (~5 trang)",
        "signals": "tự động tạo chứng từ, phân bổ",
        "not_for": ["chứng từ nhập liệu thường"],
    },
    "Page.019": {
        "what": "Chứng từ đơn giản có khung truy vấn đi kèm (~3 trang)",
        "signals": "chứng từ đơn giản có truy vấn",
        "not_for": ["chứng từ thường"],
    },
    "Page.020": {
        "what": "Báo cáo tài chính: bảng cân đối, kết quả kinh doanh, xem "
                "nhiều kỳ hoặc nhiều đơn vị, có đồ thị. Gồm cả các bản "
                "customize từ báo cáo tài chính (vd zcbcdVASIFRS). Rất ít "
                "(~8 trang)",
        "signals": "bảng cân đối VAS/IFRS/US-GAAP, kết quả kinh doanh, báo "
                   "cáo tài chính",
        "not_for": ["bảng kê, sổ sách, báo cáo listing thông thường",
                    "danh mục"],
    },
    "Page.021": {
        "what": "Chứng từ riêng cho bút toán JRTran (1 trang)",
        "signals": "chứng từ JRTran",
        "not_for": ["mọi trường hợp khác"],
    },
    "Page.022": {
        "what": "Chứng từ riêng cho BMTran (1 trang)",
        "signals": "chứng từ BMTran",
        "not_for": ["mọi trường hợp khác"],
    },
    "Page.023": {
        "what": "Màn hình dạng lưới kèm form nhập riêng có mã hóa (1 trang)",
        "signals": "lưới kèm form riêng có mã hóa",
        "not_for": ["mọi trường hợp khác"],
    },
    "Page.024": {
        "what": "Màn hình dạng lưới kèm form nhập riêng (1 trang)",
        "signals": "lưới kèm form riêng",
        "not_for": ["mọi trường hợp khác"],
    },
    "Flow": {
        "what": "Màn hình quy trình (Flow/QRT)",
        "signals": "quy trình, flow, QRT",
        "not_for": ["báo cáo", "danh mục", "chứng từ"],
    },
    "Query": {
        "what": "Màn hình xem ngược số liệu từ một báo cáo khác, không phải "
                "báo cáo chính",
        "signals": "truy vấn số liệu, xem ngược từ báo cáo",
        "not_for": ["báo cáo chính", "danh mục", "chứng từ"],
    },
}


CATEGORY_PAGE = "Page.001"

_REPORT_IDS = ("Page.003", "Page.004", "Page.017", "Page.020", "Query")
_VOUCHER_IDS = ("Page.008", "Page.011", "Page.012", "Page.013", "Page.014",
                "Page.015", "Page.016", "Page.018", "Page.019", "Page.021",
                "Page.022")

REPORT_PAGES: dict[str, dict] = {k: PAGE_TEMPLATES[k] for k in _REPORT_IDS}
VOUCHER_PAGES: dict[str, dict] = {k: PAGE_TEMPLATES[k] for k in _VOUCHER_IDS}
