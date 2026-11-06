"""excel_handler — xuất mẫu in Excel (.xlsx) từ file Grid XML của báo cáo FBO.

Cách dùng cho agent:

    from excel_handler import excel_handler
    result = excel_handler(grid_file=r"z:\\FBI\\CHUBB\\SP2264\\App_Data\\Controllers\\Grid\\zcbccashflow.xml")

Tool tự đọc Grid XML và nhận diện 2 chế độ:

- mode='pivot' : Grid có thẻ <pivot rowField=.. columnField=.. dataFields=../> (báo cáo xoay)
                 → sinh .xlsx có PivotTable thật (sheet 'Main - Pivot') qua PivotExcel.exe
                 (yêu cầu Windows + Excel desktop). Dùng row_fields / column_fields /
                 value_fields để bố trí pivot; bỏ trống → tự suy ra từ XML.
- mode='normal': Grid thường → đổ token vào template mau_chuan.xlsx
                 (row 9 = '?h_<field>', row 10 = '!2.<field>{b:systotal=0}').

Token trong mẫu Excel (FBO thay thế lúc in):
- '?h_<field>'  : giá trị header <field name='h_<field>'> trong Report XML (caption động).
- '!2.<field>'  : field của recordset 2 (dữ liệu).
- '{b:systotal=0}': binder lọc dòng (bỏ dòng tổng systotal=1).
- 'systotal'    : cột tổng ẩn của grid (row field pivot).
- 'npivot'      : cột nhóm phụ pivot (column field pivot).

Kết quả trả về ExcelHandlerResult (pydantic) — xem field descriptions.
File .xlsx sinh ra đặt vào Controllers/Templates/Excel và khai báo qua
templateFile trong Report XML tương ứng.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .grid_parser import (
    build_pivot_defaults,
    has_pivot_tag,
    parse_header_fields,
)
from .normal_export import export_normal_excel
from .pivot_export import export_pivot_excel
from .report_fields import ReportUpdate, update_report_fields


class ExcelHandlerRequest(BaseModel):
    """Input của excel_handler — agent truyền kwargs cùng tên field."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    grid_file: str = Field(
        min_length=1,
        description=(
            "BẮT BUỘC. Path tuyệt đối file Grid XML của báo cáo (local hoặc UNC), "
            "vd 'z:\\FBI\\CHUBB\\SP2264\\App_Data\\Controllers\\Grid\\zcbccashflow.xml'. "
            "File phải là .xml nằm trong thư mục tên 'Grid'."
        ),
    )
    row_fields: Optional[Union[str, List[str]]] = Field(
        default=None,
        description=(
            "CHỈ dùng khi mode='pivot'. CSV 'a,b,c' hoặc list field đặt vào vùng Row Labels "
            "của PivotTable. Hỗ trợ token 'systotal' (cột tổng ẩn) và '?h_<field>' "
            "(header field trong Report XML, hiển thị caption động). "
            "None/rỗng → auto = rowField trong <pivot> + 'systotal' + các field trong "
            "<view id='Grid'> dạng '?h_<name>' (trừ field trùng dataFields)."
        ),
    )
    column_fields: Optional[Union[str, List[str]]] = Field(
        default=None,
        description=(
            "CHỈ dùng khi mode='pivot'. CSV/list field đặt vào vùng Column Labels. "
            "Token 'npivot' = cột nhóm phụ của báo cáo xoay FBO. "
            "None/rỗng → auto = columnField trong <pivot> + ',npivot'."
        ),
    )
    value_fields: Optional[Union[str, List[str]]] = Field(
        default=None,
        description=(
            "CHỈ dùng khi mode='pivot'. CSV/list field đặt vào vùng Values (mặc định Sum). "
            "None/rỗng → auto = dataFields của thẻ <pivot>."
        ),
    )
    output_path: Optional[str] = Field(
        default=None,
        description=(
            "Path file .xlsx đích (kèm thư mục). None → thư mục mặc định "
            "'<Controllers>\\Templates\\Excel' + excel_name/<tên_grid>.xlsx. "
            "KHÔNG truyền cùng excel_name."
        ),
    )
    excel_name: Optional[str] = Field(
        default=None,
        description=(
            "TÊN file .xlsx muốn xuất, vd 'zcbccashflow_01.xlsx' hoặc 'zcbccashflow_01' "
            "(thiếu đuôi tự thêm '.xlsx'). Chỉ nhận tên file — đặt trong thư mục mặc "
            "định '<Controllers>\\Templates\\Excel'. None → '<tên_grid>.xlsx'. "
            "KHÔNG truyền cùng output_path."
        ),
    )

    @field_validator("row_fields", "column_fields", "value_fields", mode="before")
    @classmethod
    def _csv_or_list(cls, v):
        """Chấp nhận list → chuẩn hóa csv 'a,b,c'; chuỗi trống → None (dùng auto default)."""
        if v is None:
            return None
        if isinstance(v, (list, tuple)):
            csv = ",".join(str(x).strip() for x in v if str(x).strip())
            return csv or None
        s = str(v).strip()
        return s or None

    @field_validator("grid_file")
    @classmethod
    def _check_grid_file(cls, v: str) -> str:
        p = Path(v)
        if p.suffix.lower() != ".xml":
            raise ValueError(f"grid_file phải là file .xml: {v}")
        if p.parent.name.lower() != "grid":
            raise ValueError(f"grid_file phải nằm trong thư mục 'Grid': {v}")
        if not p.exists():
            raise ValueError(f"Không tìm thấy file grid: {v}")
        return v

    @field_validator("excel_name")
    @classmethod
    def _check_excel_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        p = Path(v)
        if p.parent != Path(".") or p.is_absolute():
            raise ValueError(
                f"excel_name chỉ nhận TÊN file (vd 'abc_01.xlsx'), không nhận path: {v}"
            )
        return v

    def model_post_init(self, __context) -> None:
        if self.output_path and self.excel_name:
            raise ValueError("Chỉ truyền output_path HOẶC excel_name, không truyền cả hai.")


