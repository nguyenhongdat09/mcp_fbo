import sys, time
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from browser_fbo import session as S
from fastbusiness_mcp.mcp_app import get_config
from trace_profile.connection import resolve_profiler_connection, run_sql

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
TEST_MA = "ZZ_TEST_MCP"

def db_check(tag):
    conn = resolve_profiler_connection(FP, 'app', cfg)
    res = run_sql(conn["parsed"],
        f"SELECT ma_kh, ten_kh FROM dmkh WHERE ma_kh='{TEST_MA}'")
    rows = (res.get('result_sets') or [{}])[0].get('rows', [])
    print(f"  DB[{tag}]:", rows)
    return rows

r = BS.browser_fbo(action="login", file_path=FP, user="ADMIN",
                   password="2222222222", config=cfg)
print("login:", r["success"])
db_check("truoc")
BS.browser_fbo(action="menu", menu_text="Danh mục khách hàng", config=cfg)
time.sleep(2)
BS.browser_fbo(action="command", command_name="New", config=cfg)
time.sleep(1.5)

page = S.current_page()
# dump HTML của updateDlg — tìm cấu trúc nút thật
out = page.evaluate("""() => {
  const vis = el => !!(el.offsetWidth || el.offsetHeight
    || el.getClientRects().length);
  const dlgs = [...document.querySelectorAll(
    '[id*=updateDlg],[id*=Dlg],[id*=Dialog],[id*=Modal]')]
    .filter(vis);
  const res = [];
  for (const d of dlgs.slice(0, 3)) {
    // tìm MỌI element có onclick hoặc text Lưu/Hủy trong dialog
    const acts = [...d.querySelectorAll('*')].filter(el => {
      if (!vis(el)) return false;
      const t = (el.innerText || el.value || '').trim();
      const oc = el.getAttribute && el.getAttribute('onclick');
      return (oc && oc.length) || /^(Lưu|Hủy|Save|Cancel|Nhận|Đồng ý)$/.test(t);
    }).slice(0, 15).map(el => ({
      tag: el.tagName, id: el.id || '',
      cls: String(el.className||'').slice(0,60),
      text: (el.innerText || el.value || '').trim().slice(0,40),
      oc: String(el.getAttribute('onclick')||'').slice(0,100),
    }));
    res.push({dlg_id: d.id, dlg_cls: String(d.className||'').slice(0,80), acts});
  }
  return res;
}""")
import json
print(json.dumps(out, ensure_ascii=False, indent=1)[:3000])

BS.browser_fbo(action="close", config=cfg)
