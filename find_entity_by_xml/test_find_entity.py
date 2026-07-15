"""Tests for find_entity_by_xml."""

from __future__ import annotations

import pytest

from find_entity_by_xml.entity_cache import find_entity, list_entity_names, normalize_entity_name
from find_entity_by_xml.service import get_xml_entities, normalize_modes
from find_entity_by_xml.xml_entity_reader import clear_parse_cache, read_entity

SAMPLE_XML_PATH = (
    r"\\172.168.5.14\CustomerPro\FBI\SHOWA\FBISP242"
    r"\App_Data\Controllers\Dir\SOTran.xml"
)


class TestNormalizeEntityName:
    def test_plain(self):
        assert normalize_entity_name("APVXMLFields") == "APVXMLFields"

    def test_with_ampersand_semicolon(self):
        assert normalize_entity_name("&APVXMLFields;") == "APVXMLFields"

    def test_strips_whitespace(self):
        assert normalize_entity_name("  &Foo;  ") == "Foo"


class TestEntityCacheHelpers:
    def test_find_and_list(self):
        data = [
            {"Name": "A", "Content": "<a/>"},
            {"Name": "B", "Content": "<b/>"},
            {"Name": "A", "Content": "<a2/>"},
        ]
        hit = find_entity(data, "&A;")
        assert hit is not None
        assert hit["Content"] == "<a/>"
        assert list_entity_names(data) == ["A", "B"]


class TestNormalizeModes:
    def test_default_content(self):
        assert normalize_modes(None) == {"content"}

    def test_path_and_both(self):
        assert normalize_modes("path") == {"path"}
        assert normalize_modes(["content", "path"]) == {"content", "path"}


class TestXmlEntityReaderInline:
    def test_inline_entity_content_and_path(self, tmp_path):
        clear_parse_cache()
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
<!ENTITY Foo "<field name='x'/>">
]>
<dir>&Foo;</dir>
""",
            encoding="utf-8",
        )

        info = read_entity(xml_file, "Foo")
        assert info["found"] is True
        assert "<field name='x'/>" in info["content"]
        assert info["declarations"][0]["line"] == 3


class TestGetXmlEntitiesInline:
    def test_content_and_path(self, tmp_path):
        clear_parse_cache()
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
<!ENTITY Foo "<field name='x'/>">
]>
<dir>&Foo;</dir>
""",
            encoding="utf-8",
        )

        result = get_xml_entities(
            str(xml_file),
            ["&Foo;", "Missing"],
            mode=["content", "path"],
        )
        assert result["success"] is True
        assert result["entities"][0]["found"] is True
        assert "<field name='x'/>" in result["entities"][0]["content"]
        assert result["entities"][1]["found"] is False
        assert result["entity_paths"][0]["found"] is True
        assert result["entity_paths"][0]["line"] == 3

    def test_list_all(self, tmp_path):
        clear_parse_cache()
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
<!ENTITY Foo "<field name='x'/>">
<!ENTITY Bar "<field name='y'/>">
]>
<dir>&Foo;&Bar;</dir>
""",
            encoding="utf-8",
        )

        result = get_xml_entities(str(xml_file), list_all=True)
        assert result["success"] is True
        assert set(result["entity_names"]) == {"Foo", "Bar"}

    def test_missing_file(self):
        result = get_xml_entities(r"E:\no\such\file.xml", ["Foo"])
        assert result["success"] is False

    def test_requires_entities_or_list_all(self, tmp_path):
        clear_parse_cache()
        xml_file = tmp_path / "x.xml"
        xml_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
<!ENTITY Foo "<field name='x'/>">
]>
<dir>&Foo;</dir>
""",
            encoding="utf-8",
        )
        result = get_xml_entities(str(xml_file))
        assert result["success"] is False

    def test_path_requires_entities(self, tmp_path):
        clear_parse_cache()
        xml_file = tmp_path / "x.xml"
        xml_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
<!ENTITY Foo "<field name='x'/>">
]>
<dir>&Foo;</dir>
""",
            encoding="utf-8",
        )
        result = get_xml_entities(str(xml_file), mode="path")
        assert result["success"] is False


class TestIntegrationShowaSOTran:
    """Chạy khi truy cập được network path SHOWA FBISP242."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        clear_parse_cache()
        yield
        clear_parse_cache()

    def test_list_declare_content(self):
        xml_path = SAMPLE_XML_PATH
        if not pytest.importorskip("pathlib").Path(xml_path).is_file():
            pytest.skip("Không truy cập được SOTran.xml trên network")

        result = get_xml_entities(
            xml_path,
            ["&ListDeclare;"],
            mode="content",
        )
        assert result["success"] is True
        content = result["entities"][0]["content"]
        assert result["entities"][0]["found"] is True
        assert "declare @invoke" in content.lower()

    def test_list_declare_path(self):
        xml_path = SAMPLE_XML_PATH
        if not pytest.importorskip("pathlib").Path(xml_path).is_file():
            pytest.skip("Không truy cập được SOTran.xml trên network")

        result = get_xml_entities(
            xml_path,
            ["ListDeclare"],
            mode="path",
        )
        assert result["success"] is True
        path_info = result["entity_paths"][0]
        assert path_info["found"] is True
        assert path_info["line"] > 0
        assert path_info["source_file"].lower().endswith("extender.ent")
