"""File system utilities."""

import os
from pathlib import Path
from typing import Optional


def detect_bom_encoding(raw: bytes) -> str | None:
    """BOM → codec name; None nếu không có BOM.

    THỨ TỰ BẮT BUỘC: utf-32 trước utf-16 vì FF FE 00 00 trùng prefix FF FE.
    Codec 'utf-16'/'utf-32'/'utf-8-sig' tự consume BOM (KHÔNG dùng 'utf-16-le'
    — nó để lại ký tự \\ufeff đầu text).
    """
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return "utf-32"      # LE
    if raw.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32"      # BE
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return "utf-16"
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return None


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """Decode bytes → (text, encoding_used). Không raise; fallback cp1258 errors=replace.

    - BOM (utf-32/utf-16/utf-8-sig) → decode theo BOM.
    - Không BOM → thử utf-8; nếu utf-8 thành công GIẢ (UTF-16 không BOM: NUL
      0x00 là utf-8 hợp lệ) thì check '\\x00' và retry utf-16.
    - utf-8 fail → cp1258 errors=replace (tiếng Việt Windows cũ).
    """
    enc = detect_bom_encoding(raw)
    if enc:
        return raw.decode(enc, errors="replace"), enc
    try:
        text = raw.decode("utf-8")
        if "\x00" in text:
            return raw.decode("utf-16", errors="replace"), "utf-16"
        return text, "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1258", errors="replace"), "cp1258"


def ensure_directory(path: str) -> None:
    """
    Ensure directory exists, create if necessary.

    Args:
        path: Directory path
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def read_file(file_path: str) -> Optional[str]:
    """
    Read file content safely.

    Args:
        file_path: Path to file

    Returns:
        File content or None if read fails
    """
    try:
        raw = Path(file_path).read_bytes()
    except Exception:
        return None
    if not raw:
        return ""
    text, _enc = decode_bytes(raw)
    return text


def write_file(file_path: str, content: str) -> bool:
    """
    Write content to file safely.

    Args:
        file_path: Path to file
        content: Content to write

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        path = Path(file_path)
        ensure_directory(str(path.parent))

        # Preserve encoding cũ: file đã có BOM (utf-16/utf-32/utf-8-sig) → ghi
        # đúng codec (tự emit BOM); không BOM hoặc file mới → utf-8.
        enc = "utf-8"
        if path.is_file():
            try:
                enc = detect_bom_encoding(path.read_bytes()[:4]) or "utf-8"
            except Exception:
                enc = "utf-8"

        path.write_bytes(content.encode(enc, errors="replace"))
        return True
    except Exception:
        return False


def find_xml_files(directory: str, recursive: bool = True) -> list[str]:
    """
    Find all XML files in directory.

    Args:
        directory: Directory to search
        recursive: Whether to search recursively

    Returns:
        List of XML file paths
    """
    xml_files = []
    path = Path(directory)

    if not path.exists():
        return xml_files

    pattern = "**/*.xml" if recursive else "*.xml"

    for file_path in path.glob(pattern):
        if file_path.is_file():
            xml_files.append(str(file_path))

    return xml_files


def get_file_extension(file_path: str) -> str:
    """
    Get file extension.

    Args:
        file_path: Path to file

    Returns:
        File extension (without dot)
    """
    return Path(file_path).suffix.lstrip(".")


def get_file_name(file_path: str) -> str:
    """
    Get file name without extension.

    Args:
        file_path: Path to file

    Returns:
        File name without extension
    """
    return Path(file_path).stem
