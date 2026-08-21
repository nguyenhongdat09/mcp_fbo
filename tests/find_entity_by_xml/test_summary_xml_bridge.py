"""Tests for summary_xml bridge, caching, .f handling, and facade delegation."""

import tempfile
import pytest
from pathlib import Path
from find_entity_by_xml.bridges import summary_xml, format_summary_xml_result
from find_entity_by_xml.facade import extract_expanded_blocks

SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<dir table="dmtk" code="tk" title="Danh mục tài khoản" xmlns="urn:schemas-ai-erp:data-dir">
  <fields>
    <field name="tk" allowNulls="false">
      <clientScript><![CDATA[onchange="onChange$Voucher$Customer(this);"]]></clientScript>
    </field>
    <field name="ten_tk" allowNulls="false" />
    <field name="loai_tk" type="Decimal" />
  </fields>
  <commands>
    <command event="Loading">
      <text><![CDATA[
        select * from dmtk
      ]]></text>
    </command>
    <command event="Checking">
      <text><![CDATA[
        function check$Account(f) {
            return true;
        }
      ]]></text>
    </command>
  </commands>
  <script>
    <text><![CDATA[
      function init$Account(f) {
          f.executeExpression('loai_tk');
      }
    ]]></text>
  </script>
</dir>
"""

UNC_SVTRAN = r"\\172.168.5.14\CustomerPro\HRM\LIKSIN\FBISP23\App_Data\Controllers\Dir\SVTran.xml"


def test_summary_xml_bridge_temp_file():
    with tempfile.NamedTemporaryFile(suffix=".xml", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write(SAMPLE_XML)
        tf_path = tf.name

    try:
        res = summary_xml(tf_path)
        assert res["success"] is True
        assert res["mode"] == "summary"
        assert res["spec_version"] == "1.0"
        assert "init$Account" in res["js"]["functions"]
        assert "dmtk" in [t.lower() for t in res["sql"]["tables"]]
        assert len(res["fields"]) == 3

        # Test cache hit
        res_cached = summary_xml(tf_path, use_cache=True)
        assert res_cached == res

        formatted = format_summary_xml_result(res)
        assert "[OK] read_local_file summary_xml" in formatted
        assert "```json" in formatted
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_summary_xml_cache_deepcopy_mutation():
    with tempfile.NamedTemporaryFile(suffix=".xml", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write(SAMPLE_XML)
        tf_path = tf.name

    try:
        r1 = summary_xml(tf_path, use_cache=True)
        r1["js"]["functions"].append("HACKED_FUNCTION")
        r2 = summary_xml(tf_path, use_cache=True)
        assert "HACKED_FUNCTION" not in r2["js"]["functions"]
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_summary_xml_dot_f_encrypted_handling():
    with tempfile.NamedTemporaryFile(suffix=".f", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write("\x00\x01\x02\x03ENCRYPTED_BINARY_CONTENT")
        tf_path = tf.name

    try:
        res = summary_xml(tf_path)
        assert res["success"] is False
        assert "encrypted_file_not_supported" in res["meta"]["warnings"]
    finally:
        Path(tf_path).unlink(missing_ok=True)


def test_facade_extract_expanded_blocks_delegation():
    with tempfile.NamedTemporaryFile(suffix=".xml", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write(SAMPLE_XML)
        tf_path = tf.name

    try:
        blocks = extract_expanded_blocks(tf_path)
        assert "sql_blocks" in blocks
        assert "js_blocks" in blocks
        assert "system_entities" in blocks
        assert "param_entities" in blocks
        assert "flat_text" in blocks

        # Verify Checking JS was routed to js_blocks with tag command:Checking
        js_tags = [b["tag"] for b in blocks["js_blocks"]]
        assert "command:Checking" in js_tags
        assert "script" in js_tags
        # R1: Verify clientScript was also captured in js_blocks for FBOGraph
        assert "clientScript" in js_tags
        client_script_block = next(b for b in blocks["js_blocks"] if b["tag"] == "clientScript")
        assert "onChange$Voucher$Customer" in client_script_block["content"]

        # Verify Loading was routed to sql_blocks
        sql_tags = [b["tag"] for b in blocks["sql_blocks"]]
        assert "command:Loading" in sql_tags
    finally:
        Path(tf_path).unlink(missing_ok=True)


import os

@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("FBO_TEST_UNC") != "1",
    reason="UNC integration test skipped unless FBO_TEST_UNC=1 is set",
)
def test_svtran_unc_smoke():
    if not Path(UNC_SVTRAN).exists():
        pytest.skip("share not mounted")
    d = summary_xml(UNC_SVTRAN)
    assert d["success"]
    assert "onChange$Voucher$Customer" in d["js"]["functions"]
    ma = next(f for f in d["fields"] if f["name"] == "ma_kh")
    assert d["file"].replace("/", "\\").endswith(r"Dir\SVTran.xml") or "SVTran.xml" in d["file"]


def test_mcp_read_local_file_non_xml_switch_to_raw():
    from xml_fbograph.mcp_tools import mcp_read_local_file

    with tempfile.TemporaryDirectory() as tmpdir:
        root_dir = Path(tmpdir)
        controllers_dir = root_dir / "App_Data" / "Controllers" / "Dir"
        controllers_dir.mkdir(parents=True, exist_ok=True)

        ref_xml = controllers_dir / "Ref.xml"
        ref_xml.write_text("<dir></dir>", encoding="utf-8")

        sql_file = controllers_dir / "query.sql"
        sql_file.write_text("SELECT 1 AS TestVal;", encoding="utf-8")

        # Call with read_option=3 on .sql file -> should auto switch to raw content
        res = mcp_read_local_file(str(sql_file), str(ref_xml), read_option=3)
        assert res.strip() == "SELECT 1 AS TestVal;"
        assert "```json" not in res



