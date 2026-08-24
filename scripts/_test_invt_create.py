"""E2E thêm mới vật tư — lookup chuẩn (quickFind khi có từ khóa; không thì chọn dòng 1)."""
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
SUFFIX = datetime.now().strftime("%H%M%S")
MA_VT = f"ZTEST{SUFFIX}"
TEN_VT = f"VT test Chrome CDP {SUFFIX}"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def ev(p, js, arg=None):
    return p.evaluate(js, arg) if arg is not None else p.evaluate(js)


def dismiss_msg(p):
    return ev(p, """() => {
      var btns = document.querySelectorAll('input[type="button"], button');
      for (var b of btns) {
        if ((b.value || b.innerText || '').trim() === 'Nhận') { b.click(); return { ok: true }; }
      }
      return { ok: false };
    }""")


def click_tab_taikhoan(p):
    return ev(p, """() => {
      var a = document.getElementById('__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel2');
      if (a) { a.click(); return true; }
      return false;
    }""")


def lookup_select(p, field, search_term=None, prefer_code=None):
    """
    Mở CellImgLookup → (optional QuickFind + quickFind) → click dòng data.
    QuickFind lọc theo TÊN (Diễn giải), không phải mã — dùng search_term phù hợp tên.
    """
    open_res = ev(p, """(field) => {
      var inp = document.querySelector('[id*="dirExtender_form_' + field + '"]');
      if (!inp) return { ok: false, error: 'no input' };
      var img = (inp.closest('td') || inp.parentElement).querySelector('img.CellImgLookup');
      if (!img) return { ok: false, error: 'no lookup img' };
      img.click();
      return { ok: true, input_id: inp.id };
    }""", field)
    time.sleep(2)
    if not open_res.get("ok"):
        return {"open": open_res}

    lookup_btn = f"{DE}_FormLookup{field}_Button_Lookup"
    quick_find = f"{DE}_FormLookup{field}_Button_Lookup_QuickFind"
    lookup_table = f"{DE}_FormLookup{field}_Button_Lookup_Table"

    filter_res = None
    if search_term:
        filter_res = ev(p, """(args) => {
          var qf = document.getElementById(args.qf);
          if (!qf) return { error: 'no QuickFind' };
          qf.focus();
          qf.value = args.term;
          qf.dispatchEvent(new Event('input', { bubbles: true }));
          qf.dispatchEvent(new Event('change', { bubbles: true }));
          var ac = FastBusiness.AjaxControlExtender.AutoCompleteExtender.find(args.btn);
          ac.quickFind();
          return { ok: true, term: args.term };
        }""", {"qf": quick_find, "btn": lookup_btn, "term": search_term})
        time.sleep(2.5)

    pick = ev(p, """(args) => {
      var skip = {
        'Đóng':1,'Đvt':1,'Diễn giải':1,'Làm tươi':1,'Chọn:':1,'Trước':1,'Tiếp':1,
        'Mã loại':1,'Tên loại vật tư':1,'Tài khoản':1,'Tên tài khoản':1,'Mã':1,'Tên':1
      };
      var t = document.getElementById(args.table);
      if (!t) return { error: 'no table', id: args.table };
      var links = t.querySelectorAll('a');

      if (args.prefer) {
        for (var a of links) {
          var txt = (a.innerText || '').trim();
          if (txt === args.prefer) { a.click(); return { picked: txt, method: 'prefer' }; }
        }
      }

      var trs = t.querySelectorAll('tr');
      for (var tr of trs) {
        var tds = tr.querySelectorAll('td');
        if (tds.length < 2) continue;
        var c1 = (tds[0].innerText || '').trim();
        var c2 = (tds[1].innerText || '').trim();
        if (!c1 || skip[c1]) continue;
        if (/Danh mục|Các bản ghi|Xem |Chọn:|Trang|Không có bản ghi/.test(c1)) continue;
        var link = tds[0].querySelector('a') || tr.querySelector('a');
        if (!link) continue;
        var txt = (link.innerText || '').trim() || c1;
        if (skip[txt] || txt === 'Làm tươi') continue;
        link.click();
        return { picked: txt, desc: c2, method: 'first_data_row' };
      }
      return { error: 'no pickable row' };
    }""", {"table": lookup_table, "prefer": prefer_code})
    time.sleep(1.5)

    val = ev(p, f"() => $find('{DE}').getItemValue('{field}')")
    return {"open": open_res, "filter": filter_res, "pick": pick, "value": val}


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    log("0. Test data", {"ma_vt": MA_VT, "ten_vt": TEN_VT})
    p.goto(URL, timeout=90000)
    time.sleep(8)

    ev(p, f"() => {{ $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }}); }}")
    time.sleep(3)
    log("1. Mới", "OK")

    fill = ev(p, f"""(args) => {{
      var f = $find('{DE}');
      f.setItemValue('ma_vt', args.ma);
      f.setItemValue('ten_vt', args.ten);
      return {{ ma_vt: f.getItemValue('ma_vt'), ten_vt: f.getItemValue('ten_vt') }};
    }}""", {"ma": MA_VT, "ten": TEN_VT})
    log("2. Fill ma_vt / ten_vt", fill)

    # dvt: QuickFind theo tên "khối" → chọn Khối
    r_dvt = lookup_select(p, "dvt", search_term="khối", prefer_code="Khối")
    log("3. Lookup dvt", r_dvt)
    dismiss_msg(p)

    # loai_vt: không lọc (mã 08 không có trên DB này) → chọn dòng 1 (21 - Vật tư)
    r_loai = lookup_select(p, "loai_vt", search_term=None, prefer_code=None)
    log("4. Lookup loai_vt (dòng đầu)", r_loai)
    dismiss_msg(p)

    # tk_vt: tab Tài khoản → không lọc → chọn dòng 1 (account hợp lệ loai_tk=1)
    click_tab_taikhoan(p)
    time.sleep(1.5)
    r_tk = lookup_select(p, "tk_vt", search_term=None, prefer_code=None)
    log("5. Lookup tk_vt (dòng đầu tab Tài khoản)", r_tk)
    dismiss_msg(p)

    vals = ev(p, f"""() => {{
      var f = $find('{DE}');
      return {{
        ma_vt: f.getItemValue('ma_vt'),
        ten_vt: f.getItemValue('ten_vt'),
        dvt: f.getItemValue('dvt'),
        loai_vt: f.getItemValue('loai_vt'),
        tk_vt: f.getItemValue('tk_vt')
      }};
    }}""")
    log("6. Values trước Lưu", vals)

    missing = [k for k in ("ma_vt", "ten_vt", "dvt", "loai_vt", "tk_vt") if not vals.get(k)]
    if missing:
        log("STOP", {"missing": missing})
        p.close()
        return

    p.locator("#ctl00_FastBusiness_MainReport_dirExtender_updateDlgOk").click(force=True)
    time.sleep(5)
    dismiss_msg(p)
    time.sleep(3)

    after_save = ev(p, """() => {
      var btn = document.getElementById('ctl00_FastBusiness_MainReport_dirExtender_updateDlgOk');
      var open = !!(btn && btn.offsetParent !== null);
      var body = document.body.innerText || '';
      return {
        dialog_open: open,
        has_error: /chưa nhập|không hợp lệ|trùng|lỗi/i.test(body),
        err_line: (body.match(/Trường[^\\n]+|[^\\n]*không hợp lệ[^\\n]*|[^\\n]*trùng[^\\n]*/i)||[])[0] || null
      };
    }""")
    log("7. Sau Lưu", after_save)

    if after_save.get("dialog_open"):
        dismiss_msg(p)
        log("KẾT LUẬN", {"pass": False, "reason": "dialog còn mở / Lưu lỗi", "after_save": after_save})
        p.close()
        return

    # Sau Lưu: reload rồi lọc bằng Playwright fill + Enter (ổn định hơn synthetic KeyboardEvent)
    p.goto(URL, timeout=90000)
    time.sleep(8)
    filt = p.locator("#ctl00_FastBusiness_MainReport_FilterPanelTextma_vt")
    filt.click()
    filt.fill(MA_VT)
    filt.press("Enter")
    log("7b. Reload + Playwright fill/Enter FilterPanelTextma_vt", {"ma_vt": MA_VT})
    time.sleep(5)

    grid = ev(p, f"""() => {{
      var mr = $find('{MR}');
      if (!mr._rows || !mr._rows.length) return {{ row_count: 0, rows: [] }};
      var rows = [];
      for (var r = 1; r <= Math.min(mr._rows.length, 5); r++) {{
        rows.push({{
          ma_vt: mr._getItemValue(r, 1),
          ten_vt: mr._getItemValue(r, 2),
          dvt: mr._getItemValue(r, 3)
        }});
      }}
      return {{ row_count: mr._rows.length, rows: rows }};
    }}""")
    log("8. Grid sau lọc", grid)

    found = any(r.get("ma_vt", "").strip() == MA_VT for r in grid.get("rows", []))
    log("KẾT LUẬN", {
        "pass": found,
        "ma_vt": MA_VT,
        "ten_vt": TEN_VT,
        "created_found_in_grid": found,
        "values": vals,
    })

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
