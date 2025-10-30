"""Parent form access validator for Grid Detail."""

import re
from ..core.models import ValidationResult, ValidationWarning


class ParentFormValidator:
    """Validates parent form access in Grid Detail scripts."""

    def validate(self, javascript: str, is_grid_detail: bool) -> ValidationResult:
        """
        Validate parent form access in Grid Detail.

        CRITICAL RULE from Section 7:
        - Grid Detail MUST use: var f = g.get_element().parentForm
        - Cannot access form fields directly from grid

        Args:
            javascript: JavaScript code
            is_grid_detail: Whether this is a Grid Detail file

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        if not is_grid_detail:
            return result

        # Check for form field access without parentForm
        has_parent_form = "parentForm" in javascript
        accesses_form_fields = self._check_form_field_access(javascript)

        if accesses_form_fields and not has_parent_form:
            warning = ValidationWarning(
                message="Grid Detail accesses form fields but missing parentForm declaration",
                code="GRID_DETAIL_PARENT_FORM",
                suggestion="Add at the beginning: var f = g.get_element().parentForm;",
            )
            result.warnings.append(warning)

        return result

    def _check_form_field_access(self, javascript: str) -> bool:
        """
        Check if code attempts to access form fields.

        Indicators:
        - f.getItemValue(...)
        - f.setItemValue(...)
        - Reference to parent variables with $

        Args:
            javascript: JavaScript code

        Returns:
            True if form field access detected
        """
        # Check for form methods
        if re.search(r"\bf\.getItemValue\(", javascript):
            return True
        if re.search(r"\bf\.setItemValue\(", javascript):
            return True

        # Check for parent variable references in expressions
        if re.search(r"\[\$\w+\]", javascript):
            return True

        return False
