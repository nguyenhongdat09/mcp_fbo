import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto("http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39", timeout=90000)
time.sleep(8)

# fill + nhan (same as before)
p.evaluate("""() => {
  var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
  function fill(name, val) {
    var el = document.querySelector('[id*="searchExtender_form_' + name + '"]');
    if (el) { el.value = val; if (el.onchange) el.onchange(); }
  }
  fill('tu_ngay', '01/01/2025');
  fill('den_ngay', '31/12/2025');
  se.setItemValue('ma_vt', '001');
}""")
p.locator("#ctl00_FastBusiness_MainReport_searchExtender_updateDlgOk").click()
time.sleep(6)

grid = p.evaluate("""() => {
  var tables = document.querySelectorAll('table');
  var info = [];
  for (var t of tables) {
    if (!t.id || t.id.indexOf('MainReport') < 0) continue;
    var trs = t.querySelectorAll('tr');
    var dataRows = [];
    for (var tr of trs) {
      var tds = tr.querySelectorAll('td');
      if (tds.length >= 5) {
        var txt = Array.from(tds).map(x => (x.innerText||'').trim()).filter(x => x);
        if (txt.length >= 3 && !txt[0].includes('Người sử dụng')) dataRows.push(txt.slice(0, 8));
      }
    }
    if (dataRows.length) info.push({ tableId: t.id, rows: dataRows.slice(0, 5) });
  }
  // empty message
  var empty = document.body.innerText.match(/không có dữ liệu|no data|không tìm thấy/i);
  return { tables: info, empty_msg: empty ? empty[0] : null, body_snippet: document.body.innerText.substring(0, 500) };
}""")
print(json.dumps(grid, ensure_ascii=False, indent=2))
p.close()
