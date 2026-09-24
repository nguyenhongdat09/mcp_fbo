# -*- coding: utf-8 -*-
"""Recon socthda 11.11.06: dump field/grid/button của dialog New."""
import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
URL = "http://172.168.5.14/HAOHOA/Main/socthda.aspx?id=11.11.06"

def bf(**kw):
    kw.setdefault("config", cfg)
    r = BS.browser_fbo(**kw)
    print(f"== {kw.get('action')} {kw.get('command_name','')}{kw.get('field','')} "
          f"ok={r.get('success')} err={str(r.get('error'))[:100]}")
    return r

r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
if not r["success"]:
    sys.exit("LOGIN FAIL: " + str(r.get("error"))[:150])

bf(action="open", url=URL)
time.sleep(2)
st = bf(action="snapshot").get("state") or {}
print("screen:", st.get("screen"), "| toolbar:", st.get("toolbar"),
      "| grid:", (st.get("grid") or {}).get("id"), "rows:", (st.get("grid") or {}).get("row_count"))

# mở dialog New
bf(action="command", command_name="New")
time.sleep(2)

# dump tất cả component $find + fields trong updateDlg
r = bf(action="evaluate", js="""() => {
  const out = {components: [], fields: [], grids: [], buttons: []};
  // mọi element có id chứa dirExtender → component id
  document.querySelectorAll('[id*="dirExtender"],[id*="updateDlg"]').forEach(el => {
    const id = el.id;
    if (id && !out.components.includes(id) && out.components.length < 40)
      out.components.push(id);
  });
  // inputs/selects/textarea visible trong dialog
  document.querySelectorAll('[id*="_updateDlg"] input, [id*="_updateDlg"] select, [id*="_updateDlg"] textarea').forEach(el => {
    if (el.offsetParent || el.offsetHeight) {
      const lb = document.querySelector(`label[for="${el.id}"]`);
      out.fields.push({id: el.id.slice(-40), tag: el.tagName, type: el.type,
                       label: lb ? lb.textContent.trim().slice(0,30) : '',
                       val: (el.value||'').slice(0,30), disabled: el.disabled});
    }
  });
  // grid element trong dialog
  document.querySelectorAll('[id*="grid"],[id*="Grid"]').forEach(el => {
    if (el.offsetHeight > 30 && out.grids.length < 10)
      out.grids.push(el.id.slice(-60));
  });
  // nút
  document.querySelectorAll('[id*="_updateDlg"] button,[id*="_updateDlg"] a,[id*="_updateDlg"] [onclick]').forEach(el => {
    if ((el.offsetParent||el.offsetHeight) && out.buttons.length < 25)
      out.buttons.push({id: el.id.slice(-45), txt: (el.textContent||'').trim().slice(0,25)});
  });
  return out;
}""")
print(json.dumps(r.get("result"), ensure_ascii=False, indent=1)[:6000])
bf(action="cancel")
bf(action="close")
