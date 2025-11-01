"""File type detection for FastBusiness XML files using REGEX ONLY."""

import re
from typing import Optional, List

from ..core.constants import FileType
from ..core.models import FileContext, EventType


class FileTypeDetector:
    """Detects FastBusiness XML file types using REGEX ONLY - NO XML libraries."""

    def detect(self, xml_content: str, file_path: Optional[str] = None) -> FileContext:
        """
        Detect file type and extract context using REGEX.

        Detection priority:
        1. Check folder path pattern (if provided): ...App_Data\\Controllers\\[Dir|Filter|Grid]\\
        2. Then check content for sub-types using regex:
           - Filter folder → Check for 'operation' attribute (FILTER_VOUCHER vs FILTER_NORMAL)
           - Grid folder → Check for 'allowSorting'/'allowFilter' (GRID_VIEW vs GRID_INPUT)
        3. Fallback to content-based detection

        Args:
            xml_content: XML file content
            file_path: Optional file path for folder pattern detection

        Returns:
            File context information
        """
        # Priority 1: Detect by folder structure pattern
        if file_path:
            context = self._detect_by_path(file_path, xml_content)
            if context.file_type != FileType.UNKNOWN:
                return context

        # Fallback: Content-based detection
        return self._detect_by_content(xml_content)

    def _detect_by_path(self, file_path: str, xml_content: str) -> FileContext:
        """
        Detect by folder structure pattern using REGEX

        Args:
            file_path: File path (Windows or Unix style)
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
            return self._build_dir_context(xml_content)

        # FILTER folder - Check sub-type
        elif folder_name == "Filter":
            return self._detect_filter_subtype(xml_content)

        # GRID folder - Check sub-type
        elif folder_name == "Grid":
            return self._detect_grid_subtype(xml_content)

        return FileContext(file_type=FileType.UNKNOWN)

    def _detect_filter_subtype(self, xml_content: str) -> FileContext:
        """
        Detect FILTER_VOUCHER vs FILTER_NORMAL using REGEX

        Rules:
        - Has field with 'operation' attribute → FILTER_VOUCHER
        - No field with 'operation' attribute → FILTER_NORMAL
        """
        # Check if any field has "operation" attribute
        has_operation = bool(re.search(r'<field[^>]+operation\s*=', xml_content, re.IGNORECASE))

        if has_operation:
            context = FileContext(file_type=FileType.FILTER_VOUCHER)
        else:
            context = FileContext(file_type=FileType.FILTER_NORMAL)

        # Extract events from <command event="...">
        event_matches = re.finditer(r'<command[^>]+event\s*=\s*["\'](\w+)["\']', xml_content, re.IGNORECASE)
        for match in event_matches:
            event = match.group(1)
            if hasattr(EventType, event.upper()):
                context.events.append(EventType(event))

        # Check partition
        context.has_partition = self._check_partition_regex(xml_content)

        return context

    def _detect_grid_subtype(self, xml_content: str) -> FileContext:
        """
        Detect GRID_VIEW vs GRID_INPUT using REGEX

        Rules:
        - Has field with 'allowSorting' or 'allowFilter' → GRID_VIEW
        - No field with these attributes → GRID_INPUT
        """
        # Check if any field has "allowSorting" or "allowFilter"
        has_sorting = bool(re.search(r'<field[^>]+allowSorting\s*=', xml_content, re.IGNORECASE))
        has_filter = bool(re.search(r'<field[^>]+allowFilter\s*=', xml_content, re.IGNORECASE))

        if has_sorting or has_filter:
            context = FileContext(file_type=FileType.GRID_VIEW)

            # Extract table name from <grid table="...">
            table_match = re.search(r'<grid[^>]+table\s*=\s*["\']([^"\']+)["\']', xml_content, re.IGNORECASE)
            if table_match:
                context.table_name = table_match.group(1)

            # Check partition
            context.has_partition = self._check_partition_regex(xml_content)

            # Extract events from <query event="...">
            event_matches = re.finditer(r'<query[^>]+event\s*=\s*["\'](\w+)["\']', xml_content, re.IGNORECASE)
            for match in event_matches:
                event = match.group(1)
                if hasattr(EventType, event.upper()):
                    context.events.append(EventType(event))
        else:
            context = FileContext(file_type=FileType.GRID_INPUT)

            # Extract controller name from <grid name="...">
            name_match = re.search(r'<grid[^>]+name\s*=\s*["\']([^"\']+)["\']', xml_content, re.IGNORECASE)
            if name_match:
                context.controller_name = name_match.group(1)

        return context

    def _detect_by_content(self, xml_content: str) -> FileContext:
        """
        Fallback content-based detection using REGEX

        Detection priority:
        1. Check <dir type="Report"> + XMLWhenFilterLoading → FILTER
        2. Check <grid type="Detail"> without <toolbar> → GRID INPUT
        3. Check <grid> + <queries> + <toolbar> → GRID VIEW
        4. Check <dir type="Voucher|Category"> → DIR FORM
        """
        # Check for FILTER XML
        if self._is_filter_content_regex(xml_content):
            return self._detect_filter_subtype(xml_content)

        # Check for GRID VIEW or GRID INPUT
        if re.search(r'<grid\b', xml_content, re.IGNORECASE):
            # Check for Grid View (has queries and toolbar)
            has_queries = bool(re.search(r'<queries\b', xml_content, re.IGNORECASE))
            has_toolbar = bool(re.search(r'<toolbar\b', xml_content, re.IGNORECASE))

            if has_queries and has_toolbar:
                return self._detect_grid_subtype(xml_content)
            else:
                # Grid Input (type="Detail" without toolbar)
                context = FileContext(file_type=FileType.GRID_INPUT)

                # Extract controller name
                name_match = re.search(r'<grid[^>]+name\s*=\s*["\']([^"\']+)["\']', xml_content, re.IGNORECASE)
                if name_match:
                    context.controller_name = name_match.group(1)

                return context

        # Check for DIR FORM XML
        if self._is_dir_form_content_regex(xml_content):
            return self._build_dir_context(xml_content)

        return FileContext(file_type=FileType.UNKNOWN)

    def _is_filter_content_regex(self, xml_content: str) -> bool:
        """Check if file is a filter XML by content using REGEX."""
        # Check for <dir type="Report">
        has_report_dir = bool(re.search(r'<dir[^>]+type\s*=\s*["\']Report["\']', xml_content, re.IGNORECASE))

        # Check for XMLWhenFilterLoading entity
        has_filter_entity = "XMLWhenFilterLoading" in xml_content

        return has_report_dir and has_filter_entity

    def _is_dir_form_content_regex(self, xml_content: str) -> bool:
        """Check if file is a DIR form XML by content using REGEX."""
        # Check for <dir> tag
        if not re.search(r'<dir\b', xml_content, re.IGNORECASE):
            return False

        # If it has <dir> tag and NOT a filter (XMLWhenFilterLoading), then it's a DIR form
        # Filters have type="Report" + XMLWhenFilterLoading
        has_filter_entity = "XMLWhenFilterLoading" in xml_content

        # If no filter entity, it's definitely a DIR form
        if not has_filter_entity:
            return True

        # If has filter entity, check if type="Report"
        # If NOT type="Report", still a DIR form (edge case)
        has_report = bool(re.search(r'<dir\b[^>]*\btype\s*=\s*["\']Report["\']', xml_content, re.IGNORECASE))

        return not has_report

    def _build_dir_context(self, xml_content: str) -> FileContext:
        """Build context for DIR form XML using REGEX."""
        context = FileContext(file_type=FileType.DIR)

        # Extract table name from <dir table="...">
        table_match = re.search(r'<dir[^>]+table\s*=\s*["\']([^"\']+)["\']', xml_content, re.IGNORECASE)
        if table_match:
            context.table_name = table_match.group(1)

        # Check partition
        context.has_partition = self._check_partition_regex(xml_content)

        # Extract partition field from <partition field="...">
        partition_match = re.search(r'<partition[^>]+field\s*=\s*["\']([^"\']+)["\']', xml_content, re.IGNORECASE)
        if partition_match:
            context.partition_field = partition_match.group(1)

        # Extract events from <command event="...">
        event_matches = re.finditer(r'<command[^>]+event\s*=\s*["\'](\w+)["\']', xml_content, re.IGNORECASE)
        for match in event_matches:
            event = match.group(1)
            if hasattr(EventType, event.upper()):
                context.events.append(EventType(event))

        return context

    def _check_partition_regex(self, xml_content: str) -> bool:
        """Check if file uses partition strategy using REGEX."""
        # Check for <partition> element
        if re.search(r'<partition\b', xml_content, re.IGNORECASE):
            return True

        # Check for partition placeholders
        partition_patterns = ["@@partition", "@@prime$partition", "@@master"]

        return any(pattern in xml_content for pattern in partition_patterns)
