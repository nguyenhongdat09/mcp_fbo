"""Configuration for LevelDB paths"""

from pathlib import Path
from typing import Dict, Optional
import os

class LevelDBConfig:
    """Configuration for LevelDB database locations"""

    # Default paths relative to project root
    DEFAULT_DB_BASE = Path(__file__).parent.parent / "database"

    # JSON export files (fallback when plyvel/rocksdb not available)
    DEFAULT_JSON_BASE = Path(__file__).parent.parent / "database" / "json_exports"

    # Alternative: Use VS Code extension path if available
    VSCODE_EXTENSION_PATH = os.getenv(
        'FASTBUSINESS_VSCODE_DB_PATH',
        r'C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database'
    )

    # JSON export path
    JSON_EXPORT_PATH = os.getenv(
        'FASTBUSINESS_JSON_DB_PATH',
        str(DEFAULT_JSON_BASE)
    )

    @classmethod
    def get_db_paths(cls, use_vscode_extension: bool = False) -> Dict[str, str]:
        """
        Get database paths for all file types

        Args:
            use_vscode_extension: If True, use VS Code extension path

        Returns:
            Dict mapping file type to database path
        """
        if use_vscode_extension and Path(cls.VSCODE_EXTENSION_PATH).exists():
            base_path = Path(cls.VSCODE_EXTENSION_PATH)
        else:
            base_path = cls.DEFAULT_DB_BASE

        return {
            "DIR": str(base_path / "Dir"),
            "FILTER_VOUCHER": str(base_path / "Filter"),
            "FILTER_NORMAL": str(base_path / "Filter"),
            "GRID_VIEW": str(base_path / "GridView"),
            "GRID_INPUT": str(base_path / "GridInput"),
        }

    @classmethod
    def get_db_path(cls, file_type: str, use_vscode_extension: bool = False) -> str:
        """Get database path for specific file type"""
        paths = cls.get_db_paths(use_vscode_extension)
        return paths.get(file_type, str(cls.DEFAULT_DB_BASE / file_type))

    @classmethod
    def get_json_paths(cls) -> Dict[str, str]:
        """
        Get JSON export file paths for all file types

        Returns:
            Dict mapping file type to JSON file path
        """
        base_path = Path(cls.JSON_EXPORT_PATH)

        return {
            "DIR": str(base_path / "dir.json"),
            "FILTER_VOUCHER": str(base_path / "filter.json"),
            "FILTER_NORMAL": str(base_path / "filter.json"),
            "GRID_VIEW": str(base_path / "gridview.json"),
            "GRID_INPUT": str(base_path / "gridinput.json"),
        }

    @classmethod
    def get_json_path(cls, file_type: str) -> str:
        """Get JSON export path for specific file type"""
        paths = cls.get_json_paths()
        return paths.get(file_type, str(Path(cls.JSON_EXPORT_PATH) / f"{file_type.lower()}.json"))
