"""Đọc XML entity bằng Python thuần (thay lxml)."""

from .service import get_xml_entities, set_config
from .entity_resolver import resolve_fbo_xml_entities, read_file_content

__all__ = ["get_xml_entities", "set_config", "resolve_fbo_xml_entities", "read_file_content"]
