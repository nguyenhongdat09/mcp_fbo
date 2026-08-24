"""Probe tk_vt quickFind 51."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

DE = "ctl00_FastBusiness_MainReport_dirExtender"
cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto("http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06", timeout=90000)
time.sleep(8)
p.evaluate("() => { $find('ctl00_FastBusiness_MainReport').executeCommand({ commandName: 'New', commandArgument: '0' }); }")
time.sleep(3)
p.evaluate("() => { document.getElementById('__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel2').click(); }")
time.sleep(1.5)
p.evaluate("""() => {
  document.querySelector('[id*="dirExtender_form_tk_vt"]').closest('td').querySelector('img.CellImgLookup').click();
}""")
time.sleep(2)
p.evaluate(f"""() => {{
  document.getElementById('{DE}_FormLookuptk_vt_Button_Lookup_QuickFind').value = '51';
  FastBusiness.AjaxControlExtender.AutoCompleteExtender.find('{DE}_FormLookuptk_vt_Button_Lookup').quickFind();
}}""")
time.sleep(3)
rows = p.evaluate(f"""() => {{
  var t = document.getElementById('{DE}_FormLookuptk_vt_Button_Lookup_Table');
  return Array.from(t.querySelectorAll('tr')).map((tr,i) => ({{
    i:i,
    cells: Array.from(tr.querySelectorAll('td')).map(td => (td.innerText||'').trim().substring(0,50)),
    links: Array.from(tr.querySelectorAll('a')).map(a => (a.innerText||'').trim()).filter(Boolean)
  }}));
}}""")
print(json.dumps(rows, ensure_ascii=False, indent=2))
p.close()
