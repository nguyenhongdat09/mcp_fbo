"""Unit tests for signals 2 sides, table PK order-independent, and meta_diff message.

Specification: docs/doc/doc_fix/FIX-compare_things-signals-pk-message.md
1) SQL signals: dual-sided (source_refs_* and target_refs_*), delegation_view_mismatch, refs_match_body_diff, refs structured.
2) Table PK: same columns in different order -> identical status, pk_diff=False, pk_column_order_diff=True.
3) Message file/xml: meta_diff mismatch fixed; does not claim 'hoàn toàn giống nhau về nội dung và metadata' when meta_diff is non-empty.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from compare_things import compare_things
from compare_things.sql_fingerprint import extract_sql_refs, extract_sql_signals
from compare_things.table_compare import _build_schema_diff


def test_sql_signals_dual_sided():
    """Test 1: source uses vdmduyetuq and target uses dmduyet -> dual signals + delegation_view_mismatch."""
    src = """
    SELECT a.* FROM dbo.dmuqduyet a
    JOIN dbo.vdmduyetuq b ON a.loai_duyet = b.loai_duyet
    """
    tgt = """
    SELECT a.* FROM dbo.dmduyet a
    """
    signals = extract_sql_signals(src, tgt)
    assert "source_refs_vdmduyetuq" in signals
    assert "source_refs_dmuqduyet" in signals
    assert "target_refs_dmduyet" in signals
    assert "delegation_view_mismatch" in signals

    # Word boundary test: dmuqduyet must NOT trigger refs_dmduyet
    src_only_uq = "SELECT * FROM dbo.dmuqduyet"
    tgt_only_uq = "SELECT * FROM dbo.gndmuqduyet"
    signals_uq = extract_sql_signals(src_only_uq, tgt_only_uq)
    assert "source_refs_dmduyet" not in signals_uq
    assert "target_refs_dmduyet" not in signals_uq
    assert "source_refs_dmuqduyet" in signals_uq
    assert "target_refs_dmuqduyet" in signals_uq


def test_sql_signals_both_refs_same_view_different_body():
    """Test 2: Both routines ref vdmduyetuq but have different bodies -> refs_match_body_diff."""
    src = "SELECT 1 FROM dbo.vdmduyetuq WHERE 1=1"
    tgt = "SELECT 2 FROM dbo.vdmduyetuq WHERE 2=2"
    signals = extract_sql_signals(src, tgt)
    assert "source_refs_vdmduyetuq" in signals
    assert "target_refs_vdmduyetuq" in signals
    assert "refs_match_body_diff" in signals
    assert "delegation_view_mismatch" not in signals


def test_sql_refs_structured_extraction():
    """Test 3: extract_sql_refs extracts views and tables properly."""
    code = """
    SELECT a.* FROM dbo.dmuqduyet a
    JOIN dbo.vdmduyetuq b ON a.loai_duyet = b.loai_duyet
    JOIN dbo.dmquyen c ON a.u_id = c.u_id
    """
    refs = extract_sql_refs(code)
    assert "dbo.vdmduyetuq" in refs["views"]
    assert "dbo.dmuqduyet" in refs["tables"]
    assert "dbo.dmquyen" in refs["tables"]


def test_table_pk_order_independent_identical():
    """Test 4: Tables with identical PK columns in different ordinal order are identical."""
    sch_src = {
        "columns": {
            "loai_duyet": {"name": "loai_duyet", "type": "varchar(33) not null"},
            "u_id4": {"name": "u_id4", "type": "int not null"},
            "ngay_hl": {"name": "ngay_hl", "type": "smalldatetime not null"},
        },
        "pk": ["loai_duyet", "u_id4", "ngay_hl"],
        "indexes": {},
        "triggers": {},
    }
    sch_tgt = {
        "columns": {
            "loai_duyet": {"name": "loai_duyet", "type": "varchar(33) not null"},
            "u_id4": {"name": "u_id4", "type": "int not null"},
            "ngay_hl": {"name": "ngay_hl", "type": "smalldatetime not null"},
        },
        "pk": ["loai_duyet", "ngay_hl", "u_id4"],
        "indexes": {},
        "triggers": {},
    }

    diff = _build_schema_diff(sch_src, sch_tgt)
    assert diff["pk_diff"] is False
    assert diff["pk_column_order_diff"] is True

    # Test via compare_things
    with patch("compare_things.table_compare.resolve_project_dbs") as mock_resolve:
        mock_resolve.side_effect = lambda proj, warn: {"app": {"server": "s_src"}} if "proj_a" in str(proj) else {"app": {"server": "s_tgt"}}
        with patch("compare_things.table_compare.fetch_table_schema") as mock_fetch:
            mock_fetch.side_effect = lambda conn, name, schema: sch_src if conn.get("server") == "s_src" else sch_tgt
            res = compare_things(
                kind="table",
                project_source="E:/proj_a",
                project_target="E:/proj_b",
                object="dmuqduyet",
            )
            assert res["success"] is True
            assert len(res["summary"]["different"]) == 0
            assert len(res["summary"]["identical"]) == 1
            item = res["compared"][0]
            assert item["status"] == "identical"
            assert item.get("pk_column_order_diff") is True
            assert "noop" in item["next_actions"]


def test_table_pk_different_columns():
    """Test 5: Tables with different PK columns are marked different with pk_diff=True."""
    sch_src = {
        "columns": {"id": {"name": "id", "type": "int not null"}},
        "pk": ["id"],
        "indexes": {},
        "triggers": {},
    }
    sch_tgt = {
        "columns": {"id": {"name": "id", "type": "int not null"}, "sub_id": {"name": "sub_id", "type": "int not null"}},
        "pk": ["id", "sub_id"],
        "indexes": {},
        "triggers": {},
    }
    diff = _build_schema_diff(sch_src, sch_tgt)
    assert diff["pk_diff"] is True
    assert diff["pk_column_order_diff"] is False


def test_file_message_reflects_meta_diff(tmp_path: Path):
    """Test 6: kind=file message mentions meta difference and does not claim 'hoàn toàn giống'."""
    fa = tmp_path / "kbuqd.aspx"
    fb = tmp_path / "kbuqd_copy.aspx"
    content = "<%@ Page Language=\"C#\" %>\n<html></html>\n"
    fa.write_text(content, encoding="utf-8")
    fb.write_text(content, encoding="utf-8")

    res = compare_things(kind="file", file_a=str(fa), file_b=str(fb))
    assert res["success"] is True
    item = res["compared"][0]
    assert item["identical_content"] is True

    # If meta_diff is non-empty, message must not claim hoàn toàn giống nhau về metadata
    if item["meta_diff"]:
        assert "hoàn toàn giống nhau về nội dung và metadata" not in res["message"]
        assert "khác metadata" in res["message"]
    else:
        assert "hoàn toàn giống nhau" in res["message"]
