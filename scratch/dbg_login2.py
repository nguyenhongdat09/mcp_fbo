import sys, time
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import session as S
from fastbusiness_mcp.mcp_app import get_config
get_config()
print("t0", flush=True)
page = S.get_page(headless=False, timeout_ms=60000)
print("page", page.url, flush=True)
# Bắt mọi response để xem request nào pending
page.on("request", lambda r: print("REQ", r.method, r.url[-70:], flush=True))
page.on("response", lambda r: print("RES", r.status, r.url[-70:], flush=True))
page.on("console", lambda m: print("CONSOLE", m.type, m.text[:100], flush=True))
t0=time.time()
try:
    page.goto("http://172.168.5.14/HAOHOA/Main/login.aspx",
              wait_until="domcontentloaded", timeout=45000)
    print(f"goto ok {time.time()-t0:.0f}s url={page.url} title={page.title()!r}", flush=True)
except Exception as e:
    print(f"goto FAIL {type(e).__name__}: {e}", flush=True)
time.sleep(2)
print("final url:", page.url, "| readyState:",
      page.evaluate("() => document.readyState"), flush=True)
print("has user field:", page.locator("#LoginExtender_txtUserName").count(), flush=True)
# dump text trang — có thể là session-conflict / license / error page
print("body text:", (page.locator("body").inner_text() or "")[:500], flush=True)
