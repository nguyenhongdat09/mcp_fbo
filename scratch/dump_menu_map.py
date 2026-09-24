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
if not r["success"]:
    sys.exit(1)
page = S.current_page()
time.sleep(2)

# Tất cả leaf menu item: anchor có href *.aspx?id=
items = page.evaluate("""() => {
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href') || '';
    const m = href.match(/([\\w]+\\.aspx\\?id=[\\d.]+)/i);
    if (!m) continue;
    const t = (a.innerText || '').trim();
    const key = m[1] + '|' + t;
    if (seen.has(key)) continue;
    seen.add(key);
    // group path: leo DOM tìm nhóm cha gần nhất (td/div chứa)
    out.push({text: t, url: m[1], id: a.id || ''});
  }
  return out;
}""")
print("TOTAL leaf items:", len(items))
with open(r"E:\PythonProject\mcp_fbo\scratch\menu_map.json", "w",
          encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=1)
for it in items:
    print("  ", it["url"], "|", it["text"])
BS.browser_fbo(action="close", config=cfg)
