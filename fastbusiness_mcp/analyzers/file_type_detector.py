"""File type detection for FastBusiness XML files."""

import re
from typing import Optional
from lxml import etree

from ..core.constants import FileType
from ..core.models import FileContext, EventType
from ..utils.xml_utils import parse_xml_safe, get_attribute


class FileTypeDetector:
    """Detects FastBusiness XML file types."""

    def detect(self, xml_content: str) -> FileContext:
        """
        Detect file type and extract context.

        Detection priority (from docs):
        1. Check <dir type="Report"> + <!ENTITY XMLWhenFilterLoading> → FILTER
        2. Check <grid type="Detail"> without <toolbar> → GRID DETAIL
        3. Check <grid> + <queries> + <toolbar> → GRID VIEW
        4. Check <dir type="Voucher|Category"> → DIR FORM

        Args:
            xml_content: XML file content

        Returns:
            File context information
        """
        root = parse_xml_safe(xml_content)

        if root is None:
            return FileContext(file_type=FileType.UNKNOWN)

        # Check for FILTER XML
        if self._is_filter(xml_content, root):
            return self._build_filter_context(root)

        # Check for GRID DETAIL XML
        if self._is_grid_detail(root):
            return self._build_grid_detail_context(root)

        # Check for GRID VIEW XML
        if self._is_grid_view(root):
            return self._build_grid_view_context(root)

        # Check for DIR FORM XML
        if self._is_dir_form(root):
            return self._build_dir_context(root)

        return FileContext(file_type=FileType.UNKNOWN)

    def _is_filter(self, xml_content: str, root: etree._Element) -> bool:
        """Check if file is a filter XML."""
        # Check for dir type="Report"
        if root.tag == "dir" and get_attribute(root, "type") == "Report":
            # Check for XMLWhenFilterLoading entity
            if "XMLWhenFilterLoading" in xml_content:
                return True

        return False

    def _is_grid_detail(self, root: etree._Element) -> bool:
        """Check if file is a grid detail XML."""
        if root.tag == "grid" and get_attribute(root, "type") == "Detail":
            # Grid detail does NOT have toolbar
            toolbar = root.find(".//toolbar")
            return toolbar is None

        return False

    def _is_grid_view(self, root: etree._Element) -> bool:
        """Check if file is a grid view XML."""
        if root.tag == "grid":
            # Must have queries and toolbar
            has_queries = root.find(".//queries") is not None
            has_toolbar = root.find(".//toolbar") is not None

            return has_queries and has_toolbar

        return False

    def _is_dir_form(self, root: etree._Element) -> bool:
        """Check if file is a DIR form XML."""
        if root.tag == "dir":
            dir_type = get_attribute(root, "type")
            return dir_type in ["Voucher", "Category", ""]

        return False

    def _build_filter_context(self, root: etree._Element) -> FileContext:
        """Build context for filter XML."""
        context = FileContext(file_type=FileType.FILTER)

        # Extract events
        for command in root.findall(".//command"):
            event = get_attribute(command, "event")
            if event and hasattr(EventType, event.upper()):
                context.events.append(EventType(event))

        # Check partition
        context.has_partition = self._check_partition(root)

        return context

    def _build_grid_detail_context(self, root: etree._Element) -> FileContext:
        """Build context for grid detail XML."""
        context = FileContext(file_type=FileType.GRID_DETAIL)

        # Grid details are embedded in forms
        context.controller_name = get_attribute(root, "name")

        return context

    def _build_grid_view_context(self, root: etree._Element) -> FileContext:
        """Build context for grid view XML."""
        context = FileContext(file_type=FileType.GRID_VIEW)

        # Extract table name
        context.table_name = get_attribute(root, "table")

        # Check partition
        context.has_partition = self._check_partition(root)

        # Extract events
        for query in root.findall(".//query"):
            event = get_attribute(query, "event")
            if event and hasattr(EventType, event.upper()):
                context.events.append(EventType(event))

        return context

    def _build_dir_context(self, root: etree._Element) -> FileContext:
        """Build context for DIR form XML."""
        context = FileContext(file_type=FileType.DIR)

        # Extract table name
        context.table_name = get_attribute(root, "table")

        # Check partition
        context.has_partition = self._check_partition(root)

        # Extract partition field
        partition_elem = root.find(".//partition")
        if partition_elem is not None:
            context.partition_field = get_attribute(partition_elem, "field")

        # Extract events
        for command in root.findall(".//command"):
            event = get_attribute(command, "event")
            if event and hasattr(EventType, event.upper()):
                context.events.append(EventType(event))

        return context

    def _check_partition(self, root: etree._Element) -> bool:
        """Check if file uses partition strategy."""
        # Check for partition element
        if root.find(".//partition") is not None:
            return True

        # Check for partition placeholders in text
        xml_str = etree.tostring(root, encoding="unicode")
        partition_patterns = ["@@partition", "@@prime$partition", "@@master"]

        return any(pattern in xml_str for pattern in partition_patterns)
