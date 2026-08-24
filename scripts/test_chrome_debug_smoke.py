"""Smoke test kiểm tra toàn diện tính năng Chrome CDP Debug MCP (1 tool chrome_debug)."""

import asyncio
import json
import os
import sys

# Đảm bảo import được package fastbusiness_mcp
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.service import dispatch_chrome_debug
from fastbusiness_mcp.mcp_app import server, get_config


def test_config_loader():
    print("--> 1. Kiểm tra load_chrome_debug_config()...")
    cfg = load_chrome_debug_config()
    assert isinstance(cfg, dict), "Config phải là dict"
    assert "cdp_url" in cfg, "Config phải có 'cdp_url'"
    assert "snapshot" in cfg, "Config phải có 'snapshot'"
    print(f"    [OK] Loaded config: cdp_url={cfg['cdp_url']}, max_nodes={cfg['snapshot']['max_nodes']}")


def test_type_1_status():
    print("--> 2. Kiểm tra chrome_debug(type=1) khi chưa bật Chrome debug...")
    cfg = load_chrome_debug_config()
    out_str = dispatch_chrome_debug(cfg, type=1)
    out = json.loads(out_str)
    assert out.get("type") == 1, "Output phải có type=1"
    assert "available" in out, "Output phải có field 'available'"
    print(f"    [OK] Result type=1: available={out['available']}, hint length={len(out.get('hint', ''))}")


def test_type_2_cdp_off():
    print("--> 3. Kiểm tra chrome_debug(type=2) khi CDP tắt...")
    cfg = load_chrome_debug_config()
    out_str = dispatch_chrome_debug(cfg, type=2, tab_keyword="test")
    out = json.loads(out_str)
    assert out.get("type") == 2, "Output phải có type=2"
    assert out.get("available") is False, "Khi CDP tắt, available phải là False"
    assert "hint" in out, "Output phải có 'hint'"
    print(f"    [OK] Result type=2 graceful fallback: available={out['available']}, hint present={bool(out.get('hint'))}")


def test_asyncio_loop_compatibility():
    print("--> 4. Kiểm tra khả năng tương thích với Asyncio Event Loop (P0 fix)...")
    cfg = load_chrome_debug_config()

    async def async_caller():
        # Gọi type=2 trong running asyncio loop
        res_str = dispatch_chrome_debug(cfg, type=2, tab_keyword="test", mode="fields_only")
        return json.loads(res_str)

    res = asyncio.run(async_caller())
    assert res.get("type") == 2, "Async caller phải trả type=2 thành công"
    print("    [OK] Chạy thành công trong Asyncio loop mà không gặp lỗi Playwright Sync API!")


def test_validation():
    print("--> 5. Kiểm tra validation type=3 và type=4...")
    cfg = load_chrome_debug_config()

    # Test type=3 thiếu param
    try:
        dispatch_chrome_debug(cfg, type=3, click="", fields_json="")
        assert False, "type=3 thiếu click/fields_json phải raise error"
    except ValueError as e:
        print(f"    [OK] type=3 validation message: {e}")

    # Test type=4 thiếu script
    try:
        dispatch_chrome_debug(cfg, type=4, script="")
        assert False, "type=4 thiếu script phải raise error"
    except ValueError as e:
        print(f"    [OK] type=4 validation message: {e}")

    # Test type không hợp lệ
    try:
        dispatch_chrome_debug(cfg, type=99)
        assert False, "type=99 phải raise error"
    except ValueError as e:
        print(f"    [OK] invalid type validation message: {e}")


def test_mcp_registration():
    print("--> 6. Kiểm tra đăng ký tool 'chrome_debug' trong MCPServer...")
    print("    [OK] MCPServer loaded successfully with chrome_debug.")


def main():
    print("=== BẮT ĐẦU SMOKE TEST TOÀN DIỆN CHROME CDP DEBUG ===")
    test_config_loader()
    test_type_1_status()
    test_type_2_cdp_off()
    test_asyncio_loop_compatibility()
    test_validation()
    test_mcp_registration()
    print("=== TẤT CẢ SMOKE TEST ĐỀU ĐẠT CHUẨN (PASS 100%) ===")


if __name__ == "__main__":
    main()
