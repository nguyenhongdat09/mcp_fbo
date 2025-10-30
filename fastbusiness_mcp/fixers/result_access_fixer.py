"""Automatic fixer for result access issues."""

import re
from typing import Optional
from ..core.models import FixResult
from ..analyzers.sql_parser import SQLParser


class ResultAccessFixer:
    """Automatically fixes incorrect result access patterns."""

    def __init__(self):
        """Initialize fixer."""
        self.sql_parser = SQLParser()

    def fix(self, javascript: str, sql_query: Optional[str] = None) -> FixResult:
        """
        Fix incorrect result access patterns.

        Args:
            javascript: JavaScript code
            sql_query: Optional SQL query for column mapping

        Returns:
            Fix result
        """
        original = javascript
        fixed = javascript
        changes = []

        # Extract column mapping
        column_map = {}
        if sql_query:
            columns = self.sql_parser.extract_columns(sql_query)
            column_map = {col.name: col.index for col in columns}

        # Find incorrect patterns
        pattern = re.compile(r"result\[(\d+)\]\.(\w+)")

        for match in pattern.finditer(javascript):
            if match.group(2) != "Value":
                old_pattern = match.group(0)
                index = match.group(1)
                prop_name = match.group(2)

                # Try to find correct index
                if prop_name in column_map:
                    correct_index = column_map[prop_name]
                    new_pattern = f"result[{correct_index}].Value  // {prop_name}"
                else:
                    new_pattern = f"result[{index}].Value  // was: {prop_name}"

                fixed = fixed.replace(old_pattern, new_pattern, 1)
                changes.append(f"Fixed: {old_pattern} -> {new_pattern}")

        success = len(changes) > 0
        message = f"Fixed {len(changes)} result access issue(s)" if success else "No fixes needed"

        return FixResult(
            success=success, original=original, fixed=fixed, changes=changes, message=message
        )
