# 云后端部署文档

本应用各平台的解析方案、环境变量配置、cookie 维护与常驻部署。

## 一、各平台方案总览

| 平台 | 解析方式 | 后端接口 | 阿里云香港可行性 | 状态 |
|------|---------|---------|----------------|------|
| 抖音 | **App 本地 JS 解析**（不走后端） | 无 | ✅ 直接用 | ✅ 已通 |
| B站 / 快手 | App 本地 JS 解析 | 无 | ✅ 直接用 | ✅ 已通 |
| TikTok | App 本地 JS（手机能访问 TikTok 即可） | 无 | ✅ | ✅ |
| Instagram | 云后端 instaloader + 登录 cookie + **私有 API** | `POST /api/instagram` | ✅ 香港直连 ins | ✅ 已通（私有 API 不限流） |
| 小红书 | 云后端 xhs + Playwright 签名 | `POST /api/xhs` | ⚠️ 异地风控未通 | ⚠️ 待解决 |

**抖音/B站等在 App 本地解析，无需后端**，后端只为 Instagram（和小红书）服务。

## 二、前置条件

- 阿里云 ECS（推荐**香港**节点，能直连 Instagram；国内节点访问不了 ins 需配代理）
- 公网 IP，安全组放行 **TCP 8000** 入方向
- Python 3.10+
- 手机能访问服务器公网 IP:8000

## 三、环境变量配置

| 变量 | 必需 | 说明 |
|------|------|------|
| `STEALTH_JS_PATH` | 小红书+ins登录需要 | stealth.min.js 绝对路径，绕过浏览器环境检测 |
| `INSTAGRAM_COOKIE` | Instagram | 手机导出的 ins 登录 cookie 字符串（`sessionid=...; csrftoken=...; ...`） |
| `INSTAGRAM_USERNAME` | 可选 | instaloader 命令行登录的 session 用户名（`instaloader -l` 生成 session 文件后设） |
| `XHS_COOKIE` | 小红书 | 服务器登录生成的小红书 cookie（`a1=...; web_session=...; webId=...`） |
| `XHS_HEADLESS` | 可选 | 小红书 Playwright 模式：`1`=headless（默认），`0`=有头（需 `xvfb-run`，绕 headless 检测） |
| `HTTPS_PROXY` / `HTTP_PROXY` | 国内节点才需 | 访问 Instagram 的代理（香港节点不需） |

> **关键**：cookie 必须通过 `EnvironmentFile=/etc/media-downloader.env` 传给进程。`systemd` 的 `Environment=` 在含 `;` `%` 等 cookie 特殊字符时易出错，且手动部署时容易漏写。务必用 `EnvironmentFile`（见第九节）。验证进程是否拿到 cookie：`cat /proc/$(pgrep -f "uvicorn app.main"|head -1)/environ | tr '\0' '\n' | grep INSTAGRAM_COOKIE`

## 四、部署步骤（香港节点）

