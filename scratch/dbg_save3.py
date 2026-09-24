import sys, time, json
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import service as BS, session as S
from fastbusiness_mcp.mcp_app import get_config
from trace_profile import profiler as TP_fn
class TP:
    profiler = staticmethod(TP_fn)
cfg = get_config()
FP = r'\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent'

# start profiler trước
tr = TP.profiler(action="start", file_path=FP, db_type="app", config=cfg)
tid = (tr or {}).get("trace_id")
print("trace:", tid, tr.get("error"), flush=True)

BS.browser_fbo(action='login', file_path=FP, user='ADMIN', password='2222222222', config=cfg)
BS.browser_fbo(action='menu', menu_text='Danh mục khách hàng', config=cfg)
time.sleep(1.5)
BS.browser_fbo(action='command', command_name='New', config=cfg)
time.sleep(1.5)
BS.browser_fbo(action='set_field', field='ma_kh', value='ZZ_TEST_MCP', config=cfg)
BS.browser_fbo(action='set_field', field='ten_kh', value='KH TEST MCP', config=cfg)
BS.browser_fbo(action='set_field', field='dia_chi', value='Dia chi test', config=cfg)
BS.browser_fbo(action='command', command_name='Save', config=cfg)
time.sleep(4)
page = S.current_page()
st = BS.browser_fbo(action='snapshot', config=cfg).get('state') or {}
print("ALL DIALOGS:", json.dumps([d.get('text','')[:150] for d in (st.get('dialogs') or [])], ensure_ascii=False), flush=True)
print("screen:", st.get('screen'), "fields:", len(st.get('form_fields') or []), flush=True)

# đọc trace — SQL nào chạy trong lúc save
rr = TP.profiler(action="read", file_path=FP, trace_id=tid, wait_seconds=8, config=cfg)
rows = rr.get("rows") or []
print(f"trace rows: {len(rows)}", flush=True)
for r_ in rows[-25:]:
    txt = (r_.get("TextData") or r_.get("textdata") or "")[:180]
    ev = r_.get("EventClass") or r_.get("eventclass")
    print(f"  [{ev}] {txt}", flush=True)
TP.profiler(action="stop", file_path=FP, trace_id=tid, config=cfg)
BS.browser_fbo(action='close', config=cfg)
