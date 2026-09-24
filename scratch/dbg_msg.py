import sys, time
sys.path.insert(0, r'E:\PythonProject\mcp_fbo')
from browser_fbo import service as BS, session as S
from fastbusiness_mcp.mcp_app import get_config
cfg = get_config()
FP = r'\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent'
BS.browser_fbo(action='login', file_path=FP, user='ADMIN', password='2222222222', config=cfg)
BS.browser_fbo(action='menu', menu_text='Danh mục khách hàng', config=cfg)
time.sleep(1.5)
BS.browser_fbo(action='command', command_name='New', config=cfg)
time.sleep(1.5)
BS.browser_fbo(action='command', command_name='Save', config=cfg)
time.sleep(2.5)
page = S.current_page()
# dump toàn bộ element có 'Message'/'Dialog' trong id đang visible + outerHTML
out = page.evaluate("""() => {
  const vis = el => !!(el.offsetWidth||el.offsetHeight||el.getClientRects().length);
  return [...document.querySelectorAll('[id*="Message"],[id*="Dialog"]')]
    .filter(vis)
    .map(el => ({id: el.id, cls: String(el.className||'').slice(0,50),
                 text: (el.innerText||'').trim().slice(0,120)}));
}""")
for e in out:
    print(e, flush=True)
# tìm element chứa text 'chưa nhập' → leo lên xem cấu trúc
html = page.evaluate("""() => {
  const all = [...document.querySelectorAll('div,td,span')];
  const hit = all.find(el => (el.innerText||'').includes('chưa nhập'));
  if (!hit) return 'not found';
  let cur = hit, chain = [];
  for (let i=0;i<5 && cur;i++){ chain.push(cur.tagName+'#'+cur.id+'.'+String(cur.className||'').slice(0,30)); cur=cur.parentElement; }
  return chain.join('  <  ');
}""")
print('CHAIN:', html, flush=True)
BS.browser_fbo(action='message', config=cfg)
BS.browser_fbo(action='cancel', config=cfg)
BS.browser_fbo(action='close', config=cfg)
