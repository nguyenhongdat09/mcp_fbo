import sys, time
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
print("t0 import done", flush=True)
from browser_fbo import service as BS, session as S
from fastbusiness_mcp.mcp_app import get_config
cfg = get_config()
FP = r'\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent'
print("t1 get_page...", flush=True)
t0=time.time()
try:
    page = S.get_page(headless=False, timeout_ms=60000)
    print(f"t2 page ok {time.time()-t0:.0f}s url={page.url}", flush=True)
except Exception as e:
    print(f"t2 page FAIL {type(e).__name__}: {e}", flush=True); sys.exit(1)
print("t3 login...", flush=True)
t0=time.time()
r = BS.browser_fbo(action='login', file_path=FP, user='ADMIN', password='2222222222', config=cfg)
print(f"t4 login: {r['success']} err={str(r.get('error'))[:200]} {time.time()-t0:.0f}s", flush=True)
st = r.get('state') or {}
print("state url:", st.get('url'), "| screen:", st.get('screen'), flush=True)
