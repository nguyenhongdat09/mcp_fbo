"""Auto UTF-8 BOM — port Utf8BomHandler.js (SearchFile).

Extension gốc prepend EF BB BF cho .xml/.aspx/.ent thiếu BOM. Bản này chính
xác hơn: chỉ thêm khi decode_bytes xác nhận file là UTF-8 thuần (không BOM) —
skip UTF-16, cp1258, file đã có BOM hay file rỗng.
"""

from __future__ import annotations

import threading
from pathlib import Path

from fastbusiness_mcp.utils.file_utils import decode_bytes

UTF8_BOM = b"\xef\xbb\xbf"
BOM_EXTENSIONS = {".xml", ".aspx", ".ent"}

_processing: set[str] = set()
_lock = threading.Lock()


def is_utf8_no_bom(raw: bytes) -> bool:
    """True nếu raw decode được bằng UTF-8 thuần (không BOM, không phải UTF-16...)."""
    if not raw or raw[:3] == UTF8_BOM:
        return False
    _text, enc = decode_bytes(raw)
    return enc == "utf-8"


def ensure_utf8_bom(abs_path: str) -> bool:
    """Thêm UTF-8 BOM nếu file thuộc BOM_EXTENSIONS và đang là UTF-8 no-BOM.

    Trả True nếu đã ghi BOM. Lỗi (lock/quyền) -> bỏ qua âm thầm, False.
    """
    if not abs_path:
        return False
    if Path(abs_path).suffix.lower() not in BOM_EXTENSIONS:
        return False

    norm = str(Path(abs_path))
    with _lock:
        if norm in _processing:
            return False
        _processing.add(norm)
    try:
        p = Path(norm)
        try:
            st = p.stat()
        except OSError:
            return False
        if not st.st_size:
            return False
        raw = p.read_bytes()
        if not is_utf8_no_bom(raw):
            return False
        p.write_bytes(UTF8_BOM + raw)
        return True
    except OSError:
        return False
    finally:
        with _lock:
            _processing.discard(norm)
