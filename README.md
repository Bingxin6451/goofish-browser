# goofish-browser 闲鱼浏览器通道

用「真浏览器 + 反检测注入」驱动闲鱼网页版搜索——服务器视角是真人浏览器，绕开接口通道的风控瓶颈。

## 对比

| | 传统 mtop 接口通道 | 本项目浏览器通道 |
|---|---|---|
| 频控 | 15 分钟 4 次搜索即触发 RGV587 封窗（≥20 分钟拒答） | 实测 1 秒间隔连发 10+ 次零风控 |
| 拦截 | 缺设备指纹，易触发验证 | 页面 JS 原生签名，无「非法访问」拦截 |
| 环境 | 裸 Cookie + 签名复刻 | 真 Chrome（headless=new）+ CDP 控制 |
| 登录态 | Cookie 复制，易过期 | 扫码一次 + Cookie 落盘可注回 |

## 原理

1. **无头 Chrome + 反检测**：每次页面加载前注入脚本抹掉 `navigator.webdriver`、伪装 User-Agent（无头模式的三大暴露点：webdriver=true、UA 含 HeadlessChrome、软渲染）。
2. **让页面自己干活**：搜索走网页版 URL（`goofish.com/search?q=...`），页面自己的 JS 生成签名和指纹，行为与真人一致。
3. **登录态持久化**：登录后导出全套 Cookie 落盘（600 权限），浏览器实例重建后注回即可恢复，免重复扫码。

## 文件

| 文件 | 说明 |
|---|---|
| `goofish_browser.py` | 通用版：纯 Python CDP 客户端（websocket 直连任意带 `--remote-debugging-port` 的 Chrome），不依赖特定 Agent 框架 |
| `hermes_templates.py` | Hermes Agent 版：browser_exec 代码模板（注入 / 注回 / 保存 / 搜索四件套） |

## 快速开始（通用版）

```bash
pip install websocket-client requests
# 1. 起无头 Chrome
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/xy-profile \
  --disable-blink-features=AutomationControlled about:blank &
# 2. 搜索
python3 goofish_browser.py search "iPhone 15 Pro 256" --max 14
# 3. 登录（扫码，二维码存 qr.png）
python3 goofish_browser.py login
# 4. 登录后保存 Cookie
python3 goofish_browser.py save-cookies
# 5. 登录态丢失后注回
python3 goofish_browser.py restore-cookies
```

## 频控边界（实测数据）

- 浏览器通道：3 秒间隔 5 连发 + 1 秒间隔 5 连发 + 累计 25+ 次搜索，**零风控**。
- 建议底线：单窗口 ≤10 连发、跨窗口歇 30 秒。核心件 Cookie 有效期约 1 年，短周期件自动续期。

## 已知坑

- **配件霸屏**：「品牌+型号 手机」类词可能返回 100% 配件（电池/后盖/钢化膜）。对策：规格词（如「一加13 16+512」）、过滤词表、切换「新降价」排序。
- **登录框二维码被视口裁掉**：iframe 高 454 超出视口，滚动 `window.scrollTo(0, 250)` 后截图可见。
- **跨域 iframe 内操作**：CDP 隔离世界（`Page.createIsolatedWorld`）可进 passport 登录框内部执行 JS。

## 合规与免责

- 仅供学习研究个人账号自动化；请遵守平台规则，勿用于批量骚扰、群发营销等滥用场景。
- 任何凭据（Cookie/Token）勿进仓库、勿进聊天记录；本项目不含任何账号信息。
- 风控会演进：本方案的注入点在实测日期（2026-10）有效，平台更新后可能需要调整。

## License

MIT
