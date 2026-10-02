"""Catalog proc số-dư nội bộ FastBusiness — nguồn cho task_type db_balance.

Harvest chuẩn từ FBISP24 (AnNhien_FBISP24_A). Tên proc là STABLE framework;
params/schema #t/project-variant THAY ĐỔI theo version — card/notice luôn
bắt agent verify trên DB đích (mode=search '%$Balance$%' + mode=summary).

Hai nhóm:
- BALANCE_PROCS         : đọc/tính số dư — kết quả đổ vào #t (caller tự tạo
                          schema) hoặc trả result set (vd Investment).
- OPENING_BALANCE_PROCS : ghi/cập nhật số dư đầu kỳ.
"""
from __future__ import annotations

# Param contract chung (tham khảo — verify trên DB đích trước khi EXEC):
COMMON_PARAMS = ("@Date @Unit <dims> @BalanceType @ResultType [@DataType] "
                 "@UserID @Admin @JoinClause @WhereClause")

# proc suffix (sau 'FastBusiness$Balance$') -> {dims, purpose}
BALANCE_PROCS: dict[str, dict] = {
    # --- tồn kho ---
    "Item": {"dims": ["Site", "Item", "DataType"],
             "purpose": "Tồn kho theo vật tư + kho (r70$/r90$)"},
    "Lot": {"dims": ["Site", "Lot", "Item", "DataType"],
            "purpose": "Tồn theo lô + kho + vật tư"},
    "Location": {"dims": ["Site", "Location", "Item", "DataType"],
                 "purpose": "Tồn theo vị trí + kho + vật tư"},
    "LocationLot": {"dims": ["Site", "Location", "Lot", "Item",
                             "DataType", "GroupClause", "Statement"],
                    "purpose": "Tồn theo vị trí + lô chi tiết"},
    "SiteLocationItemLot": {"dims": ["Site", "Location", "Lot", "Item",
                                     "DataType", "GroupClause", "Statement"],
                            "purpose": "Tồn full granularity "
                                       "kho/vị trí/lô/vật tư"},
    "ItemAccount": {"dims": ["Item", "Account"],
                    "purpose": "Dư/tồn theo vật tư × tài khoản "
                               "(thường là variant project, vd z*ItemAccount)"},
    # --- sổ cái / GL ---
    "Account": {"dims": ["Account"],
                "purpose": "Dư tài khoản sổ cái (r00$/dmtk0)"},
    "AccountUnit": {"dims": ["Account"],
                    "purpose": "Dư tài khoản group theo đơn vị"},
    "DCAccount": {"dims": ["Account", "Customer"],
                  "purpose": "Dư TK theo khách hàng (KHÔNG có @ResultType)"},
    # --- công nợ / đối tượng ---
    "Customer": {"dims": ["Account", "Customer"],
                 "purpose": "Công nợ khách hàng (cdkh)"},
    "Customer2": {"dims": ["Account", "Customer"],
                  "purpose": "Công nợ KH variant 2 (param rộng hơn)"},
    "CustomerUnit": {"dims": ["Account", "Customer"],
                     "purpose": "Công nợ KH group theo đơn vị"},
    "Contract": {"dims": ["Account", "Contract"],
                 "purpose": "Dư theo hợp đồng"},
    "ContractUnit": {"dims": ["Account", "Contract"],
                     "purpose": "Dư hợp đồng group theo đơn vị"},
    "ContractCustomer": {"dims": ["Account", "Contract", "Customer"],
                         "purpose": "Dư hợp đồng × khách hàng"},
    "BContract": {"dims": ["Account", "BContract", "ContractType",
                           "GroupByContract"],
                  "purpose": "Dư hợp đồng ngân hàng (+loại HĐ, group)"},
    "BContractUnit": {"dims": ["Account", "BContract", "ContractType"],
                      "purpose": "Dư HĐ ngân hàng group theo đơn vị"},
    "Job": {"dims": ["Account", "Job", "Type"],
            "purpose": "Dư theo vụ việc/công trình"},
    "JobUnit": {"dims": ["Account", "Job"],
                "purpose": "Dư vụ việc group theo đơn vị"},
    "JobCustomer": {"dims": ["Account", "Job", "Customer", "Type"],
                    "purpose": "Dư vụ việc × khách hàng"},
    "JobCustomerUnit": {"dims": ["Account", "Job", "Customer", "Type"],
                        "purpose": "Dư vụ việc × KH group theo đơn vị"},
    "SalesEmployee": {"dims": ["Account", "SalesEmployee",
                               "SalesEmployeeColumn",
                               "BalanceJoin/WhereClause",
                               "ArisingJoin/WhereClause"],
                      "purpose": "Công nợ/doanh số NVBH "
                                 "(join/where dư & phát sinh tách riêng)"},
    "SalesEmployeeCustomer": {"dims": ["Account", "SalesEmployee",
                                        "Customer"],
                              "purpose": "Công nợ NVBH × khách hàng"},
    "ManagementObject": {"dims": ["ObjectType", "Field", "Account",
                                   "ObjectCode"],
                         "purpose": "Dư theo đối tượng quản lý "
                                    "(@ObjectType/@Field chọn dim)"},
    "ManagementObjectUnit": {"dims": ["ObjectType", "Field", "Account",
                                       "ObjectCode"],
                             "purpose": "Dư ĐTQL group theo đơn vị"},
    "Shop": {"dims": ["Shop", "WO", "Operation", "Lot", "Item", "Type"],
             "purpose": "WIP sản xuất theo phân xưởng/lệnh SX/công đoạn"},
    # --- đầu tư ---
    "Investment": {"dims": ["Language"],
                   "purpose": "Dư đầu tư/trái phiếu (wrkgl/dtdmct) — trả "
                              "result sets, param thu gọn (không #t)"},
}

