import sys, time, re
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import session as S
from browser_fbo import actions as A

page = S.get_page(headless=False, timeout_ms=30_000)
ctx = page.context

def on_resp(r):
    try:
        if "Main.aspx" in r.url or "login" in r.url.lower():
            body = r.text()
            # tìm đoạn script điều hướng: window.open / location / opener
            hits = re.findall(
                r"(window\.open[^;]*|location\.[a-z]+ *=[^;]*|"
                r"window\.close[^;]*|opener[^;]{0,80}|document\.write[^;]{0,80})",
                body, re.I)
            print(f"\n### RESP {r.url} [{r.status}] len={len(body)}")
            for h in hits[:15]:
                print("   ", h[:150])
    except Exception as e:
        print("resp err:", e)

ctx.on("page", lambda p: print("  >> NEW PAGE:", p.url))
page.on("response", on_resp)
page.on("framenavigated",
        lambda f: print("  >> NAV:", f.url) if f == page.main_frame else None)
page.on("close", lambda p: print("  >> PAGE CLOSED"))

url = "http://172.168.5.14/HAOHOA/Main/login.aspx"
try:
    r = A.login(page, url, "ADMIN", "2222222222", "CTY",
                attempts=1, wait_ok_seconds=150)
    print("LOGIN:", r)
except Exception as e:
    print("LOGIN ERR:", e)

for i in range(16):
    pages = [(p.url, p.is_closed()) for p in ctx.pages]
    print(f"t={i*0.5:.1f}s pages={pages}")
    time.sleep(0.5)

act = S.current_page()
if act:
    print("ACTIVE:", act.url, "| title:", act.title())
S.close()
