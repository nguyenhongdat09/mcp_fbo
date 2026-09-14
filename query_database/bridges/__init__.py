"""Bridges connecting query_database with analytical engines."""

from query_database.bridges.summary_bridge import summary_object
from query_database.bridges.summary_format import format_summary_result

__all__ = ["summary_object", "format_summary_result"]
