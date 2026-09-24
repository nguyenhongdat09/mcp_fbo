"""Unit tests cho package jev/ — config gate + client (mock HTTP)."""
from __future__ import annotations

import json
import urllib.error

import pytest

import jev
from jev import load_jev_config


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    """Isolate: env FASTBUSINESS_JEV_CONFIG trỏ vào tmp theo test set."""
    monkeypatch.delenv("FASTBUSINESS_JEV_CONFIG", raising=False)
    yield


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _with_env(monkeypatch, path):
    monkeypatch.setenv("FASTBUSINESS_JEV_CONFIG", str(path))


# ---------------- load_jev_config ----------------

def test_config_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("FASTBUSINESS_JEV_CONFIG",
                       str(tmp_path / "nope.xml"))
    assert load_jev_config() is None


def test_config_xml_ok(monkeypatch, tmp_path):
    p = _write(tmp_path, "config_jev.xml", """<?xml version="1.0"?>
<jev enabled="true">
  <apiKey>ts-test</apiKey>
  <baseUrl>http://localhost:9</baseUrl>
</jev>""")
    _with_env(monkeypatch, p)
    cfg = load_jev_config()
    assert cfg is not None
    assert cfg["api_key"] == "ts-test"
    assert cfg["base_url"] == "http://localhost:9"
    assert cfg["model"] == "jev-latest"          # default
    assert cfg["timeout_seconds"] == 15          # default
    assert cfg["confidence_act"] == 0.7          # default


def test_config_xml_disabled(monkeypatch, tmp_path):
    p = _write(tmp_path, "config_jev.xml",
               '<jev enabled="false"><apiKey>x</apiKey></jev>')
    _with_env(monkeypatch, p)
    assert load_jev_config() is None


def test_config_xml_no_key(monkeypatch, tmp_path):
    p = _write(tmp_path, "config_jev.xml",
               '<jev enabled="true"><apiKey></apiKey></jev>')
    _with_env(monkeypatch, p)
    assert load_jev_config() is None


def test_config_xml_broken(monkeypatch, tmp_path):
    p = _write(tmp_path, "config_jev.xml", "<jev><apiKey>x")
    _with_env(monkeypatch, p)
    assert load_jev_config() is None


def test_config_yaml_ok(monkeypatch, tmp_path):
    p = _write(tmp_path, "config_jev.yaml", """api_key:
  jev: ts-yaml
jev:
  timeout_seconds: 30
  confidence_act: 0.8
""")
    _with_env(monkeypatch, p)
    cfg = load_jev_config()
    assert cfg is not None
    assert cfg["api_key"] == "ts-yaml"
    assert cfg["timeout_seconds"] == 30
    assert cfg["confidence_act"] == 0.8


# ---------------- ask_jev (mock urlopen) ----------------

class _Resp:
    def __init__(self, body):
        self._b = json.dumps(body).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_ask_jev_ok(monkeypatch):
    body = {"model": "jev-x",
            "answers": {"step1_tool": {"type": "choice",
                                       "choice": "grep_content",
                                       "confidence": 0.9,
                                       "probabilities": {
                                           "grep_content": 0.9}}},
            "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _Resp(body))
    res = jev.ask_jev({"api_key": "k", "base_url": "http://x"},
                      {"s": 1}, {"step1_tool": {}})
    assert res["ok"] is True
    assert res["answers"]["step1_tool"]["choice"] == "grep_content"
    assert res["usage"]["input_tokens"] == 1


def test_ask_jev_http_error(monkeypatch):
    def _raise(*a, **k):
        raise urllib.error.HTTPError("u", 401, "unauth", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    res = jev.ask_jev({"api_key": "k", "base_url": "http://x"}, {}, {})
    assert res["ok"] is False
    assert res["error"] == "unauthorized"


def test_ask_jev_url_error(monkeypatch):
    def _raise(*a, **k):
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    res = jev.ask_jev({"api_key": "k", "base_url": "http://x"}, {}, {})
    assert res["ok"] is False
    assert res["error"] == "khong_ket_noi_api"
