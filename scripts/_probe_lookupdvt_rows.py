import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

TABLE = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup_Table"
LOOKUP_BTN = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup"
QF = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup_QuickFind"

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto("http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06", timeout=90000)
time.sleep(8)
p.evaluate("() => { $find('ctl00_FastBusiness_MainReport').executeCommand({ commandName: 'New', commandArgument: '0' }); }")
time.sleep(3)
p.evaluate("() => { document.querySelector('[id*=\"dirExtender_form_dvt\"]').closest('td').querySelector('img.CellImgLookup').click(); }")
time.sleep(2)
p.evaluate(f"""() => {{
  document.getElementById('{QF}').value = 'khối';
  FastBusiness.AjaxControlExtender.AutoCompleteExtender.find('{LOOKUP_BTN}').quickFind();
}}""")
time.sleep(3)
rows = p.evaluate(f"""() => {{
  var t = document.getElementById('{TABLE}');
  var rows = [];
  t.querySelectorAll('tr').forEach(function(tr, i) {{
    var cells = Array.from(tr.querySelectorAll('td')).map(td => (td.innerText||'').trim());
    var links = Array.from(tr.querySelectorAll('a')).map(a => (a.innerText||'').trim());
    rows.push({{ i: i, cells: cells, links: links }});
  }});
  return rows;
}}""")
print(json.dumps(rows, ensure_ascii=False, indent=2))
p.close()
