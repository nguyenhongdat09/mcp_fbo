"""Constants and enums for FastBusiness MCP Server."""

from enum import Enum
from typing import Final


class FileType(str, Enum):
    """FastBusiness XML file types."""

    DIR = "dir"  # Form (Voucher/Category) - Located in App_Data/Controllers/Dir/
    FILTER_VOUCHER = "filter_voucher"  # Filter with operation attribute - Located in App_Data/Controllers/Filter/
    FILTER_NORMAL = "filter_normal"  # Filter without operation attribute - Located in App_Data/Controllers/Filter/
    GRID_VIEW = "grid_view"  # Grid with allowSorting/allowFilter - Located in App_Data/Controllers/Grid/
    GRID_INPUT = "grid_input"  # Grid without allowSorting/allowFilter - Located in App_Data/Controllers/Grid/
    UNKNOWN = "unknown"


class LanguageType(str, Enum):
    """Language types in CDATA blocks."""

    SQL = "sql"
    JAVASCRIPT = "javascript"
    XML = "xml"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    """FastBusiness event types."""

    # DIR events
    LOADING = "Loading"
    CLOSING = "Closing"
    INIT_EXTERNAL_FIELDS = "InitExternalFields"
    DECLARE = "Declare"
    INSERTING = "Inserting"
    INSERTED = "Inserted"
    UPDATING = "Updating"
    UPDATED = "Updated"
    DELETING = "Deleting"
    DELETED = "Deleted"
    CHECKING = "Checking"

    # GRID events
    SCATTERING = "Scattering"

    # FILTER events
    PROCESSING = "Processing"

    # QUERY events
    FINDING = "Finding"


# Partition placeholders
PARTITION_PLACEHOLDERS: Final[dict[str, str]] = {
    "@@partition$current": "Current period (e.g., 202501)",
    "@@partition$previous": "Previous period (e.g., 202412)",
    "@@master": "Master table with partition (e.g., m91$202501)",
    "@@prime$partition$current": "Detail table current (e.g., d91$202501)",
    "@@prime$partition$previous": "Detail table previous (e.g., d91$202412)",
    "@@inquiry$partition$current": "Inquiry table current (e.g., i91$202501)",
}

# System variables
SYSTEM_VARIABLES: Final[list[str]] = [
    "@@userID",
    "@@admin",
    "@@language",
    "@@unit",
    "@@id",
    "@@master",
    "@@prime",
    "@@partition$current",
    "@@partition$previous",
    "@@pageIndex",
    "@@pageCount",
    "@@textList",
    "@@textExternal",
    "@@textOrderBy",
    "@@queryString",
    "@@refresh",
    "@@appDatabaseName",
]

# Hardcoded partition pattern (to detect mistakes)
HARDCODED_PARTITION_PATTERN: Final[str] = r"[a-z]\d{2}\$\d{6}"

# SQL keywords
SQL_KEYWORDS: Final[set[str]] = {
    "declare",
    "select",
    "insert",
    "update",
    "delete",
    "exec",
    "begin",
    "end",
    "if",
    "while",
    "from",
    "where",
    "join",
}

# JavaScript keywords
JS_KEYWORDS: Final[set[str]] = {
    "function",
    "var",
    "const",
    "let",
    "return",
    "switch",
    "case",
    "break",
    "if",
    "for",
    "while",
}

# Field attributes
FIELD_TYPES: Final[list[str]] = [
    "String",
    "DateTime",
    "Decimal",
    "Int16",
    "Int32",
    "Boolean",
]

# Lookup styles
LOOKUP_STYLES: Final[list[str]] = [
    "AutoComplete",
    "DropDownList",
    "Grid",
    "CheckBox",
    "Numeric",
    "Lookup",
]
