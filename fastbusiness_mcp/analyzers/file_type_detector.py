"""File type detection for FastBusiness XML files with folder pattern detection."""

import re
from typing import Optional, List
from lxml import etree

from ..core.constants import FileType
from ..core.models import FileContext, EventType
from ..utils.xml_utils import parse_xml_safe, get_attribute


class FileTypeDetector:
    """Detects FastBusiness XML file types with priority-based detection."""

    def detect(self, xml_content: str, file_path: Optional[str] = None) -> FileContext:
        """
        Detect file type and extract context.

        Detection priority:
        1. Check folder path pattern (if provided): ...App_Data\\Controllers\\[Dir|Filter|Grid]\\
        2. Then check content for sub-types:
           - Filter folder → Check for 'operation' attribute (FILTER_VOUCHER vs FILTER_NORMAL)
           - Grid folder → Check for 'allowSorting'/'allowFilter' (GRID_VIEW vs GRID_INPUT)
        3. Fallback to content-based detection (old logic)

        Args:
            xml_content: XML file content
            file_path: Optional file path for folder pattern detection

        Returns:
            File context information
        """
        root = parse_xml_safe(xml_content)

        if root is None:
            return FileContext(file_type=FileType.UNKNOWN)

        # Priority 1: Detect by folder structure pattern
        if file_path:
            context = self._detect_by_path(file_path, root, xml_content)
            if context.file_type != FileType.UNKNOWN:
                return context

        # Fallback: Content-based detection (old logic)
        return self._detect_by_content(root, xml_content)

    def _detect_by_path(
        self,
        file_path: str,
        root: etree._Element,
        xml_content: str
    ) -> FileContext:
        """
        Detect by folder structure pattern: ...App_Data\\Controllers\\[Dir|Filter|Grid]\\

        Args:
            file_path: File path (Windows or Unix style)
            root: Parsed XML root
            xml_content: Raw XML content

        Returns:
            FileContext with detected type
        """
        # Normalize path separators (convert to Windows style for pattern matching)
        normalized_path = file_path.replace('/', '\\')

        # Check if path matches ...App_Data\Controllers\[Dir|Filter|Grid]\
        if '\\App_Data\\Controllers\\' not in normalized_path:
            return FileContext(file_type=FileType.UNKNOWN)

        # Extract folder after Controllers
        parts = normalized_path.split('\\App_Data\\Controllers\\')
        if len(parts) < 2:
            return FileContext(file_type=FileType.UNKNOWN)

        # Get folder name (Dir, Filter, or Grid)
        controller_path = parts[1]
        folder_name = controller_path.split('\\')[0]

        # DIR folder - 100% certain
        if folder_name == "Dir":
            return self._build_dir_context(root)

        # FILTER folder - Check sub-type
        elif folder_name == "Filter":
            return self._detect_filter_subtype(root, xml_content)

        # GRID folder - Check sub-type
        elif folder_name == "Grid":
            return self._detect_grid_subtype(root)

        return FileContext(file_type=FileType.UNKNOWN)

    def _detect_filter_subtype(
        self,
        root: etree._Element,
        xml_content: str
    ) -> FileContext:
        """
        Detect FILTER_VOUCHER vs FILTER_NORMAL

        Rules:
        - Has field with 'operation' attribute → FILTER_VOUCHER
        - No field with 'operation' attribute → FILTER_NORMAL
        """
        try:
            # Check if any field has "operation" attribute
            has_operation = len(root.xpath("//field[@operation]")) > 0

            if has_operation:
                context = FileContext(file_type=FileType.FILTER_VOUCHER)
            else:
                context = FileContext(file_type=FileType.FILTER_NORMAL)

            # Extract events
            for command in root.findall(".//command"):
                event = get_attribute(command, "event")
                if event and hasattr(EventType, event.upper()):
                    context.events.append(EventType(event))

            # Check partition
            context.has_partition = self._check_partition(root)

            return context

        except Exception:
            # Fallback to regex
            if re.search(r'<field[^>]+operation\s*=', xml_content):
                return FileContext(file_type=FileType.FILTER_VOUCHER)
            else:
                return FileContext(file_type=FileType.FILTER_NORMAL)

    def _detect_grid_subtype(self, root: etree._Element) -> FileContext:
        """
        Detect GRID_VIEW vs GRID_INPUT

        Rules:
        - Has field with 'allowSorting' or 'allowFilter' → GRID_VIEW
        - No field with these attributes → GRID_INPUT
        """
        try:
            # Check if any field has "allowSorting" or "allowFilter"
            has_sorting_or_filter = (
                len(root.xpath("//field[@allowSorting]")) > 0 or
                len(root.xpath("//field[@allowFilter]")) > 0
            )

            if has_sorting_or_filter:
                context = FileContext(file_type=FileType.GRID_VIEW)

                # Extract table name
                context.table_name = get_attribute(root, "table")

                # Check partition
                context.has_partition = self._check_partition(root)

                # Extract events from queries
                for query in root.findall(".//query"):
                    event = get_attribute(query, "event")
                    if event and hasattr(EventType, event.upper()):
                        context.events.append(EventType(event))

            else:
                context = FileContext(file_type=FileType.GRID_INPUT)
                context.controller_name = get_attribute(root, "name")

            return context

        except Exception:
            # Fallback: default to GRID_INPUT
            return FileContext(file_type=FileType.GRID_INPUT)

    def _detect_by_content(
        self,
        root: etree._Element,
        xml_content: str
    ) -> FileContext:
        """
        Fallback content-based detection (when path is not available)

        Detection priority (from old logic):
        1. Check <dir type="Report"> + <!ENTITY XMLWhenFilterLoading> → FILTER
        2. Check <grid type="Detail"> without <toolbar> → GRID INPUT
        3. Check <grid> + <queries> + <toolbar> → GRID VIEW
        4. Check <dir type="Voucher|Category"> → DIR FORM
        """

        # Check for FILTER XML
        if self._is_filter_content(xml_content, root):
            return self._detect_filter_subtype(root, xml_content)

        # Check for GRID VIEW or GRID INPUT
        if root.tag == "grid":
            # Check for Grid View (has queries and toolbar)
            has_queries = root.find(".//queries") is not None
            has_toolbar = root.find(".//toolbar") is not None

            if has_queries and has_toolbar:
                return self._detect_grid_subtype(root)
            else:
                # Grid Input (type="Detail" without toolbar)
                context = FileContext(file_type=FileType.GRID_INPUT)
                context.controller_name = get_attribute(root, "name")
                return context

        # Check for DIR FORM XML
        if self._is_dir_form_content(root):
            return self._build_dir_context(root)

        return FileContext(file_type=FileType.UNKNOWN)

    def _is_filter_content(self, xml_content: str, root: etree._Element) -> bool:
        """Check if file is a filter XML by content."""
        # Check for dir type="Report"
        if root.tag == "dir" and get_attribute(root, "type") == "Report":
            # Check for XMLWhenFilterLoading entity
            if "XMLWhenFilterLoading" in xml_content:
                return True

        return False

    def _is_dir_form_content(self, root: etree._Element) -> bool:
        """Check if file is a DIR form XML by content."""
        if root.tag == "dir":
            dir_type = get_attribute(root, "type")
            return dir_type in ["Voucher", "Category", ""]

        return False

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
