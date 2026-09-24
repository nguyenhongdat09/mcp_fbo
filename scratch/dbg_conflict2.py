import sys, time
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import session as S
from fastbusiness_mcp.mcp_app import get_config
get_config()
page = S.get_page(headless=False, timeout_ms=60000)
ctx = page.context
ctx.on("page", lambda p: print("NEW PAGE:", p.url, flush=True))
page.on("crash", lambda p: print("!! CRASH on", p.url, flush=True))
page.on("close", lambda p: print("PAGE CLOSED:", p.url, flush=True))
page.goto("http://172.168.5.14/HAOHOA/Main/login.aspx",
          wait_until="domcontentloaded", timeout=45000)
page.locator("#LoginExtender_txtUserName").wait_for(state="visible", timeout=30000)
page.locator("#LoginExtender_txtUserName").fill("ADMIN")
page.locator("#LoginExtender_txtUserName").press("Tab")
time.sleep(3)
page.evaluate("() => { const s=document.querySelector('#LoginExtender_cboUnit'); for(let i=0;i<s.options.length;i++){if(s.options[i].value){s.selectedIndex=i;break}} }")
page.locator("#LoginExtender_txtPassword").fill("2222222222")
page.locator("#LoginExtender_Ok").click(timeout=8000)
time.sleep(4)
print("attention:", page.evaluate("() => (document.querySelector('#LoginExtender_Attention')||{}).innerText||''"), flush=True)
print("click 'Nhấn vào đây' (onclick span)...", flush=True)
page.locator('[onclick*="_login(true)"]').first.click()
for i in range(45):
    time.sleep(1)
    try:
        pages = ctx.pages
        urls = [p.url for p in pages]
        alive = [not p.is_closed() for p in pages]
        if i % 5 == 4 or any('Main.aspx' in u for u in urls):
            print(f"{i+1}s pages={list(zip(urls, alive))}", flush=True)
        if any('Main.aspx' in u for u in urls):
            break
    except Exception as e:
        print(f"{i+1}s ctx err: {e}", flush=True)
