# 小红书服务器登录 + Instagram cookie 方案

## Context

小红书后端卡在反爬：
- 匿名 a1：签名成功（XYW_）但 API `code -1`
- 用户 Mac cookie（a1+web_session）：签名成功但 `300011 当前账号存在异常`（异地风控——Mac 登录的 cookie 在香港服务器请求，小红书检测异地）
- 服务器 a1 + 用户 web_session：`SignError 浏览器异常`（a1 与 web_session 设备不匹配，_webmsxyw 检测异常）

根因：a1（设备标识）必须与 web_session 登录时的设备一致，且请求 IP 最好与登录 IP 一致。Mac cookie 异地、服务器 a1 不匹配。唯一出路：**在服务器本地登录小红书**，生成服务器 a1+web_session（匹配 + 同 IP）。

Instagram：headless 登录大概率被 ins 检测拦（ins 反爬严）。最可靠是手机真实浏览器登录导出 sessionid（C 方案），ins 对 sessionid 异地比小红书宽松。

## 方案

### 1. 小红书：服务器 Xvfb + Playwright 有头登录

headless 被检测（SignError），改有头模式 + Xvfb 虚拟显示，更接近真实浏览器。

**部署 Xvfb：**
```bash
apt install -y xvfb
```

**写 `backend/xhs_login.py`**（服务器登录小红书导出 cookie）：
- Playwright `chromium.launch(headless=False)` + stealth.min.js
- 导航 `https://www.xiaohongshu.com` 登录页
- 小红书 web 登录默认二维码扫码：截图二维码保存 `/tmp/xhs_qr.png`，提示用户下载扫码；或手机号+短信验证码（用户终端输入）
- 用 `xvfb-run python xhs_login.py` 跑（虚拟显示）
- 登录成功后导出 `a1`、`web_session`、`webId`，打印 `XHS_COOKIE=...`

**改 `backend/app/xhs_runtime.py` `init()`：**
- 支持 `XHS_COOKIE` 环境变量
- 有 cookie：设到 page context（add_cookies，**不 reload** 避免触发检测）+ 用作 XhsClient cookie；a1 从 cookie 解析（与 web_session 一致）
- 无 cookie：维持当前匿名浏览器 a1（兜底）
- 启动改 `chromium.launch(headless=os.environ.get("XHS_HEADLESS","1")=="1")`，配合 `xvfb-run` 用有头

### 2. Instagram：手机导 cookie（C 方案，最可靠）

用户手机真实浏览器登录 ins，导 sessionid，设 `INSTAGRAM_COOKIE`。后端已支持。

步骤（Android）：
1. 装 Kiwi Browser（支持 Chrome 扩展）
2. Kiwi 装 Cookie Editor 扩展
3. Kiwi 登录 instagram.com
4. Cookie Editor → instagram.com → Export
5. 找 `sessionid`/`csrftoken`/`ds_user_id`/`mid`/`ig_did`，拼 `sessionid=xxx; csrftoken=yyy; ...`
6. 服务器 `export INSTAGRAM_COOKIE='...'` 重启

iOS 不支持浏览器扩展，建议借 Android 设备或用 A 方案（ig_login.py，已给）。

### 3. 启动方式

```bash
# 小红书需 Xvfb 有头（绕检测）
export XHS_COOKIE='a1=...; web_session=...; webId=...'  # xhs_login.py 导出
export XHS_HEADLESS=0
export STEALTH_JS_PATH=$(pwd)/stealth.min.js
xvfb-run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

systemd 需 `xvfb-run` 包装或设 DISPLAY。

## 涉及文件

- 新增：`backend/xhs_login.py`（服务器登录脚本）
- 修改：`backend/app/xhs_runtime.py`（init 支持 XHS_COOKIE + headless 开关 + 不 reload 设 cookie）
- 已有：`backend/ig_login.py`（Instagram A 方案，已给）

## 验证

1. `apt install xvfb`
2. `xvfb-run python xhs_login.py` 登录小红书，导出 XHS_COOKIE
3. `export XHS_COOKIE=... XHS_HEADLESS=0; xvfb-run uvicorn ...`
4. `curl -X POST localhost:8000/api/xhs -d '{"url":"https://xhslink.cn/o/8FphTTg7UPw"}'` → 返回 note
5. Instagram：手机导 sessionid 设 INSTAGRAM_COOKIE，`curl /api/instagram` → 返回媒体

## 风险

- 小红书有头 + Xvfb 仍可能被检测（stealth 不万能）。若仍 SignError，可能需更完善 stealth 或接受小红书不可用
- 小红书登录页结构（二维码/手机号）可能变，脚本需按实际调
- Instagram C 方案最稳，A 方案 headless 大概率被拦
