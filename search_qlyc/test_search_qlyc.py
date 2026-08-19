import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import pytest
except ImportError:
    pytest = None

from search_qlyc.service import search_qlyc


def test_missing_all_criteria():
    res = search_qlyc(query="", fcode1="", ma_da="")
    assert res["ok"] is False
    assert res["error"] == "query_thieu"


def test_missing_config():
    res = search_qlyc(query="test", config=None)
    assert res["ok"] is False
    assert res["error"] == "config_thieu"


def test_missing_api_key_in_config():
    res = search_qlyc(query="test", config={"base_url": "http://localhost:8000"})
    assert res["ok"] is False
    assert res["error"] == "config_thieu"


def test_connection_error_with_query():
    res = search_qlyc(query="test", config={"base_url": "http://invalid-host-that-does-not-exist:9999", "api_key": "123"})
    assert res["ok"] is False
    assert res["error"] == "khong_ket_noi_api"


def test_connection_error_with_fcode1_only():
    res = search_qlyc(query="", fcode1="YC123", config={"base_url": "http://invalid-host-that-does-not-exist:9999", "api_key": "123"})
    assert res["ok"] is False
    assert res["error"] == "khong_ket_noi_api"


if __name__ == "__main__":
    test_missing_all_criteria()
    test_missing_config()
    test_missing_api_key_in_config()
    test_connection_error_with_query()
    test_connection_error_with_fcode1_only()
    print("All search_qlyc tests passed!")

