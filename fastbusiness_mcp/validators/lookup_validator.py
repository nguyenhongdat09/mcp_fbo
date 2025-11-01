"""Lookup field validator using REGEX ONLY."""

import re
from ..core.models import ValidationResult, ValidationError


class LookupValidator:
    """Validates lookup field definitions using REGEX ONLY - NO XML libraries."""

    def validate(self, xml_content: str) -> ValidationResult:
        """
        Validate lookup fields have companion fields using REGEX.

        CRITICAL RULE from Section 5:
        - Lookup fields MUST have companion field with %l suffix
        - Companion MUST be external="true" and readOnly="true"

        Args:
            xml_content: XML file content

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        # Find all lookup fields using regex
        lookup_fields = self._find_lookup_fields_regex(xml_content)

        # Check each lookup for companion
        for field_name, reference_field in lookup_fields:
            companion_name = reference_field if reference_field else f"{field_name}%l"

            # Find companion field
            companion = self._find_field_regex(xml_content, companion_name)

            if companion is None:
                result.is_valid = False
                error = ValidationError(
                    message=f"Lookup field '{field_name}' missing companion '{companion_name}'",
                    code="LOOKUP_MISSING_COMPANION",
                    suggestion=self._generate_companion_field(companion_name),
                )
                result.errors.append(error)
            else:
                # Validate companion attributes
                external_val = self._extract_attribute_regex(companion, "external")
                if external_val != "true":
                    result.is_valid = False
                    error = ValidationError(
                        message=f"Companion field '{companion_name}' must have external=\"true\"",
                        code="LOOKUP_COMPANION_NOT_EXTERNAL",
                        suggestion='Add attribute: external="true"',
                    )
                    result.errors.append(error)

                readonly_val = self._extract_attribute_regex(companion, "readOnly")
                if readonly_val != "true":
                    result.is_valid = False
                    error = ValidationError(
                        message=f"Companion field '{companion_name}' must have readOnly=\"true\"",
                        code="LOOKUP_COMPANION_NOT_READONLY",
                        suggestion='Add attribute: readOnly="true"',
                    )
                    result.errors.append(error)

        return result

    def _find_lookup_fields_regex(self, xml_content: str) -> list[tuple[str, str]]:
        """
        Find all lookup fields in XML using REGEX.

        Args:
            xml_content: XML content

        Returns:
            List of (field_name, reference_field) tuples
        """
        lookup_fields = []

        # Find all <field> tags with <items style="AutoComplete">
        # Pattern: <field name="X">...<items style="AutoComplete" reference="Y">...</field>
        field_pattern = r'<field\b([^>]*)>(.*?)</field>'

        for field_match in re.finditer(field_pattern, xml_content, re.DOTALL | re.IGNORECASE):
            field_attrs = field_match.group(1)
            field_content = field_match.group(2)

            # Extract field name
            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', field_attrs)
            if not name_match:
                continue

            field_name = name_match.group(1)

            # Check if field has <items style="AutoComplete">
            items_match = re.search(r'<items\b([^>]*)\bstyle\s*=\s*["\']AutoComplete["\']', field_content, re.IGNORECASE)
            if items_match:
                items_attrs = items_match.group(1)

                # Extract reference attribute if present
                reference_match = re.search(r'reference\s*=\s*["\']([^"\']+)["\']', items_attrs)
                reference_field = reference_match.group(1) if reference_match else ""

                lookup_fields.append((field_name, reference_field))

        return lookup_fields

    def _find_field_regex(self, xml_content: str, field_name: str) -> str:
        """
        Find field element by name using REGEX.

        Args:
            xml_content: XML content
            field_name: Field name to find

        Returns:
            Field tag string or None
        """
        # Escape special regex characters in field_name
        escaped_name = re.escape(field_name)

        # Pattern: <field name="field_name" ...> or <field ...name="field_name"...>
        pattern = rf'<field\b[^>]*\bname\s*=\s*["\']' + escaped_name + r'["\'][^>]*>.*?</field>'

        match = re.search(pattern, xml_content, re.DOTALL | re.IGNORECASE)

        return match.group(0) if match else None

    def _extract_attribute_regex(self, tag_content: str, attr_name: str) -> str:
        """
        Extract attribute value from a tag string using REGEX.

        Args:
            tag_content: Tag string
            attr_name: Attribute name

        Returns:
            Attribute value or empty string
        """
        pattern = rf'{attr_name}\s*=\s*["\']([^"\']*)["\']'
        match = re.search(pattern, tag_content)

        return match.group(1) if match else ""

    def _generate_companion_field(self, companion_name: str) -> str:
        """Generate companion field XML."""
        return f"""<field name="{companion_name}" external="true" readOnly="true">
  <header v="" e=""/>
</field>"""
