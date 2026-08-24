"""服务器登录小红书（扫码模式），生成 XHS_COOKIE。

用法：
  export STEALTH_JS_PATH=$(pwd)/stealth.min.js
  python xhs_login.py
  # 另开终端下载二维码扫码（脚本会提示），扫码后自动检测登录
"""
import os
import time
from playwright.sync_api import sync_playwright

STEALTH = os.environ.get("STEALTH_JS_PATH", "stealth.min.js")


def click_first(page, selectors, label="btn"):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=3000)
                print(f"clicked {label}: {sel}")
                return True
        except Exception:
            pass
    return False


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    if os.path.exists(STEALTH):
        ctx.add_init_script(path=STEALTH)
    page = ctx.new_page()
    page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
    time.sleep(4)

    # 点登录按钮（默认二维码扫码）
    click_first(page, ['text=登录', 'button:has-text("登录")'], "login-btn")
    time.sleep(4)

    page.screenshot(path="/tmp/xhs_qr.png")
    print("=== 二维码已截图: /tmp/xhs_qr.png ===")
    print(">>> 另开一个终端执行（下载二维码 + 扫码）:")
    print("    sudo systemctl stop media-downloader")
    print("    cd /tmp && python3 -m http.server 8000")
    print("    Mac 浏览器打开: http://47.239.52.21:8000/xhs_qr.png")
    print("    用手机小红书 App 扫描二维码 → 确认登录")
    print(">>> 扫码后本脚本自动检测（180秒内）")
    print("")

    # 等 web_session cookie（扫码登录后出现）
    logged = False
    for i in range(180):
        time.sleep(1)
        cookies = ctx.cookies()
        ws = next((c for c in cookies if c["name"] == "web_session" and c.get("value")), None)
        if ws:
            logged = True
            print("✅ 扫码登录成功")
            break
        if i % 30 == 29:
            print(f"  等待扫码... ({i+1}s)")
    if not logged:
        print("❌ 180s 超时未登录。确认二维码是否扫了，或重试。")

    cookies = ctx.cookies()
    xhs = [c for c in cookies if "xiaohongshu.com" in c["domain"]]
    names = ("a1", "web_session", "webId")
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in xhs if c["name"] in names)
    print("=== RESULT ===")
    print("XHS_COOKIE=" + cookie_str)
    browser.close()
