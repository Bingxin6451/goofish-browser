#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""goofish-browser 通用版：CDP 直连无头 Chrome 驱动闲鱼网页版搜索。

依赖: pip install websocket-client requests
用法:
  python3 goofish_browser.py search "关键词" [--max N] [--port 9222]
  python3 goofish_browser.py login [--port 9222]        # 扫码登录,二维码存 qr.png
  python3 goofish_browser.py save-cookies                # 登录后导出 Cookie
  python3 goofish_browser.py restore-cookies             # 登录态丢失后注回

仅学习研究用途。Cookie 落盘 ~/.xy-browser/cookies.json (600)，值不进 stdout。
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from urllib.parse import quote

try:
    import websocket  # websocket-client
except ImportError:
    sys.exit("请先安装: pip install websocket-client requests")

REAL_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")
INJECT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
try { Object.defineProperty(navigator, 'userAgent', {get: () => '%s'}); } catch(e) {}
""" % REAL_UA
STATE_DIR = os.path.expanduser("~/.xy-browser")
COOKIE_FILE = os.path.join(STATE_DIR, "cookies.json")
COOKIE_DOMAINS = ["https://www.goofish.com", "https://passport.goofish.com",
                  "https://login.taobao.com", "https://www.taobao.com"]


class CDP:
    """最小 CDP 客户端（浏览器级 + 页面级命令）。"""

    def __init__(self, port=9222):
        self.port = port
        self.ws = None
        self.msg_id = 0
        self._connect_browser()
        self._attach_page()

    def _connect_browser(self):
        info = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/json/version", timeout=5).read())
        self.browser_ws = websocket.create_connection(
            info["webSocketDebuggerUrl"], timeout=10)

    def _attach_page(self):
        tabs = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/json", timeout=5).read())
        page = next((t for t in tabs if t["type"] == "page"), tabs[0])
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)

    def send(self, method, **params):
        self.msg_id += 1
        self.ws.send(json.dumps({"id": self.msg_id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.msg_id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def browser(self, method, **params):
        self.msg_id += 1
        self.browser_ws.send(json.dumps({"id": self.msg_id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.browser_ws.recv())
            if msg.get("id") == self.msg_id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True)
        return r.get("result", {}).get("value")

    def navigate(self, url):
        self.send("Page.navigate", url=url)
        time.sleep(3.5)
        self._inject()

    def _inject(self):
        self.send("Network.setUserAgentOverride", userAgent=REAL_UA, platform="macOS")
        self.send("Page.addScriptToEvaluateOnNewDocument", source=INJECT)


def go(url, cdp):
    cdp.navigate(url)
    time.sleep(2.5)


def cmd_search(args):
    cdp = CDP(args.port)
    go("https://www.goofish.com/", cdp)
    url = "https://www.goofish.com/search?q=" + quote(args.keyword) + "&spm=a21ybx.home.searchInput.0"
    cdp.navigate(url)
    body = cdp.js("document.body.innerText.slice(0,800)") or ""
    flag = [k for k in ("被挤爆", "RGV587", "非法访问", "滑块") if k in body]
    items = cdp.js("""(()=>{const out=[];const seen=new Set();
      for(const a of document.querySelectorAll("a[href*='/item']")){
        const id=(a.href.match(/id=(\\d+)/)||[])[1];
        if(!id||seen.has(id))continue; seen.add(id);
        const t=(a.innerText||'').replace(/\\s+/g,' ').trim();
        if(t.length>15) out.push({id:id, txt:t.slice(0,90), href:a.href});
      } return out.slice(0,%d);})()""" % args.max)
    if flag:
        print("风控:", flag, "——停手，稍后再试")
        return
    for i, it in enumerate(items or [], 1):
        print(f"{i}. {it['txt'][:60]}\n   {it['href']}")
    print(f"[OK] {len(items or [])} 条")


def cmd_login(args):
    cdp = CDP(args.port)
    go("https://www.goofish.com/login?spm=a21ybx.seo.sitemap.1", cdp)
    cdp.js("window.scrollTo(0, 250)")
    time.sleep(1)
    shot = cdp.send("Page.captureScreenshot", format="png")
    import base64
    png = os.path.join(os.getcwd(), "qr.png")
    with open(png, "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print(f"二维码已存 {png}，用闲鱼 App 首页左上角「扫一扫」扫码")
    print("扫完回车，我验证登录态……")
    input()
    cdp.navigate("https://www.goofish.com/")
    head = cdp.js("document.body.innerText.slice(0,100)") or ""
    print("登录态:", "OK" if "登录" not in head.split("订单")[0] or "贝贝" in head else "需确认")
    print("提示: 登录成功后运行 save-cookies")


def cmd_save(args):
    cdp = CDP(args.port)
    cdp._inject()
    all_ck = {}
    for d in COOKIE_DOMAINS:
        r = cdp.send("Network.getCookies", urls=[d])
        for c in r.get("cookies", []):
            all_ck[c["name"]] = {"value": c["value"], "domain": c.get("domain", ""),
                                 "path": c.get("path", "/"), "httpOnly": c.get("httpOnly"),
                                 "secure": c.get("secure"), "expires": c.get("expires")}
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(COOKIE_FILE, "w") as f:
        json.dump(all_ck, f, ensure_ascii=False, indent=1)
    os.chmod(COOKIE_FILE, 0o600)
    print(f"已保存 {len(all_ck)} 个 Cookie → {COOKIE_FILE}（值不打印）")


def cmd_restore(args):
    cdp = CDP(args.port)
    go("https://www.goofish.com/", cdp)
    with open(COOKIE_FILE) as f:
        ck = json.load(f)
    ok = 0
    for name, c in ck.items():
        try:
            p = {"name": name, "value": c["value"], "domain": c.get("domain") or ".goofish.com",
                 "path": c.get("path") or "/"}
            if c.get("httpOnly"):
                p["httpOnly"] = True
            if c.get("secure"):
                p["secure"] = True
            if c.get("expires") and c["expires"] > 0:
                p["expires"] = c["expires"]
            cdp.send("Network.setCookie", **p)
            ok += 1
        except Exception:
            pass
    cdp.navigate("https://www.goofish.com/")
    print(f"注回 {ok} 个 Cookie，刷新后检查首页右上角昵称")


def main():
    ap = argparse.ArgumentParser(description="闲鱼浏览器通道（CDP 直连版）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="搜索")
    s.add_argument("keyword")
    s.add_argument("--max", type=int, default=14)
    s.add_argument("--port", type=int, default=9222)
    s.set_defaults(fn=cmd_search)
    for name, fn in [("login", cmd_login), ("save-cookies", cmd_save), ("restore-cookies", cmd_restore)]:
        p = sub.add_parser(name)
        p.add_argument("--port", type=int, default=9222)
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
