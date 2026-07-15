from enum import Enum

class EdgeType(str, Enum):
    ENTITY_INCLUDE = "ENTITY_INCLUDE"       # File XML include file Entity/Txt khác qua DTD SYSTEM
    PARAM_ENTITY_USE = "PARAM_ENTITY_USE"   # File XML dùng parameter entity (%Invoice;)
    SQL_TABLE_USE = "SQL_TABLE_USE"         # File XML/SQL thao tác với bảng DB
    SQL_PROC_CALL = "SQL_PROC_CALL"         # File XML/SQL gọi Stored Procedure
    JS_FUNC_CALL = "JS_FUNC_CALL"           # Script JS gọi hàm/sự kiện
    SHARED_INCLUDE = "SHARED_INCLUDE"       # Hai hay nhiều file dùng chung một file include
    
    # Mới: Mối quan hệ đặc thù trong FBO
    GRID_MASTER_DETAIL = "GRID_MASTER_DETAIL"     # Master Dir -> Detail Grid (e.g. CPTran -> CPDetail)
    RETRIEVE_DATA_SOURCE = "RETRIEVE_DATA_SOURCE" # Detail Grid -> Retrieve Filter/Grid/Lookup/Form (e.g. CPDetail -> CPRequestFilter, CPRequestGrid)
    LOOKUP_REFERENCE = "LOOKUP_REFERENCE"         # Field -> Lookup controller (e.g. ma_kh -> Customer)
    COMPANION_FILE = "COMPANION_FILE"             # File cùng tên ở các folder khác nhau (e.g. Dir/SVTran <-> Filter/SVTran)

# Định nghĩa mô tả cho các loại mối quan hệ để Agent dễ hiểu
EDGE_DESCRIPTIONS = {
    EdgeType.ENTITY_INCLUDE: "Include trực tiếp file cấu hình bổ sung qua thực thể SYSTEM XML",
    EdgeType.PARAM_ENTITY_USE: "Sử dụng tham số thực thể (Parameter Entity) để kế thừa cấu trúc",
    EdgeType.SQL_TABLE_USE: "Thao tác truy vấn hoặc ghi dữ liệu xuống bảng SQL Server",
    EdgeType.SQL_PROC_CALL: "Thực thi thủ tục lưu trữ (Stored Procedure) trên SQL Server",
    EdgeType.JS_FUNC_CALL: "Gọi thực thi hàm Javascript trên Client-side",
    EdgeType.SHARED_INCLUDE: "Dùng chung tài nguyên/file cấu hình với controller khác",
    EdgeType.GRID_MASTER_DETAIL: "Mối quan hệ Master - Detail (ví dụ: CPTran liên kết với chi tiết CPDetail)",
    EdgeType.RETRIEVE_DATA_SOURCE: "Nguồn lấy dữ liệu của Detail (ví dụ: CPDetail lấy dữ liệu từ CPRequestFilter/CPRequestGrid)",
    EdgeType.LOOKUP_REFERENCE: "Trường dữ liệu tham chiếu đến danh mục Lookup (ví dụ: ma_kh tham chiếu đến Customer)",
    EdgeType.COMPANION_FILE: "Các file cùng tên ở các phân hệ khác nhau đại diện cho cùng một nghiệp vụ (ví dụ: Dir/SVTran và Filter/SVTran)",
}

