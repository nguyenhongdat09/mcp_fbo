"""Unit tests for tsql_engine without any database or MCP dependencies."""

import pytest
from tsql_engine import parse, TSqlEngine


def test_parse_simple_proc():
    sql = """
    CREATE PROCEDURE dbo.sp_test
        @a INT,
        @b VARCHAR(50) = 'default'
    AS
    BEGIN
        SET NOCOUNT ON;
        SELECT a, b FROM dbo.my_table WHERE a = @a;
    END
    """
    res = parse(sql)
    assert res.status == "ok"
    assert len(res.errors) == 0
    assert res.tree is not None


def test_parse_fastbusiness_symbols():
    sql = """
    CREATE PROCEDURE dbo.zc_bcthlv
        @Status CHAR(1) = '0'
    AS
    BEGIN
        EXEC FastBusiness$Partition$Execute @name='r00$';
        SELECT * INTO #temp FROM dmku;
        SELECT * FROM #temp;
    END
    """
    res = parse(sql)
    assert res.status == "ok"
    assert len(res.errors) == 0
    assert res.tree is not None


def test_parse_go_separator():
    sql = """
    -- Batch 1
    CREATE PROC dbo.p AS
    BEGIN
        SELECT 1;
    END
    GO
    """
    res = parse(sql)
    assert res.status == "ok"
    assert res.tree is not None
