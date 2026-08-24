"""E2E lọc báo cáo: lookup ma_vt từ danh mục (không gõ tay)."""
import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

REPORT_URL = "http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39"
SEARCH_BTN = "#ctl00_FastBusiness_MainReport_ToolbarButton_Search"
NHAN_BTN = "#ctl00_FastBusiness_MainReport_searchExtender_updateDlgOk"

DISCOVER_LOOKUP_JS = """
() => {
  var out = { ma_vt_input: null, lookup_buttons: [], lookup_dialog: null };
  // Input ma_vt trong filter
  var inp = document.querySelector('[id*="searchExtender_form_ma_vt"]');
  if (inp) out.ma_vt_input = { id: inp.id, value: inp.value, tag: inp.tagName };

  // Nút lookup gần ma_vt — thường là img/a/input button cạnh field
  var container = inp ? inp.closest('td') || inp.parentElement : null;
  if (container) {
    container.querySelectorAll('img, a, input[type="button"], span, div').forEach(function(el) {
      var hint = (el.id || '') + ' ' + (el.className || '') + ' ' + (el.title || '') + ' ' + (el.alt || '');
      if (/lookup|btn|search|find|list|select|choose/i.test(hint) || el.tagName === 'IMG') {
        out.lookup_buttons.push({
          id: el.id, tag: el.tagName, className: (el.className || '').substring(0, 80),
          title: el.title || el.alt || '', visible: el.offsetParent !== null
        });
      }
    });
  }

  // Tìm tất cả img clickable cạnh ma_vt (pattern FBO: ..._ma_vt... hoặc ..._l...)
  document.querySelectorAll('[id*="searchExtender"][id*="ma_vt"], [id*="searchExtender"] img, [id*="searchExtender"] a').forEach(function(el) {
    out.lookup_buttons.push({ id: el.id, tag: el.tagName, parent: el.parentElement ? el.parentElement.id : '' });
  });

  return out;
}
"""

SELECT_LOOKUP_CODE_JS = """
(code) => {
  // Popup lookup thường là FlowGrid hoặc iframe/dialog
  var dialogs = document.querySelectorAll('[id*="Lookup"], [id*="lookup"], [id*="Dir"], .modal, .popup, div[id*="Extender"]');
  var log = { clicked: false, method: null, dialog_titles: [] };

  // Tìm link/text chứa mã vật tư trong toàn trang (popup overlay)
  var links = document.querySelectorAll('a, span.GridLink, td a, tr a, .Link');
  for (var el of links) {
    var t = (el.innerText || el.textContent || '').trim();
    if (t === code) {
      el.click();
      log.clicked = true;
      log.method = 'link_text';
      log.element_id = el.id;
      return log;
    }
  }

  // Fallback: tìm trong table row
  var rows = document.querySelectorAll('tr');
  for (var tr of rows) {
    var tds = tr.querySelectorAll('td');
    if (tds.length >= 1 && (tds[0].innerText || '').trim() === code) {
      var clickTarget = tds[0].querySelector('a') || tds[0];
      clickTarget.click();
      log.clicked = true;
      log.method = 'first_cell';
      return log;
    }
  }

  return log;
}
"""


