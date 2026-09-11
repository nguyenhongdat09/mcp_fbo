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


def test_ma_da_uppercased(monkeypatch=None):
    from unittest.mock import patch

    captured_payload = {}

    def mock_post_search_api(base_url, api_key, timeout, payload):
        captured_payload.update(payload)
        return {"ok": True, "data": []}

    with patch("search_qlyc.service.post_search_api", side_effect=mock_post_search_api):
        res = search_qlyc(
            query="test",
            ma_da="liksin_fbo_2024",
            config={"base_url": "http://mock-api", "api_key": "secret"}
        )
        assert res["ok"] is True
        assert captured_payload.get("ma_da") == "LIKSIN_FBO_2024"


if __name__ == "__main__":
    test_missing_all_criteria()
    test_missing_config()
    test_missing_api_key_in_config()
    test_connection_error_with_query()
    test_connection_error_with_fcode1_only()
    test_ma_da_uppercased()
    print("All search_qlyc tests passed!")

