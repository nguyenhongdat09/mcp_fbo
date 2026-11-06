"""Khai báo grid truy ngược (``Query*``) vào ``Grid/Config/Aggregation.q``.

Controller truy ngược (drill-down từ báo cáo) phải có dòng
``<controller name="..." description=""/>`` trong file này, nếu không mở trang sẽ báo
"Chưa có quyền truy cập hoặc truy cập bị từ chối". Áp dụng cả bản cũ lẫn SP30+.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_BOM = b"\xef\xbb\xbf"
_AGG_Q = Path("App_Data") / "Controllers" / "Grid" / "Config" / "Aggregation.q"
# QueryX hoặc zus_QueryX (tiền tố riêng dự án kết thúc bằng '_')
_RE_QUERY_CTRL = re.compile(r"(?:^|_)Query[A-Z0-9]")


def is_query_controller(name: str) -> bool:
    return bool(_RE_QUERY_CTRL.search(name))


def register_query_aggregation(
    root_tgt: Path, controllers: list[str], execute: bool
) -> list[dict[str, Any]]:
    """Thêm từng controller truy ngược vào cuối ``Aggregation.q`` của dự án đích.
    ``status``: added | planned | exists | file_missing | error."""
    path = Path(root_tgt) / _AGG_Q
    out: list[dict[str, Any]] = []
    names = [c for c in dict.fromkeys(controllers) if is_query_controller(c)]
    if not names:
        return out
    if not path.is_file():
        return [{"controller": c, "status": "file_missing", "file": _AGG_Q.as_posix()} for c in names]
    try:
        raw = path.read_bytes()
        has_bom = raw.startswith(_BOM)
        text = raw.decode("utf-8-sig")
        nl = "\r\n" if "\r\n" in text else "\n"
        added: list[str] = []
        for c in names:
            if re.search(r'name\s*=\s*"' + re.escape(c) + r'"', text, re.IGNORECASE):
                out.append({"controller": c, "status": "exists", "file": _AGG_Q.as_posix()})
                continue
            if text and not text.endswith(("\n", "\r")):
                text += nl
            text += f'<controller name="{c}" description=""/>{nl}'
            added.append(c)
            out.append(
                {
                    "controller": c,
                    "status": "added" if execute else "planned",
                    "file": _AGG_Q.as_posix(),
                }
            )
        if execute and added:
            path.write_bytes((_BOM if has_bom else b"") + text.encode("utf-8"))
    except Exception as ex:
        return [
            {"controller": c, "status": "error", "message": f"{type(ex).__name__}: {ex}"}
            for c in names
        ]
    return out
