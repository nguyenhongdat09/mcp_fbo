"""Execute SQL query against FBO SQL Server using connection resolved from file path."""

from .service import query_database

__all__ = ["query_database"]
