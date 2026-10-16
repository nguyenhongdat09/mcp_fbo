"""Notice rules — nhắc nhỏ nhỏ đính kèm response tool_help để agent không
quên convention/skill bắt buộc.

Mỗi rule:
    id      : định danh duy nhất (debug)
    text    : nội dung notice (hiển thị nguyên văn cho agent)
    task_types : set task_type — notice xuất hiện khi response route ≥1 step
              vào task_type trong set (None = không check)
    requirements : set requirement_type — xuất hiện khi classify trúng
              (None = không check)
    ur_pattern : regex (str) — xuất hiện khi match UR/steps text thô
              (vd bắt id 'zcjgkka' trong yêu cầu)
    always  : True = luôn đính kèm

Rule kích hoạt khi THỎA ÍT NHẤT 1 điều kiện có khai (task_types ∩ used ≠ ∅,
requirement ∈ requirements, ur_pattern match, always). Rule không khai điều kiện nào và
always=False → không bao giờ kích hoạt (nháp).

Thêm notice mới = thêm 1 entry vào NOTICE_RULES — không sửa code.
"""

_SQL_TASK_TYPES = {"db_run_sql", "db_run_file", "db_object", "db_add_field",
                   "db_check_syntax", "clone_data", "clone_sql", "paste_sql",
                   "new_sql_file", "save_as_existing", "db_balance"}
_VOUCHER_TYPES = {
    "voucher",
    "voucher_normal_no_currency",
    "voucher_normal_currency",
    "voucher_approval_no_currency",
    "voucher_approval_currency",
}

_RETRIEVE_TYPES = {"retrieve_flow_parition_table",
                   "retrieve_flow_single_table"}
_REPORT_TYPES = {"report_normal", "report_check", "report_mau",
                 "report_pivot"}
_CATEGORY_TYPES = {"category_1_key", "category_multi_key",
                   "category_1_key_detail", "category_multi_key_detail"}

