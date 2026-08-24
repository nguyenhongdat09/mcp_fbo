"""Orchestration service cho chrome_debug tool (dispatch theo type 1, 2, 3, 4)."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .actions import click_target, execute_page_script, fill_fields
from .buffers import TabBuffers
from .constants import (
    DEFAULT_CDP_URL,
    MAX_LABEL_CHARS_DEFAULT,
    MAX_RESULT_CHARS_DEFAULT,
    MAX_SNAPSHOT_NODES_DEFAULT,
)
from .runtime import run_playwright_sync
from .session import ChromeSession, ping_cdp
from .snapshot import build_page_snapshot
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


def _check_cdp_ready(cfg: Dict[str, Any], type_num: int) -> Optional[Dict[str, Any]]:
    """Kiểm tra nhanh CDP endpoint trước khi connect Playwright."""
    cdp_url = cfg.get("cdp_url", DEFAULT_CDP_URL)
    available, ver_info, tabs, hint = ping_cdp(cdp_url)
    if not available:
        return {
            "type": type_num,
            "available": False,
            "cdp_url": cdp_url,
            "browser": "",
            "count": 0,
            "tabs": [],
            "hint": hint,
        }
    return None


def handle_type_1_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """type=1: Kiểm tra trạng thái Chrome Debug CDP + liệt kê tabs (ping HTTP thuần)."""
    cdp_url = cfg.get("cdp_url", DEFAULT_CDP_URL)
    available, ver_info, tabs, hint = ping_cdp(cdp_url)

    browser_str = ver_info.get("Browser", "Chrome") if available else ""
    return {
        "type": 1,
        "available": available,
        "cdp_url": cdp_url,
        "browser": browser_str,
        "count": len(tabs),
        "tabs": tabs,
        "hint": hint if not available else "",
    }


def handle_type_2_inspect(
    cfg: Dict[str, Any],
    tab_keyword: str = "",
    mode: str = "interactive",
    include_errors: bool = True,
    clear_errors: bool = False,
) -> Dict[str, Any]:
    """type=2: Đọc buffer lỗi console/network + snapshot phần tử tương tác trên trang."""
    not_ready = _check_cdp_ready(cfg, 2)
    if not_ready:
        return not_ready

    session = ChromeSession.get_instance()
    session.set_config(cfg)
    cdp_url = cfg.get("cdp_url", DEFAULT_CDP_URL)

    page = session.resolve_page(tab_keyword, cdp_url=cdp_url)
    session.hook_page_events(page)

    buf = session.get_page_buffer(page)
    console_errors = buf.get_console_errors() if include_errors else []
    network_errors = buf.get_network_errors() if include_errors else []

    if clear_errors:
        buf.clear()

    errors_note = ""
    if include_errors and not console_errors and not network_errors:
        errors_note = (
            "Buffer lỗi hiện đang rỗng. Lưu ý: Buffer chỉ bắt đầu ghi nhận sau khi session hook tab. "
            "Nếu bạn vừa thao tác trước đó, hãy thực hiện lại thao tác hoặc reload trang để ghi nhận lỗi."
        )

    snap_cfg = cfg.get("snapshot", {})
    max_nodes = snap_cfg.get("max_nodes", MAX_SNAPSHOT_NODES_DEFAULT)
    max_label_chars = snap_cfg.get("max_label_chars", MAX_LABEL_CHARS_DEFAULT)

    snapshot_data = build_page_snapshot(
        page,
        max_nodes=max_nodes,
        max_label_chars=max_label_chars,
        mode=mode,
    )

    out: Dict[str, Any] = {
        "type": 2,
        "tab_url": snapshot_data["tab_url"],
        "tab_title": snapshot_data["tab_title"],
    }
    if include_errors:
        out["console"] = console_errors
        out["network_errors"] = network_errors
        if errors_note:
            out["errors_note"] = errors_note

    out["frames"] = snapshot_data["frames"]
    return out


def handle_type_3_interact(
    cfg: Dict[str, Any],
    tab_keyword: str = "",
    click: str = "",
    fields_json: str = "",
    frame_index: int = 0,
) -> Dict[str, Any]:
    """type=3: Điền trường dữ liệu và/hoặc click phần tử."""
    if not click and not fields_json:
        raise ValueError("Với type=3 (interact), cần cung cấp ít nhất một trong hai tham số: 'click' hoặc 'fields_json'.")

    not_ready = _check_cdp_ready(cfg, 3)
    if not_ready:
        return not_ready

    session = ChromeSession.get_instance()
    session.set_config(cfg)
    cdp_url = cfg.get("cdp_url", DEFAULT_CDP_URL)

    page = session.resolve_page(tab_keyword, cdp_url=cdp_url)

    out: Dict[str, Any] = {"type": 3}

    # 1. Fill fields trước
    if fields_json and fields_json.strip():
        try:
            fields_dict = json.loads(fields_json)
            if not isinstance(fields_dict, dict):
                raise ValueError("'fields_json' phải là một JSON Object (key-value dictionary).")
        except Exception as e:
            raise ValueError(f"Không thể parse 'fields_json': {e}")

        filled_results = fill_fields(page, fields_dict, frame_index=frame_index)
        out["filled"] = filled_results

    # 2. Click sau
    if click and click.strip():
        click_res = click_target(page, click, frame_index=frame_index)
        out["click"] = click_res

    return out


def handle_type_4_execute(
    cfg: Dict[str, Any],
    tab_keyword: str = "",
    script: str = "",
) -> Dict[str, Any]:
    """type=4: Thực thi JavaScript trên tab."""
    if not script or not script.strip():
        raise ValueError("Với type=4 (execute), tham số 'script' không được để trống.")

    not_ready = _check_cdp_ready(cfg, 4)
    if not_ready:
        return not_ready

    session = ChromeSession.get_instance()
    session.set_config(cfg)
    cdp_url = cfg.get("cdp_url", DEFAULT_CDP_URL)

    page = session.resolve_page(tab_keyword, cdp_url=cdp_url)

    max_result_chars = cfg.get("execute_js", {}).get("max_result_chars", MAX_RESULT_CHARS_DEFAULT)
    res = execute_page_script(page, script, max_result_chars=max_result_chars)

    out: Dict[str, Any] = {"type": 4}
    out.update(res)
    return out


def dispatch_chrome_debug(
    cfg: Dict[str, Any],
    type: int,
    tab_keyword: str = "",
    mode: str = "interactive",
    include_errors: bool = True,
    clear_errors: bool = False,
    click: str = "",
    fields_json: str = "",
    frame_index: int = 0,
    script: str = "",
) -> str:
    """Entry point điều phối yêu cầu chrome_debug theo type và trả về JSON string."""
    if not cfg.get("enabled", True):
        return json.dumps(
            {
                "type": type,
                "enabled": False,
                "message": "Tính năng Chrome Debug hiện đang bị tắt trong cấu hình (enabled=false).",
            },
            ensure_ascii=False,
            indent=2,
        )

    if type == 1:
        res = handle_type_1_status(cfg)
    elif type == 2:
        res = run_playwright_sync(
            handle_type_2_inspect,
            cfg=cfg,
            tab_keyword=tab_keyword,
            mode=mode,
            include_errors=include_errors,
            clear_errors=clear_errors,
        )
    elif type == 3:
        res = run_playwright_sync(
            handle_type_3_interact,
            cfg=cfg,
            tab_keyword=tab_keyword,
            click=click,
            fields_json=fields_json,
            frame_index=frame_index,
        )
    elif type == 4:
        res = run_playwright_sync(
            handle_type_4_execute,
            cfg=cfg,
            tab_keyword=tab_keyword,
            script=script,
        )
    else:
        raise ValueError(
            f"Giá trị 'type={type}' không hợp lệ. Vui lòng chọn: 1 (status), 2 (inspect), 3 (interact), 4 (execute)."
        )

    return json.dumps(res, ensure_ascii=False, indent=2)
