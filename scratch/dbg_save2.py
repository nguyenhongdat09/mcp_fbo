import sys, time, json
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import service as BS, session as S
from fastbusiness_mcp.mcp_app import get_config
cfg = get_config()
FP = r'\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent'
r = BS.browser_fbo(action='login', file_path=FP, user='ADMIN', password='2222222222', config=cfg)
print('login:', r['success'], flush=True)
r = BS.browser_fbo(action='menu', menu_text='Danh mục khách hàng', config=cfg)
time.sleep(2)
r = BS.browser_fbo(action='command', command_name='New', config=cfg)
time.sleep(2)
BS.browser_fbo(action='set_field', field='ma_kh', value='ZZ_TEST_MCP', config=cfg)
BS.browser_fbo(action='set_field', field='ten_kh', value='KH TEST MCP', config=cfg)
r = BS.browser_fbo(action='command', command_name='Save', config=cfg)
print('SAVE RESULT:', json.dumps(r.get('result'), ensure_ascii=False), flush=True)
for i in range(10):
    time.sleep(1)
    st = BS.browser_fbo(action='snapshot', config=cfg).get('state') or {}
    dl = [d.get('text','')[:100] for d in (st.get('dialogs') or [])]
    print(f'{i+1}s dialogs={dl}', flush=True)
    if dl: break
BS.browser_fbo(action='close', config=cfg)
