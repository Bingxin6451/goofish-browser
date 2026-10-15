# -*- coding: utf-8 -*-
"""Hermes Agent 版模板：browser_exec 内使用的四件套代码。

把这些代码块复制进 browser_exec(session='xianyu') 的 code 参数即可。
实测于 2026-10，闲鱼网页版。
"""

# ═══ 1. 反检测注入（每次调用开头必跑；新 tab/导航后注入会丢）═══
REAL_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
cdp('Network.setUserAgentOverride', userAgent=REAL_UA, platform='macOS')
cdp('Page.addScriptToEvaluateOnNewDocument', source="""
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
try { Object.defineProperty(navigator, 'userAgent', {get: () => '%s'}); } catch(e) {}
""" % REAL_UA)

# ═══ 2. 登录态检查 + 免扫码注回恢复 ═══
import json, os, time
goto_url('https://www.goofish.com/')
wait_for_load(); time.sleep(4)
head = js('document.body.innerText.slice(0, 100)')
logged = '贝贝' in head  # 改成你的昵称判定词
print('登录态:', 'OK' if logged else '丢失')
if not logged:
    ck = json.load(open(os.path.expanduser('~/.xhs-xianyu-state/xianyu_browser_cookies.json')))
    ok = 0
    for name, c in ck.items():
        try:
            params = {'name': name, 'value': c['value'], 'domain': c.get('domain') or '.goofish.com', 'path': c.get('path') or '/'}
            if c.get('httpOnly'): params['httpOnly'] = True
            if c.get('secure'): params['secure'] = True
            if c.get('expires') and c['expires'] > 0: params['expires'] = c['expires']
            cdp('Network.setCookie', **params)
            ok += 1
        except Exception: pass
    goto_url('https://www.goofish.com/')
    wait_for_load(); time.sleep(4)
    print('注回', ok, '个 →', 'OK' if '贝贝' in js('document.body.innerText.slice(0,100)') else '仍丢（需重扫）')

# ═══ 3. 登录后保存 Cookie（值不进聊天）═══
all_cookies = {}
for domain in ['https://www.goofish.com', 'https://passport.goofish.com', 'https://login.taobao.com', 'https://www.taobao.com']:
    c = cdp('Network.getCookies', urls=[domain])
    for ck in c.get('cookies', []):
        all_cookies[ck['name']] = {'value': ck['value'], 'domain': ck.get('domain',''), 'path': ck.get('path','/'), 'httpOnly': ck.get('httpOnly'), 'secure': ck.get('secure'), 'expires': ck.get('expires')}
out = os.path.expanduser('~/.xhs-xianyu-state/xianyu_browser_cookies.json')
json.dump(all_cookies, open(out, 'w'), ensure_ascii=False, indent=1)
os.chmod(out, 0o600)
print('saved', len(all_cookies))

# ═══ 4. URL 直搜 + 卡片提取（连发版，1s 间隔连发 5+ 次实测零风控）═══
from urllib.parse import quote
OUT = os.path.expanduser('~/.xhs-xianyu-state/xy_batch_browser.jsonl')
def search(word):
    goto_url('https://www.goofish.com/search?q=' + quote(word) + '&spm=a21ybx.home.searchInput.0')
    wait_for_load(); time.sleep(3.5)
    body = js('document.body.innerText.slice(0, 800)')
    flag = ''.join(k for k in ('被挤爆','RGV587','非法访问','滑块') if k in body)
    items = js("""(()=>{const out=[];const seen=new Set();
    for(const a of document.querySelectorAll("a[href*='/item']")){
      const id=(a.href.match(/id=(\\d+)/)||[])[1];
      if(!id||seen.has(id))continue; seen.add(id);
      const t=(a.innerText||'').replace(/\\s+/g,' ').trim();
      if(t.length>15) out.push({id:id, txt:t.slice(0,90), href:a.href});
    } return out.slice(0,14);})()""")
    with open(OUT,'a') as f:
        for it in (items or []): f.write(json.dumps({'word':word,'flag':flag,**it},ensure_ascii=False)+'\n')
    print(f"[{word}] {'风控:'+flag if flag else 'OK'} {len(items or [])}条")
    return not flag
for w in ['词1','词2','词3']:
    if not search(w): break
