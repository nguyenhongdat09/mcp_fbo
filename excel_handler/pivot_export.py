"""Xuất Excel xoay (PivotTable) — gọi PivotExcel.exe (clone nguyên từ fbo-autocomplete).

Exe nhận 4 args: <rowCsv> <columnCsv> <valueCsv> <outputPath.xlsx>.
Yêu cầu: Windows + Excel desktop (exe dùng COM Interop).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
PIVOT_EXE_PATH = _ASSETS_DIR / "PivotExcelExe" / "PivotExcel.exe"


def export_pivot_excel(
    row_csv: str,
    column_csv: str,
    value_csv: str,
    output_path: str,
    exe_path: str | Path | None = None,
    timeout: int = 300,
) -> str:
    """Chạy PivotExcel.exe sinh file xlsx pivot tại output_path. Trả về output_path."""
    for name, csv in (("row", row_csv), ("column", column_csv), ("value", value_csv)):
        if not (csv or "").strip():
            raise ValueError(f"{name}_fields rỗng — PivotExcel.exe yêu cầu đủ 3 danh sách field.")

    exe = Path(exe_path) if exe_path else PIVOT_EXE_PATH
    if not exe.exists():
        raise FileNotFoundError(f"Không tìm thấy PivotExcel.exe: {exe}")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [str(exe), row_csv, column_csv, value_csv, str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        detail = "\n".join(x for x in [proc.stdout.strip(), proc.stderr.strip()] if x)
        raise RuntimeError(
            f"PivotExcel.exe lỗi (exit {proc.returncode}): {detail or 'không có output'}"
        )
    return str(out)
