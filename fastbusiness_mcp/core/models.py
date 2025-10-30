"""Pydantic models for FastBusiness MCP Server."""

from typing import Optional
from pydantic import BaseModel, Field

from .constants import FileType, LanguageType, EventType


class ValidationResult(BaseModel):
    """Result of a validation operation."""

    is_valid: bool
    errors: list["ValidationError"] = Field(default_factory=list)
    warnings: list["ValidationWarning"] = Field(default_factory=list)


class ValidationError(BaseModel):
    """Validation error details."""

    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    code: str  # Error code for categorization
    suggestion: Optional[str] = None  # Fix suggestion
    context: Optional[str] = None  # Code context


class ValidationWarning(BaseModel):
    """Validation warning details."""

    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    code: str
    suggestion: Optional[str] = None


class FieldDefinition(BaseModel):
    """Field definition from XML."""

    name: str
    type: str = "String"
    header_vi: str = ""
    header_en: str = ""
    width: Optional[int] = None
    align: Optional[str] = None
    allow_nulls: bool = True
    read_only: bool = False
    hidden: bool = False
    external: bool = False
    is_lookup: bool = False
    lookup_controller: Optional[str] = None
    lookup_reference: Optional[str] = None
    companion_field: Optional[str] = None


class SQLResultColumn(BaseModel):
    """SQL result column mapping."""

    index: int
    name: str
    type: Optional[str] = None


class PartitionInfo(BaseModel):
    """Partition information."""

    table_prefix: str  # e.g., "d91"
    current_period: str  # e.g., "202501"
    previous_period: str  # e.g., "202412"


class FileContext(BaseModel):
    """Context information about a FastBusiness XML file."""

    file_type: FileType
    has_partition: bool = False
    partition_field: Optional[str] = None
    controller_name: Optional[str] = None
    table_name: Optional[str] = None
    events: list[EventType] = Field(default_factory=list)


class CodeSnippet(BaseModel):
    """Generated code snippet."""

    language: LanguageType
    code: str
    description: str
    category: str  # e.g., "field", "command", "script"


class FixResult(BaseModel):
    """Result of a fix operation."""

    success: bool
    original: str
    fixed: str
    changes: list[str] = Field(default_factory=list)
    message: str
