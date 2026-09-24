import sys, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"

def bf(**kw):
    kw.setdefault("config", cfg)
    r = BS.browser_fbo(**kw)
    print(f"== {kw.get('action')} ok={r.get('success')} err={str(r.get('error'))[:130]}")
    return r

# đóng browser trước → các action trên page chưa mở
bf(action="close")

# action sai
r = bf(action="hack_the_planet")

# page chưa mở → command trên trang trắng (browser mở blank)
r = bf(action="command", command_name="New")

# thiếu param
r = bf(action="menu")          # thiếu menu_text
r = bf(action="set_field")     # thiếu field
r = bf(action="select_row", row=99)

# login thiếu url + file_path sai → phải báo HỎI USER link
r = bf(action="login", file_path=r"D:\nonexistent\x.ent",
       user="X", password="Y")

# login không có creds config + không truyền user/pass
cfg2 = dict(cfg); cfg2["browser_fbo"] = {}
r = BS.browser_fbo(action="login", url="http://172.168.5.14/HAOHOA",
                   config=cfg2)
print("== login-no-creds ok=%s err=%s" % (r.get("success"), str(r.get("error"))[:150]))

bf(action="close")
print("DONE")
