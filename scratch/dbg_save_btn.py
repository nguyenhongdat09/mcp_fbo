import sys, time
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from browser_fbo import session as S
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"

r = BS.browser_fbo(action="login", file_path=FP, user="ADMIN",
                   password="2222222222", config=cfg)
print("login:", r["success"])
BS.browser_fbo(action="menu", menu_text="Danh mục khách hàng", config=cfg)
time.sleep(2)
BS.browser_fbo(action="command", command_name="New", config=cfg)
time.sleep(1.5)

page = S.current_page()
# Dump mọi button/input/anchor trong updateDlg + các nút Lưu/Hủy
out = page.evaluate("""() => {
  const vis = el => !!(el.offsetWidth || el.offsetHeight
    || el.getClientRects().length);
  const res = {dlg_buttons: [], toolbar_like: [], ok_ids: []};
  // dialog đang mở (updateDlg / Dialog)
  const dlgs = [...document.querySelectorAll(
    '[id*=updateDlg],[id*=Dlg],[id*=Dialog]')].filter(vis);
  for (const d of dlgs.slice(0,4)) {
    for (const b of d.querySelectorAll(
        'button,input[type=button],input[type=submit],a')) {
      if (!vis(b)) continue;
      res.dlg_buttons.push({
        dlg: d.id, tag: b.tagName, id: b.id || '',
        text: (b.innerText || b.value || '').trim().slice(0,40),
        oc: (b.getAttribute('onclick') || '').slice(0,80),
      });
    }
  }
  // mọi element có id chứa Ok/Save
  for (const el of document.querySelectorAll(
      '[id*=Ok],[id*=Save],[id*=Luu]')) {
    if (vis(el)) res.ok_ids.push(el.id + '|' + el.tagName);
  }
  return res;
}""")
for b in out.get("dlg_buttons", []):
    print("  DLGBTN", b)
print("  ok_ids:", out.get("ok_ids"))

# components có executeCommand nào
comps = page.evaluate("""() => {
  try {
    return Sys.Application.getComponents()
      .filter(c => typeof c.executeCommand === 'function')
      .map(c => c.get_id());
  } catch(e) { return ['err:'+e]; }
}""")
print("  executeCommand components:", comps)
BS.browser_fbo(action="close", config=cfg)
