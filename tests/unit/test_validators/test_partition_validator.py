"""Tests for partition validator."""

import pytest
from fastbusiness_mcp.validators.partition_validator import PartitionValidator


@pytest.fixture
def validator():
    """Create validator instance."""
    return PartitionValidator()


def test_detect_hardcoded_partition(validator):
    """Test detection of hardcoded partition."""
    sql = "select * from d91$202501 where stt_rec = @stt_rec"

    result = validator.validate(sql)

    assert not result.is_valid
    assert len(result.errors) == 1
    assert "d91$202501" in result.errors[0].message
    assert "@@prime$partition$current" in result.errors[0].suggestion


def test_correct_partition_usage(validator):
    """Test correct partition placeholder."""
    sql = "select * from @@prime$partition$current where stt_rec = @stt_rec"

    result = validator.validate(sql)

    assert result.is_valid
    assert len(result.errors) == 0


def test_multiple_hardcoded_partitions(validator):
    """Test detection of multiple hardcoded partitions."""
    sql = """
        select * from d91$202501
        union all
        select * from d91$202412
    """

    result = validator.validate(sql)

    assert not result.is_valid
    assert len(result.errors) == 2


def test_master_table_hardcoded(validator):
    """Test detection of hardcoded master table."""
    sql = "select * from m91$202501"

    result = validator.validate(sql)

    assert not result.is_valid
    assert "@@master" in result.errors[0].suggestion


def test_inquiry_table_hardcoded(validator):
    """Test detection of hardcoded inquiry table."""
    sql = "select * from i91$202501"

    result = validator.validate(sql)

    assert not result.is_valid
    assert "@@inquiry$partition$current" in result.errors[0].suggestion
