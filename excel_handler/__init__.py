"""Package excel_handler — xuất mẫu Excel (.xlsx) từ file Grid XML FBO.

Clone từ fbo-autocomplete: ConvertToExcel (Excel thường) + ConvertGridToPivotExcel
(PivotTable qua PivotExcel.exe). Tự nhận diện theo thẻ <pivot> trong Grid XML.
"""

from .grid_parser import (
    build_header_field_defs,
    build_pivot_defaults,
    extract_grid_attrs,
    extract_grid_view_field_names,
    has_pivot_tag,
    parse_header_fields,
)
from .report_fields import ReportUpdate, update_report_fields
from .service import ExcelHandlerRequest, ExcelHandlerResult, excel_handler

__all__ = [
    "excel_handler",
    "ExcelHandlerRequest",
    "ExcelHandlerResult",
    "ReportUpdate",
    "update_report_fields",
    "build_header_field_defs",
    "build_pivot_defaults",
    "extract_grid_attrs",
    "extract_grid_view_field_names",
    "has_pivot_tag",
    "parse_header_fields",
]
