"""File system utilities."""

import os
from pathlib import Path
from typing import Optional


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
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


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
        ensure_directory(str(Path(file_path).parent))

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
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
