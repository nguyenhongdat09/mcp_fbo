"""Models for SQL Server database object catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ParameterMeta:
    name: str
    type_name: str
    max_length: int = 0
    is_output: bool = False
    has_default_value: bool = False
    default_value: Optional[str] = None


@dataclass
class DbObjectMeta:
    schema_name: str
    name: str
    object_id: int
    type_desc: str
    sys_type: str
    definition: str
    modify_date: Optional[datetime | str] = None
    parameters: list[ParameterMeta] = field(default_factory=list)
