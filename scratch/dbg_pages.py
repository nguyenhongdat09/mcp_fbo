import sys, time
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import session as S
from browser_fbo import actions as A

page = S.get_page(headless=False, timeout_ms=30_000)
ctx = page.context

ctx.on("page", lambda p: print("  >> NEW PAGE:", p.url))
page.on("popup", lambda p: print("  >> POPUP:", p.url))
page.on("framenavigated", lambda f: print("  >> NAV:", f.url)
        if f == page.main_frame else None)

url = "http://172.168.5.14/HAOHOA/Main/login.aspx"
try:
    r = A.login(page, url, "ADMIN", "2222222222", "CTY",
                attempts=1, wait_ok_seconds=120)
    print("LOGIN:", r)
except Exception as e:
    print("LOGIN ERR:", e)

for i in range(16):
    pages = [(p.url, p.is_closed()) for p in ctx.pages]
    print(f"t={i*0.5:.1f}s pages={pages}")
    time.sleep(0.5)

# thử nội dung page active
act = S.current_page()
if act:
    print("ACTIVE:", act.url, "| title:", act.title())
    print("anchors:", act.evaluate("() => document.querySelectorAll('a').length"))
S.close()
