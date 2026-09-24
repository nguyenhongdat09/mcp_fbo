"""E2E comprehensive test: profiler + browser_fbo on live HAOHOA."""
import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from trace_profile.service import profiler as PROF
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\x.ent"

def bf(**kw):
    t0 = time.time()
    r = BS.browser_fbo(config=cfg, **kw)
    print(f"== BROWSER {kw.get('action')} ({time.time()-t0:.1f}s) ok={r['success']} err={str(r.get('error'))[:100]}")
    return r

def pf(**kw):
    t0 = time.time()
    r = PROF(file_path=FP, config=cfg.get("profiler"),
             classify_key=(cfg.get("api_key") or {}).get("Jev", ""),
             classify_config=cfg.get("jev"), **kw)
    print(f"== PROFILER {kw.get('action')} ({time.time()-t0:.1f}s) ok={r.get('success')} err={str(r.get('error'))[:120]}")
    return r

print("========== PHASE 0: profiler list ==========")
r = pf(action="list")
print(json.dumps(r, ensure_ascii=False, default=str)[:800])

print("========== PHASE 1: profiler start ==========")
r = pf(action="start", db_type="all", events="standard")
tid = (r or {}).get("trace_id")
print("  trace_id:", tid)

print("========== PHASE 2: browser login ==========")
r = bf(action="login", file_path=FP, headless=True)
print("  login_as:", (r.get("result") or {}).get("login_as"),
      "| screen:", (r.get("state") or {}).get("screen"),
      "| menus:", len((r.get("state") or {}).get("menu_links") or []))
if not r["success"]:
    pf(action="stop", trace_id=tid or 0)
    sys.exit("LOGIN FAIL")

print("========== PHASE 3: snapshot ==========")
r = bf(action="snapshot")
st = r.get("state") or {}
print("  screen:", st.get("screen"), "| menus:", len(st.get("menu_links") or []),
      "| comps:", [c.get("id") for c in (st.get("components") or [])][:8])
print("  menus:", (st.get("menu_links") or [])[:15])

print("========== PHASE 4: evaluate menu ==========")
r = bf(action="evaluate", js="""() => {
  const links = [...document.querySelectorAll('a')].filter(a =>
    (a.innerText||'').trim() && /khách hàng|customer|danh mục/i.test(a.innerText||''));
  return links.slice(0,8).map(a => ({t:(a.innerText||'').trim().slice(0,40), oc:String(a.getAttribute('onclick')||'').slice(0,80), href:String(a.getAttribute('href')||'').slice(0,80)}));
}""")
print("  menu candidates:", json.dumps(r.get("result"), ensure_ascii=False)[:900])

print("========== PHASE 5: edge cases ==========")
r = bf(action="nonexistent_action_xyz")
print("  invalid action ->", str(r.get("error"))[:100])
r = bf(action="message")
print("  message no-dialog ->", r.get("result"))
r = bf(action="confirm", answer="yes", required=False)
print("  confirm no-dialog required=False ->", r.get("result"))
r = bf(action="row_count")
print("  row_count on main ->", r.get("result"), "| err:", r.get("error"))

print("========== PHASE 6: profiler read ==========")
time.sleep(2)
r = pf(action="read", trace_id=tid or 0, since_seq=0, max_rows=40, classify=True)
evs = (r or {}).get("events") or []
print("  events:", len(evs))
for e in evs[:10]:
    print("   -", str(e.get("event") or e.get("EventClass") or "")[:40],
          "| tag:", e.get("tag"), "|", str(e.get("text") or e.get("TextData") or "")[:80])

print("========== PHASE 7: close + stop ==========")
bf(action="close")
r = pf(action="stop", trace_id=tid or 0)
print("  stopped:", r.get("success"))
print("DONE")
