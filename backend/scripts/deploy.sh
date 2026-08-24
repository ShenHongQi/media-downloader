#!/bin/bash
# 一键部署 Media Downloader 后端为 systemd 常驻服务
#
# 用法（以 root 在服务器执行）：
#   export INSTAGRAM_COOKIE='sessionid=xxx; csrftoken=yyy; ...'
#   bash /root/media-downloader/backend/scripts/deploy.sh
#
# 部署后：开机自启 + 崩溃自动重启 + 断开终端不影响
# 更新 cookie：改 INSTAGRAM_COOKIE 环境变量后重新跑本脚本，或直接改 /etc/media-downloader.env 后 systemctl restart

set -e

BACKEND_DIR="/root/media-downloader/backend"
COOKIE="${INSTAGRAM_COOKIE:-}"

if [ -z "$COOKIE" ]; then
    echo "ERROR: 请先设置 INSTAGRAM_COOKIE 环境变量"
    echo "  export INSTAGRAM_COOKIE='sessionid=...; csrftoken=...; ds_user_id=...; ig_did=...; mid=...; datr=...; rur=...'"
    echo "  获取方式见 docs/BACKEND_DEPLOY.md 第五节（手机 Kiwi+Cookie Editor 导出）"
    exit 1
fi

if [ ! -d "$BACKEND_DIR" ]; then
    echo "ERROR: $BACKEND_DIR 不存在，请先 git clone https://github.com/ShenHongQi/media-downloader.git"
    exit 1
fi

echo "=== [1/6] 安装系统依赖 ==="
apt-get update -qq
apt-get install -y python3-venv python3-pip curl >/dev/null

echo "=== [2/6] Python 依赖 ==="
cd "$BACKEND_DIR"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q

echo "=== [3/6] Playwright Chromium ==="
playwright install chromium
playwright install-deps chromium 2>/dev/null || apt-get install -y libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libnss3 libnspr4 >/dev/null

echo "=== [4/6] stealth.min.js ==="
[ -f stealth.min.js ] || curl -L -o stealth.min.js https://cdn.jsdelivr.net/gh/requireCool/stealth.min.js/stealth.min.js

echo "=== [5/6] 写环境变量文件（cookie 敏感，权限 600）==="
cat > /etc/media-downloader.env << ENVFILE
STEALTH_JS_PATH=$BACKEND_DIR/stealth.min.js
INSTAGRAM_COOKIE=$COOKIE
ENVFILE
chmod 600 /etc/media-downloader.env

echo "=== [6/6] systemd 服务 ==="
cat > /etc/systemd/system/media-downloader.service << SVC
[Unit]
Description=Media Downloader Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=/etc/media-downloader.env
ExecStart=$BACKEND_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable --now media-downloader

echo ""
echo "=== 启动中，等 5 秒 ==="
sleep 5
systemctl status media-downloader --no-pager -l || true

echo ""
echo "=== 验证 ==="
curl -s http://localhost:8000/api/health || echo "（服务可能还在初始化，稍等后再 curl）"

echo ""
echo "=== ⚠️ 验证进程拿到 cookie（非空才对）==="
cat /proc/$(pgrep -f "uvicorn app.main" | head -1)/environ 2>/dev/null | tr '\0' '\n' | grep INSTAGRAM_COOKIE | head -c 40 || echo "（未检测到，检查 /etc/media-downloader.env）"

echo ""
echo "=== 完成 ==="
echo "服务已常驻（开机自启 + 断开终端不影响 + 崩溃自动重启）"
echo "查看日志:   sudo journalctl -u media-downloader -f"
echo "重启服务:   sudo systemctl restart media-downloader"
echo "更新cookie: 编辑 /etc/media-downloader.env 后 sudo systemctl restart media-downloader"
echo "App服务器地址: http://<公网IP>:8000 （阿里云安全组放行 TCP 8000）"
