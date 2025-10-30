"""Initialize the FastBusiness MCP database."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastbusiness_mcp.database.db_manager import DatabaseManager
from fastbusiness_mcp.utils.logger import setup_logger

logger = setup_logger(__name__)


async def main():
    """Initialize database with schema."""
    db_path = "data/fields.db"

    logger.info(f"Initializing database: {db_path}")

    db = DatabaseManager(db_path)

    try:
        await db.connect()
        await db.initialize_schema()
        logger.info("✅ Database initialized successfully")

        # Verify
        cursor = await db.execute("SELECT COUNT(*) FROM fields")
        count = (await cursor.fetchone())[0]
        logger.info(f"Fields table: {count} records")

        cursor = await db.execute("SELECT COUNT(*) FROM patterns")
        count = (await cursor.fetchone())[0]
        logger.info(f"Patterns table: {count} records")

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        sys.exit(1)
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
