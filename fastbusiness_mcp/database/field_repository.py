"""Repository for field operations."""

from typing import Optional
from ..core.models import FieldDefinition
from .db_manager import DatabaseManager


class FieldRepository:
    """Repository for managing field definitions."""

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize field repository.

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager

    async def add_field(self, field: FieldDefinition, file_path: str, controller: str) -> int:
        """
        Add or update a field definition.

        Args:
            field: Field definition
            file_path: Source file path
            controller: Controller name

        Returns:
            Field ID
        """
        cursor = await self.db.execute(
            """
            INSERT INTO fields (
                name, type, header_vi, header_en, width, align,
                allow_nulls, read_only, hidden, external,
                is_lookup, lookup_controller, lookup_reference, companion_field,
                file_path, controller
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                header_vi=excluded.header_vi,
                header_en=excluded.header_en,
                usage_count=usage_count+1,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                field.name,
                field.type,
                field.header_vi,
                field.header_en,
                field.width,
                field.align,
                int(field.allow_nulls),
                int(field.read_only),
                int(field.hidden),
                int(field.external),
                int(field.is_lookup),
                field.lookup_controller,
                field.lookup_reference,
                field.companion_field,
                file_path,
                controller,
            ),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def search_fields(self, query: str, limit: int = 50) -> list[FieldDefinition]:
        """
        Search fields by name or header.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of field definitions
        """
        rows = await self.db.fetchall(
            """
            SELECT name, type, header_vi, header_en, width, align,
                   allow_nulls, read_only, hidden, external,
                   is_lookup, lookup_controller, lookup_reference, companion_field
            FROM fields
            WHERE name LIKE ? OR header_vi LIKE ? OR header_en LIKE ?
            ORDER BY usage_count DESC, name
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        )

        return [
            FieldDefinition(
                name=row[0],
                type=row[1],
                header_vi=row[2] or "",
                header_en=row[3] or "",
                width=row[4],
                align=row[5],
                allow_nulls=bool(row[6]),
                read_only=bool(row[7]),
                hidden=bool(row[8]),
                external=bool(row[9]),
                is_lookup=bool(row[10]),
                lookup_controller=row[11],
                lookup_reference=row[12],
                companion_field=row[13],
            )
            for row in rows
        ]

    async def get_field_by_name(self, name: str) -> Optional[FieldDefinition]:
        """
        Get field definition by name.

        Args:
            name: Field name

        Returns:
            Field definition or None
        """
        row = await self.db.fetchone(
            """
            SELECT name, type, header_vi, header_en, width, align,
                   allow_nulls, read_only, hidden, external,
                   is_lookup, lookup_controller, lookup_reference, companion_field
            FROM fields
            WHERE name = ?
            ORDER BY usage_count DESC
            LIMIT 1
            """,
            (name,),
        )

        if not row:
            return None

        return FieldDefinition(
            name=row[0],
            type=row[1],
            header_vi=row[2] or "",
            header_en=row[3] or "",
            width=row[4],
            align=row[5],
            allow_nulls=bool(row[6]),
            read_only=bool(row[7]),
            hidden=bool(row[8]),
            external=bool(row[9]),
            is_lookup=bool(row[10]),
            lookup_controller=row[11],
            lookup_reference=row[12],
            companion_field=row[13],
        )

    async def get_lookup_fields(self) -> list[FieldDefinition]:
        """
        Get all lookup fields.

        Returns:
            List of lookup field definitions
        """
        rows = await self.db.fetchall(
            """
            SELECT name, type, header_vi, header_en, width, align,
                   allow_nulls, read_only, hidden, external,
                   is_lookup, lookup_controller, lookup_reference, companion_field
            FROM fields
            WHERE is_lookup = 1
            ORDER BY usage_count DESC
            """
        )

        return [
            FieldDefinition(
                name=row[0],
                type=row[1],
                header_vi=row[2] or "",
                header_en=row[3] or "",
                width=row[4],
                align=row[5],
                allow_nulls=bool(row[6]),
                read_only=bool(row[7]),
                hidden=bool(row[8]),
                external=bool(row[9]),
                is_lookup=bool(row[10]),
                lookup_controller=row[11],
                lookup_reference=row[12],
                companion_field=row[13],
            )
            for row in rows
        ]
