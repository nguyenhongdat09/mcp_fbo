"""E2E: focus gridCell → Sửa → Lưu → focus → Xóa hết ZTEST."""
import json
import sys
import time
from datetime import datetime

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"
FILTER = f"{MR}_FilterPanelTextma_vt"
SUFFIX = datetime.now().strftime("%H%M%S")
TEN_EDIT = f"VT EDIT {SUFFIX}"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def ev(p, js, arg=None):
    return p.evaluate(js, arg) if arg is not None else p.evaluate(js)


def filter_ma(p, code):
    filt = p.locator(f"#{FILTER}")
    filt.click()
    filt.fill(code)
    filt.press("Enter")
    time.sleep(4)


def read_grid(p, n=20):
    return ev(p, f"""(n) => {{
      var mr = $find('{MR}');
      if (!mr._rows || !mr._rows.length) return {{ row_count: 0, rows: [] }};
      var rows = [];
      for (var r = 1; r <= Math.min(mr._rows.length, n); r++) {{
        rows.push({{
          row: r,
          ma_vt: String(mr._getItemValue(r, 1)).trim(),
          ten_vt: String(mr._getItemValue(r, 2)).trim(),
          dvt: String(mr._getItemValue(r, 3)).trim()
        }});
      }}
      return {{ row_count: mr._rows.length, rows: rows }};
    }}""", n)


def focus_row(p, row_index):
    """Focus dòng grid: click cell ma_vt (gridCell_{row}.1) — row 1-based."""
    cell_id = f"{MR}_gridCell_{row_index}.1"
    # CSS escape for Playwright: gridCell_1.1 → id with dot
    p.locator(f'[id="{cell_id}"]').click(timeout=8000)
    time.sleep(0.4)
    return ev(p, f"""() => {{
      var mr = $find('{MR}');
      var selected = false;
      try {{ selected = !!mr._rowSelected(); }} catch (e) {{}}
      var ma = null;
      try {{ ma = mr._getItemValue({row_index}, 1); }} catch (e) {{}}
      return {{
        cell_id: '{cell_id}',
        row_selected: selected,
        active_row: mr._activeRow || null,
        ma_vt: ma
      }};
    }}""")


def fire_toolbar(p, command):
    """Click ToolbarButton hoặc executeCommand sau khi đã focus row."""
    btn_map = {"Edit": "Edit", "Delete": "Delete", "New": "New"}
    btn = btn_map.get(command, command)
    btn_id = f"{MR}_ToolbarButton_{btn}"
    try:
        p.locator(f"#{btn_id}").click(timeout=5000)
        return {"via": "toolbar_click", "id": btn_id}
    except Exception:
        ev(p, f"() => {{ $find('{MR}').executeCommand({{ commandName: '{command}', commandArgument: '0' }}); }}")
        return {"via": "executeCommand", "command": command}


def dismiss(p):
    for name in ["Nhận", "Có", "OK", "Yes", "Đồng ý"]:
        try:
            loc = p.get_by_role("button", name=name)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=2000)
                return {"clicked": name}
        except Exception:
            pass
    return ev(p, """() => {
      var btns = document.querySelectorAll('input[type="button"], button');
      for (var b of btns) {
        var t = (b.value || b.innerText || '').trim();
        if (t === 'Nhận' || t === 'Có' || t === 'OK') { b.click(); return { clicked: t }; }
      }
      return { clicked: null };
    }""")


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    p.goto(URL, timeout=90000)
    time.sleep(8)

    filter_ma(p, "ZTEST")
    grid0 = read_grid(p)
    log("1. ZTEST hiện có", grid0)
    rows = [r for r in grid0.get("rows", []) if r["ma_vt"].startswith("ZTEST")]
    if not rows:
        log("STOP", "Không có ZTEST")
        p.close()
        return

    target = rows[0]
    log("2. Target sửa", {"ma_vt": target["ma_vt"], "row": target["row"], "ten_edit": TEN_EDIT})

    # --- FOCUS rồi SỬA ---
    focus = focus_row(p, target["row"])
    log("3. Focus dòng", focus)
    if not focus.get("row_selected") and not focus.get("active_row"):
        # retry click cell
        focus = focus_row(p, target["row"])
        log("3b. Focus retry", focus)

    fire = fire_toolbar(p, "Edit")
    log("4. Fire Sửa", fire)
    time.sleep(3)

    form = ev(p, f"""() => {{
      var f = $find('{DE}');
      if (!f) return {{ error: 'dirExtender chưa mở — chưa focus đúng dòng?' }};
      return {{ ma_vt: f.getItemValue('ma_vt'), ten_vt: f.getItemValue('ten_vt') }};
    }}""")
    log("5. Form Sửa", form)
    if form.get("error"):
        p.close()
        return

    ev(p, f"""(ten) => {{ $find('{DE}').setItemValue('ten_vt', ten); }}""", TEN_EDIT)
    p.locator(f"#{DE}_updateDlgOk").click(force=True)
    time.sleep(4)
    dismiss(p)

    # Verify edit
    p.goto(URL, timeout=90000)
    time.sleep(8)
    filter_ma(p, target["ma_vt"])
    grid_edit = read_grid(p, 5)
    edited = any(r["ma_vt"] == target["ma_vt"] and r["ten_vt"] == TEN_EDIT for r in grid_edit.get("rows", []))
    log("6. Sau Sửa", {"edited": edited, "grid": grid_edit})

    # --- XÓA từng ZTEST: focus → Delete → confirm ---
    filter_ma(p, "ZTEST")
    to_delete = [r for r in read_grid(p).get("rows", []) if r["ma_vt"].startswith("ZTEST")]
    log("7. Danh sách xóa", [r["ma_vt"] for r in to_delete])

    deleted_ok = []
    failed = []
    for item in to_delete:
        code = item["ma_vt"]
        p.goto(URL, timeout=90000)
        time.sleep(6)
        filter_ma(p, code)
        g = read_grid(p, 5)
        if not g.get("rows"):
            failed.append({"ma_vt": code, "error": "not found"})
            continue
        row = g["rows"][0]["row"]
        foc = focus_row(p, row)
        log(f"8a. Focus {code}", foc)
        fire_toolbar(p, "Delete")
        time.sleep(1.5)
        conf = dismiss(p)
        time.sleep(1)
        dismiss(p)  # đôi khi 2 lớp confirm
        time.sleep(3)

        p.goto(URL, timeout=90000)
        time.sleep(6)
        filter_ma(p, code)
        after = read_grid(p, 5)
        gone = after.get("row_count", 0) == 0 or not any(r["ma_vt"] == code for r in after.get("rows", []))
        log(f"8b. Xóa {code}", {"confirm": conf, "gone": gone, "after": after})
        if gone:
            deleted_ok.append(code)
        else:
            failed.append({"ma_vt": code, "error": "still exists", "confirm": conf})

    p.goto(URL, timeout=90000)
    time.sleep(6)
    filter_ma(p, "ZTEST")
    final = read_grid(p)
    log("9. ZTEST còn lại", final)

    log("KẾT LUẬN", {
        "edit_pass": edited,
        "edit_ma_vt": target["ma_vt"],
        "ten_vt_after": TEN_EDIT if edited else None,
        "deleted": deleted_ok,
        "delete_failed": failed,
        "remaining": [r["ma_vt"] for r in final.get("rows", [])],
        "pass": edited and len(failed) == 0 and final.get("row_count", 0) == 0,
    })

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
