"""Thực hiện các thao tác tương tác (Fill, Click, Execute JS) trên Page."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


def resolve_target_frame(page: Any, frame_index: int = 0) -> Any:
    """Lấy frame theo index, fallback về main frame nếu không tìm thấy."""
    frames = page.frames
    if 0 <= frame_index < len(frames):
        return frames[frame_index]
    return page.main_frame


def fill_fields(page: Any, fields_dict: Dict[str, Any], frame_index: int = 0) -> List[str]:
    """Điền giá trị vào các trường form và kích hoạt sự kiện blur/change/Tab."""
    frame = resolve_target_frame(page, frame_index)
    results: List[str] = []

    for field_name, val in fields_dict.items():
        val_str = "" if val is None else str(val)
        matched = False

        selectors = [
            f'input[name="{field_name}"]',
            f'textarea[name="{field_name}"]',
            f'select[name="{field_name}"]',
            f'#{field_name}',
            f'[data-field="{field_name}"]',
            f'[name*="{field_name}"]',
        ]

        for sel in selectors:
            try:
                locator = frame.locator(sel)
                if locator.count() > 0:
                    target = locator.first
                    tag_name = target.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name == "select":
                        target.select_option(value=val_str)
                    else:
                        target.fill(val_str)
                        target.dispatch_event("change")
                        target.dispatch_event("blur")

                    results.append(f"{field_name} -> {sel}")
                    matched = True
                    break
            except Exception as e:
                logger.debug(f"Failed to fill with {sel}: {e}")
                continue

        if not matched:
            try:
                locator = frame.get_by_label(field_name)
                if locator.count() > 0:
                    target = locator.first
                    target.fill(val_str)
                    target.dispatch_event("change")
                    target.dispatch_event("blur")
                    results.append(f"{field_name} -> get_by_label('{field_name}')")
                    matched = True
            except Exception:
                pass

        if not matched:
            results.append(f"{field_name} -> NOT FOUND")

    return results


def click_target(page: Any, target: str, frame_index: int = 0) -> str:
    """Click vào element theo thứ tự ưu tiên: ref (e0, e1) -> selector -> text."""
    frame = resolve_target_frame(page, frame_index)
    target = target.strip()

    # 1. Kiểm tra nếu là ref (e.g., e0, e12)
    if target.startswith("e") and target[1:].isdigit():
        ref_sel = f'[data-cdp-ref="{target}"]'
        try:
            locator = frame.locator(ref_sel)
            if locator.count() > 0:
                locator.first.click()
                return f"Clicked ref={target}"
        except Exception as e:
            logger.debug(f"Click by ref failed: {e}")

    # 2. Thử coi target là CSS Selector
    try:
        locator = frame.locator(target)
        if locator.count() > 0:
            locator.first.click()
            return f"Clicked selector={target}"
    except Exception:
        pass

    # 3. Thử tìm theo Text chính xác hoặc chứa text (Button, Link, Element)
    try:
        locator = frame.get_by_role("button", name=target)
        if locator.count() > 0:
            locator.first.click()
            return f"Clicked button text='{target}'"
    except Exception:
        pass

    try:
        locator = frame.get_by_text(target, exact=True)
        if locator.count() > 0:
            locator.first.click()
            return f"Clicked text exact='{target}'"
    except Exception:
        pass

    try:
        locator = frame.get_by_text(target, exact=False)
        if locator.count() > 0:
            locator.first.click()
            return f"Clicked text partial='{target}'"
    except Exception:
        pass

    raise ValueError(f"Không tìm thấy phần tử nào để click khớp với '{target}' trên frame {frame_index}.")


def execute_page_script(page: Any, script: str, max_result_chars: int = 2000) -> Dict[str, Any]:
    """Thực thi script JavaScript trên main frame của Page an toàn."""
    try:
        res = page.evaluate(script)
        res_json = json.dumps(res, ensure_ascii=False) if res is not None else "null"
        if len(res_json) > max_result_chars:
            return {
                "ok": True,
                "result": res_json[:max_result_chars] + "... [truncated]",
                "truncated": True,
            }
        return {"ok": True, "result": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}
