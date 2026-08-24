"""Quản lý CDP connection, session lifecycle, và page routing."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from .buffers import TabBuffers
from .constants import (
    DEFAULT_CDP_URL,
    DEFAULT_PING_TIMEOUT_SECONDS,
    HINT_CHROME_DEBUG_WINDOWS,
)
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

# Import guard Playwright
try:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Error as PlaywrightError,
        Page,
        Playwright,
        Response,
        sync_playwright,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Playwright = Any  # type: ignore
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    Response = Any  # type: ignore
    PlaywrightError = Exception  # type: ignore


def ping_cdp(cdp_url: str = DEFAULT_CDP_URL, timeout: float = DEFAULT_PING_TIMEOUT_SECONDS) -> Tuple[bool, Dict[str, Any], List[Dict[str, Any]], str]:
    """Kiểm tra CDP endpoint có khả dụng hay không bằng HTTP GET thuần (không cần Playwright).
    
    Returns: (available, version_info, tabs_list, error_or_hint)
    """
    version_url = f"{cdp_url.rstrip('/')}/json/version"
    list_url = f"{cdp_url.rstrip('/')}/json/list"

    version_info: Dict[str, Any] = {}
    tabs_list: List[Dict[str, Any]] = []

    try:
        req = urllib.request.Request(version_url, headers={"User-Agent": "FastBusiness-MCP-CDP-Client"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = response.read().decode("utf-8")
                version_info = json.loads(data)
    except Exception as e:
        hint = HINT_CHROME_DEBUG_WINDOWS.format(cdp_url=cdp_url)
        return False, {}, [], f"Không thể kết nối đến {version_url}: {e}\n{hint}"

    # Lấy danh sách tab qua /json/list
    try:
        req = urllib.request.Request(list_url, headers={"User-Agent": "FastBusiness-MCP-CDP-Client"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = response.read().decode("utf-8")
                raw_tabs = json.loads(data)
                index = 0
                for tab in raw_tabs:
                    # Lọc page thông thường
                    tab_type = tab.get("type", "page")
                    if tab_type in ("page", "app"):
                        tabs_list.append({
                            "index": index,
                            "title": tab.get("title", ""),
                            "url": tab.get("url", ""),
                        })
                        index += 1
    except Exception as e:
        logger.debug(f"Failed to fetch /json/list: {e}")

    return True, version_info, tabs_list, ""


class ChromeSession:
    """Singleton quản lý kết nối Playwright qua CDP."""

    _instance: Optional["ChromeSession"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._buffers: Dict[str, TabBuffers] = {}
        self._hooked_pages: set[str] = set()
        self._config: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "ChromeSession":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def set_config(self, cfg: Dict[str, Any]) -> None:
        self._config = cfg

    def is_connected(self) -> bool:
        return bool(self._browser and self._browser.is_connected())

    def disconnect(self) -> None:
        """Đóng kết nối CDP và giải phóng Playwright an toàn."""
        with self._lock:
            try:
                if self._browser:
                    self._browser.close()
            except Exception:
                pass
            try:
                if self._playwright:
                    self._playwright.stop()
            except Exception:
                pass
            self._browser = None
            self._playwright = None
            self._buffers.clear()
            self._hooked_pages.clear()

    def connect(self, cdp_url: str = DEFAULT_CDP_URL) -> Browser:
        """Kết nối Playwright qua CDP (Thread-safe)."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Thiếu thư viện 'playwright'. Vui lòng cài đặt: pip install playwright")

        with self._lock:
            if self._browser and self._browser.is_connected():
                return self._browser

            # Nếu cũ bị stale thì dọn dẹp
            try:
                if self._playwright:
                    self._playwright.stop()
            except Exception:
                pass

            logger.info(f"Connecting Playwright over CDP to {cdp_url}...")
            self._playwright = sync_playwright().start()
            try:
                self._browser = self._playwright.chromium.connect_over_cdp(cdp_url)
                logger.info("Playwright CDP connected successfully.")
            except Exception as e:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
                self._browser = None
                raise RuntimeError(f"Lỗi khi kết nối Playwright tới {cdp_url}: {e}")

            return self._browser

    def _get_page_id(self, page: Page) -> str:
        try:
            return str(id(page))
        except Exception:
            return "page_default"

    def get_page_buffer(self, page: Page) -> TabBuffers:
        page_id = self._get_page_id(page)
        max_lines = self._config.get("console", {}).get("max_lines", 200)
        if page_id not in self._buffers:
            self._buffers[page_id] = TabBuffers(max_console_lines=max_lines)
        return self._buffers[page_id]

    def hook_page_events(self, page: Page) -> None:
        """Lắng nghe console và response lỗi HTTP trên Page."""
        page_id = self._get_page_id(page)
        if page_id in self._hooked_pages:
            return

        buf = self.get_page_buffer(page)
        capture_from = self._config.get("network", {}).get("capture_status_from", 400)
        max_body_chars = self._config.get("network", {}).get("max_response_chars", 4000)

        def on_console(msg: Any) -> None:
            try:
                msg_type = msg.type
                text = msg.text
                if msg_type in ("error", "warning"):
                    buf.add_console(msg_type, text)
            except Exception:
                pass

        def on_request_failed(request: Any) -> None:
            try:
                fail_text = request.failure
                buf.add_network_error(
                    url=request.url,
                    method=request.method,
                    status=0,
                    request_payload=str(request.post_data or "")[:500],
                    response_body=f"Request failed: {fail_text}",
                )
            except Exception:
                pass

        def on_response(response: Response) -> None:
            try:
                if response.status >= capture_from:
                    req = response.request
                    body_text = ""
                    try:
                        body_text = response.text()[:max_body_chars]
                    except Exception:
                        body_text = "[Body unavailable]"

                    buf.add_network_error(
                        url=response.url,
                        method=req.method,
                        status=response.status,
                        request_payload=str(req.post_data or "")[:500],
                        response_body=body_text,
                    )
            except Exception:
                pass

        try:
            page.on("console", on_console)
            page.on("requestfailed", on_request_failed)
            page.on("response", on_response)
            self._hooked_pages.add(page_id)
        except Exception:
            pass

    def all_pages(self) -> List[Page]:
        """Lấy tất cả các pages từ các contexts."""
        if not self._browser or not self._browser.is_connected():
            return []
        pages: List[Page] = []
        try:
            for ctx in self._browser.contexts:
                pages.extend(ctx.pages)
        except Exception:
            return []
        return pages

    def resolve_page(self, tab_keyword: str = "", cdp_url: str = DEFAULT_CDP_URL) -> Page:
        """Tìm page theo từ khóa URL/Title, hoặc lấy page cuối cùng (kèm auto-reconnect nếu stale)."""
        def _find_page() -> Page:
            browser = self.connect(cdp_url)
            pages = self.all_pages()

            if not pages:
                raise RuntimeError("Không tìm thấy tab nào đang mở trong trình duyệt Chrome.")

            # Hook tất cả các page hiện có
            for p in pages:
                try:
                    self.hook_page_events(p)
                except Exception:
                    pass

            if not tab_keyword or not tab_keyword.strip():
                return pages[-1]

            kw = tab_keyword.strip().lower()
            matched: List[Page] = []
            tab_summaries: List[str] = []

            for p in pages:
                try:
                    title = p.title() or ""
                    url = p.url or ""
                    tab_summaries.append(f"[{title}] ({url})")
                    if kw in title.lower() or kw in url.lower():
                        matched.append(p)
                except Exception:
                    continue

            if matched:
                return matched[-1]

            tab_list_str = "\n".join(f"- {t}" for t in tab_summaries)
            raise ValueError(
                f"Không tìm thấy tab nào khớp từ khóa '{tab_keyword}'.\n"
                f"Danh sách các tab hiện có:\n{tab_list_str}"
            )

        try:
            return _find_page()
        except PlaywrightError as e:
            err_msg = str(e)
            if "Target closed" in err_msg or "Browser has been closed" in err_msg or "Connection closed" in err_msg:
                logger.info(f"Target connection closed: {e}. Reconnecting...")
                self.disconnect()
                return _find_page()
            raise
