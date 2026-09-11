"""Unit tests for normalize, exclude, and queue operations."""

from clone_things.service import (
    normalize_object_name,
    normalize_fbo_db_table,
    is_excluded,
    to_partition_structure_name,
)
from sql_object_summary.options import DEFAULT_EXCLUDE_LIKE


def test_normalize_object_name():
    schema, name, key = normalize_object_name("zc_test")
    assert schema == "dbo"
    assert name == "zc_test"
    assert key == "dbo.zc_test"

    schema, name, key = normalize_object_name("dbo.zc_test")
    assert schema == "dbo"
    assert name == "zc_test"
    assert key == "dbo.zc_test"

    schema, name, key = normalize_object_name("sys.objects")
    assert schema == "sys"
    assert name == "objects"
    assert key == "sys.objects"

    # Brackets and quotes
    schema, name, key = normalize_object_name("[custom].[my_proc]")
    assert schema == "custom"
    assert name == "my_proc"
    assert key == "custom.my_proc"

    # Partition template / kỳ → bảng cấu trúc $000000
    schema, name, key = normalize_object_name("m41$")
    assert name == "m41$000000"
    assert key == "dbo.m41$000000"

    schema, name, key = normalize_object_name("dbo.r00$202601")
    assert name == "r00$000000"
    assert key == "dbo.r00$000000"

    schema, name, key = normalize_object_name("m51$000000")
    assert name == "m51$000000"


def test_to_partition_structure_name():
    assert to_partition_structure_name("m41$") == "m41$000000"
    assert to_partition_structure_name("m46$") == "m46$000000"
    assert to_partition_structure_name("r00$") == "r00$000000"
    assert to_partition_structure_name("m41$202601") == "m41$000000"
    assert to_partition_structure_name("m41$000000") == "m41$000000"
    assert to_partition_structure_name("dmkh") == "dmkh"
    assert to_partition_structure_name("wrkgl") == "wrkgl"


def test_normalize_fbo_db_table():
    assert normalize_fbo_db_table("d91$@@prime$partition$current") == "d91$"
    assert normalize_fbo_db_table("c91$$$partition$current") == "c91$"
    assert normalize_fbo_db_table("dmkh") == "dmkh"
    assert normalize_fbo_db_table("") == ""


def test_is_excluded():
    excludes = list(DEFAULT_EXCLUDE_LIKE) + [r"^sp_", r"^xp_"]

    assert is_excluded("FastBusiness$ReportHelper", excludes) is True
    assert is_excluded("ff_GetDate", excludes) is True
    assert is_excluded("fsd_Split", excludes) is True
    assert is_excluded("sp_executesql", excludes) is True
    assert is_excluded("zc_custom_report", excludes) is False
    assert is_excluded("dmkh", excludes) is False


def test_default_extra_excludes_allows_fastbusiness_and_fsd():
    from clone_things.service import DEFAULT_EXTRA_EXCLUDES

    # DEFAULT_EXTRA_EXCLUDES should ONLY exclude system routines (sp_, xp_, sys., sp_executesql)
    assert is_excluded("sp_executesql", DEFAULT_EXTRA_EXCLUDES) is True
    assert is_excluded("xp_cmdshell", DEFAULT_EXTRA_EXCLUDES) is True
    assert is_excluded("sys.objects", DEFAULT_EXTRA_EXCLUDES) is True

    # FastBusiness$, ff_, fsd_ MUST NOT be excluded by default so missing items can be cloned
    assert is_excluded("FastBusiness$App$GetLayoutConfig", DEFAULT_EXTRA_EXCLUDES) is False
    assert is_excluded("ff_NumberFormatConfig", DEFAULT_EXTRA_EXCLUDES) is False
    assert is_excluded("fsd_StringToTable", DEFAULT_EXTRA_EXCLUDES) is False
    assert is_excluded("rs_rptCheckVoucherEditLog", DEFAULT_EXTRA_EXCLUDES) is False

