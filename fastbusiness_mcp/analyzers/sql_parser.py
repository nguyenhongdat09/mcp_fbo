"""SQL parser for extracting column information."""

import re
from typing import Optional
from ..core.models import SQLResultColumn


class SQLParser:
    """Parses SQL queries to extract result columns."""

    def extract_columns(self, sql: str) -> list[SQLResultColumn]:
        """
        Extract columns from SELECT statement.

        Args:
            sql: SQL query string

        Returns:
            List of result columns with index and name
        """
        columns = []

        # Find SELECT clause
        select_match = re.search(
            r"\bselect\s+(.*?)\s+from\b", sql, re.IGNORECASE | re.DOTALL
        )

        if not select_match:
            return columns

        select_clause = select_match.group(1)

        # Split by comma (basic parser)
        parts = self._split_columns(select_clause)

        for index, part in enumerate(parts):
            column_name = self._extract_column_name(part.strip())
            if column_name:
                columns.append(
                    SQLResultColumn(
                        index=index, name=column_name, type=self._infer_type(part)
                    )
                )

        return columns

    def _split_columns(self, select_clause: str) -> list[str]:
        """Split select clause by comma, respecting parentheses."""
        parts = []
        current = []
        paren_depth = 0

        for char in select_clause:
            if char == "(":
                paren_depth += 1
                current.append(char)
            elif char == ")":
                paren_depth -= 1
                current.append(char)
            elif char == "," and paren_depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(char)

        if current:
            parts.append("".join(current))

        return parts

    def _extract_column_name(self, column_expr: str) -> Optional[str]:
        """Extract column name from expression."""
        # Check for 'AS alias'
        as_match = re.search(r"\bas\s+(\w+)\s*$", column_expr, re.IGNORECASE)
        if as_match:
            return as_match.group(1)

        # Check for simple column name or table.column
        simple_match = re.search(r"(\w+)\s*$", column_expr)
        if simple_match:
            return simple_match.group(1)

        return None

    def _infer_type(self, column_expr: str) -> Optional[str]:
        """Infer column type from expression."""
        expr_lower = column_expr.lower()

        if "count(" in expr_lower or "sum(" in expr_lower:
            return "Numeric"
        elif "getdate()" in expr_lower or "date" in expr_lower:
            return "DateTime"
        elif "cast(" in expr_lower:
            cast_match = re.search(r"cast\(.*?\s+as\s+(\w+)", expr_lower)
            if cast_match:
                return cast_match.group(1)

        return None
