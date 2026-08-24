"""Probe FormLookuploai_vt / FormLookuptk_vt sau quickFind."""
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

def probe(field, term, tab=None):
    if tab:
        p.evaluate("""(t) => {
          var as = document.querySelectorAll('[id*="dirExtender_Tabs"] a');
          for (var a of as) if ((a.innerText||'').trim()===t) { a.click(); return; }
        }""", tab)
        time.sleep(1)
    p.evaluate("""(field) => {
      var inp = document.querySelector('[id*="dirExtender_form_' + field + '"]');
      inp.closest('td').querySelector('img.CellImgLookup').click();
    }""", field)
    time.sleep(2)
    btn = f"{DE}_FormLookup{field}_Button_Lookup"
    qf = f"{DE}_FormLookup{field}_Button_Lookup_QuickFind"
    table = f"{DE}_FormLookup{field}_Button_Lookup_Table"
    p.evaluate("""(args) => {
      document.getElementById(args.qf).value = args.term;
      FastBusiness.AjaxControlExtender.AutoCompleteExtender.find(args.btn).quickFind();
    }""", {"qf": qf, "btn": btn, "term": term})
    time.sleep(2.5)
    rows = p.evaluate("""(tableId) => {
      var t = document.getElementById(tableId);
      if (!t) return { error: 'no table', id: tableId };
      var rows = [];
      t.querySelectorAll('tr').forEach(function(tr, i) {
        rows.push({
          i: i,
          cells: Array.from(tr.querySelectorAll('td')).map(td => (td.innerText||'').trim().substring(0,40)),
          links: Array.from(tr.querySelectorAll('a')).map(a => (a.innerText||'').trim()).filter(Boolean)
        });
      });
      return { id: tableId, rows: rows };
    }""", table)
    # close
    p.evaluate("""() => {
      var btns = document.querySelectorAll('a, button, input');
      for (var b of btns) {
        if ((b.innerText||b.value||'').trim() === 'Đóng') { b.click(); return; }
      }
    }""")
    time.sleep(1)
    return rows

print("=== loai_vt ===")
print(json.dumps(probe("loai_vt", "08"), ensure_ascii=False, indent=2))
print("=== tk_vt ===")
print(json.dumps(probe("tk_vt", "51", "Tài khoản"), ensure_ascii=False, indent=2))
p.close()
