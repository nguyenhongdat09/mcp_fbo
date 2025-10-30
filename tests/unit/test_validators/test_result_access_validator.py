"""Tests for result access validator."""

import pytest
from fastbusiness_mcp.validators.result_access_validator import ResultAccessValidator


@pytest.fixture
def validator():
    """Create validator instance."""
    return ResultAccessValidator()


def test_incorrect_property_access(validator):
    """Test detection of property access."""
    js = "var maKH = result[0].ma_kh;"

    result = validator.validate(js)

    assert not result.is_valid
    assert len(result.errors) == 1
    assert "result[0].ma_kh" in result.errors[0].message


def test_correct_value_access(validator):
    """Test correct Value access."""
    js = "var maKH = result[0].Value;"

    result = validator.validate(js)

    assert result.is_valid
    assert len(result.errors) == 0


def test_with_column_mapping(validator):
    """Test validation with SQL column mapping."""
    sql = "select ma_kh, ten_kh from dmkh"
    js = "var x = result[0].ten_kh;"

    result = validator.validate(js, sql)

    assert not result.is_valid
    # Should suggest correct index for ten_kh
    assert "result[1].Value" in result.errors[0].suggestion


def test_multiple_incorrect_accesses(validator):
    """Test multiple incorrect accesses."""
    js = """
        var maKH = result[0].ma_kh;
        var tenKH = result[1].ten_kh;
    """

    result = validator.validate(js)

    assert not result.is_valid
    assert len(result.errors) == 2
