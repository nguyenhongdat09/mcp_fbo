import sys, time, json, re
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from fastbusiness_mcp.mcp_app import get_config
from query_database.service import query_database

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
TEST_MA = "ZZTESTMCP"  # FBO cấm _ và ký tự đặc biệt trong ma_kh

def db_row():
    """Verify DB bằng creds app từ Web.config (query_database) — login
    'profile' của profiler chỉ trace được, KHÔNG có quyền vào app DB."""
    res = query_database(FP,
        f"SELECT ma_kh, RTRIM(ten_kh) ten_kh FROM dmkh WHERE ma_kh='{TEST_MA}'",
        db_type="app", config=cfg)
    sets = res.get("result_sets") or res.get("results") or []
    if sets and isinstance(sets, list) and "rows" in sets[0]:
        return sets[0]["rows"]
    if res.get("success") is False:
        print("   DB ERR:", str(res.get("error"))[:150])
        return "?"
    return []

def db_exec(sql):
    res = query_database(FP, sql, db_type="app", config=cfg)
    print("   exec:", str(res.get("error") or res.get("success"))[:120])

def bf(**kw):
    kw.setdefault("config", cfg)
    t = time.time()
    r = BS.browser_fbo(**kw)
    print(f"== {kw.get('action')} {kw.get('command_name','')}"
          f"{kw.get('field','')} ({time.time()-t:.1f}s) "
          f"ok={r.get('success')} err={str(r.get('error'))[:120]}")
    return r

def dlg_texts():
    st = bf(action="snapshot").get("state") or {}
    return [str(d.get("text",""))[:150] for d in (st.get("dialogs") or [])]

def save_with_retry(fills: dict, max_try=4):
    """Save → nếu DialogMessage báo 'Trường X chưa nhập' → map field → fill → Save lại.
    Đây là vòng lặp đúng của agent: đọc state → thấy lỗi → sửa → thử lại."""
    # map text lỗi → field name
    FIELD_VI = {"địa chỉ": "dia_chi", "tên khách": "ten_kh", "tên": "ten_kh",
                "mã khách": "ma_kh", "mã": "ma_kh", "mã số thuế": "ma_so_thue",
                "tài khoản": "tk", "điện thoại": "dien_thoai"}
    FILL_DEFAULT = {"dia_chi": "Dia chi test", "ten_kh": "KH TEST MCP",
                    "ma_kh": TEST_MA, "ma_so_thue": "0100100100",
                    "tk": "131", "dien_thoai": "0900000000"}
    for i in range(max_try):
        bf(action="command", command_name="Save")
        # chờ dialog — server trả async, poll tới 12s. MỌI DialogMessage sau
        # Save đều là message cần xử lý (validation 'chưa nhập', 'không hợp
        # lệ', 'không được phép', 'tồn tại', 'trùng'...) — không lọc keyword
        # cứng, message nào cũng đọc rồi quyết. (dmkh lưu save&stay — form
        # KHÔNG đóng khi thành công)
        texts = []
        for _ in range(24):
            time.sleep(0.5)
            texts = dlg_texts()
            # bỏ dialog là chính form 'Thêm/Sửa thông tin' (title updateDlg)
            real = [t for t in texts if "Fast Business Online" in t]
            if real:
                texts = real
                break
        err = [t for t in texts
               if any(w in t for w in ("chưa nhập", "không hợp lệ",
                      "đã tồn tại", "trùng", "không được", "lỗi", "Lỗi"))]
        if not err:
            print(f"  Save lần {i+1}: không thấy validation error")
            return True
        print(f"  Save lần {i+1} VALIDATION: {err[0]}")
        bf(action="message")  # dismiss Nhận
        # tìm field bị thiếu từ text lỗi
        fixed = False
        low = err[0].lower()
        for vi, fn in FIELD_VI.items():
            if vi in low:
                val = fills.get(fn) or FILL_DEFAULT.get(fn)
                if val:
                    print(f"    → fill {fn}={val}")
                    bf(action="set_field", field=fn, value=val)
                    fixed = True
                    break
        if not fixed:
            print("    → không map được field từ lỗi — bỏ")
            return False
    return False

# ============================================================
db_exec(f"DELETE FROM dmkh WHERE ma_kh='{TEST_MA}'")
print("db truoc:", db_row())

r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
print("login:", r["success"], "|", str(r.get("error"))[:100])
if not r["success"]:
    # session cũ có thể còn sống — thử mở thẳng menu
    r2 = bf(action="menu", menu_text="Danh mục khách hàng")
    if not r2["success"]:
        sys.exit("LOGIN FAIL")
else:
    bf(action="menu", menu_text="Danh mục khách hàng")
time.sleep(2)

# --- THÊM ---
bf(action="command", command_name="New")
time.sleep(1.5)
bf(action="set_field", field="ma_kh", value=TEST_MA)
bf(action="set_field", field="ten_kh", value="KH TEST MCP TAO MOI")
ok = save_with_retry({"ma_kh": TEST_MA, "ten_kh": "KH TEST MCP TAO MOI"})
print("  >>> SAVE ADD:", ok, "| DB:", db_row())
bf(action="cancel")  # đóng form (save&stay)
time.sleep(1)

# tìm dòng trong grid qua client API
bf(action="command", command_name="Retrieve")
time.sleep(2)
r = bf(action="evaluate", js="""() => {
    const g = $find('ctl00_FastBusiness_MainReport');
    if (!g || !g._getItemValue) return null;
    for (let i = 1; i <= (g._rowCount || 0); i++)
        if (String(g._getItemValue(i, 1) || '').trim() === '""" + TEST_MA + """')
            return i;
    return null; }""")
row_idx = (r.get("result") or {}).get("result")
print("  TEST_MA dong:", row_idx)

if row_idx:
    # --- SỬA ---
    bf(action="select_row", row=row_idx)
    bf(action="command", command_name="Edit")
    time.sleep(1.5)
    # Edit có thể bắn info dialog (vd 'mã số thuế chưa cập nhật') che form —
    # dismiss trước khi fill, đúng vòng lặp agent: observe → xử lý → act.
    for _ in range(6):
        texts = dlg_texts()
        info = [t for t in texts if "Nhận" in t and "Có" not in t]
        if not info:
            break
        print("  info dialog:", info[0][:80])
        bf(action="message")
        time.sleep(0.5)
    bf(action="set_field", field="ten_kh", value="KH TEST MCP DA SUA")
    ok = save_with_retry({"ten_kh": "KH TEST MCP DA SUA"})
    print("  >>> SAVE EDIT:", ok, "| DB:", db_row())
    bf(action="cancel")
    time.sleep(1)

    # --- XÓA ---
    bf(action="select_row", row=row_idx)
    bf(action="command", command_name="Delete")
    time.sleep(1)
    print("  dialog xóa:", dlg_texts())
    bf(action="confirm", answer="yes")
    time.sleep(2)
    print("  sau Delete:", dlg_texts())
    bf(action="message")  # dismiss "đã xóa" nếu có
    print("  DB sau Delete:", db_row())

bf(action="close")
print("DONE")
