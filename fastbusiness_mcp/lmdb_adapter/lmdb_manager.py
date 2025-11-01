"""LMDB Database Manager for FastBusiness Field Definitions

LMDB (Lightning Memory-Mapped Database) is faster and more reliable than LevelDB/RocksDB
- No build dependencies (pure Python)
- Very fast reads
- ACID transactions
- Memory-mapped for performance
"""

import lmdb
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class LMDBManager:
    """Manager for LMDB database storing field definitions"""

    def __init__(self, db_path: str = "data/fields_lmdb"):
        """
        Initialize LMDB connection

        Args:
            db_path: Path to LMDB database directory
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Open LMDB environment
        # map_size: maximum database size (1GB)
        # max_dbs: number of named databases (one per context type)
        self.env = lmdb.open(
            str(self.db_path),
            map_size=1024 * 1024 * 1024,  # 1GB
            max_dbs=10,
            readonly=False
        )

        # Open named databases for each context type
        self.dbs = {}
        for db_name in ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']:
            self.dbs[db_name] = self.env.open_db(db_name.encode())

        logger.info(f"LMDB initialized at {self.db_path}")

    def put_field(self, context_type: str, field_name: str, field_data: Dict) -> bool:
        """
        Store field definition in database

        Args:
            context_type: Context type (DIR, FILTER_VOUCHER, etc.)
            field_name: Field name (e.g., 'ma_khat', 'so_luong')
            field_data: Field definition as dict

        Returns:
            True if successful
        """
        if context_type not in self.dbs:
            logger.error(f"Unknown context type: {context_type}")
            return False

        try:
            with self.env.begin(db=self.dbs[context_type], write=True) as txn:
                key = field_name.encode('utf-8')
                value = json.dumps(field_data, ensure_ascii=False).encode('utf-8')
                txn.put(key, value)
            return True
        except Exception as e:
            logger.error(f"Error storing field {field_name}: {e}")
            return False

    def get_field(self, context_type: str, field_name: str) -> Optional[Dict]:
        """
        Get field definition from database

        Args:
            context_type: Context type
            field_name: Field name

        Returns:
            Field definition dict or None if not found
        """
        if context_type not in self.dbs:
            return None

        try:
            with self.env.begin(db=self.dbs[context_type]) as txn:
                value = txn.get(field_name.encode('utf-8'))
                if value:
                    return json.loads(value.decode('utf-8'))
            return None
        except Exception as e:
            logger.error(f"Error reading field {field_name}: {e}")
            return None

    def search_fields(self, context_type: str, pattern: str, limit: int = 100) -> List[Dict]:
        """
        Search for fields matching pattern

        Args:
            context_type: Context type
            pattern: Search pattern (substring match)
            limit: Maximum results

        Returns:
            List of {'field_name': str, 'definition': dict}
        """
        if context_type not in self.dbs:
            return []

        results = []
        pattern_lower = pattern.lower()

        try:
            with self.env.begin(db=self.dbs[context_type]) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    field_name = key.decode('utf-8')
                    if pattern_lower in field_name.lower():
                        field_data = json.loads(value.decode('utf-8'))
                        results.append({
                            'field_name': field_name,
                            'definition': field_data
                        })
                        if len(results) >= limit:
                            break
            return results
        except Exception as e:
            logger.error(f"Error searching fields: {e}")
            return []

    def get_all_fields(self, context_type: str) -> List[Dict]:
        """
        Get all fields from context type

        Args:
            context_type: Context type

        Returns:
            List of all field definitions
        """
        if context_type not in self.dbs:
            return []

        results = []
        try:
            with self.env.begin(db=self.dbs[context_type]) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    field_name = key.decode('utf-8')
                    field_data = json.loads(value.decode('utf-8'))
                    results.append({
                        'field_name': field_name,
                        'definition': field_data
                    })
            return results
        except Exception as e:
            logger.error(f"Error getting all fields: {e}")
            return []

    def count_fields(self, context_type: str) -> int:
        """Count total fields in context type"""
        if context_type not in self.dbs:
            return 0

        try:
            with self.env.begin(db=self.dbs[context_type]) as txn:
                return txn.stat()['entries']
        except Exception as e:
            logger.error(f"Error counting fields: {e}")
            return 0

    def close(self):
        """Close LMDB environment"""
        if self.env:
            self.env.close()
            logger.info("LMDB closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
