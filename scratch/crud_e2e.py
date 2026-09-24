import sys, time
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from fastbusiness_mcp.mcp_app import get_config
from trace_profile.connection import resolve_profiler_connection, run_sql

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
TEST_MA = "ZZ_TEST_MCP"
TEN1 = "KH TEST MCP TAO MOI"
TEN2 = "KH TEST MCP DA SUA"
conn = resolve_profiler_connection(FP, "app", cfg)

def db_row():
    res = run_sql(conn["parsed"],
        f"SELECT ma_kh, RTRIM(ten_kh) ten_kh FROM dmkh WHERE ma_kh='{TEST_MA}'")
    return (res.get("result_sets") or [{}])[0].get("rows", [])

def bf(**kw):
    kw.setdefault("config", cfg)
    t = time.time()
    r = BS.browser_fbo(**kw)
    print(f"== {kw.get('action')} {kw.get('command_name','')}"
          f"{kw.get('field','')} ({time.time()-t:.1f}s) "
          f"ok={r.get('success')} err={str(r.get('error'))[:120]}")
    return r

def dlgs(st):
    return [str(d.get("text"))[:80] for d in (st.get("dialogs") or []) if d.get("text")]

# dọn rác test cũ nếu còn sót
run_sql(conn["parsed"], f"DELETE FROM dmkh WHERE ma_kh='{TEST_MA}'")
print("db truoc:", db_row())

r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
if not r["success"]:
    sys.exit("LOGIN FAIL: " + str(r.get("error")))

bf(action="menu", menu_text="Danh mục khách hàng")
time.sleep(2)

# --- THÊM ---
bf(action="command", command_name="New")
time.sleep(1.5)
for f, v in (("ma_kh", TEST_MA), ("ten_kh", TEN1), ("dia_chi", "Dia chi test"),
             ("ma_so_thue", "9999999999")):
    bf(action="set_field", field=f, value=v)
bf(action="command", command_name="Save")
time.sleep(2)
st = bf(action="snapshot").get("state") or {}
print("  sau Save dialogs:", dlgs(st))
print("  DB sau Save:", db_row())

# form còn mở (save&stay) → cancel đóng
bf(action="cancel")
time.sleep(1)

# --- SỬA: tìm dòng theo ma_kh qua client API (không quét UI) ---
page_row = None
r = bf(action="evaluate", js="""() => {
    const g = $find('ctl00_FastBusiness_MainReport');
    if (!g || !g._getItemValue) return null;
    for (let i = 1; i <= (g._rowCount || 0); i++)
        if (String(g._getItemValue(i, 1) || '').trim() === '""" + TEST_MA + """')
            return i;
    return null; }""")
print("  find row:", r.get("result"))
# Retrieve trước để grid có dữ liệu mới
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
print("  TEST_MA ở dòng:", row_idx)

if row_idx:
    bf(action="select_row", row=row_idx)
    bf(action="command", command_name="Edit")
    time.sleep(1.5)
    bf(action="set_field", field="ten_kh", value=TEN2)
    bf(action="command", command_name="Save")
    time.sleep(2)
    st = bf(action="snapshot").get("state") or {}
    print("  sau Save edit dialogs:", dlgs(st))
    print("  DB sau Edit:", db_row())
    bf(action="cancel")
    time.sleep(1)

    # --- XÓA ---
    bf(action="select_row", row=row_idx)
    bf(action="command", command_name="Delete")
    time.sleep(1)
    st = bf(action="snapshot").get("state") or {}
    print("  dialog xóa:", dlgs(st))
    bf(action="confirm", answer="yes")
    time.sleep(2)
    st = bf(action="snapshot").get("state") or {}
    print("  sau Delete dialogs:", dlgs(st))
    print("  DB sau Delete:", db_row())

bf(action="close")
print("DONE")
