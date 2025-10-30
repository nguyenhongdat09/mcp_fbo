"""Result access validator - CRITICAL component."""

import re
from typing import Optional

from ..core.models import ValidationResult, ValidationError, SQLResultColumn
from ..analyzers.sql_parser import SQLParser


class ResultAccessValidator:
    """Validates SQL result access patterns in JavaScript."""

    def __init__(self):
        """Initialize validator."""
        self.sql_parser = SQLParser()

    def validate(
        self, javascript: str, sql_query: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate result access patterns in JavaScript.

        CRITICAL RULE from Section 4:
        - MUST access by index: result[0].Value
        - MUST NOT access by property: result[0].column_name

        Args:
            javascript: JavaScript code
            sql_query: Optional SQL query to map columns

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        # Extract column mapping if SQL provided
        column_map = {}
        if sql_query:
            columns = self.sql_parser.extract_columns(sql_query)
            column_map = {col.name: col.index for col in columns}

        # Find incorrect result access patterns
        incorrect_patterns = self._find_incorrect_access(javascript)

        for pattern, line_num in incorrect_patterns:
            result.is_valid = False

            error = ValidationError(
                line=line_num,
                message=f"Incorrect result access: {pattern}",
                code="RESULT_ACCESS_PROPERTY",
                suggestion=self._suggest_fix(pattern, column_map),
                context=pattern,
            )
            result.errors.append(error)

        return result

    def _find_incorrect_access(self, javascript: str) -> list[tuple[str, int]]:
        """
        Find incorrect result access patterns.

        Incorrect: result[0].column_name
        Correct: result[0].Value

        Args:
            javascript: JavaScript code

        Returns:
            List of (pattern, line_number) tuples
        """
        # Pattern: result[number].word (where word is not "Value")
        pattern = re.compile(r"result\[(\d+)\]\.(\w+)")
        findings = []

        for line_num, line in enumerate(javascript.split("\n"), 1):
            matches = pattern.finditer(line)
            for match in matches:
                property_name = match.group(2)
                # "Value" is correct, anything else is wrong
                if property_name != "Value":
                    findings.append((match.group(0), line_num))

        return findings

    def _suggest_fix(self, pattern: str, column_map: dict[str, int]) -> str:
        """
        Suggest fix for incorrect result access.

        Args:
            pattern: Incorrect pattern (e.g., "result[0].ma_kh")
            column_map: Column name to index mapping

        Returns:
            Suggested fix
        """
        # Extract index and property name
        match = re.search(r"result\[(\d+)\]\.(\w+)", pattern)
        if match:
            index = match.group(1)
            prop_name = match.group(2)

            # Try to find correct index from column map
            if prop_name in column_map:
                correct_index = column_map[prop_name]
                return f"result[{correct_index}].Value  // {prop_name}"
            else:
                return f"result[{index}].Value  // Use index-based access"

        return "result[index].Value"

    def generate_column_mapping(self, sql_query: str) -> str:
        """
        Generate JavaScript comment with column mapping.

        Args:
            sql_query: SQL query

        Returns:
            Comment block with column mapping
        """
        columns = self.sql_parser.extract_columns(sql_query)

        if not columns:
            return ""

        lines = ["// Column mapping:"]
        for col in columns:
            lines.append(f"// result[{col.index}].Value -> {col.name}")

        return "\n".join(lines)
