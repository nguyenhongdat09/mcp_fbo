"""Hằng số mặc định cho Chrome CDP Debug package."""

DEFAULT_CDP_URL = "http://localhost:9222"
DEFAULT_PING_TIMEOUT_SECONDS = 2.0
DEFAULT_ACTION_TIMEOUT_MS = 5000

MAX_SNAPSHOT_NODES_DEFAULT = 120
MAX_LABEL_CHARS_DEFAULT = 120
MAX_RESPONSE_CHARS_DEFAULT = 4000
MAX_CONSOLE_LINES_DEFAULT = 200
MAX_RESULT_CHARS_DEFAULT = 2000

HINT_CHROME_DEBUG_WINDOWS = (
    'Chưa kết nối được Chrome Debug tại {cdp_url}.\n'
    'Vui lòng khởi động Chrome với lệnh sau:\n'
    '  chrome.exe --remote-debugging-port=9222 --user-data-dir="%TEMP%\\chrome-fbo-debug"\n'
    'Hoặc tạo Shortcut trên Windows với Target:\n'
    '  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\\chrome-fbo-debug"'
)
