"""Test lookup dvt qua FormLookupdvt — chọn dòng 1 hoặc QuickFind."""
import json
import sys
import time
from datetime import datetime

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"
DE = "ctl00_FastBusiness_MainReport_dirExtender"
LOOKUP = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt"
QUICK_FIND = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup_QuickFind"
SUFFIX = datetime.now().strftime("%H%M%S")
MA_VT = f"ZTEST{SUFFIX}"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    p.goto(URL, timeout=90000)
    time.sleep(8)

    # Mới
    p.evaluate(f"() => {{ $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }}); }}")
    time.sleep(3)

    p.evaluate(f"""() => {{
      $find('{DE}').setItemValue('ma_vt', '{MA_VT}');
      $find('{DE}').setItemValue('ten_vt', 'VT test lookup dvt {SUFFIX}');
    }}""")

    # --- TEST A: mở lookup dvt, inspect FormLookup component ---
    p.evaluate("""() => {
      var inp = document.querySelector('[id*="dirExtender_form_dvt"]');
      inp.closest('td').querySelector('img.CellImgLookup').click();
    }""")
    time.sleep(2)

    inspect = p.evaluate(f"""() => {{
      var lk = $find('{LOOKUP}');
      if (!lk) return {{ error: 'no FormLookupdvt' }};
      var out = {{
        id: lk.get_id ? lk.get_id() : '{LOOKUP}',
        _type: lk._type,
        has_rows: !!lk._rows,
        row_count: lk._rows ? lk._rows.length : 0,
        field_count: lk._fields ? lk._fields.length : 0,
        columns: lk._fields ? lk._fields.slice(0, 4).map(f => f.Name || f.HeaderText) : [],
        methods: []
      }};
      for (var k in lk) {{
        if (typeof lk[k] === 'function' && /row|select|pick|find|search|get/i.test(k)) {{
          out.methods.push(k);
        }}
      }}
      // DOM first row
      var firstLink = null;
      document.querySelectorAll('[id*="FormLookupdvt"] a, [id*="FormLookupdvt"] td').forEach(function(el) {{
        var t = (el.innerText||'').trim();
        if (!firstLink && t && t.length <= 20 && /^[A-Za-zÀ-ỹ0-9]/.test(t) && t !== 'Đóng' && t.indexOf('Trang') < 0) {{
          firstLink = t;
        }}
      }});
      out.first_link_text = firstLink;
      return out;
    }}""")
    log("A. Inspect FormLookupdvt", inspect)

    # --- TEST B: chọn dòng đầu tiên qua _getItemValue / click link ---
    pick_first = p.evaluate(f"""() => {{
      var lk = $find('{LOOKUP}');
      var log = {{ steps: [] }};

      // Cách 1: đọc dòng 1 col 1 qua _getItemValue nếu có
      if (lk && typeof lk._getItemValue === 'function' && lk._rows && lk._rows.length) {{
        try {{
          log.first_code = lk._getItemValue(1, 1);
          log.steps.push('read row1 via _getItemValue');
        }} catch(e) {{ log.get_err = String(e); }}
      }}

      // Cách 2: click link dòng đầu trong popup
      var scope = document.querySelector('[id*="FormLookupdvt"]');
      var picked = null;
      var tables = document.querySelectorAll('[id*="FormLookupdvt"] table tr, table[id*="FormLookupdvt"] tr');
      for (var tr of tables) {{
        var a = tr.querySelector('td a') || tr.querySelector('a');
        if (a) {{
          var t = (a.innerText||'').trim();
          if (t && t.length <= 20) {{ picked = t; a.click(); log.steps.push('click first link: ' + t); break; }}
        }}
      }}
      log.picked = picked;
      return log;
    }}""")
    log("B. Chọn dòng đầu", pick_first)
    time.sleep(2)

    dvt_after_first = p.evaluate(f"() => $find('{DE}').getItemValue('dvt')")
    log("B. dvt sau chọn dòng 1", dvt_after_first)

    # Nếu chưa có — mở lại và thử QuickFind
    if not dvt_after_first:
        p.evaluate("""() => {
          var inp = document.querySelector('[id*="dirExtender_form_dvt"]');
          inp.closest('td').querySelector('img.CellImgLookup').click();
        }""")
        time.sleep(2)

        quickfind = p.evaluate(f"""(code) => {{
          var qf = document.getElementById('{QUICK_FIND}');
          if (!qf) return {{ error: 'no QuickFind input' }};
          qf.focus();
          qf.value = code;
          qf.dispatchEvent(new Event('change', {{ bubbles: true }}));
          qf.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }}));
          qf.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', keyCode: 13, bubbles: true }}));
          return {{ typed: code, id: qf.id }};
        }}""", "Cái")
        log("C. QuickFind 'Cái'", quickfind)
        time.sleep(2)

        pick_search = p.evaluate("""(code) => {
          var links = document.querySelectorAll('[id*="FormLookupdvt"] a');
          for (var a of links) {
            if ((a.innerText||'').trim() === code) { a.click(); return { picked: code }; }
          }
          return { picked: null };
        }""", "Cái")
        log("C. Click kết quả QuickFind", pick_search)
        time.sleep(2)

        dvt_after_qf = p.evaluate(f"() => $find('{DE}').getItemValue('dvt')")
        log("C. dvt sau QuickFind", dvt_after_qf)
    else:
        dvt_after_qf = dvt_after_first

    # --- TEST D: verify FormLookup API read rows ---
    read_lookup_grid = p.evaluate(f"""() => {{
      var lk = $find('{LOOKUP}');
      if (!lk || !lk._rows || !lk._rows.length) return {{ open: false }};
      var rows = [];
      for (var r = 1; r <= Math.min(3, lk._rows.length); r++) {{
        var row = {{}};
        for (var c = 0; c < Math.min(3, lk._fields.length); c++) {{
          row[lk._fields[c].Name] = lk._getItemValue(r, c + 1);
        }}
        rows.push(row);
      }}
      return {{ open: true, row_count: lk._rows.length, rows: rows }};
    }}""")
    log("D. Đọc grid lookup (nếu còn mở)", read_lookup_grid)

    ok = bool(dvt_after_qf or dvt_after_first)
    log("KẾT LUẬN", {
        "pass": ok,
        "dvt_assigned": dvt_after_qf or dvt_after_first,
        "FormLookup_id": LOOKUP,
        "QuickFind_id": QUICK_FIND,
    })

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
