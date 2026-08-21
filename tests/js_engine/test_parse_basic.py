"""Basic unit tests for js_engine parsing."""

import pytest
from js_engine import parse


def test_parse_simple_function():
    code = "function test() { return 1; }"
    result = parse(code)
    assert result.status == "ok"
    assert result.tree is not None
    assert len(result.errors) == 0


def test_parse_fbo_function_with_dollar():
    code = """
    function onChange$Voucher$Customer(o) {
        var f = o.parentForm;
        f.request('Customer', 'Customer', ['ma_kh'], o);
        $message.show('Customer changed');
    }
    """
    result = parse(code)
    assert result.status == "ok"
    assert result.tree is not None
    assert len(result.errors) == 0


def test_parse_empty():
    result = parse("")
    assert result.status == "ok"
    assert result.tree is None


def test_parse_syntax_error_partial():
    code = "function broken( { return 1; }"
    result = parse(code)
    assert result.status in {"partial", "failed"}
    assert len(result.errors) > 0
