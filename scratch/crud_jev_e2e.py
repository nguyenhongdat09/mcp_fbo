import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from fastbusiness_mcp.mcp_app import get_config
from trace_profile.connection import resolve_profiler_connection, run_sql

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
TEST_MA = "ZZ_TEST_MCP"
conn = resolve_profiler_connection(FP, "app", cfg)
JEV_CALLS = []

def db_row():
    res = run_sql(conn["parsed"],
        f"SELECT ma_kh, RTRIM(ten_kh) ten_kh FROM dmkh WHERE ma_kh='{TEST_MA}'")
    return (res.get("result_sets") or [{}])[0].get("rows", [])

def bf(**kw):
    kw.setdefault("config", cfg)
    t = time.time()
    r = BS.browser_fbo(**kw)
    print(f"== {kw.get('action')} {kw.get('command_name','')}"
          f"{kw.get('field','')}{kw.get('smart_kind','')} "
          f"({time.time()-t:.1f}s) ok={r.get('success')} "
          f"err={str(r.get('error'))[:120]}")
    return r

def jev(kind, intent):
    """Gọi action smart — JeV phán trên state thật."""
    r = bf(action="smart", smart_kind=kind, intent=intent)
    d = (r.get("result") or {}).get("decision")
    JEV_CALLS.append((kind, d))
    print(f"    JEV[{kind}] intent='{intent}' → "
          f"{json.dumps(d, ensure_ascii=False)[:220]}")
    return d

run_sql(conn["parsed"], f"DELETE FROM dmkh WHERE ma_kh='{TEST_MA}'")
print("db truoc:", db_row())

r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
if not r["success"]:
    sys.exit("LOGIN FAIL: " + str(r.get("error")))

bf(action="menu", menu_text="Danh mục khách hàng")
time.sleep(2)
jev("classify_screen", "vừa mở danh mục khách hàng")

# --- THÊM ---
bf(action="command", command_name="New")
time.sleep(1.5)
jev("classify_dialog", "dialog vừa mở sau khi bấm New — là gì, có chặn không")
for f, v in (("ma_kh", TEST_MA), ("ten_kh", "KH TEST MCP TAO MOI"),
             ("dia_chi", "Dia chi test"), ("ma_so_thue", "9999999999")):
    bf(action="set_field", field=f, value=v)
bf(action="command", command_name="Save")
time.sleep(2)
jev("verify_outcome", f"đã lưu khách hàng {TEST_MA} thành công")
print("  DB sau Save:", db_row())
jev("route", "dialog còn mở sau save — xử lý gì tiếp")
bf(action="cancel")
time.sleep(1)

# --- tìm dòng TEST_MA qua client API ---
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
    bf(action="set_field", field="ten_kh", value="KH TEST MCP DA SUA")
    bf(action="command", command_name="Save")
    time.sleep(2)
    jev("verify_outcome", f"đã sửa ten_kh của {TEST_MA} thành 'DA SUA'")
    print("  DB sau Edit:", db_row())
    bf(action="cancel")
    time.sleep(1)

    # --- XÓA ---
    bf(action="select_row", row=row_idx)
    bf(action="command", command_name="Delete")
    time.sleep(1)
    jev("classify_dialog", "dialog vừa hiện sau Delete — hỏi gì")
    bf(action="confirm", answer="yes")
    time.sleep(2)
    jev("verify_outcome", f"đã xóa khách hàng {TEST_MA}")
    print("  DB sau Delete:", db_row())

bf(action="close")
print("\n=== JEV CALLS:", len(JEV_CALLS))
for k, d in JEV_CALLS:
    print(" ", k, "→", json.dumps(d, ensure_ascii=False)[:160])
print("DONE")
