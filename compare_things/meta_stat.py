"""Metadata extraction and file statistics for compare_things."""

from __future__ import annotations

import datetime
import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple

from .models import FileMeta
from .text_normalize import detect_line_ending


def is_binary_bytes(raw_bytes: bytes, sample_size: int = 8192) -> bool:
    """Check if bytes contain null byte 0x00 in the first sample_size bytes."""
    sample = raw_bytes[:sample_size]
    return b"\x00" in sample


def decode_bytes_with_fallback(raw_bytes: bytes) -> Tuple[str, str, Optional[str]]:
    """
    Decode raw bytes trying:
    1. utf-8-sig
    2. utf-8
    3. cp1258
    4. latin-1
    Returns (decoded_text, encoding_name, warning_message_or_None)
    """
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        try:
            return raw_bytes.decode("utf-8-sig"), "utf-8-sig", None
        except Exception:
            pass

    for enc in ("utf-8", "cp1258"):
        try:
            return raw_bytes.decode(enc), enc, None
        except UnicodeDecodeError:
            continue

    # Fallback to latin-1 which never fails
    return raw_bytes.decode("latin-1"), "latin-1", "encoding_fallback_latin1"


def get_file_meta_and_bytes(
    file_path: str,
    max_file_bytes: int = 10485760,  # 10MB soft limit
) -> Tuple[FileMeta, bytes, Optional[str], Optional[str]]:
    """
    Read file, calculate meta stats, raw sha256 and decode text if not binary.
    Returns:
      (FileMeta, raw_bytes, decoded_text_or_None, warning_or_None)
    """
    p = Path(file_path)
    meta = FileMeta(path=str(p.resolve()))

    if not p.exists() or not p.is_file():
        meta.exists = False
        return meta, b"", None, None

    meta.exists = True
    stat = p.stat()
    meta.size = stat.st_size
    meta.created = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()
    meta.modified = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()

    warning: Optional[str] = None
    if meta.size > max_file_bytes:
        warning = "file_too_large_truncated"
        with open(p, "rb") as f:
            raw_bytes = f.read(max_file_bytes)
    else:
        with open(p, "rb") as f:
            raw_bytes = f.read()

    meta.sha256 = hashlib.sha256(raw_bytes).hexdigest()
    meta.line_ending = detect_line_ending(raw_bytes)

    if is_binary_bytes(raw_bytes):
        meta.is_binary = True
        return meta, raw_bytes, None, warning

    text, enc, dec_warn = decode_bytes_with_fallback(raw_bytes)
    meta.encoding = enc
    meta.is_binary = False

    if dec_warn:
        warning = dec_warn if not warning else f"{warning}; {dec_warn}"

    return meta, raw_bytes, text, warning
