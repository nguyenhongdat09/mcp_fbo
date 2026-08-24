"""Probe DOM grid FormLookupdvt sau quickFind."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

LOOKUP_BTN = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup"

p_cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(p_cfg["cdp_url"]).contexts[0].new_page()
p.goto("http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06", timeout=90000)
time.sleep(8)
p.evaluate("() => { $find('ctl00_FastBusiness_MainReport').executeCommand({ commandName: 'New', commandArgument: '0' }); }")
time.sleep(3)
p.evaluate("() => { document.querySelector('[id*=\"dirExtender_form_dvt\"]').closest('td').querySelector('img.CellImgLookup').click(); }")
time.sleep(2)
p.evaluate("""() => {
  var qf = document.getElementById('ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup_QuickFind');
  qf.value = 'khối';
  FastBusiness.AjaxControlExtender.AutoCompleteExtender.find('ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup').quickFind();
}""")
time.sleep(2)
res = p.evaluate("""() => {
  var out = { tables: [] };
  document.querySelectorAll('[id*="FormLookupdvt"]').forEach(function(el) {
    if (el.tagName === 'TABLE' || el.id.indexOf('grid') >= 0) {
      out.tables.push({ id: el.id, tag: el.tagName, tr_count: el.querySelectorAll('tr').length });
    }
  });
  document.querySelectorAll('table[id*="FormLookupdvt"], table[id*="Lookupdvt"]').forEach(function(t) {
    var rows = [];
    t.querySelectorAll('tr').forEach(function(tr, i) {
      if (i > 5) return;
      var tds = tr.querySelectorAll('td');
      rows.push(Array.from(tds).map(td => (td.innerText||'').trim().substring(0,30)));
    });
    out['table_' + t.id] = rows;
  });
  return out;
}""")
print(json.dumps(res, ensure_ascii=False, indent=2))
p.close()