```bash
# 1. 拉代码
git clone https://github.com/ShenHongQi/media-downloader.git
cd media-downloader/backend

# 2. 虚拟环境 + 依赖
apt install -y python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Playwright Chromium（小红书签名 + ins 登录脚本用）
playwright install chromium
playwright install-deps chromium   # 缺系统库时：apt install -y libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libnss3 libnspr4

# 4. stealth.min.js（绕浏览器检测）
curl -L -o stealth.min.js https://cdn.jsdelivr.net/gh/requireCool/stealth.min.js/stealth.min.js
# 备用：curl -L -o stealth.min.js https://raw.githubusercontent.com/requireCool/stealth.min.js/master/stealth.min.js

# 5. 设环境变量（见第五、六节获取 cookie）
export STEALTH_JS_PATH=$(pwd)/stealth.min.js
export INSTAGRAM_COOKIE='sessionid=...; csrftoken=...; ...'

# 6. 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动日志应见 `[instagram] backend initialized`。`[xhs] backend initialized` 也会出现但小红书解析仍受异地风控（见第七节）。

## 五、Instagram cookie 获取（手机导出，已验证可行）

Instagram 用 `sessionid` 登录态，不绑定设备，手机导出即可。

1. Android 装 **Kiwi Browser**（支持 Chrome 扩展）
2. Kiwi 装 **Cookie Editor** 扩展（Chrome 网上应用店）
3. Kiwi 登录 `instagram.com`
4. Cookie Editor → instagram.com → **Export**
5. 找 `sessionid`/`csrftoken`/`ds_user_id`/`ig_did`/`mid`/`datr`/`rur`，拼成：
   `sessionid=xxx; csrftoken=yyy; ds_user_id=zzz; ig_did=...; mid=...; datr=...; rur=...`
6. 设 `export INSTAGRAM_COOKIE='上面那串'`，重启后端

iOS 不支持浏览器扩展，建议借 Android 设备，或用 `ig_login.py`（服务器 Playwright 登录，但 headless 大概率被 ins 检测拦，不推荐）。

## 六、抖音方案（App 本地，无需后端）

抖音解析在 App 内（`packaging/android/www/parsers.js` 的 `DouyinParser`）：
- 解析 `v.douyin.com` 短链重定向 → 提取 aweme_id
- 获取 ttwid → 调抖音 web detail API → 提取无水印图片/视频
- **不走后端**，手机直接解析，下载走原生 Downloader 插件（带 douyin Referer）

后端 `/api/parse` 也支持抖音（Python parser），但 App 默认本地解析更快，不用后端。

## 七、小红书现状与方案（异地风控，待解决）

### 问题
小红书 `a1`（设备标识）必须与 `web_session` 登录设备一致，且请求 IP 需与登录 IP 一致：
- Mac 登录的 cookie 在香港服务器用 → **300011 账号异常**（异地风控）
- 服务器 a1 + 用户 web_session → **SignError 浏览器异常**（a1 与 web_session 不匹配）
- 匿名 a1 → 签名成功但 **code -1**（风控）

### 唯一可行路：服务器本地登录小红书
生成与服务器 IP 一致且匹配的 a1+web_session。用 `backend/xhs_login.py`：
```bash
cd ~/media-downloader/backend
source .venv/bin/activate
export STEALTH_JS_PATH=$(pwd)/stealth.min.js
python xhs_login.py
# 截图 /tmp/xhs_login.png，本地 scp 下载，手机小红书 App 扫码
# 脚本检测登录后打印 XHS_COOKIE=...
export XHS_COOKIE='a1=...; web_session=...; webId=...'
export XHS_HEADLESS=0   # 若 headless 仍 SignError，改有头 + xvfb-run
apt install -y xvfb
xvfb-run uvicorn app.main:app --host 0.0.0.0 --port 8000
```
**风险**：小红书登录页结构可能变（二维码/手机号）、headless 可能仍被检测。未验证通过，折腾项。

## 八、Cookie 过期解决方案

### Instagram（sessionid）
- 有效期约 1 年，但异地登录/可疑活动可能提前失效
- 失效表现：`/api/instagram` 报 `no such group` 或 `401/login required`
- **解决**：重新手机导 cookie（第五节），更新 `INSTAGRAM_COOKIE`，重启后端

### 小红书（web_session）
- 有效期约 1-3 月
- 失效表现：`300011 账号异常` 或 `code -1`
- **解决**：重新服务器登录（`xhs_login.py`），更新 `XHS_COOKIE`，重启

### 检测脚本（定时验证 cookie 是否有效）
```bash
curl -s http://localhost:8000/api/health
curl -s -X POST http://localhost:8000/api/instagram -H "Content-Type: application/json" -d '{"url":"https://www.instagram.com/p/DYwoclTD2-b/"}' | head -c 100
```
返回正常 JSON 即 cookie 有效；报错即需更新。

## 九、常驻运行（systemd）+ 一键部署

### 一键部署脚本（推荐）

`backend/scripts/deploy.sh` 自动完成：系统依赖 → Python 依赖 → Playwright Chromium → stealth.min.js → 写 `/etc/media-downloader.env` → systemd 服务（用 `EnvironmentFile`）→ 启动。

```bash
# 服务器 root 执行
cd ~/media-downloader
git pull origin main
export INSTAGRAM_COOKIE='sessionid=...; csrftoken=...; ds_user_id=...; ig_did=...; mid=...; datr=...; rur=...'
bash backend/scripts/deploy.sh
```

脚本完成后服务常驻：**开机自启 + 崩溃自动重启 + 断开 SSH 终端不影响**。

> **断开终端会断吗？** 不会。systemd 是系统级服务管理器，独立于终端会话。前台 `uvicorn`（关终端停）或 `nohup &`（关终端不停但开机不自启）才受影响。systemd 是正确方案。

### ⚠️ 必读：cookie 必须用 EnvironmentFile 传给进程

**常见坑**：手动写 service 时用 `Environment=INSTAGRAM_COOKIE=...`，含 `;` `%` 等 cookie 特殊字符易解析错，或漏写导致进程无 cookie → Instagram 私有 API 无 session → 回退 graphql → 401 限流。

正确做法：cookie 写进 `/etc/media-downloader.env`，service 用 `EnvironmentFile`：

```bash
# 1. 写 env 文件（cookie 持久化，权限 600）
cat > /etc/media-downloader.env << 'EOF'
STEALTH_JS_PATH=/root/media-downloader/backend/stealth.min.js
INSTAGRAM_COOKIE=sessionid=xxx; csrftoken=yyy; ds_user_id=zzz; ig_did=...; mid=...; datr=...; rur=...
EOF
chmod 600 /etc/media-downloader.env

