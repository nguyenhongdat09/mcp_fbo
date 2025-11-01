"""JSON-based adapter for LevelDB data (fallback when plyvel/rocksdb not available)"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class JSONAdapter:
    """
    Adapter to read LevelDB data from JSON export files

    This is a fallback when plyvel or rocksdb cannot be installed (e.g., Windows Python 3.13)

    JSON file format:
    {
        "metadata": {
            "source": "leveldb",
            "db_type": "DIR",
            "exported_at": "2024-11-01T10:30:00",
            "total_fields": 150
        },
        "fields": {
            "field_name_1": { ...field definition... },
            "field_name_2": { ...field definition... },
            ...
        }
    }
    """

    def __init__(self, json_path: str):
        """
        Initialize JSON adapter

        Args:
            json_path: Path to JSON export file
        """
        self.json_path = Path(json_path)
        self.data: Dict[str, Any] = {}
        self.fields: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        """Load JSON data from file"""
        if not self.json_path.exists():
            logger.warning(f"JSON file not found: {self.json_path}")
            return

        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
                self.fields = self.data.get('fields', {})

            field_count = len(self.fields)
            db_type = self.data.get('metadata', {}).get('db_type', 'unknown')
            logger.info(f"Loaded {field_count} fields from JSON ({db_type})")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON file {self.json_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading JSON file {self.json_path}: {e}")

    def get(self, key_bytes: bytes) -> Optional[bytes]:
        """
        Get field by key (LevelDB-compatible interface)

        Args:
            key_bytes: Field name as bytes

        Returns:
            Field definition as JSON bytes, or None if not found
        """
        try:
            key = key_bytes.decode('utf-8')

            if key in self.fields:
                # Return as JSON bytes (compatible with LevelDB interface)
                return json.dumps(self.fields[key]).encode('utf-8')

            return None

        except Exception as e:
            logger.error(f"Error getting field from JSON: {e}")
            return None

    def iterator(self):
        """
        Iterator over all fields (LevelDB-compatible interface)

        Yields:
            Tuple of (key_bytes, value_bytes)
        """
        for field_name, field_def in self.fields.items():
            try:
                key_bytes = field_name.encode('utf-8')
                value_bytes = json.dumps(field_def).encode('utf-8')
                yield (key_bytes, value_bytes)
            except Exception as e:
                logger.error(f"Error iterating field {field_name}: {e}")
                continue

    def close(self):
        """Close adapter (no-op for JSON, but keeps interface compatible)"""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