class ExcelHandlerResult(BaseModel):
    """Kết quả excel_handler."""

    mode: Literal["pivot", "normal"] = Field(
        description="'pivot' = file có thẻ <pivot> (Excel xoay); 'normal' = Excel thường."
    )
    output_path: str = Field(description="Path file .xlsx đã sinh.")
    row_fields: Optional[str] = Field(
        default=None, description="(pivot) CSV row fields đã dùng (sau merge auto default)."
    )
    column_fields: Optional[str] = Field(
        default=None, description="(pivot) CSV column fields đã dùng."
    )
    value_fields: Optional[str] = Field(
        default=None, description="(pivot) CSV value fields đã dùng."
    )
    headers: Optional[List[str]] = Field(
        default=None,
        description="(normal) Danh sách 'h_<field>' đã ghi lên row 9 template (?h_*).",
    )
    report_update: Optional[ReportUpdate] = Field(
        default=None,
        description=(
            "Kết quả bước AddFieldToReport chạy TRƯỚC export: inject field h_* "
            "thiếu vào Controllers/Report/<tên_grid>.xml để token '?h_*' trong "
            "mẫu Excel resolve được. Xem status/added_fields."
        ),
    )


def _default_output_dir(grid_path: Path) -> Path:
    """<Controllers>/Templates/Excel; fallback cùng thư mục Grid."""
    parts = [p.lower() for p in grid_path.parts]
    if "controllers" in parts:
        idx = parts.index("controllers")
        return Path(*grid_path.parts[: idx + 1]) / "Templates" / "Excel"
    return grid_path.parent


def _default_output_path(grid_path: Path) -> Path:
    """<Controllers>/Templates/Excel/<stem>.xlsx; fallback cùng thư mục Grid."""
    return _default_output_dir(grid_path) / f"{grid_path.stem}.xlsx"


def _resolve_output_path(req: "ExcelHandlerRequest", grid_path: Path) -> Path:
    """output_path > excel_name (trong thư mục mặc định) > <stem>.xlsx."""
    if req.output_path:
        return Path(req.output_path)
    if req.excel_name:
        name = req.excel_name
        if not name.lower().endswith(".xlsx"):
            name += ".xlsx"
        return _default_output_dir(grid_path) / name
    return _default_output_path(grid_path)


def excel_handler(
    request: Optional[ExcelHandlerRequest] = None,
    **kwargs,
) -> ExcelHandlerResult:
    """Xuất mẫu Excel từ Grid XML (xem docstring module + ExcelHandlerRequest).

    Gọi bằng kwargs: excel_handler(grid_file=..., row_fields=..., output_path=...),
    hoặc truyền sẵn ExcelHandlerRequest. Raise:
    - pydantic.ValidationError: input sai (không phải .xml / không trong thư mục Grid /
      file không tồn tại / tham số lạ).
    - ValueError: pivot nhưng row/column/value rỗng sau merge, hoặc grid thường không
      có field xuất được (toàn hidden).
    - RuntimeError: PivotExcel.exe lỗi (thiếu Excel, template hỏng...).
    """
    if request is not None and kwargs:
        raise TypeError("Truyền request HOẶC kwargs, không truyền cả hai.")
    req = request if request is not None else ExcelHandlerRequest(**kwargs)

    grid_path = Path(req.grid_file)
    xml = grid_path.read_text(encoding="utf-8-sig")
    out_path = _resolve_output_path(req, grid_path)

    # AddFieldToReport trước: inject field h_* thiếu vào Report XML để '?h_*' resolve
    report_update = update_report_fields(grid_path, xml)

    if has_pivot_tag(xml):
        defaults = build_pivot_defaults(xml)
        row_csv = req.row_fields or defaults["row_csv"]
        col_csv = req.column_fields or defaults["column_csv"]
        val_csv = req.value_fields or defaults["value_csv"]
        export_pivot_excel(row_csv, col_csv, val_csv, str(out_path))
        return ExcelHandlerResult(
            mode="pivot",
            output_path=str(out_path),
            row_fields=row_csv,
            column_fields=col_csv,
            value_fields=val_csv,
            report_update=report_update,
        )

    headers = parse_header_fields(xml)
    export_normal_excel(headers, str(out_path))
    return ExcelHandlerResult(
        mode="normal",
        output_path=str(out_path),
        headers=[h[0] for h in headers],
        report_update=report_update,
    )
