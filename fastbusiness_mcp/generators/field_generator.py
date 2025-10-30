"""Field definition generator."""

from typing import Optional
from ..core.models import FieldDefinition


class FieldGenerator:
    """Generates field definitions for FastBusiness XML."""

    def generate_field(
        self,
        name: str,
        field_type: str = "String",
        header_vi: str = "",
        header_en: str = "",
        is_lookup: bool = False,
        lookup_controller: Optional[str] = None,
        lookup_reference: Optional[str] = None,
        **attributes: dict,
    ) -> str:
        """
        Generate complete field definition.

        Args:
            name: Field name
            field_type: Field type
            header_vi: Vietnamese header
            header_en: English header
            is_lookup: Whether this is a lookup field
            lookup_controller: Controller for lookup
            lookup_reference: Reference field for lookup
            **attributes: Additional attributes

        Returns:
            XML field definition
        """
        # Build attributes
        attrs = []
        attrs.append(f'name="{name}"')

        if field_type != "String":
            attrs.append(f'type="{field_type}"')

        for key, value in attributes.items():
            if value:
                if isinstance(value, bool):
                    attrs.append(f'{key}="{str(value).lower()}"')
                else:
                    attrs.append(f'{key}="{value}"')

        attrs_str = " ".join(attrs)

        # Generate field XML
        xml = f'<field {attrs_str}>\n'
        xml += f'  <header v="{header_vi}" e="{header_en}"/>\n'

        # Add items for lookup
        if is_lookup and lookup_controller:
            ref = lookup_reference or f"{name}%l"
            xml += f'  <items style="AutoComplete"\n'
            xml += f'         controller="{lookup_controller}"\n'
            xml += f'         reference="{ref}"/>\n'

        xml += "</field>"

        return xml

    def generate_companion_field(self, field_name: str) -> str:
        """
        Generate companion field for lookup.

        Args:
            field_name: Lookup field name

        Returns:
            Companion field XML
        """
        companion_name = f"{field_name}%l"
        return f'<field name="{companion_name}" external="true" readOnly="true">\n  <header v="" e=""/>\n</field>'

    def generate_dropdown_field(
        self, name: str, header_vi: str, header_en: str, options: list[tuple[str, str, str]]
    ) -> str:
        """
        Generate dropdown field.

        Args:
            name: Field name
            header_vi: Vietnamese header
            header_en: English header
            options: List of (value, text_vi, text_en) tuples

        Returns:
            Dropdown field XML
        """
        xml = f'<field name="{name}">\n'
        xml += f'  <header v="{header_vi}" e="{header_en}"/>\n'
        xml += '  <items style="DropDownList">\n'

        for value, text_vi, text_en in options:
            xml += f'    <item value="{value}"><text v="{text_vi}" e="{text_en}"/></item>\n'

        xml += "  </items>\n"
        xml += "</field>"

        return xml

    def generate_grid_detail_field(
        self, name: str, controller: str, foreign_key: str
    ) -> str:
        """
        Generate grid detail field reference.

        Args:
            name: Field name (usually table name like "d91")
            controller: Controller name
            foreign_key: Foreign key field

        Returns:
            Grid detail field XML
        """
        xml = f'<field name="{name}" external="true" rows="144">\n'
        xml += '  <header v="" e=""/>\n'
        xml += f'  <items style="Grid" controller="{controller}" row="1">\n'
        xml += '    <item value="ForeignKey">\n'
        xml += f'      <text v="String: {foreign_key}, {foreign_key}"/>\n'
        xml += "    </item>\n"
        xml += "  </items>\n"
        xml += "</field>"

        return xml