def main():
    cfg = load_chrome_debug_config()
    session = ChromeSession.get_instance()
    session.disconnect()
    page = session.connect(cfg["cdp_url"]).contexts[0].new_page()

    print("=== 1. Mở báo cáo ===")
    page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(8)

    # Mở filter nếu chưa mở (click toolbar filter hoặc search extender)
    print("\n=== 2. Khám phá lookup ma_vt ===")
    discover = page.evaluate(DISCOVER_LOOKUP_JS)
    print(json.dumps(discover, ensure_ascii=False, indent=2))

    ma_vt_input_id = discover.get("ma_vt_input", {}).get("id")
    if not ma_vt_input_id:
        print("FAIL: không tìm thấy input ma_vt")
        page.close()
        return

    # Tìm nút lookup — pattern FBO: thường id kết thúc _l hoặc _btn hoặc img cạnh input
    lookup_clicked = False
    lookup_selectors = [
        f'[id*="searchExtender_form_ma_vt"][id*="_l"]',
        f'[id*="searchExtender"][id*="ma_vt"][id*="Lookup"]',
        f'[id*="searchExtender"][id*="ma_vt"] img',
        f'[id*="searchExtender_form_ma_vt"] ~ img',
        f'[id*="searchExtender_form_ma_vt"] + *',
        '#ctl00_FastBusiness_MainReport_searchExtender_form_ma_vt_l',
        'img[id*="ma_vt"]',
    ]

    for sel in lookup_selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=5000)
                lookup_clicked = True
                print(f"Clicked lookup via: {sel}")
                break
        except Exception:
            pass

    if not lookup_clicked:
        # JS: tìm img/a cạnh input ma_vt
        js_res = page.evaluate(
            """(inputId) => {
          var inp = document.getElementById(inputId);
          if (!inp) return { ok: false, error: 'no input' };
          var row = inp.closest('tr') || inp.parentElement;
          var candidates = row ? row.querySelectorAll('img, a, input[type="image"], span') : [];
          for (var el of candidates) {
            if (el === inp) continue;
            if (el.tagName === 'IMG' || (el.id && el.id.indexOf('_l') >= 0)) {
              el.click();
              return { ok: true, id: el.id, tag: el.tagName };
            }
          }
          // sibling trong cùng td
          var td = inp.closest('td');
          if (td) {
            var imgs = td.querySelectorAll('img, a');
            for (var img of imgs) {
              img.click();
              return { ok: true, id: img.id, tag: img.tagName, via: 'td_img' };
            }
          }
          return { ok: false, error: 'no lookup btn found', row_html: row ? row.innerHTML.substring(0, 300) : '' };
        }""",
            ma_vt_input_id,
        )
        print("JS lookup click:", json.dumps(js_res, ensure_ascii=False))
        lookup_clicked = js_res.get("ok", False)

    time.sleep(3)

    # Kiểm tra popup lookup đã mở
    popup_info = page.evaluate(
        """() => {
      var body = document.body.innerText || '';
      var has_title = body.indexOf('Danh mục hàng hóa') >= 0 || body.indexOf('Mã vật tư') >= 0;
      var codes = [];
      document.querySelectorAll('a, td').forEach(function(el) {
        var t = (el.innerText || '').trim();
        if (/^\\d{3,}[A-Za-z0-9\\-]*$/.test(t) && t.length <= 20) codes.push(t);
      });
      return { has_lookup_title: has_title, sample_codes: [...new Set(codes)].slice(0, 10) };
    }"""
    )
    print("\n=== 3. Popup lookup ===")
    print(json.dumps(popup_info, ensure_ascii=False, indent=2))

    # Chọn mã thật — ưu tiên 00131 như user gạch chân
    target_code = "00131"
    if target_code not in popup_info.get("sample_codes", []):
        # lấy mã đầu tiên hợp lệ
        codes = popup_info.get("sample_codes", [])
        target_code = codes[0] if codes else "00131"

    print(f"\n=== 4. Chọn mã: {target_code} ===")
    select_res = page.evaluate(SELECT_LOOKUP_CODE_JS, target_code)
    print(json.dumps(select_res, ensure_ascii=False))

    if not select_res.get("clicked"):
        # Playwright fallback
        try:
            page.get_by_role("link", name=target_code, exact=True).click(timeout=8000)
            select_res = {"clicked": True, "method": "playwright_role_link"}
            print("Clicked via Playwright link role")
        except Exception as ex:
            print("Playwright link click failed:", ex)

    time.sleep(2)

    # Verify ma_vt đã fill
    ma_vt_after = page.evaluate(
        """() => {
      var el = document.querySelector('[id*="searchExtender_form_ma_vt"]');
      return el ? el.value : null;
    }"""
    )
    print(f"ma_vt sau lookup: {ma_vt_after!r}")

    print("\n=== 5. Click Nhận ===")
    page.locator(NHAN_BTN).click()
    time.sleep(3)

    filter_summary = page.evaluate(
        """() => {
      var m = (document.body.innerText || '').match(/Vật tư:[^\\n]+/);
      return m ? m[0].trim() : null;
    }"""
    )
    print(f"Filter summary: {filter_summary}")

    print("\n=== 6. Click Tìm ===")
    page.locator(SEARCH_BTN).click()
    time.sleep(6)

    final = page.evaluate(
        """() => {
      var mr = $find('ctl00_FastBusiness_MainReport');
      var body = document.body.innerText || '';
      return {
        mr_type: mr ? mr._type : null,
        filter_summary: (body.match(/Vật tư:[^\\n]+/) || [null])[0],
        ma_vt_in_filter: (body.match(/Vật tư:\\s*([^,]+)/) || [])[1],
        row_count: mr && mr._rows ? mr._rows.length : 0,
      };
    }"""
    )
    print("\n=== KẾT QUẢ ===")
    print(json.dumps(final, ensure_ascii=False, indent=2))

    ok_lookup = ma_vt_after and ma_vt_after != "001" and ma_vt_after == target_code
    ok_filter = final.get("filter_summary") and target_code in (final.get("filter_summary") or "")

    if ok_lookup and ok_filter:
        print(f"\n=> PASS: Đã chọn mã {target_code} qua lookup và lọc OK")
    elif ok_lookup:
        print(f"\n=> PASS (partial): Lookup chọn {target_code} OK, filter text cần kiểm tra thêm")
    else:
        print("\n=> FAIL: Chưa chọn được mã qua lookup")

    page.close()
    session.disconnect()


if __name__ == "__main__":
    main()
