"""Runtime worker thread quản lý thực thi an toàn cho Playwright Sync API trong môi trường asyncio."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Dedicated single-thread worker để chạy Playwright Sync API mà không bị conflict với asyncio loop
_PLAYWRIGHT_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chrome_cdp_worker")


def run_playwright_sync(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Thực thi function gọi Playwright sync trong dedicated thread nếu đang ở trong asyncio event loop."""
    try:
        asyncio.get_running_loop()
        in_async_loop = True
    except RuntimeError:
        in_async_loop = False

    if not in_async_loop:
        # Nếu đang ở sync thread thông thường, chạy trực tiếp
        return fn(*args, **kwargs)

    # Nếu đang ở asyncio loop (ví dụ MCP FastMCP call_tool), submit sang worker thread
    future = _PLAYWRIGHT_EXECUTOR.submit(fn, *args, **kwargs)
    return future.result(timeout=120)
