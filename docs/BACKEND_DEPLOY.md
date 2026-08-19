# 云后端部署说明（阿里云）

小红书、Instagram 走云后端解析（App 本地解析受限：小红书需 x-s 签名、Instagram 需登录/CSR）。抖音/B站等仍在 App 本地解析，**不走后端，不受影响**。

## 平台路由

| 平台 | 解析方式 | 后端接口 | 备注 |
|------|---------|---------|------|
| 抖音 / B站 / 快手 / TikTok | App 本地 JS | 无 | 直接用 |
| 小红书 | 云后端 | `POST /api/xhs` | xhs 库 + Playwright 签名，访问小红书（国内站点，阿里云直连） |
| Instagram | 云后端 | `POST /api/instagram` | instaloader 库，**需服务器能访问 instagram（阿里云国内默认被墙，需配代理）** |

## 前置条件

- 阿里云 ECS（华东1，公网 IP，Ubuntu 22.04，2C2G）
- 手机能访问服务器公网 IP:8000（安全组放行 8000 端口）
- Python 3.10+
- **Instagram 额外**：服务器需能访问 instagram.com（配 HTTPS_PROXY 代理），否则 Instagram 后端无效

## 部署步骤

```bash
# 1. 拉代码
git clone https://github.com/ShenHongQi/media-downloader.git
cd media-downloader/backend

# 2. 虚拟环境 + 依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 小红书：安装 Playwright Chromium（真浏览器签名）
playwright install chromium
playwright install-deps chromium   # 缺系统库时

# 4. 下载反检测脚本 stealth.min.js
curl -L -o stealth.min.js https://cdn.jsdelivr.net/gh/requireCool/stealth.min.js/stealth.min.js
# 备用：curl -L -o stealth.min.js https://raw.githubusercontent.com/requireCool/stealth.min.js/master/stealth.min.js

# 5. （可选）Instagram：配代理让 instaloader 能访问 instagram
#    阿里云国内默认访问不了 instagram，需翻墙代理。设环境变量：
export HTTPS_PROXY=http://你的代理地址:端口
export HTTP_PROXY=http://你的代理地址:端口

# 6. （可选）Instagram：配登录 cookie 提高成功率（匿名常被限）
#    浏览器登录 instagram → F12 → Application/Network 复制完整 Cookie 字符串
export INSTAGRAM_COOKIE='sessionid=xxx; csrftoken=yyy; mid=zzz; ds_user_id=...; ig_did=...'

# 7. 启动
export STEALTH_JS_PATH=$(pwd)/stealth.min.js
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动日志看到 `[xhs] backend initialized` 和 `[instagram] backend initialized` 即就绪（某后端失败不影响另一个）。

## 验证

```bash
# 健康检查
curl http://localhost:8000/api/health
# 应返回 {"status":"ok","xhs_ready":true,"instagram_ready":true}

# 测试小红书
curl -X POST http://localhost:8000/api/xhs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://xhslink.cn/o/6VumsyNX7Gk"}'

# 测试 Instagram（需代理+cookie 配好）
curl -X POST http://localhost:8000/api/instagram \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.instagram.com/p/DYwoclTD2-b/"}'
```

## App 配置

1. 安装 `MediaDownloader.apk`
2. 点右上角 ⚙
3. 填服务器地址：`http://<阿里云公网IP>:8000`
4. 保存。粘贴小红书/Instagram 链接即自动走后端；抖音/B站走本地

## 阿里云安全组

控制台 → ECS → 安全组 → 放行 **TCP 8000** 入方向（手机才能访问）。

## 常驻运行（systemd）

```bash
sudo tee /etc/systemd/system/media-downloader.service << 'EOF'
[Unit]
Description=Media Downloader Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/media-downloader/backend
Environment=STEALTH_JS_PATH=/root/media-downloader/backend/stealth.min.js
Environment=HTTPS_PROXY=http://你的代理:端口
Environment=INSTAGRAM_COOKIE=sessionid=xxx;csrftoken=yyy
ExecStart=/root/media-downloader/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now media-downloader
```

## 维护与排错

- **小红书签名失效**：`pip install -U xhs && playwright install chromium`，重启
- **Instagram 429/登录墙**：匿名被限，配 `INSTAGRAM_COOKIE`；cookie 过期需更新
- **Instagram 连接超时**：服务器访问不了 instagram，检查 `HTTPS_PROXY` 代理是否生效（`curl -x $HTTPS_PROXY https://www.instagram.com` 测试）
- **某后端初始化失败不影响另一个**：日志看 `[xxx] backend init failed`，小红书和 Instagram 互相独立
