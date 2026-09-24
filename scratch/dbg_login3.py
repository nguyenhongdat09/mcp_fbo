import sys, time
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import session as S
from fastbusiness_mcp.mcp_app import get_config
get_config()
page = S.get_page(headless=False, timeout_ms=60000)
print("page", page.url, flush=True)
page.on("crash", lambda p: print("!! PAGE CRASHED", flush=True))
t0 = time.time()
try:
    page.goto("http://172.168.5.14/HAOHOA/Main/login.aspx",
              wait_until="domcontentloaded", timeout=45000)
    print(f"goto {time.time()-t0:.0f}s url={page.url}", flush=True)
    # điền form thủ công từng bước, in ra mỗi bước
    page.locator("#LoginExtender_txtUserName").wait_for(state="visible", timeout=30000)
    print("user visible", flush=True)
    page.locator("#LoginExtender_txtUserName").fill("ADMIN")
    page.locator("#LoginExtender_txtUserName").press("Tab")
    print("filled user, wait cboUnit...", flush=True)
    for i in range(30):
        n = page.evaluate("() => { const s=document.querySelector('#LoginExtender_cboUnit'); return s?s.options.length:-1 }")
        if n and n > 1:
            break
        time.sleep(1)
    opts = page.evaluate("() => [...document.querySelectorAll('#LoginExtender_cboUnit option')].map(o=>o.value+'|'+o.text)")
    print("unit opts:", opts, flush=True)
    page.evaluate("() => { const s=document.querySelector('#LoginExtender_cboUnit'); for(let i=0;i<s.options.length;i++){if(s.options[i].value){s.selectedIndex=i;break}} }")
    page.locator("#LoginExtender_txtPassword").fill("2222222222")
    print("filled pass, click Ok...", flush=True)
    page.locator("#LoginExtender_Ok").click(timeout=8000)
    for i in range(40):
        time.sleep(1)
        u = page.url
        if "login.aspx" not in u.lower():
            print(f"navigated {i+1}s → {u}", flush=True)
            break
        if i % 10 == 9:
            att = page.evaluate("() => { const a=document.querySelector('#LoginExtender_Attention'); return a?a.innerText.slice(0,200):'' }")
            print(f"  still login {i+1}s, attention={att!r}", flush=True)
    print("final url:", page.url, flush=True)
except Exception as e:
    print(f"FAIL {type(e).__name__}: {e}", flush=True)
    print("url:", getattr(page, 'url', '?'), flush=True)
