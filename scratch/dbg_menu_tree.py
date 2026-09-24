import sys, json, time
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from browser_fbo import session as S
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"

r = BS.browser_fbo(action="login", file_path=FP, user="ADMIN",
                   password="2222222222", config=cfg)
print("login:", r["success"], str(r.get("error"))[:100])
page = S.current_page()
time.sleep(2)

# Dump cấu trúc MenuExtender — tìm field chứa items/urls
out = page.evaluate("""() => {
  const res = {keys: [], items: []};
  try {
    const me = $find('ctl00_MenuExtender');
    if (!me) return {err: 'no MenuExtender'};
    // liệt kê property chứa mảng/object có vẻ là items
    for (const k of Object.keys(me)) {
      const v = me[k];
      if (Array.isArray(v) && v.length)
        res.keys.push(k + ': array[' + v.length + ']');
      else if (v && typeof v === 'object' && !v.nodeType)
        res.keys.push(k + ': obj');
      else if (typeof v === 'string' && v.length < 60)
        res.keys.push(k + '=' + v);
      else if (typeof v !== 'function' && typeof v !== 'object')
        res.keys.push(k + ':' + typeof v);
    }
    // thử các field hay gặp
    const cand = me._items || me._menuItems || me._data || me._menus;
    if (cand) res.sample = JSON.stringify(cand).slice(0, 1500);
  } catch (e) { res.err = String(e); }
  return res;
}""")
print("KEYS:", json.dumps(out.get("keys"), ensure_ascii=False)[:2000])
print("SAMPLE:", (out.get("sample") or "")[:1500])
print("ERR:", out.get("err"))

# Fallback: dump toàn bộ anchor menu + thuộc tính (href/onclick/data-*)
out2 = page.evaluate("""() => {
  return [...document.querySelectorAll(
    'a.MenuExtenderContextItem, a.MenuItem, td[id*=Menu] a, div[id*=Menu] a')]
    .slice(0, 400).map(a => ({
      t: (a.innerText||'').trim().slice(0,50),
      href: a.getAttribute('href') || '',
      oc: (a.getAttribute('onclick')||'').slice(0,120),
      id: a.id || '',
      name: a.getAttribute('name') || '',
    })).filter(x => x.t);
}""")
print("ANCHORS:", len(out2))
for a in out2[:60]:
    print("  ", json.dumps(a, ensure_ascii=False)[:200])
BS.browser_fbo(action="close", config=cfg)
