"""Probe loai_vt list + tk_vt sau tab Tài khoản."""
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

# loai_vt: mở không lọc — lấy mã trang 1
p.evaluate("""() => {
  document.querySelector('[id*="dirExtender_form_loai_vt"]').closest('td').querySelector('img.CellImgLookup').click();
}""")
time.sleep(2)
loai_rows = p.evaluate(f"""() => {{
  var t = document.getElementById('{DE}_FormLookuploai_vt_Button_Lookup_Table');
  return Array.from(t.querySelectorAll('tr')).map((tr,i) => ({{
    i:i,
    cells: Array.from(tr.querySelectorAll('td')).map(td => (td.innerText||'').trim().substring(0,40)),
    links: Array.from(tr.querySelectorAll('a')).map(a => (a.innerText||'').trim()).filter(Boolean)
  }}));
}}""")
print("=== loai_vt no filter ===")
print(json.dumps(loai_rows, ensure_ascii=False, indent=2))

# close
p.evaluate("""() => {
  var as = document.querySelectorAll('a');
  for (var a of as) if ((a.innerText||'').trim()==='Đóng') { a.click(); return; }
}""")
time.sleep(1)

# Tab Tài khoản + inspect tk_vt
tab = p.evaluate("""() => {
  var a = document.getElementById('__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel2');
  if (a) { a.click(); return { clicked: a.id }; }
  return { clicked: null };
}""")
time.sleep(2)
tk_info = p.evaluate("""() => {
  var inp = document.querySelector('[id*="dirExtender_form_tk_vt"]');
  return {
    input_id: inp ? inp.id : null,
    visible: inp ? inp.offsetParent !== null : false,
    has_lookup: inp ? !!(inp.closest('td')||inp.parentElement).querySelector('img.CellImgLookup') : false
  };
}""")
print("=== tab / tk_vt ===")
print(json.dumps({"tab": tab, "tk": tk_info}, ensure_ascii=False, indent=2))

if tk_info.get("input_id"):
    p.evaluate("""() => {
      var inp = document.querySelector('[id*="dirExtender_form_tk_vt"]');
      (inp.closest('td')||inp.parentElement).querySelector('img.CellImgLookup').click();
    }""")
    time.sleep(2)
    # không lọc — lấy vài mã
    tk_rows = p.evaluate(f"""() => {{
      var t = document.getElementById('{DE}_FormLookuptk_vt_Button_Lookup_Table');
      if (!t) return {{ error: 'no table' }};
      return Array.from(t.querySelectorAll('tr')).slice(0,12).map((tr,i) => ({{
        i:i,
        cells: Array.from(tr.querySelectorAll('td')).map(td => (td.innerText||'').trim().substring(0,40)),
        links: Array.from(tr.querySelectorAll('a')).map(a => (a.innerText||'').trim()).filter(Boolean)
      }}));
    }}""")
    print("=== tk_vt no filter ===")
    print(json.dumps(tk_rows, ensure_ascii=False, indent=2))

p.close()
