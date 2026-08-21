"""Bridges connecting find_entity_by_xml and xml_controller_summary to MCP."""

from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
from find_entity_by_xml.bridges.summary_xml_format import format_summary_xml_result

__all__ = ["summary_xml", "format_summary_xml_result"]
