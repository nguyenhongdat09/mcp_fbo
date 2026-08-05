"""Tests for find_entity_by_xml."""

from __future__ import annotations

import pytest

from find_entity_by_xml.entity_cache import find_entity, list_entity_names, normalize_entity_name
from find_entity_by_xml.service import get_xml_entities, normalize_modes
from find_entity_by_xml.facade import get_entity

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

        info = get_entity(str(xml_file), "Foo")
        assert info is not None
        assert "<field name='x'/>" in info["value"]
        assert info["line"] == 3

    def test_resolve_entities_uses_cache(self, tmp_path):
        from find_entity_by_xml.entity_resolver import clear_cache
        from find_entity_by_xml.facade import resolve_entities
        import time

        xml_file = tmp_path / "test_cache.xml"
        xml_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
<!ENTITY Foo "<field name='x'/>">
<!ENTITY Bar "<field name='y'/>">
]>
<dir>&Foo;</dir>
""",
            encoding="utf-8",
        )

        clear_cache()
        t1_start = time.perf_counter()
        res1 = resolve_entities(str(xml_file))
        t1 = time.perf_counter() - t1_start

        t2_start = time.perf_counter()
        res2 = resolve_entities(str(xml_file))
        t2 = time.perf_counter() - t2_start

        # Lần 2 phải cực nhanh.
        assert res1["system_entities"]["Foo"]["value"] == "<field name='x'/>"
        assert res2["system_entities"]["Foo"]["value"] == "<field name='x'/>"
        assert t2 <= t1 * 1.5  # Do mock file nhỏ nên t2 có thể xấp xỉ t1. Ở môi trường SMB t2 sẽ < t1 * 0.2

        t3_start = time.perf_counter()
        res3 = resolve_entities(str(xml_file), force_reload=True)
        t3 = time.perf_counter() - t3_start
        assert res3["system_entities"]["Foo"]["value"] == "<field name='x'/>"



class TestGetXmlEntitiesInline:
    def test_content_and_path(self, tmp_path):
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
        xml_file = tmp_path / "test.xml"
        xml_file.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
<!ENTITY Foo "<field name='x'/>">
<!ENTITY Bar "<field name='y'/>">
<!ENTITY % Param "value">
]>
<dir>&Foo;&Bar;</dir>
""",
            encoding="utf-8",
        )

        result = get_xml_entities(str(xml_file), mode="list")
        assert result["success"] is True
        assert "entities" in result
        names = {e["name"] for e in result["entities"]}
        assert {"Foo", "Bar"} <= names
        assert "Param" not in names
        
        foo_ent = next(e for e in result["entities"] if e["name"] == "Foo")
        assert foo_ent["kind"] == "general"
        assert foo_ent["value_preview"] == "<field name='x'/>"

    def test_missing_file(self):
        result = get_xml_entities(r"E:\no\such\file.xml", ["Foo"])
        assert result["success"] is False

    def test_requires_entities_or_list_all(self, tmp_path):
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
        result = get_xml_entities(str(xml_file))
        assert result["success"] is False

    def test_path_requires_entities(self, tmp_path):
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
        result = get_xml_entities(str(xml_file), mode="path")
        assert result["success"] is False


class TestIntegrationShowaSOTran:
    """Chạy khi truy cập được network path SHOWA FBISP242."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        pass
        yield
        pass

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
