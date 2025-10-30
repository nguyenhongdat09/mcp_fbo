"""Automatic fixer for partition issues."""

import re
from ..core.models import FixResult


class PartitionFixer:
    """Automatically fixes hardcoded partitions."""

    def fix(self, sql: str) -> FixResult:
        """
        Fix hardcoded partitions in SQL.

        Args:
            sql: SQL code with hardcoded partitions

        Returns:
            Fix result with original and fixed code
        """
        original = sql
        fixed = sql
        changes = []

        # Find and replace hardcoded partitions
        pattern = re.compile(r"\b([a-z])(\d{2})\$\d{6}\b", re.IGNORECASE)

        matches = list(pattern.finditer(sql))

        for match in matches:
            old_table = match.group(0)
            prefix = match.group(1).lower()
            number = match.group(2)

            # Determine replacement
            replacement = self._get_replacement(prefix)

            # Replace
            fixed = fixed.replace(old_table, replacement, 1)
            changes.append(f"Replaced '{old_table}' with '{replacement}'")

        success = len(changes) > 0
        message = (
            f"Fixed {len(changes)} hardcoded partition(s)" if success else "No fixes needed"
        )

        return FixResult(
            success=success, original=original, fixed=fixed, changes=changes, message=message
        )

    def _get_replacement(self, prefix: str) -> str:
        """Get appropriate placeholder for table prefix."""
        if prefix == "m":
            return "@@master"
        elif prefix == "d":
            return "@@prime$partition$current"
        elif prefix == "i":
            return "@@inquiry$partition$current"
        else:
            return "@@prime$partition$current"
