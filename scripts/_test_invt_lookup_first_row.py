"""Test chọn dòng 1 lookup dvt qua FormLookup API."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

LK = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt"
DE = "ctl00_FastBusiness_MainReport_dirExtender"

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto("http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06", timeout=90000)
    time.sleep(8)
    p.evaluate("() => { $find('ctl00_FastBusiness_MainReport').executeCommand({ commandName: 'New', commandArgument: '0' }); }")
    time.sleep(3)
    p.evaluate("""() => {
      document.querySelector('[id*="dirExtender_form_dvt"]').closest('td').querySelector('img.CellImgLookup').click();
    }""")
    time.sleep(3)

    res = p.evaluate(f"""() => {{
      var lk = $find('{LK}');
      var log = {{}};
      // đọc rows sau render
      if (lk._rows) log.row_count = lk._rows.length;
      try {{ log.r1c1 = lk._getItemValue(1, 1); }} catch(e) {{ log.read_err = String(e); }}

      // thử mark + execute
      var tries = [];
      function tryFn(name, fn) {{
        try {{ fn(); tries.push({{ name: name, ok: true }}); }}
        catch(e) {{ tries.push({{ name: name, error: String(e).substring(0,120) }}); }}
      }}
      tryFn('set_firstRowSelected(true)', () => lk.set_firstRowSelected(true));
      tryFn('markSelectedRow(0)', () => lk.markSelectedRow(0));
      tryFn('markSelectedRow(1)', () => lk.markSelectedRow(1));
      tryFn('toggleSelectedRow(0)', () => lk.toggleSelectedRow(0));
      tryFn('executeSelectedRow()', () => lk.executeSelectedRow());

      log.tries = tries;
      log.dvt = $find('{DE}').getItemValue('dvt');
      return log;
    }}""")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    p.close()

if __name__ == "__main__":
    main()
