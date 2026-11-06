"""Câu hỏi Jev cho SP30+.

Lần gọi 1 (chung call tool_help): tạo mới menu? + loại menu (báo cáo/chứng
từ/danh mục). Lần gọi 2 (chỉ khi báo cáo/chứng từ): chọn Page.0xx trong nhóm
tương ứng, state chỉ gồm yêu cầu."""

from tool_help.classify_page.catalog import REPORT_PAGES, VOUCHER_PAGES

IS_NEW_MENU = "is_new_menu"
MENU_KIND = "menu_kind"
PAGE_TEMPLATE = "page_template"

KIND_REPORT = "report"
KIND_VOUCHER = "voucher"
KIND_CATEGORY = "category"

_NEW_MENU_RULE = (
    "Quy tắc xác định:\n"
    "- TRUE (Tạo mới menu): Chứa hành động thêm mới, tạo mới, hoặc "
    "'Gen/Clone/Save as' một menu/chức năng sang menu mới.\n"
    "- FALSE (Không phải tạo mới menu): Chỉ sửa đổi nội dung, thêm nút, "
    "sửa logic tính toán trên một menu/chứng từ đã có sẵn.")

_KIND_DESCRIPTION = (
    "State là dạng hỏi về vấn đề thực hiện 1 yêu cầu trên phần mềm ERP. Khi "
    "yêu cầu là tạo mới 1 menu/chức năng thì menu đó chỉ thuộc 1 trong 3 "
    "dạng: báo cáo, chứng từ hoặc danh mục, dù có bao nhiêu biến thể. Với "
    "Gen/Clone/Save as từ menu nguồn thì phân loại theo loại của menu nguồn "
    "(vd Gen từ 'Bảng cân đối', 'Bảng kê', 'Sổ chi tiết' = báo cáo; Gen từ "
    "'Phiếu thu', 'Hóa đơn', 'Đơn hàng' = chứng từ; Gen từ 'Vào số dư' hoặc "
    "'Khai báo ...' = danh mục). Ví dụ tạo chức năng "
    "lấy các chứng từ xuất kho và có nút tạo chứng từ bán hàng thì chức "
    "năng này là báo cáo (lọc chọn rồi tạo ra thứ khác).")

_KIND_PAGES = {KIND_REPORT: ("BÁO CÁO", REPORT_PAGES),
               KIND_VOUCHER: ("CHỨNG TỪ", VOUCHER_PAGES)}

_PAGE_RULES = {
    KIND_REPORT: "Báo cáo bình thường chỉ lọc và xem dữ liệu. Báo cáo tài "
                 "chính như bảng cân đối, kết quả kinh doanh là loại riêng. "
                 "Nếu là save-as/gen từ báo cáo nguồn thì chọn loại giống "
                 "báo cáo nguồn. Không có Page nào thật sự khớp thì để xác "
                 "suất thấp, đừng ép.",
    KIND_VOUCHER: "Phân biệt chứng từ có ký số hay không, có qua duyệt hay "
                  "không, có báo cáo con hay không. Không có Page nào thật "
                  "sự khớp thì để xác suất thấp, đừng ép.",
}


def build_questions() -> dict:
    """Câu hỏi gộp vào lần gọi Jev chính."""
    return {
        IS_NEW_MENU: {
            "type": "noul",
            "instructions": {
                "description": _NEW_MENU_RULE,
                "question": "Yêu cầu trên State thuộc trường hợp tạo mới "
                            "menu (TRUE) hay chỉ chỉnh sửa chức năng có "
                            "sẵn (FALSE)?",
            },
            "criteria": {
                "true": "tạo mới/thêm mới/Gen/Clone/Save as sang menu mới",
                "false": "chỉ sửa nội dung, thêm nút, sửa logic trên "
                         "menu/chứng từ có sẵn",
            },
        },
        MENU_KIND: {
            "type": "choice",
            "instructions": {
                "description": _KIND_DESCRIPTION,
                "question": "Menu cần tạo mới trong State là dạng báo cáo, "
                            "chứng từ hay danh mục trên ERP?",
            },
            "criteria": {
                KIND_REPORT: "Báo cáo, bảng kê, sổ sách, bảng cân đối, "
                             "tiện ích/chức năng đặc thù: có bộ lọc (Filter) "
                             "rồi hiển thị/tạo ra kết quả trên lưới. Gồm cả "
                             "chức năng lọc chọn dữ liệu rồi tạo thứ gì đó.",
                KIND_VOUCHER: "Tạo chứng từ mới. Thường state mô tả chức "
                              "năng có lưới chi tiết (grid, detail), số "
                              "phiếu hoặc số chứng từ, ngày chứng từ, hạch "
                              "toán. Nói chung là nhìn giống 1 cái chứng "
                              "từ hoặc State nhắc thẳng là tạo chứng từ.",
                KIND_CATEGORY: "Là dạng danh mục. Tạo 1 chức năng có thể "
                               "thêm, xóa, sửa, import data (danh mục khách "
                               "hàng, vật tư, tài khoản, tham số...). Menu "
                               "'Vào số dư' (nhập số dư đầu kỳ) và các menu "
                               "'Khai báo ...' (khai báo bút toán kết "
                               "chuyển, diễn giải chứng từ tự động, bảng "
                               "cân đối, báo cáo kết quả kinh doanh...) "
                               "cũng là dạng danh mục.",
            },
        },
    }


def page_questions(kind: str) -> dict | None:
    """Câu hỏi cho lần gọi Jev thứ 2: chỉ list Page của nhóm `kind`."""
    if kind not in _KIND_PAGES:
        return None
    label, pages = _KIND_PAGES[kind]
    return {
        PAGE_TEMPLATE: {
            "type": "choice",
            "instructions": {
                "question": f"Menu cần tạo là {label}: đâu là Page (template "
                            "trang SP30+) gần đúng với yêu cầu trong State "
                            "nhất?",
                "rules": _PAGE_RULES[kind],
            },
            "criteria": pages,
        },
    }
