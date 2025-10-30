"""Partition strategy validator - CRITICAL component."""

import re
from typing import Optional

from ..core.models import ValidationResult, ValidationError
from ..core.constants import PARTITION_PLACEHOLDERS


class PartitionValidator:
    """Validates partition usage in SQL queries."""

    def validate(self, sql: str) -> ValidationResult:
        """
        Validate partition usage in SQL.

        This is CRITICAL validation based on Section 3 of the docs.
        Rules:
        - NEVER hardcode partition tables (e.g., d91$202501)
        - ALWAYS use placeholders (@@prime$partition$current)

        Args:
            sql: SQL query string

        Returns:
            Validation result with errors
        """
        result = ValidationResult(is_valid=True)

        # Find hardcoded partitions
        hardcoded = self._find_hardcoded_partitions(sql)

        for match, line_num in hardcoded:
            result.is_valid = False

            # Determine appropriate placeholder
            suggestion = self._suggest_placeholder(match)

            error = ValidationError(
                line=line_num,
                message=f"Hardcoded partition table '{match}' detected",
                code="PARTITION_HARDCODED",
                suggestion=f"Replace with: {suggestion}",
                context=match,
            )
            result.errors.append(error)

        return result

    def _find_hardcoded_partitions(self, sql: str) -> list[tuple[str, int]]:
        """
        Find hardcoded partition tables in SQL.

        Pattern: d91$202501, m91$202412, i91$202501, etc.
        Format: [a-z]##$YYYYMM

        Args:
            sql: SQL string

        Returns:
            List of (table_name, line_number) tuples
        """
        # Pattern matches: letter + 2 digits + $ + 6 digits
        pattern = re.compile(r"\b([a-z]\d{2})\$(\d{6})\b", re.IGNORECASE)
        findings = []

        for line_num, line in enumerate(sql.split("\n"), 1):
            matches = pattern.finditer(line)
            for match in matches:
                findings.append((match.group(0), line_num))

        return findings

    def _suggest_placeholder(self, table_name: str) -> str:
        """
        Suggest appropriate placeholder for hardcoded table.

        Args:
            table_name: Hardcoded table name (e.g., "d91$202501")

        Returns:
            Suggested placeholder
        """
        prefix = table_name.split("$")[0].lower()

        # Master table (m##)
        if prefix.startswith("m"):
            return "@@master"

        # Detail table (d##)
        if prefix.startswith("d"):
            return "@@prime$partition$current"

        # Inquiry table (i##)
        if prefix.startswith("i"):
            return "@@inquiry$partition$current"

        # Default
        return "@@prime$partition$current"

    def check_cross_month_update(self, sql: str) -> Optional[ValidationError]:
        """
        Check for proper cross-month update pattern.

        When date field changes, must:
        1. DELETE from @@prime$partition$previous
        2. INSERT into @@prime$partition$current

        Args:
            sql: SQL string

        Returns:
            Validation error if pattern is incorrect, None otherwise
        """
        sql_lower = sql.lower()

        # Check if this is an update query
        if "update " in sql_lower and "@@prime$partition$current" in sql_lower:
            # Check if previous partition is also handled
            if "delete" not in sql_lower or "@@prime$partition$previous" not in sql_lower:
                return ValidationError(
                    message="Cross-month update detected but missing DELETE from previous partition",
                    code="PARTITION_CROSS_MONTH",
                    suggestion="Add: delete @@prime$partition$previous where stt_rec = @stt_rec",
                )

        return None
