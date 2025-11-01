"""LevelDB Manager for field definitions"""

try:
    import plyvel
    PLYVEL_AVAILABLE = True
except ImportError:
    PLYVEL_AVAILABLE = False
    import warnings
    warnings.warn(
        "plyvel is not installed. LevelDB features will be disabled. "
        "Install with: pip install plyvel",
        ImportWarning
    )

from typing import Optional, Dict, List
from pathlib import Path
import json
import logging
from ..core.exceptions import DatabaseError
from .config import LevelDBConfig

logger = logging.getLogger(__name__)


class LevelDBManager:
    """Manager for LevelDB database connections"""

    def __init__(self, custom_paths: Optional[Dict[str, str]] = None, use_vscode_extension: bool = False):
        """
        Initialize LevelDB connections

        Args:
            custom_paths: Custom paths for databases. Format: {"DIR": "path/to/dir", ...}
            use_vscode_extension: Use VS Code extension database if True
        """
        if not PLYVEL_AVAILABLE:
            logger.warning("LevelDB not available - plyvel is not installed")
            self.paths = {}
            self.dbs = {}
            return

        if custom_paths:
            self.paths = custom_paths
        else:
            self.paths = LevelDBConfig.get_db_paths(use_vscode_extension)

        self.dbs = {}
        self._connect_all()

    def _connect_all(self):
        """Connect to all LevelDB databases"""
        for db_type, path in self.paths.items():
            try:
                db_path = Path(path)
                if db_path.exists():
                    self.dbs[db_type] = plyvel.DB(
                        str(db_path),
                        create_if_missing=False,
                        compression='snappy'
                    )
                    logger.info(f"Connected to {db_type} LevelDB at {path}")
                else:
                    logger.warning(f"LevelDB not found at {path}")
            except Exception as e:
                logger.error(f"Error connecting to {db_type} LevelDB: {e}")

    def get_field(self, field_name: str, db_type: str) -> Optional[Dict]:
        """
        Get field definition from LevelDB

        Args:
            field_name: Field name (e.g., "ma_khat", "so_luong", "ma_khlk")
            db_type: Database type ("DIR", "FILTER_VOUCHER", "FILTER_NORMAL", "GRID_VIEW", "GRID_INPUT")

        Returns:
            Field definition as dict, or None if not found
        """
        if not PLYVEL_AVAILABLE:
            logger.warning("LevelDB not available - plyvel is not installed")
            return None

        if db_type not in self.dbs:
            logger.warning(f"Database type {db_type} not available")
            return None

        try:
            db = self.dbs[db_type]
            key_bytes = field_name.encode('utf-8')
            value = db.get(key_bytes)

            if value:
                json_str = value.decode('utf-8')
                return json.loads(json_str)

            return None

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON for field {field_name}: {e}")
            raise DatabaseError(f"Invalid JSON in database for field {field_name}")

        except Exception as e:
            logger.error(f"Error reading from LevelDB: {e}")
            raise DatabaseError(f"Error reading from LevelDB: {e}")

    def search_fields(
        self,
        pattern: str,
        db_type: str,
        limit: int = 10,
        exact_match: bool = False
    ) -> List[Dict]:
        """
        Search for fields matching pattern

        Args:
            pattern: Search pattern (e.g., "so_luong", "ma_kh", "ngay_")
            db_type: Database type
            limit: Max results to return
            exact_match: If True, only return exact matches

        Returns:
            List of matching field definitions with field names
        """
        if not PLYVEL_AVAILABLE:
            return []

        if db_type not in self.dbs:
            return []

        results = []
        pattern_lower = pattern.lower()

        try:
            db = self.dbs[db_type]

            for key, value in db.iterator():
                key_str = key.decode('utf-8')

                if exact_match:
                    if key_str.lower() == pattern_lower:
                        field_data = json.loads(value.decode('utf-8'))
                        results.append({
                            'field_name': key_str,
                            'definition': field_data
                        })
                        break
                else:
                    if pattern_lower in key_str.lower():
                        field_data = json.loads(value.decode('utf-8'))
                        results.append({
                            'field_name': key_str,
                            'definition': field_data
                        })

                        if len(results) >= limit:
                            break

            return results

        except Exception as e:
            logger.error(f"Error searching LevelDB: {e}")
            raise DatabaseError(f"Error searching LevelDB: {e}")

    def get_all_fields(self, db_type: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get all fields from database

        Args:
            db_type: Database type
            limit: Optional limit on results

        Returns:
            List of all field definitions
        """
        if not PLYVEL_AVAILABLE:
            return []

        if db_type not in self.dbs:
            return []

        results = []

        try:
            db = self.dbs[db_type]

            for key, value in db.iterator():
                key_str = key.decode('utf-8')
                field_data = json.loads(value.decode('utf-8'))
                results.append({
                    'field_name': key_str,
                    'definition': field_data
                })

                if limit and len(results) >= limit:
                    break

            return results

        except Exception as e:
            logger.error(f"Error reading all fields: {e}")
            raise DatabaseError(f"Error reading all fields: {e}")

    def count_fields(self, db_type: str) -> int:
        """Count total fields in database"""
        if not PLYVEL_AVAILABLE:
            return 0

        if db_type not in self.dbs:
            return 0

        try:
            count = 0
            db = self.dbs[db_type]

            for _ in db.iterator():
                count += 1

            return count

        except Exception as e:
            logger.error(f"Error counting fields: {e}")
            return 0

    def close_all(self):
        """Close all database connections"""
        for db_type, db in self.dbs.items():
            try:
                db.close()
                logger.info(f"Closed {db_type} LevelDB connection")
            except Exception as e:
                logger.error(f"Error closing {db_type} database: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()