NOTICE_RULES = [
    {
        "id": "mcp_first",
        "text": "FBO: nếu IDE có sẵn grep/search đã indexing file (vd "
                "Cursor) thì ưu tiên dùng IDE — nhanh và tiện hơn; nếu "
                "không thì dùng tool MCP (read_local_file, search_files, "
                "query_database, clone_things...) — KHÔNG chạy shell/"
                "grep/find thô trên đường dẫn UNC của project",
        "always": True,
    },
    {
        "id": "sql_style",
        "text": 'Nếu cần viết proc, sql xin hãy tuân thủ skill '
                '"fbo-style-sql"',
        "task_types": _SQL_TASK_TYPES,
        "requirements": _VOUCHER_TYPES | _RETRIEVE_TYPES,
    },
    {
        "id": "sql_sign",
        "text": "Khi SỬA/TẠO proc, function, view, trigger → đặt comment "
                "ký tên --{user_name} ngay TRƯỚC dòng AS (sau phần khai "
                "báo tham số, trước AS BEGIN) để các dev khác biết ai "
                "đang sửa object đó",
        "task_types": _SQL_TASK_TYPES,
        "requirements": _VOUCHER_TYPES | _RETRIEVE_TYPES,
    },
    {
        "id": "sql_temp_file",
        "text": "Cần VIẾT SQL ra file .sql (proc/script mới để user F5) → "
                "clone_things type=5 (project_source=<abs path project>, "
                "để trống path_to_pasted) tạo file trong sql_temp_folder "
                "rồi Edit/Write vào đó — TUYỆT ĐỐI không tạo .sql trực "
                "tiếp trong workspace/project",
        "task_types": _SQL_TASK_TYPES,
        "requirements": (_VOUCHER_TYPES | _RETRIEVE_TYPES
                         | _REPORT_TYPES | _CATEGORY_TYPES),
    },
    {
        "id": "sql_proc_report_skill",
        "text": "Xử lý liên quan tạo/sửa proc báo cáo (rs_*, zc_*, print "
                "proc...) → tham khảo skill fbo-procedure-create-report "
                "(4 vùng Struct/Key/Data/Processing, partition load, "
                "drill số CT, tag chọn in)",
        "task_types": _SQL_TASK_TYPES,
        "requirements": _REPORT_TYPES,
    },
    {
        "id": "schema_check",
        "text": "Phiên bản FBO khác nhau thiếu bảng/cột — trước khi "
                "INSERT/ALTER phải check OBJECT_ID + schema thật của "
                "project đích, không hardcode danh sách cột mà không "
                "đối chiếu",
        "task_types": _SQL_TASK_TYPES,
        "requirements": _VOUCHER_TYPES | _RETRIEVE_TYPES,
    },
    {
        "id": "verify_parse",
        "text": "Trước khi kết thúc: PARSEONLY mọi script SQL viết ra + "
                "get_xml_entities checking mọi file XML controller đã sửa "
                "(bắt entity khai thiếu / CDATA lệch)",
        "task_types": {"paste_sql", "clone_sql", "new_sql_file",
                       "save_as_existing"},
        "requirements": _VOUCHER_TYPES | _RETRIEVE_TYPES,
    },
    {
        "id": "balance_procs",
        "text": "Tính/lấy số dư·tồn·công nợ → dùng proc nội bộ "
                "FastBusiness$Balance$<Dim>/$OpeningBalance$*, TUYỆT ĐỐI "
                "không tự SUM trên bảng raw (r00$/cdtk$/cdkh/r70$/r90$/"
                "wrkgl/dmtk0). Hầu hết đổ kết quả vào #t — chép cách gọi "
                "+schema #t từ proc/report đang gọi nó (query_database "
                "mode=search references='<proc>'). Params khác theo "
                "version/variant (_KhanhTd/z*/_goc) → mode=summary verify "
                "trên DB đích trước khi EXEC. Post sổ chứng từ là nhóm "
                "fs_Post*/Voucher$Posting$* — không phải $Balance$",
        "task_types": {"db_balance"},
    },
    {
        "id": "save_as_flow",
        "text": "SAVE-AS chức năng có sẵn: clone_things type=6 "
                "'saveas:title:<tiêu đề>-><new>' tự resolve controller + "
                "clone suite + export proc; tool tự quét <title> trên "
                "disk; không thấy → HỎI USER file nguồn, đừng đoán. Proc export giữ NGUYÊN tên nguồn "
                "— đổi tên tay trong .sql + sửa <title v> + đăng ký "
                "menu/aspx",
        "task_types": {"save_as_existing", "find_by_title"},
        "requirements": {"clone_existing"},
    },
    {
        "id": "voucher_partition",
        "text": "Bảng chứng từ partition theo tháng: m/d/i{x}$YYYYMM — "
                "insert/query phải đúng partition; c{x}$000000 giữ ngày "
                "gốc; sysfilterdeclares phải là m{x}$%Partition của CT mới",
        "requirements": _VOUCHER_TYPES | _RETRIEVE_TYPES,
    },
    {
        "id": "voucher_no_structure",
        "text": "KHÔNG tạo Structure/App/*.xml tay — hệ thống tự sinh khi "
                "đăng ký bảng; file .aspx đặt ở project-root Main/ (KHÔNG "
                "phải App_Data/Controllers)",
        "requirements": _VOUCHER_TYPES | _RETRIEVE_TYPES,
    },
    {
        "id": "voucher_append_config",
        "text": "Nếu đối tượng là CHỨNG TỪ (voucher): file config chung "
                "chỉ APPEND dòng/block mới — TUYỆT ĐỐI không overwrite "
                "hay sửa entry chứng từ khác. Đủ bộ gồm: Include/"
                "Extender.ent (CẢ nhánh List lẫn Post), Filter/Config/"
                "Initialize.xml (<controller group=\"Aggregation."
                "Voucher\">), Grid/Config/Aggregation.* (voucher thường "
                ".v — grep tên controller mẫu trong Aggregation.* để "
                "chọn đúng file/đuôi theo project), Grid/Config/Include/"
                "Voucher.Controller.* (append vào ĐÚNG file .00x đang "
                "chứa controller mẫu), Post/Post.xml (<view controller="
                "\"{X}Tran\" table=\"m{x}$000000\" key=\"stt_rec\"/> — "
                "thiếu thì phiếu không có feed Post/comment), Options/"
                "Message.xml (nếu có duyệt). Save-as (type=6) KHÔNG tự "
                "đăng ký mấy chỗ này — grep tên controller nguồn để "
                "biết phải append ở đâu",
        "requirements": _VOUCHER_TYPES | {"clone_existing"},
    },
    {
        "id": "voucher_gn_apv",
        "text": "Chứng từ duyệt phổ biến dùng bảng gn* (gndmkieuduyet, "
                "gndmloaiduyet, gndmttcttg, gndmquyenct, gnctkieuduyet, "
                "dmctduyet) + proc FastBusiness$APV$PostAuthorize/"
                "UnPostAuthorize KHÔNG prefix — không dùng bộ PU$/SO$",
        "requirements": {"voucher_approval_no_currency",
                         "voucher_approval_currency"},
    },
    {
        "id": "voucher_template_drift",
        "text": "Nếu task này là tạo chứng từ mới từ template: template "
                "chứng từ hiện tại là template mới nhất — có "
                "thể không phù hợp một vài thứ so với dự án đang làm "
                "(vd thiếu entity). Phải double check lại entity bằng "
                "tool cho đến khi parse XML (vd hàm get_xml_entities), "
                "và đối chiếu với các chứng từ *Tran khác như "
                "Dir/SVTran.xml, Grid/SVTran.xml, Grid/SVDetail.xml để "
                "soi lại 1 lần nữa. Sau đó clear hết các comment hướng "
                "dẫn có sẵn trên các XML mà clone_things đã clone ra; "
                "đồng thời double check các SQL liên quan đến phiên "
                "bản này — rồi mới bàn giao cho user",
        "requirements": _VOUCHER_TYPES,
    },
    {
        "id": "report_aggregation",
        "text": "Tạo báo cáo → nhớ APPEND <controller name=\"{report_id}\" "
                "description=\"...\"/> vào Grid/Config/Aggregation.xml — "
                "thiếu thì grid báo cáo không hiện dòng tổng ở footer",
        "requirements": _REPORT_TYPES | _VOUCHER_TYPES,
    },
    {
        "id": "proc_name_underscore",
        "text": "ID trong yêu cầu dạng 'zcxxxx'/'rsxxxx' (không gạch dưới) "
                "→ tên proc/object chuẩn phải CHÈN '_' sau prefix: "
                "zc_xxxx / rs_xxxx (vd zcjgkka → zc_jgkka). KHÔNG tạo "
                "proc trùng nguyên id không gạch — xem "
                "proc_name_suggestions trong response cho tên đã chuẩn hóa",
        "ur_pattern": r"\b(?:zc|rs)(?!_)[a-z0-9]{3,}\b",
    },
    {
        "id": "report_graph_button",
        "text": "Chức năng có nút Đồ thị cần đủ bộ: aspx phải "
                "LoadControl(\"Chart.ascx\") (thiếu → lỗi JS "
                "'chart$Graph$InitObject is not defined'), Grid cần entity "
                "Identification + GraphReportInit + button "
                "command=\"Graph\", Filter {X}Graph.xml. File *Graph.xml "
                "clone theo prefix chỉ đổi TÊN — nội dung vẫn trỏ "
                "entity/Identification nguồn, sửa tay sau clone",
        "ur_pattern": r"đồ\s*thị|\bgraph\b|\bchart\b",
    },
    {
        "id": "excel_pivot_template",
        "text": "Mẫu in Excel/pivot (Templates/Excel *.xlsx): clone mẫu "
                "gốc bằng clone_things type=3 rồi sửa bằng excel-mcp; "
                "token mẫu: ?h_xxx (header trong Report XML), !N.field "
                "(field recordset N), #...+ +... (biểu thức nối chuỗi); "
                "cell pivot bị đổi caption tay → MissingItemsLimit=None + "
                "refresh 2 lần — xem skill fbo-excel-pivot-template",
        "ur_pattern": r"excel|\.xlsx|pivot|mẫu\s*in|templatefile",
    },
]


def _user_name() -> str:
    """user_name từ config (config.yaml + config_path.yaml merge)."""
    try:
        from fastbusiness_mcp.mcp_app import get_config
        return str(get_config().get("user_name") or "")
    except Exception:
        return ""


def collect_notices(used_task_types: set | None,
                    requirement_type: str | None = None,
                    ur_text: str = "") -> dict:
    """Trả {"1": text, "2": text, ...} các rule khớp — giữ thứ tự khai báo.
    {user_name} trong text được thay bằng config user_name (thiếu →
    placeholder nhắc cấu hình)."""
    import re
    used_task_types = used_task_types or set()
    uname = _user_name() or "<user_name — khai trong config_path.yaml>"
    hit = [
        r["text"].replace("{user_name}", uname)
        for r in NOTICE_RULES
        if r.get("always")
        or (r.get("task_types") and r["task_types"] & used_task_types)
        or (r.get("requirements")
            and requirement_type in r["requirements"])
        or (r.get("ur_pattern") and ur_text
            and re.search(r["ur_pattern"], ur_text, re.I))
    ]
    return {str(i): t for i, t in enumerate(hit, 1)}
