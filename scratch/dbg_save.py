import sys, time, json
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import service as BS, session as S
from fastbusiness_mcp.mcp_app import get_config
cfg = get_config()
FP = r'\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent'
r = BS.browser_fbo(action='login', file_path=FP, user='ADMIN', password='2222222222', config=cfg)
print('login:', r['success'], flush=True)
r = BS.browser_fbo(action='menu', menu_text='Danh mục khách hàng', config=cfg)
time.sleep(2)
r = BS.browser_fbo(action='command', command_name='New', config=cfg)
time.sleep(2)
page = S.current_page()
st = r.get('state') or {}
print('screen:', st.get('screen'), '| fields:', len(st.get('form_fields') or []), flush=True)
# dump tất cả nút updateDlg*
info = page.evaluate("""() => {
  return [...document.querySelectorAll('[id*="updateDlg"]')].map(el => ({
    id: el.id, tag: el.tagName, text: (el.innerText||'').trim().slice(0,40),
    vis: !!(el.offsetWidth||el.offsetHeight),
    disabled: el.disabled, onclick: String(el.getAttribute('onclick')||'').slice(0,80)
  }));
}""")
print(json.dumps(info, ensure_ascii=False, indent=1), flush=True)
# điền + bấm Lưu THỦ CÔNG bằng JS, rồi theo dõi dialog
page.evaluate("() => { const e=document.querySelector('[id$=\"_form_ma_kh\"]'); if(e){e.value='ZZ_TEST_MCP'; e.dispatchEvent(new Event('change',{bubbles:true}));} }")
page.evaluate("() => { const e=document.querySelector('[id$=\"_form_ten_kh\"]'); if(e){e.value='KH TEST MCP'; e.dispatchEvent(new Event('change',{bubbles:true}));} }")
print('clicked save...', flush=True)
page.evaluate("() => { const b=[...document.querySelectorAll('[id$=\"_updateDlgOk\"]')].find(el=>el.offsetWidth||el.offsetHeight); if(b) b.click(); }")
for i in range(15):
    time.sleep(1)
    d = page.evaluate("""() => [...document.querySelectorAll('[id*="DialogMessage"],[id*="Message"],.MessageBox')]
      .filter(el=>el.offsetWidth||el.offsetHeight).map(el=>(el.innerText||'').trim().slice(0,150)).filter(Boolean)""")
    busy = page.evaluate("() => { try { return Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack(); } catch(e){ return '?'; } }")
    print(f'{i+1}s busy={busy} dialogs={d}', flush=True)
    if d: break
