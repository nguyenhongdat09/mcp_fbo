"""E2E lọc báo cáo đầy đủ: fill -> Nhận -> click Tìm (toolbar) -> verify."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39"
SEARCH_BTN = "#ctl00_FastBusiness_MainReport_ToolbarButton_Search"

VERIFY_JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  var body = document.body.innerText || '';
  var out = {
    mr_type: mr ? mr._type : null,
    filter_summary: (body.match(/Vật tư:[^\\n]+/) || [null])[0],
    row_count: mr && mr._rows ? mr._rows.length : 0,
    sample_rows: [],
    grid_table_trs: 0,
    empty_hints: []
  };
  var gt = document.getElementById('ctl00_FastBusiness_MainReport_gridTable');
  if (gt) out.grid_table_trs = gt.querySelectorAll('tr').length;

  if (mr && mr._rows) {
    for (var i = 0; i < Math.min(3, mr._rows.length); i++) {
      var r = mr._rows[i];
      var s = {};
      Object.keys(r).slice(0, 8).forEach(function(k) { s[k] = String(r[k]).substring(0, 50); });
      out.sample_rows.push(s);
    }
  }
  ['không có dữ liệu','không tìm thấy','no data','Không có bản ghi'].forEach(function(p) {
    if (body.toLowerCase().indexOf(p.toLowerCase()) >= 0) out.empty_hints.push(p);
  });
  return out;
}
"""

def test_case(p, label, tu, den, ma_vt):
    print(f"\n{'='*60}\nCASE: {label} (tu={tu}, den={den}, ma_vt={ma_vt})\n{'='*60}")
    p.goto(URL, timeout=90000)
    time.sleep(8)

    p.evaluate("""(args) => {
      var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
      function fill(name, val) {
        var el = document.querySelector('[id*="searchExtender_form_' + name + '"]');
        if (el) { el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); }
      }
      fill('tu_ngay', args.tu);
      fill('den_ngay', args.den);
      se.setItemValue('ma_vt', args.ma_vt);
    }""", {"tu": tu, "den": den, "ma_vt": ma_vt})

    p.locator("#ctl00_FastBusiness_MainReport_searchExtender_updateDlgOk").click()
    time.sleep(3)
    v_nhan = p.evaluate(VERIFY_JS)
    print("After Nhận:", json.dumps({k: v_nhan[k] for k in ['filter_summary','mr_type','row_count']}, ensure_ascii=False))

    # Click Tìm toolbar
    p.locator(SEARCH_BTN).click()
    print("Clicked ToolbarButton_Search")
    time.sleep(8)

    v = p.evaluate(VERIFY_JS)
    print("After Tìm:", json.dumps(v, ensure_ascii=False, indent=2))
    return v

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    results = []
    # Case 1: default dates + ma_vt 001
    results.append(("001/2025", test_case(p, "ma_vt=001, năm 2025", "01/01/2025", "31/12/2025", "001")))
    # Case 2: wider range 2024-2025
    results.append(("001/2024-2025", test_case(p, "ma_vt=001, 2024-2025", "01/01/2024", "31/12/2025", "001")))

    print("\n\n=== TỔNG KẾT ===")
    filter_ok = all(r[1].get('filter_summary') for r in results)
    has_data = any(r[1].get('row_count', 0) > 0 for r in results)
    has_empty = any(r[1].get('empty_hints') for r in results)

    print(f"Lọc (fill + Nhận): {'PASS' if filter_ok else 'FAIL'}")
    for name, v in results:
        print(f"  {name}: rows={v.get('row_count')}, grid_trs={v.get('grid_table_trs')}, empty={v.get('empty_hints')}")

    if filter_ok and has_data:
        print("\n=> PASS HOÀN TOÀN: Lọc được báo cáo + có dữ liệu")
    elif filter_ok:
        print("\n=> PASS LỌC: Điều kiện áp dụng OK, grid chạy (Tìm OK), DB có thể không có phiếu với ma_vt=001")
    else:
        print("\n=> FAIL")

    p.close()

if __name__ == "__main__":
    main()
