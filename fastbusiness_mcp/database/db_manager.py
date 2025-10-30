"""Database manager for SQLite operations."""

import aiosqlite
from pathlib import Path
from typing import Optional

from .schema import SCHEMA_SQL, get_initial_patterns
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, db_path: str):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Establish database connection."""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.execute("PRAGMA foreign_keys = ON")
        logger.info(f"Connected to database: {self.db_path}")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Disconnected from database")

    async def initialize_schema(self) -> None:
        """Initialize database schema."""
        if not self._connection:
            await self.connect()

        try:
            await self._connection.executescript(SCHEMA_SQL)
            await self._connection.commit()
            logger.info("Database schema initialized")

            # Insert initial patterns
            await self._insert_initial_patterns()

        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise

    async def _insert_initial_patterns(self) -> None:
        """Insert initial code patterns if not exists."""
        cursor = await self._connection.execute("SELECT COUNT(*) FROM patterns")
        count = (await cursor.fetchone())[0]

        if count == 0:
            patterns = get_initial_patterns()
            await self._connection.executemany(
                """
                INSERT INTO patterns (category, name, language, code, description, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                patterns,
            )
            await self._connection.commit()
            logger.info(f"Inserted {len(patterns)} initial patterns")

    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        """
        Execute a query.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cursor object
        """
        if not self._connection:
            await self.connect()

        return await self._connection.execute(query, params)

    async def executemany(self, query: str, params_list: list[tuple]) -> None:
        """
        Execute a query with multiple parameter sets.

        Args:
            query: SQL query
            params_list: List of parameter tuples
        """
        if not self._connection:
            await self.connect()

        await self._connection.executemany(query, params_list)
        await self._connection.commit()

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[tuple]:
        """
        Fetch one row.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row tuple or None
        """
        cursor = await self.execute(query, params)
        return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()) -> list[tuple]:
        """
        Fetch all rows.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of row tuples
        """
        cursor = await self.execute(query, params)
        return await cursor.fetchall()

    async def commit(self) -> None:
        """Commit current transaction."""
        if self._connection:
            await self._connection.commit()

    async def rollback(self) -> None:
        """Rollback current transaction."""
        if self._connection:
            await self._connection.rollback()
