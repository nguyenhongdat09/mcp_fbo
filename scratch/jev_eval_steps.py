"""Golden set cấp STEP cho tool_help — step thật lấy từ call log
(E:\\fastbusiness_mcp\\logs, 16/9–9/10/2026, mẫu phân tầng 1/6 trên 434
step distinct). Nhãn gán tay; ``ok`` = list task_type chấp nhận (step mơ
hồ cho phép nhiều đáp án — phần tử đầu là đáp án tốt nhất).

Dùng bởi ``jev_eval.py --steps-set`` để A/B prompt_style v1↔v2 và
routing flat↔hierarchical. Thêm case: append dict, giữ id tăng dần.
"""

STEP_CASES = [
    {"id": "S000", "step": "Tìm file nào chứa chuỗi 'dmku' trong project",
     "ok": ["grep_content"]},
    {"id": "S006", "step": "Lấy old_string để sửa block command Inserting "
                           "trong Dir/zccntttdcd.xml",
     "ok": ["read_suggest_edit"]},
    {"id": "S012", "step": "Clone bộ controller quydmgtt sang tên mới",
     "ok": ["copy_files", "save_as_existing"]},
    {"id": "S018", "step": "Check trên DB xem bảng của danh mục mới đã tồn "
                           "tại chưa và xem cấu trúc bảng danh mục khế ước",
     "ok": ["db_object", "db_list_tables"]},
    {"id": "S024", "step": "Đọc summary file Filter/zccntttdcdImport.xml "
                           "(đã biết path)",
     "ok": ["read_summary"]},
    {"id": "S030", "step": "Tạo bộ file Dir/Grid/Filter Import/Templates "
                           "Upload cho controller danh mục mới",
     "ok": ["clone_template"]},
    {"id": "S036", "step": "Đọc file Grid/PLHNDTDetail.xml quanh field dvt, "
                           "path đã biết App_Data/Controllers/Grid/"
                           "PLHNDTDetail.xml",
     "ok": ["read_snippet"]},
    {"id": "S042", "step": "Tìm các form import tương tự có hàm Retrieve "
                           "Data gọi _removeRowNumber",
     "ok": ["grep_content", "find_references"]},
    {"id": "S048", "step": "Sinh script SQL tạo bảng và view cho danh mục "
                           "zccnsldkbctd",
     "ok": ["new_sql_file", "no_match"]},
    {"id": "S054", "step": "Tra schema bảng chi tiết phương thức thanh toán "
                           "của chứng từ PLH",
     "ok": ["db_object"]},
    {"id": "S066", "step": "Đọc nội dung file Dir/SOTran.xml đã biết path",
     "ok": ["read_flat", "read_summary"]},
    {"id": "S072", "step": "Đọc cấu trúc file ISDetail.xml và ISTran.xml đã "
                           "biết path",
     "ok": ["read_summary"]},
    {"id": "S078", "step": "Tìm trong DB xem đã có bảng hoặc view nào tên "
                           "zcccckkm hoặc tương tự liên quan ckkm chưa",
     "ok": ["db_list_tables", "db_search"]},
    {"id": "S084", "step": "Chạy test thử nghiệm thủ tục báo cáo "
                           "rs_zccndhctp và tạo xóa chứng từ "
                           "zc_zccndhctp_CreateVoucher "
                           "zc_zccndhctp_DeleteVoucher",
     "ok": ["db_run_sql"]},
    {"id": "S090", "step": "Kiểm tra cú pháp file chubb_sp2264 (8).sql sau "
                           "khi format",
     "ok": ["db_check_syntax"]},
    {"id": "S096", "step": "Đọc file DDVDetail.xml và PLHDetail.xml để kiểm "
                           "tra sự kiện onChange khi nhập ma_vt load giá "
                           "bán thế nào",
     "ok": ["read_snippet", "read_summary"]},
    {"id": "S102", "step": "Đọc nội dung hiện tại của action Item và UOM "
                           "trong DDVDetail.xml và PLHDetail.xml",
     "ok": ["read_snippet"]},
    {"id": "S108", "step": "Đọc nội dung file SQL c:\\Users\\Windows 10\\"
                           ".gemini\\config\\skills\\SQL Temp\\"
                           "chubb_sp2264 (9).sql",
     "ok": ["read_raw"]},
    {"id": "S114", "step": "Tìm chứng từ PXA mẫu đang gán ma_nx ma_gd ma_kh "
                           "ma_bp",
     "ok": ["db_run_sql"]},
    {"id": "S120", "step": "Đọc script Loading và formula của Grid/"
                           "ISDetail.xml quanh array index",
     "ok": ["read_snippet"]},
    {"id": "S126", "step": "Đọc snippet hàm JS trong QM1Tran.xml chứa "
                           "addGridFields / addTotalFields / "
                           "set_referenceFields (đã biết tên hàm JS)",
     "ok": ["read_snippet", "find_definition"]},
    {"id": "S132", "step": "Lấy nội dung stored procedure in "
                           "GC_rs_PrintSITran từ Database ra để tham khảo "
                           "cấu trúc trả về",
     "ok": ["paste_sql"]},
    {"id": "S138", "step": "Tìm proc/view nào trong sys DB xử lý quyền menu "
                           "theo user (menu rights) liên quan "
                           "commandArgument hoặc menuItem",
     "ok": ["db_search"]},
    {"id": "S144", "step": "Tra bảng tbtttb xem dòng mã thiết bị TUANSM02 "
                           "có tồn tại, status, bộ phận, đơn vị nào",
     "ok": ["db_run_sql"]},
    {"id": "S150", "step": "Tìm chuỗi zvtbtttb trong thư mục Grid của "
                           "project SP2261",
     "ok": ["grep_content"]},
    {"id": "S156", "step": "Tra proc nào trong DB tham chiếu bảng d14$ và "
                           "bảng đơn hàng bán để lấy người order, số PO",
     "ok": ["db_search"]},
    {"id": "S162", "step": "Check proc rs_GetInputInvoiceData trong DB có "
                           "xử lý ma_ct PK1 hay không (lấy proc ra đọc)",
     "ok": ["paste_sql", "db_snippet", "db_object"]},
    {"id": "S168", "step": "Đọc cặp Dir/zcdmtd2.xml và Grid/zcdmtd2.xml đã "
                           "biết path làm mẫu danh mục có nhóm Cost Center",
     "ok": ["read_summary", "read_flat"]},
    {"id": "S174", "step": "Đọc summary Filter/zcbcallvncp.xml đã biết path",
     "ok": ["read_summary"]},
    {"id": "S180", "step": "Đọc entity list trong Dir/APTran.xml để check "
                           "entity InputInvoice/FlowMulti chưa khai báo",
     "ok": ["entity_list", "entity_check"]},
    {"id": "S192", "step": "Đọc snippet file SQL đã biết path quanh dòng "
                           "90-140 để xem cột pxa_created_yn/status_ct_desc",
     "ok": ["read_snippet", "read_raw"]},
    {"id": "S198", "step": "Tìm proc DB dùng bảng r00$ và tạo bút toán "
                           "trích lãi/đánh giá",
     "ok": ["db_search"]},
    {"id": "S204", "step": "Clone function fsd_GetSQLInsert từ DB ra file "
                           ".sql để đọc cách dùng",
     "ok": ["paste_sql"]},
    {"id": "S210", "step": "Đọc file SQL c:\\Users\\Windows 10\\.gemini\\"
                           "config\\skills\\SQL Temp\\chubb_sp2264 (13).sql "
                           "quanh dòng 130-170",
     "ok": ["read_snippet", "read_raw"]},
    {"id": "S216", "step": "Đọc summary Dir/SVTran.xml và Dir/SOTran.xml tìm "
                           "cột liên kết đơn hàng và so_po",
     "ok": ["read_summary"]},
    {"id": "S222", "step": "Query bảng options (app DB) lấy dòng name = "
                           "'m_service_api' của project Newpearl/R2SP223 "
                           "(chỉ đọc, SELECT)",
     "ok": ["db_run_sql"]},
    {"id": "S228", "step": "Clone save-as controller "
                           "rptBalanceSheetMultiPeriod sang zcssbcdkt "
                           "(clone suite file + export proc ra .sql)",
     "ok": ["save_as_existing"]},
    {"id": "S234", "step": "Check bảng zctmssbcdkt có cột chi_tieu2 hay cột "
                           "tên khác cho chỉ tiêu tiếng Hoa",
     "ok": ["db_object"]},
    {"id": "S240", "step": "Đọc summary Dir/CashFlowD.xml đã biết path để "
                           "xem field cach_tinh và khai báo chỉ tiêu",
     "ok": ["read_summary"]},
    {"id": "S246", "step": "Đọc snippet hàm JS theo symbol onChange xử lý "
                           "chọn số hóa đơn",
     "ok": ["read_snippet", "find_definition"]},
    {"id": "S258", "step": "Check syntax file haohoa_fbisp2421 (3).sql trước "
                           "khi báo user",
     "ok": ["db_check_syntax"]},
    {"id": "S264", "step": "Sửa field dept_id và layout category trong file "
                           "\\\\172.168.5.14\\CustomerPro\\FBI\\HAOHOA\\"
                           "FBISP2421\\App_Data\\Controllers\\Dir\\"
                           "DDVTran.xml để ẩn trường bộ phận",
     "ok": ["read_suggest_edit"]},
    {"id": "S270", "step": "Tìm file chứa chuỗi 'zcttthd' hoặc báo cáo mẫu "
                           "có nút tạo chứng từ từ grid báo cáo trong "
                           "project REP",
     "ok": ["grep_content"]},
    {"id": "S276", "step": "Tìm file Grid tương ứng của "
                           "rptBIPurchaseInvoiceList",
     "ok": ["match_filename"]},
    {"id": "S282", "step": "Tìm file chứa chuỗi rptTransactionList trong "
                           "project để biết các file liên quan",
     "ok": ["grep_content"]},
    {"id": "S288", "step": "Đọc nội dung file TSCreateMultiGrid.f được "
                           "clone ra .xml",
     "ok": ["read_raw", "read_flat"]},
    {"id": "S294", "step": "Tìm trong file Dir/PRTran.xml (đã biết path) các "
                           "khối khai báo tab Duyệt (grid duyệt, field, "
                           "category, view)",
     "ok": ["read_snippet", "grep_content"]},
    {"id": "S300", "step": "Đọc summary 4 file Dir (DC2Tran, tbbddk, tbscdk, "
                           "TL2Tran) đã biết path để xem hệ duyệt APV hay PR",
     "ok": ["read_summary"]},
    {"id": "S312", "step": "Đọc summary Grid/zccnslkdhtpnc.xml mẫu SP228 (đã "
                           "biết path) để xem cách gom tag chọn dòng và gọi "
                           "acceptSendMail",
     "ok": ["read_summary"]},
    {"id": "S318", "step": "Kiểm tra cấu hình ràng buộc đơn vị cơ sở (dvcs) "
                           "cho lookup trong DDVTran.xml",
     "ok": ["read_snippet", "read_summary"]},
    {"id": "S324", "step": "Lấy proc zc_rptQueryStockCard ra file .sql để "
                           "đối chiếu logic detail với summary",
     "ok": ["paste_sql"]},
    {"id": "S330", "step": "Đọc summary Grid/APTax.xml (đã biết path)",
     "ok": ["read_summary"]},
    {"id": "S336", "step": "Sửa thứ tự cột trong file xml bằng Edit",
     "ok": ["read_suggest_edit"]},
    {"id": "S354", "step": "Tìm proc zc_ttthdcctk trong DB và xuất ra file "
                           ".sql dạng ALTER để tham khảo",
     "ok": ["paste_sql", "db_search"]},
    {"id": "S360", "step": "Đọc file sql zc_printplhtranpl.sql đã biết path "
                           "(proc in mẫu PLH)",
     "ok": ["read_raw"]},
    {"id": "S366", "step": "Tra bảng CTKM trong DB để check cột số bàn tối "
                           "thiểu, loại hình tiệc, thứ trong tuần, sảnh, "
                           "nhóm khách hàng",
     "ok": ["db_object"]},
    {"id": "S372", "step": "Tạo file .sql mới trong sql_temp_folder để viết "
                           "script ALTER thêm cột sua_gt cho các bảng "
                           "partition dplhndt$/dplh$/dplhtk$",
     "ok": ["new_sql_file", "db_add_field"]},
    {"id": "S378", "step": "Đọc file Report/PLHTran.xml để xem khai báo form "
                           "in hiện có",
     "ok": ["read_raw"]},
    {"id": "S384", "step": "Tìm trong file Dir/CashFlowD.xml (đã biết path) "
                           "chuỗi 'as kind_note' để sửa lỗi cú pháp SQL",
     "ok": ["read_snippet", "read_suggest_edit", "grep_content"]},
    {"id": "S390", "step": "Đọc file SQL đã biết path c:\\Users\\Windows 10\\"
                           ".gemini\\config\\skills\\SQL Temp\\"
                           "haohoa_fbisp2421 (4).sql",
     "ok": ["read_raw"]},
    {"id": "S396", "step": "Query DB lấy giá trị distinct status, u_status "
                           "của bảng mddv$000000 và các mã giao dịch ma_gd",
     "ok": ["db_run_sql"]},
    {"id": "S402", "step": "Đọc raw file Filter/PLHMenuForm.xml để xem view/"
                           "category và JS resize",
     "ok": ["read_raw", "read_flat"]},
    {"id": "S408", "step": "Tìm file chứa chuỗi LoadContract/"
                           "LoadAppendixData để biết JS nào gọi f.request "
                           "các action này",
     "ok": ["grep_content", "find_references"]},
    {"id": "S414", "step": "Query bảng emailcontent trong DB sys để xem nội "
                           "dung error_log đầy đủ",
     "ok": ["db_run_sql"]},
    {"id": "S420", "step": "Đọc summary file Dir/GLTran.xml (đã biết path) "
                           "để nắm tab Thuế, tab chi tiết, tệp đính kèm, "
                           "ngày hạch toán",
     "ok": ["read_summary"]},
    {"id": "S426", "step": "Query DB app liệt kê bảng có tên kết thúc $log "
                           "(vd m11$log) và xem cấu trúc cột",
     "ok": ["db_list_tables"]},
    {"id": "S432", "step": "Query bảng m/d/c của DHN trong DB để check cột "
                           "phí dv-tn đã có chưa",
     "ok": ["db_object", "db_run_sql"]},
]
