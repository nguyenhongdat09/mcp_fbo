"""Lookup dvt: QuickFind 'khối' → quickFind() → click dòng 1 grid → gán dvt."""
import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"
DE = "ctl00_FastBusiness_MainReport_dirExtender"
LOOKUP_BTN = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup"
LOOKUP_TABLE = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup_Table"
QUICK_FIND = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup_QuickFind"
SEARCH_TERM = "khối"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def get_dvt(p):
    return p.evaluate(f"""() => {{
      var f = $find('{DE}');
      return {{ getItemValue: f.getItemValue('dvt') }};
    }}""")


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    p.goto(URL, timeout=90000)
    time.sleep(8)
    p.evaluate(f"() => {{ $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }}); }}")
    time.sleep(3)

    log("0. dvt trước", get_dvt(p))

    # 1. Bấm lookup
    p.evaluate("""() => {
      document.querySelector('[id*="dirExtender_form_dvt"]')
        .closest('td').querySelector('img.CellImgLookup').click();
    }""")
    time.sleep(2)

    # 2. Gõ khối vào QuickFind (KHÔNG gán input dvt)
    p.evaluate(f"""(term) => {{
      var qf = document.getElementById('{QUICK_FIND}');
      qf.focus();
      qf.value = term;
      qf.dispatchEvent(new Event('input', {{ bubbles: true }}));
      qf.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }}""", SEARCH_TERM)

    # 3. Lọc: quickFind() như user chỉ
    filter_res = p.evaluate(f"""() => {{
      var ac = FastBusiness.AjaxControlExtender.AutoCompleteExtender.find('{LOOKUP_BTN}');
      ac.quickFind();
      return {{ ok: true }};
    }}""")
    log("1-3. lookup + QuickFind + quickFind()", filter_res)
    time.sleep(2.5)

    filtered = p.evaluate("""() => {
      var body = document.body.innerText || '';
      return {
        filter_msg: (body.match(/Các bản ghi đang được lọc[^\\n]*/)||[])[0],
        record_count: (body.match(/Xem [0-9\\-]+\\/[0-9]+ bản ghi/)||[])[0]
      };
    }""")
    log("4. sau lọc", filtered)
    log("5. dvt trước chọn (phải rỗng)", get_dvt(p))

    # 4. Click item đầu tiên trong grid lookup table
    pick = p.evaluate(f"""() => {{
      var skip = ['Đóng','Đvt','Diễn giải','Làm tươi','Chọn:','Trước','Tiếp'];
      var t = document.getElementById('{LOOKUP_TABLE}');
      if (!t) return {{ error: 'no lookup table' }};

      // ưu tiên link Khối sau lọc
      var links = t.querySelectorAll('a');
      for (var a of links) {{
        var txt = (a.innerText || '').trim();
        if (txt === 'Khối') {{
          a.click();
          return {{ picked: txt, method: 'link_Khối' }};
        }}
      }}

      // fallback: dòng data đầu tiên (2 cột, có link hợp lệ)
      var trs = t.querySelectorAll('tr');
      for (var tr of trs) {{
        var tds = tr.querySelectorAll('td');
        if (tds.length < 2) continue;
        var c1 = (tds[0].innerText || '').trim();
        var c2 = (tds[1].innerText || '').trim();
        if (!c1 || skip.indexOf(c1) >= 0) continue;
        if (c1.indexOf('Danh mục') >= 0 || c1.indexOf('Các bản ghi') >= 0 || c1.indexOf('Xem') >= 0) continue;
        var link = tds[0].querySelector('a') || tr.querySelector('a');
        if (link) {{
          link.click();
          return {{ picked: c1, desc: c2, method: 'first_data_row' }};
        }}
      }}
      return {{ error: 'no pickable row' }};
    }}""")
    log("6. click chọn dòng 1", pick)
    time.sleep(1.5)

    final = get_dvt(p)
    log("7. dvt sau gán", final)

    ok = pick.get("picked") == "Khối" and final.get("getItemValue") == "Khối"
    log("KẾT LUẬN", {
        "pass": ok,
        "flow": "CellImgLookup → QuickFind 'khối' → AutoCompleteExtender.quickFind() → click Khối → dvt",
        "picked": pick.get("picked"),
        "dvt": final.get("getItemValue"),
    })

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
