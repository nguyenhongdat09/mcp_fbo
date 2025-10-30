"""Lookup field validator."""

from lxml import etree
from ..core.models import ValidationResult, ValidationError
from ..utils.xml_utils import parse_xml_safe, get_attribute


class LookupValidator:
    """Validates lookup field definitions."""

    def validate(self, xml_content: str) -> ValidationResult:
        """
        Validate lookup fields have companion fields.

        CRITICAL RULE from Section 5:
        - Lookup fields MUST have companion field with %l suffix
        - Companion MUST be external="true" and readOnly="true"

        Args:
            xml_content: XML file content

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        root = parse_xml_safe(xml_content)
        if root is None:
            return result

        # Find all lookup fields
        lookup_fields = self._find_lookup_fields(root)

        # Check each lookup for companion
        for field_name, reference_field in lookup_fields:
            companion_name = reference_field if reference_field else f"{field_name}%l"

            # Find companion field
            companion = self._find_field(root, companion_name)

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
                if get_attribute(companion, "external") != "true":
                    result.is_valid = False
                    error = ValidationError(
                        message=f"Companion field '{companion_name}' must have external=\"true\"",
                        code="LOOKUP_COMPANION_NOT_EXTERNAL",
                        suggestion='Add attribute: external="true"',
                    )
                    result.errors.append(error)

                if get_attribute(companion, "readOnly") != "true":
                    result.is_valid = False
                    error = ValidationError(
                        message=f"Companion field '{companion_name}' must have readOnly=\"true\"",
                        code="LOOKUP_COMPANION_NOT_READONLY",
                        suggestion='Add attribute: readOnly="true"',
                    )
                    result.errors.append(error)

        return result

    def _find_lookup_fields(self, root: etree._Element) -> list[tuple[str, str]]:
        """
        Find all lookup fields in XML.

        Args:
            root: XML root element

        Returns:
            List of (field_name, reference_field) tuples
        """
        lookup_fields = []

        for field in root.findall(".//field"):
            field_name = get_attribute(field, "name")
            items = field.find("items")

            if items is not None:
                style = get_attribute(items, "style")
                if style == "AutoComplete":
                    reference = get_attribute(items, "reference")
                    lookup_fields.append((field_name, reference))

        return lookup_fields

    def _find_field(self, root: etree._Element, field_name: str) -> etree._Element:
        """Find field element by name."""
        for field in root.findall(".//field"):
            if get_attribute(field, "name") == field_name:
                return field
        return None

    def _generate_companion_field(self, companion_name: str) -> str:
        """Generate companion field XML."""
        return f"""<field name="{companion_name}" external="true" readOnly="true">
  <header v="" e=""/>
</field>"""