# 2. service 用 EnvironmentFile
sudo tee /etc/systemd/system/media-downloader.service << 'EOF'
[Unit]
Description=Media Downloader Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/media-downloader/backend
EnvironmentFile=/etc/media-downloader.env
ExecStart=/root/media-downloader/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now media-downloader

# 3. ⚠️ 验证进程确实拿到 cookie（输出非空才对）
cat /proc/$(pgrep -f "uvicorn app.main" | head -1)/environ | tr '\0' '\n' | grep INSTAGRAM_COOKIE
```

**验证 cookie 生效**：
```bash
curl -s -X POST http://localhost:8000/api/instagram -H "Content-Type: application/json" -d '{"url":"https://www.instagram.com/p/某shortcode/"}'
# 返回 {"platform":"instagram",...items...} 即正常
# 返回 "Instagram 限流" 或 401 → cookie 没传进去（检查上一步验证命令输出是否非空）
```

### Instagram 解析流程（已优化，私有 API 不限流）

`/api/instagram` 解析顺序：
1. 缓存命中（1h 内重复解析同一链接）→ 瞬间返回，不请求
2. 请求间隔 ≥8s
3. embed 页（视频帖直接返回，完全不限流）
4. **私有 API** `i.instagram.com/api/v1/media/{media_id}/info/`（shortcode→media_id base64 解码，带 sessionid，**独立于 web graphql，不限流**）—— 单图/图集主路径
5. graphql 回退（私有 API 失败才走，可能限流）
6. 401 友好错误（不重试轰炸）

私有 API 是 Instagram 移动端点，限流配额独立于 web graphql，图集不再触发之前的限流。

### 常用运维命令

```bash
sudo journalctl -u media-downloader -f        # 查看日志
sudo systemctl restart media-downloader      # 重启
sudo systemctl stop media-downloader         # 停止
sudo systemctl status media-downloader        # 状态
```

### 更新 cookie（过期后）

cookie 存 `/etc/media-downloader.env`（权限 600）。

**Instagram cookie 失效**（`/api/instagram` 报 401/限流/`no such group`）：
1. 重新手机导 cookie（第五节）
2. 编辑 `/etc/media-downloader.env` 改 `INSTAGRAM_COOKIE=` 那行
3. `sudo systemctl restart media-downloader`
4. 验证进程拿到 cookie：`cat /proc/$(pgrep -f "uvicorn app.main"|head -1)/environ | tr '\0' '\n' | grep INSTAGRAM_COOKIE`

或重新跑 `export INSTAGRAM_COOKIE='...'; bash backend/scripts/deploy.sh`（会覆盖 env 文件 + 重启）。

**小红书 web_session 失效**（`300011 账号异常`）：重新 `python xhs_login.py` 服务器登录，更新 `XHS_COOKIE` 进 env 文件后 restart。

## 十、App 配置

1. 安装 `MediaDownloader.apk`
2. 点右上角 ⚙
3. 服务器地址填 `http://<公网IP>:8000`
4. 解析模式选「本地解析」（抖音/B站本地，Instagram/小红书走服务器）
5. 保存，粘贴链接测试

## 十一、维护与排错

- **小红书签名失效**：`pip install -U xhs && playwright install chromium`，重启
- **Instagram 401/需登录**：cookie 过期，重新手机导（第五节）
- **Instagram `no such group`**：cookie 没生效或 instaloader 版本问题，检查 `INSTAGRAM_COOKIE` 是否设、`[instagram] backend initialized` 日志
- **端口占用**：`fuser -k 8000/tcp`
- **Chromium 启动失败**：缺系统库，`playwright install-deps chromium`
- **国内节点访问不了 ins**：换香港节点，或设 `HTTPS_PROXY=http://代理:端口`
- **某后端初始化失败不影响另一个**：小红书和 Instagram 互相独立