OPENING_BALANCE_PROCS: dict[str, dict] = {
    "UpdateCurrentStock": {
        "dims": ["Year", "Item", "Site", "Location", "Lot", "Quantity",
                  "Type", "Action", "IDNumber", "IDNumber0"],
        "purpose": "Ghi/cập nhật dư đầu tồn kho (cdvt13/213, cdlo*, dmlo)"},
    "UpdateCurrentCustomerBalance": {
        "dims": ["Year", "Customer", "DebitAmount", "CreditAmount",
                  "Action", "Account", "Unit"],
        "purpose": "Ghi dư đầu công nợ khách hàng"},
    "ConvertLot2Stock": {
        "dims": ["Item", "Type"],
        "purpose": "Convert dư lô sang dư tồn kho"},
    "ConvertCustomer2Account": {
        "dims": ["Unit", "Account", "Year"],
        "purpose": "Convert dư KH sang dư tài khoản"},
}

HELPERS = ("FastBusiness$Function$GetBalanceDateAndPeriod / "
           "ff_GetBalanceDateAndPeriod — ngày+kỳ số dư")

VARIANT_NOTE = ("Params/tên khác theo version & variant project "
                "(*_KhanhTd, zFastBusiness$*, *_goc, *_debug) — luôn "
                "mode=search '%$Balance$%' list + mode=summary verify "
                "trên DB đích trước khi EXEC.")


def _group(items, n: int) -> list[str]:
    return ["; ".join(items[i:i + n]) for i in range(0, len(items), n)]


def render_map() -> str:
    """~5 dòng compact chiều→proc cho pitfalls."""
    stock = [k for k in ("Item", "Lot", "Location", "LocationLot",
                         "SiteLocationItemLot", "ItemAccount")
             if k in BALANCE_PROCS]
    gl = [k for k in ("Account", "AccountUnit", "DCAccount")
          if k in BALANCE_PROCS]
    ar = [k for k in ("Customer", "Customer2", "CustomerUnit", "Contract",
                      "ContractUnit", "ContractCustomer", "BContract",
                      "BContractUnit", "Job", "JobUnit", "JobCustomer",
                      "JobCustomerUnit", "SalesEmployee",
                      "SalesEmployeeCustomer", "ManagementObject",
                      "ManagementObjectUnit", "Shop")
          if k in BALANCE_PROCS]
    lines = [
        "tồn kho/lô/vị trí: " + ", ".join(stock),
        "sổ cái TK: " + ", ".join(gl),
        "công nợ/HĐ/vụ việc/NVBH/ĐTQL/WIP: " + ", ".join(ar),
        "đầu tư/TP: Investment | ghi dư đầu: $OpeningBalance$" +
        "/".join(OPENING_BALANCE_PROCS),
    ]
    return "\n".join(lines)
