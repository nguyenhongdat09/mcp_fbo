"""E2E part 2: login -> snapshot stable -> menu navigate -> grid ops -> close."""
import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\x.ent"

def bf(**kw):
    t0 = time.time()
    r = BS.browser_fbo(config=cfg, **kw)
    print(f"== {kw.get('action')} ({time.time()-t0:.1f}s) ok={r['success']} err={str(r.get('error'))[:100]}")
    return r

r = bf(action="login", file_path=FP, headless=True)
print("  login_as:", (r.get("result") or {}).get("login_as"))
if not r["success"]:
    sys.exit("LOGIN FAIL")

# snapshot NGAY sau login — trước đây rỗng
r = bf(action="snapshot")
st = r.get("state") or {}
print("  screen:", st.get("screen"), "| menus:", len(st.get("menu_links") or []),
      "| title:", st.get("title"))
print("  menus:", (st.get("menu_links") or [])[:12])

# inspect cấu trúc menu thật — agent cần biết cách mở màn hình
r = bf(action="evaluate", js="""() => {
  const out = [];
  for (const a of document.querySelectorAll('a')) {
    const t = (a.innerText||'').trim();
    const oc = a.getAttribute('onclick')||'';
    const hr = a.getAttribute('href')||'';
    if (t && (oc || hr.includes('Dir') || hr.includes('.aspx')))
      out.push({t: t.slice(0,45), oc: oc.slice(0,90), href: hr.slice(0,90)});
    if (out.length >= 15) break;
  }
  return out;
}""")
for m in (r.get("result") or {}).get("result") or []:
    print("   menu:", json.dumps(m, ensure_ascii=False))

# tìm 1 mục danh mục (Dir) để mở — vd 'Danh mục khách hàng' hoặc bất kỳ link Dir
r = bf(action="evaluate", js="""() => {
  const cand = [...document.querySelectorAll('a')].find(a =>
    /khách hàng|customer/i.test(a.innerText||''));
  if (!cand) return 'none';
  cand.click();
  return 'clicked:' + (cand.innerText||'').trim().slice(0,50);
}""")
print("  click:", r.get("result"))
time.sleep(4)
r = bf(action="snapshot")
st = r.get("state") or {}
print("  screen:", st.get("screen"), "| url:", st.get("url")[-60:],
      "| grid:", st.get("grid"), "| toolbar:", st.get("toolbar")[:10])

# nếu có grid → test row_count/grid_get/select_row
r = bf(action="row_count")
print("  row_count:", r.get("result"))
r = bf(action="grid_get", row=1, col="1")
print("  grid_get(1,1):", str(r.get("result"))[:100])
r = bf(action="select_row", row=1)
print("  select_row:", r.get("result"))

bf(action="close")
print("DONE")
