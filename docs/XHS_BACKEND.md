# 小红书后端部署说明（云主机）

小红书 note 数据需 `x-s` 签名（JSVMP），App 内本地解析不可靠。改为：**云主机部署后端（Playwright + xhs 库真浏览器签名），App 远程调用**。抖音/B站等平台仍 App 本地解析，不走后端。

## 前置条件

- 云主机：Ubuntu 22.04/24.04（已有 172.29.5.110）
- **手机能访问云机地址**：若云机无公网 IP，手机需与云机同网络或用内网穿透（如 frp/ngrok）。App 设置页填的地址必须手机可达。
- Python 3.10+

## 部署步骤

```bash
# 1. 拉代码（或上传项目）
git clone https://github.com/ShenHongQi/media-downloader.git
cd media-downloader/backend

# 2. 虚拟环境 + 依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 安装 Playwright Chromium（签名用真浏览器）
playwright install chromium
# 如缺系统库：playwright install-deps chromium

# 4. 下载反检测脚本 stealth.min.js
curl -L -o stealth.min.js https://cdn.jsdelivr.net/gh/requireCool/stealth.min.js/stealth.min.js
# 若 jsdelivr 被墙，换：curl -L -o stealth.min.js https://raw.githubusercontent.com/requireCool/stealth.min.js/master/stealth.min.js

# 5. 启动服务（stealth 路径默认 /app/stealth.min.js，这里用当前目录）
export STEALTH_JS_PATH=$(pwd)/stealth.min.js
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

首次启动会下载/启动 Chromium 访问小红书挂载签名函数，约 10-20 秒。看到 `[xhs] backend initialized` 即就绪。

## 验证

```bash
# 健康检查（xhs_ready 应为 true）
curl http://localhost:8000/api/health

# 测试小红书解析
curl -X POST http://localhost:8000/api/xhs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://xhslink.cn/o/6VumsyNX7Gk"}'
```

返回应含 `items`（图片/视频直链）。

## App 配置

1. 安装 `MediaDownloader.apk`
2. 打开 App，点右上角 ⚙
3. 选「远程服务器」模式（或本地模式下小红书也会自动用此服务器）
4. 填服务器地址：`http://<云机IP>:8000`（手机必须能访问）
5. 保存。粘贴小红书链接即可解析下载

## 常驻运行（systemd）

```bash
sudo tee /etc/systemd/system/media-downloader.service << 'EOF'
[Unit]
Description=Media Downloader Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/media-downloader/backend
Environment=STEALTH_JS_PATH=/root/media-downloader/backend/stealth.min.js
ExecStart=/root/media-downloader/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now media-downloader
sudo systemctl status media-downloader
```

## Cookie 说明

- 当前实现用**匿名 a1**（浏览器访问小红书自动生成的设备标识），可拿**公开笔记**。
- 若解析失败（笔记需要登录态/私密内容），需登录 cookie：浏览器登录小红书 → F12 复制 cookie（含 `a1`、`web_session`、`webId`）→ 修改 `xhs_runtime.py` 的 `init()` 里 `XhsClient(f"a1={a1}")` 为完整 cookie 字符串，重启。

## 维护

- 小红书签名算法每 1-3 个月小变，`xhs` 库会跟版。定期 `pip install -U xhs` 更新。
- 若签名失效报错，更新 xhs 库 + 重新 `playwright install chromium`。
