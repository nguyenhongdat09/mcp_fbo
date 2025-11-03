"""Generate Field from LMDB Database

This tool generates FastBusiness field XML definitions by querying an LMDB database
with smart pattern matching and template-based fallback.
"""

import logging
from typing import Dict, Any, Optional
from ..lmdb_adapter import LMDBManager, FieldPatternMatcher

logger = logging.getLogger(__name__)


class GenerateFieldFromLMDBTool:
    """Tool for generating field definitions from LMDB database"""

    def __init__(self, db_path: str = "data/fields_lmdb"):
        """
        Initialize LMDB field generation tool

        Args:
            db_path: Path to LMDB database
        """
        self.db_path = db_path
        self.lmdb = None
        self.matcher = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of LMDB connection"""
        if not self._initialized:
            try:
                self.lmdb = LMDBManager(db_path=self.db_path)
                self.matcher = FieldPatternMatcher(self.lmdb)
                self._initialized = True
                logger.info(f"[OK] LMDB field database initialized at {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize LMDB: {e}")
                raise

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute field generation from LMDB

        Args:
            arguments: Tool arguments
                - field_name: Field name to generate (required)
                - context_type: Context type (DIR, FILTER_VOUCHER, etc.)
                - lookup_type: 'autocomplete', 'lookup', or 'default'
                - show_similar: Whether to show similar fields if not found

        Returns:
            Result dict with field definition or error
        """
        # Ensure LMDB is initialized
        self._ensure_initialized()

        # Extract arguments
        field_name = arguments.get('field_name')
        context_type = arguments.get('context_type', 'DIR')
        lookup_type = arguments.get('lookup_type', 'default')
        show_similar = arguments.get('show_similar', True)

        # Validate arguments
        if not field_name:
            return {
                'success': False,
                'error': 'field_name is required'
            }

        valid_contexts = ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']
        if context_type not in valid_contexts:
            return {
                'success': False,
                'error': f'Invalid context_type. Must be one of: {", ".join(valid_contexts)}'
            }

        valid_lookups = ['default', 'autocomplete', 'lookup']
        if lookup_type not in valid_lookups:
            return {
                'success': False,
                'error': f'Invalid lookup_type. Must be one of: {", ".join(valid_lookups)}'
            }

        logger.info(f"Searching for field: {field_name} (context={context_type}, lookup={lookup_type})")

        # Search with smart fallback
        field_def = self.matcher.get_field_with_fallback(
            context_type=context_type,
            field_name=field_name,
            lookup_type=lookup_type
        )

        if field_def:
            # Success - found field or template
            result = {
                'success': True,
                'field_name': field_def.get('field_name', field_name),
                'header': field_def.get('header', ''),
                'definition': field_def,
                'xml': field_def.get('xml', ''),
                'source': self._determine_source(field_def, field_name),
                'database_path': str(self.lmdb.db_path.absolute())
            }

            logger.info(f"[OK] Generated field: {result['field_name']} from {result['source']}")
            return result

        else:
            # Not found - optionally show similar fields
            # Check if database is empty
            total_fields = self.lmdb.count_fields(context_type)

            if total_fields == 0:
                result = {
                    'success': False,
                    'error': f'Database is EMPTY! Field "{field_name}" not found in {context_type}',
                    'field_name': field_name,
                    'context_type': context_type,
                    'database_empty': True,
                    'database_path': str(self.lmdb.db_path.absolute()),
                    'help': 'Run: python scripts/import_fields_to_lmdb.py --xml-dir <your_xml_directory>'
                }
                logger.error(f"✗ Database is EMPTY at {self.lmdb.db_path.absolute()}")
            else:
                result = {
                    'success': False,
                    'error': f'Field "{field_name}" not found in {context_type}',
                    'field_name': field_name,
                    'context_type': context_type,
                    'database_fields_count': total_fields,
                    'database_path': str(self.lmdb.db_path.absolute())
                }

                if show_similar:
                    similar = self.matcher.search_similar_fields(
                        context_type=context_type,
                        field_name=field_name,
                        limit=10
                    )
                    if similar:
                        result['similar_fields'] = [
                            {
                                'field_name': f['field_name'],
                                'header': f['definition'].get('header', 'N/A')
                            }
                            for f in similar
                        ]
                        result['suggestion'] = f"Did you mean one of these? {', '.join([f['field_name'] for f in similar[:5]])}"

                logger.warning(f"✗ Field not found: {field_name} (database has {total_fields} fields)")
            return result

    def _determine_source(self, field_def: Dict, requested_name: str) -> str:
        """
        Determine whether field came from exact match or template

        Args:
            field_def: Field definition
            requested_name: Originally requested field name

        Returns:
            Source description
        """
        actual_name = field_def.get('field_name', '')

        if actual_name == requested_name:
            return 'exact match'
        else:
            # Determine template type
            if actual_name.startswith('sl_') or 'so_luong' in actual_name:
                return 'quantity template (so_luong)'
            elif actual_name.startswith('ngay_') or 'ngay_ct' in actual_name:
                return 'date template (ngay_ct)'
            elif actual_name.endswith('_nt') or 'tien_nt' in actual_name:
                return 'foreign currency template (tien_nt)'
            elif 'tien' in actual_name:
                return 'currency template (tien)'
            else:
                return f'template ({actual_name})'

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the LMDB database

        Returns:
            Dict with database statistics
        """
        self._ensure_initialized()

        stats = {}
        total_fields = 0

        for context_type in ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']:
            count = self.lmdb.count_fields(context_type)
            stats[context_type] = count
            total_fields += count

        stats['total'] = total_fields

        return {
            'success': True,
            'database_path': self.db_path,
            'statistics': stats
        }

    def search_fields(self, context_type: str, pattern: str, limit: int = 20) -> Dict[str, Any]:
        """
        Search for fields matching a pattern

        Args:
            context_type: Context type
            pattern: Search pattern (substring match)
            limit: Maximum results

        Returns:
            Dict with search results
        """
        self._ensure_initialized()

        results = self.lmdb.search_fields(context_type, pattern, limit=limit)

        return {
            'success': True,
            'context_type': context_type,
            'pattern': pattern,
            'count': len(results),
            'results': [
                {
                    'field_name': r['field_name'],
                    'header': r['definition'].get('header', 'N/A'),
                    'type': r['definition'].get('type', 'N/A')
                }
                for r in results
            ]
        }

    def close(self):
        """Close LMDB connection"""
        if self.lmdb:
            self.lmdb.close()
            self._initialized = False
            logger.info("LMDB connection closed")
