import pytest
from search_qlyc.service import search_qlyc

def test_missing_query():
    res = search_qlyc(query="")
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

def test_connection_error():
    res = search_qlyc(query="test", config={"base_url": "http://invalid-host-that-does-not-exist:9999", "api_key": "123"})
    assert res["ok"] is False
    assert res["error"] == "khong_ket_noi_api"
