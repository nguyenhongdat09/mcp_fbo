"""Unit tests for SQL refs noise cleanup and refs_match_body_diff precision.

Specification: docs/doc/doc_fix/FIX-compare_things-sql-refs-noise.md
1) extract_sql_refs: strips string literals, excludes datetime2 / user_id0 / status columns,
   handles UPDATE ... SET cleanly.
2) FBO view prefixes: vdm*, vgn*, vso*, vsys* recognized as views, non-view names as tables.
3) refs_match_body_diff: only emitted when full refs (views + tables) match exactly and body differs.
"""

import pytest
from compare_things.sql_fingerprint import extract_sql_refs, extract_sql_signals


def test_sql_refs_no_datetime2_noise_in_maillist():
    """Test 1: MailList-like snippet with UPDATE ... SET datetime2 and dynamic SQL."""
    snippet = """
    UPDATE dmxn SET datetime2 = @datetime2 WHERE stt_rec = @id
    SET @q = 'insert into #tmp select u_status, datetime2, ma_dvcs from ' + @t
    FROM dbo.vdmduyetuq a JOIN dbo.dmquyen b ON a.loai_duyet = b.loai_duyet
    """
    refs = extract_sql_refs(snippet)
    # Must NOT contain datetime2 or other noise columns
    all_refs = refs["views"] + refs["tables"]
    assert "dbo.datetime2" not in all_refs
    assert "dbo.u_status" not in all_refs
    assert "dbo.ma_dvcs" not in all_refs

    # Must contain real tables and views
    assert "dbo.vdmduyetuq" in refs["views"]
    assert "dbo.dmxn" in refs["tables"]
    assert "dbo.dmquyen" in refs["tables"]


def test_sql_refs_view_prefixes_fbo():
    """Test 2: FBO view prefixes vdm, vgn, vso, vsys are classified as views, not arbitrary v-words."""
    snippet = """
    SELECT * FROM dbo.vdmduyetuq
    JOIN dbo.vsysuserinfo ON 1=1
    JOIN dbo.voucher_details ON 1=1
    """
    refs = extract_sql_refs(snippet)
    assert "dbo.vdmduyetuq" in refs["views"]
    assert "dbo.vsysuserinfo" in refs["views"]
    # voucher_details does not start with vdm/vgn/vso/vsys -> classified as table
    assert "dbo.voucher_details" in refs["tables"]


def test_refs_match_body_diff_requires_exact_refs_match():
    """Test 3: refs_match_body_diff is ONLY emitted when both views and tables match."""
    # Case A: Same view, but different tables -> NO refs_match_body_diff
    src_a = "SELECT 1 FROM dbo.vdmduyetuq a JOIN dbo.dmnttduyet b ON a.id = b.id"
    tgt_a = "SELECT 1 FROM dbo.vdmduyetuq a"
    signals_a = extract_sql_signals(src_a, tgt_a)
    assert "source_refs_vdmduyetuq" in signals_a
    assert "target_refs_vdmduyetuq" in signals_a
    assert "refs_match_body_diff" not in signals_a

    # Case B: Exactly same views and tables, different body/conditions -> YES refs_match_body_diff
    src_b = "SELECT 1 FROM dbo.vdmduyetuq a JOIN dbo.dmquyen b ON a.id = b.id WHERE a.status = '1'"
    tgt_b = "SELECT 2 FROM dbo.vdmduyetuq a JOIN dbo.dmquyen b ON a.id = b.id WHERE a.status = '2'"
    signals_b = extract_sql_signals(src_b, tgt_b)
    assert "source_refs_vdmduyetuq" in signals_b
    assert "target_refs_vdmduyetuq" in signals_b
    assert "refs_match_body_diff" in signals_b


def test_sql_refs_with_db_sys_objects_resolution(monkeypatch):
    """Test 4: Accurate classification using SQL Server sys.objects types (V, U, FN, P)."""
    from compare_things import db_access

    fake_db = {"app": {"server": "localhost", "database": "fake_app"}}

    def fake_execute_query(conn, sql, max_rows=100):
        return {
            "success": True,
            "result_sets": [
                {
                    "columns": ["name", "schema_name", "type", "type_desc"],
                    "rows": [
                        ["cust_active_accounts", "dbo", "V", "VIEW"],
                        ["vat_table", "dbo", "U", "USER_TABLE"],
                        ["fn_GetRateQD", "dbo", "FN", "SQL_SCALAR_FUNCTION"],
                        ["FastBusiness$App$MailList", "dbo", "P", "SQL_STORED_PROCEDURE"],
                    ],
                }
            ],
        }

    monkeypatch.setattr(db_access, "execute_query", fake_execute_query)

    snippet = """
    SELECT * FROM dbo.cust_active_accounts a
    JOIN dbo.vat_table b ON a.id = b.id
    WHERE a.rate = dbo.fn_GetRateQD(a.val)
    EXEC dbo.FastBusiness$App$MailList @id = 1
    """

    refs = extract_sql_refs(snippet, dbs=fake_db)
    # cust_active_accounts has no 'v' prefix, but sys.objects type='V' -> VIEW
    assert "dbo.cust_active_accounts" in refs["views"]
    # vat_table starts with 'v', but sys.objects type='U' -> TABLE
    assert "dbo.vat_table" in refs["tables"]
    # fn_GetRateQD sys.objects type='FN' -> FUNC
    assert "dbo.fn_GetRateQD" in refs["funcs"]
    # FastBusiness$App$MailList sys.objects type='P' -> PROC
    assert "dbo.FastBusiness$App$MailList" in refs["procs"]

