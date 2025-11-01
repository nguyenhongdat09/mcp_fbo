"""Generate SQL Commands for Field Addition

This tool generates `fsd_addfields` SQL commands for adding fields to database tables,
with automatic SQL type detection and partitioned table support.
"""

import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class GenerateSQLForFieldsTool:
    """Tool for generating fsd_addfields SQL commands"""

    def __init__(self):
        """Initialize SQL generation tool"""
        pass

    def _detect_sql_type(self, field_name: str) -> str:
        """
        Detect SQL column type from field name pattern

        Args:
            field_name: Field name (already stripped of lookup suffix t/lk)

        Returns:
            SQL type string
        """
        # Pattern matching - check %l first
        if field_name.endswith('%l'):
            return 'nvarchar(256)'

        # Check _nt suffix (foreign currency) - BEFORE other checks
        if field_name.endswith('_nt'):
            return 'numeric(19,4)'

        # Check ma_ prefix
        if re.match(r'^ma_', field_name):
            return 'varchar(33)'

        # Check ten_, mo_ta, ghi_chu
        if re.match(r'^ten_', field_name) or field_name in ['mo_ta', 'ghi_chu', 'dien_giai']:
            return 'nvarchar(256)'

        # Check ngay_ prefix or _date suffix
        if re.match(r'^ngay_', field_name) or re.search(r'_date$', field_name):
            return 'smalldatetime'

        # Check tien patterns (NO _nt)
        if re.match(r'^tien', field_name) or re.search(r'_tien$', field_name) or re.match(r'^t_', field_name):
            return 'numeric(19,4)'

        # Check gia patterns
        if re.match(r'^gia', field_name) or 'don_gia' in field_name or 'ty_gia' in field_name:
            return 'numeric(19,4)'

        # Check so_luong patterns
        if re.match(r'^so_luong', field_name) or re.search(r'_luong$', field_name) or re.search(r'_sl$', field_name):
            return 'numeric(19,4)'

        # Check int patterns
        if re.match(r'^thang$', field_name) or re.match(r'^nam$', field_name) or re.match(r'^so_ngay', field_name) or re.search(r'_count$', field_name):
            return 'int'

        # Check tinyint patterns
        if re.match(r'^check_', field_name) or re.match(r'^is_', field_name) or re.match(r'^status$', field_name):
            return 'tinyint'

        # Default
        return 'nvarchar(256)'

    def _normalize_table_name(self, table_name: str) -> str:
        """
        Normalize table name - preserve $ suffix if present

        Args:
            table_name: Table name from XML (e.g., 'd91$000000', 'dmvt')

        Returns:
            Normalized table name for SQL (e.g., 'd91$', 'dmvt')
        """
        # Check if table has $ (partitioned)
        if '$' in table_name:
            # Extract base name before $ (e.g., 'd91$000000' → 'd91$')
            base = table_name.split('$')[0]
            return f"{base}$"
        else:
            # No partition, use as-is
            return table_name

    def _strip_lookup_suffix(self, field_name: str) -> str:
        """
        Strip lookup suffix from field name for SQL column

        Args:
            field_name: Field name with potential suffix (e.g., 'ma_kht', 'ma_khlk', 'ten_kh%l')

        Returns:
            Base field name without lookup suffix (e.g., 'ma_kh', 'ten_kh%l')
        """
        # Don't strip %l - it's part of the actual column name
        if field_name.endswith('%l'):
            return field_name

        # Don't strip _nt suffix - it's part of the actual column name (foreign currency)
        if field_name.endswith('_nt'):
            return field_name

        # Strip 'lk' suffix (lookup multi-select)
        if field_name.endswith('lk'):
            # ma_khlk → ma_kh
            return field_name[:-2]

        # Strip 't' suffix ONLY if it's a lookup autocomplete suffix
        # Check pattern: field ends with 't' AND previous char is NOT 't' (to avoid mất, vật, etc.)
        if field_name.endswith('t') and len(field_name) > 1:
            # Check if previous char is also 't' - if yes, don't strip
            if field_name[-2] != 't':
                # ma_kht → ma_kh, ma_bo_phant → ma_bo_phan
                # But ma_vt stays ma_vt (single char before t), mat stays mat
                # Only strip if there are at least 2 chars before 't' AND field starts with ma_ or similar patterns
                if len(field_name) > 3 and (field_name.startswith('ma_') or field_name.startswith('ten_')):
                    # ma_kht (len=6, >3) → strip → ma_kh
                    # ma_vt (len=5, >3) → check if real field or lookup
                    # If ends with single letter + t, likely real name, don't strip
                    # ma_vt → v + t (2 chars after _) → keep
                    # ma_kht → kh + t (3 chars after _) → strip
                    after_underscore = field_name.split('_')[-1]  # Get part after last _
                    if len(after_underscore) > 2:  # More than 2 chars (e.g., 'kht' = 3 chars)
                        return field_name[:-1]

        return field_name

    def _extract_master_table_from_field(self, field_name: str) -> Optional[str]:
        """
        Extract master table name from field pattern (e.g., ma_kh → dmkh)

        Args:
            field_name: Field name

        Returns:
            Master table name or None
        """
        # Only for ma_ fields
        if field_name.startswith('ma_'):
            # ma_kh → kh, ma_vt → vt, ma_bp → bp
            code = field_name[3:]  # Remove 'ma_'
            # Remove lookup suffixes
            code = code.replace('t', '').replace('lk', '')
            return f"dm{code}"

        return None

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute SQL generation for fields

        Args:
            arguments: Tool arguments
                - field_names: List of field names (required)
                - tables: List of table names (required)
                - create_master_table: Whether to generate master table creation (optional, default=False)

        Returns:
            Result dict with SQL commands or error
        """
        # Extract arguments
        field_names = arguments.get('field_names', [])
        tables = arguments.get('tables', [])
        create_master_table = arguments.get('create_master_table', False)

        # Validate arguments
        if not field_names:
            return {
                'success': False,
                'error': 'field_names is required (list of strings)'
            }

        if not tables:
            return {
                'success': False,
                'error': 'tables is required (list of table names)'
            }

        if not isinstance(field_names, list):
            field_names = [field_names]

        if not isinstance(tables, list):
            tables = [tables]

        logger.info(f"Generating SQL for fields: {field_names} → tables: {tables}")

        # Generate SQL commands
        sql_commands = []

        # Generate fsd_addfields for each table
        for table_name in tables:
            # Normalize table name (preserve $ if present)
            normalized_table = self._normalize_table_name(table_name)

            sql_commands.append(f"-- Thêm vào bảng {table_name}")

            for field_name in field_names:
                # Strip lookup suffix for column name
                column_name = self._strip_lookup_suffix(field_name)

                # Detect SQL type
                sql_type = self._detect_sql_type(field_name)

                # Generate fsd_addfields command
                cmd = f"exec fsd_addfields '{normalized_table}', '{column_name}', '{sql_type}'"
                sql_commands.append(cmd)

            sql_commands.append("")  # Empty line between tables

        # Optional: Generate master table creation for lookup fields
        master_tables_generated = set()
        if create_master_table:
            for field_name in field_names:
                # Only for lookup fields (ma_* pattern)
                if field_name.startswith('ma_'):
                    master_table = self._extract_master_table_from_field(field_name)
                    if master_table and master_table not in master_tables_generated:
                        # Extract base field name for columns
                        base_field = self._strip_lookup_suffix(field_name)
                        base_code = base_field[3:]  # Remove 'ma_'

                        # Find corresponding ten_ field if exists
                        ten_field = None
                        for fname in field_names:
                            if fname.startswith('ten_') and fname.endswith('%l'):
                                ten_field = fname
                                break

                        sql_commands.append(f"-- Tạo bảng master {master_table} (nếu chưa có)")
                        sql_commands.append(f"IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{master_table}')")
                        sql_commands.append("BEGIN")
                        sql_commands.append(f"  CREATE TABLE {master_table} (")
                        sql_commands.append(f"    {base_field} varchar(33) PRIMARY KEY,")
                        if ten_field:
                            sql_commands.append(f"    {ten_field} nvarchar(256),")
                        sql_commands.append("    status varchar(1) DEFAULT '1'")
                        sql_commands.append("  )")
                        sql_commands.append("END")
                        sql_commands.append("")

                        master_tables_generated.add(master_table)

        # Build result
        sql_script = '\n'.join(sql_commands)

        return {
            'success': True,
            'field_names': field_names,
            'tables': tables,
            'sql_script': sql_script,
            'command_count': len([cmd for cmd in sql_commands if cmd.startswith('exec')]),
            'master_tables': list(master_tables_generated) if master_tables_generated else []
        }
