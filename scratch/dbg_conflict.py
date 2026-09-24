import sys, time, json
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import session as S
from browser_fbo.state import capture_state
from browser_fbo import smart as SM
from fastbusiness_mcp.mcp_app import get_config
cfg = get_config()
page = S.get_page(headless=False, timeout_ms=60000)
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
# giờ đang ở conflict — capture state xem dialogs có gì
st = capture_state(page)
print("DIALOGS:", json.dumps(st.get("dialogs"), ensure_ascii=False)[:800], flush=True)
print("screen:", st.get("screen"), flush=True)
# attention box HTML
html = page.evaluate("() => { const a=document.querySelector('#LoginExtender_Attention'); return a?a.outerHTML.slice(0,600):'none' }")
print("ATTENTION HTML:", html, flush=True)
vis = page.evaluate("() => { const a=document.querySelector('#LoginExtender_Attention'); if(!a) return 'none'; const r=a.getBoundingClientRect(); const cs=getComputedStyle(a); return `disp=${cs.display} vis=${cs.visibility} w=${r.width} h=${r.height}` }")
print("ATTENTION VIS:", vis, flush=True)
# JeV classify xem nó trả type gì
dec = SM.dispatch("classify_dialog", st, "hủy phiên làm việc trước", cfg)
print("JEV:", dec, flush=True)
# thử từng candidate selector xem cái nào visible
for sel in ['button:has-text("Hủy phiên")','span:has-text("Hủy phiên")',
            'a:has-text("Hủy phiên")','[onclick*="_login(true)"]',
            '#LoginExtender_Attention .Attention span',
            '#LoginExtender_Attention a, #LoginExtender_Attention span',
            'button:has-text("Có")']:
    try:
        loc = page.locator(sel).first
        print(f"  sel {sel!r}: count={page.locator(sel).count()} vis={loc.is_visible() if page.locator(sel).count() else '-'}", flush=True)
    except Exception as e:
        print(f"  sel {sel!r}: ERR {e}", flush=True)
