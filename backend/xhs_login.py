"""服务器图形界面登录小红书，手动过验证码，生成 XHS_COOKIE。

用法（在图形界面终端跑，不是 SSH 无图形）：
  export STEALTH_JS_PATH=$(pwd)/stealth.min.js
  python xhs_login.py
  # 浏览器窗口弹出在桌面 → 扫码登录 → 出验证码手动过 → 回终端按回车 → 导出 cookie
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
    # 有头模式，显示在图形桌面（不用 Xvfb，用户可交互过验证码）
    browser = p.chromium.launch(headless=False)
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
    print(">>> 浏览器已打开，用手机小红书 App 扫码登录")

    # 等扫码登录（web_session 出现）
    logged = False
    for i in range(180):
        time.sleep(1)
        cookies = ctx.cookies()
        ws = next((c for c in cookies if c["name"] == "web_session" and c.get("value")), None)
        if ws:
            logged = True
            print("✅ 扫码登录成功")
            break
    if not logged:
        print("❌ 180s 超时未登录")

    # 导航笔记页，触发可能的验证码，让用户在浏览器手动过
    print(">>> 导航笔记页，如出验证码/滑块请在浏览器手动过")
    try:
        page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
    except Exception:
        pass
    time.sleep(2)
    print(">>> 验证码过了（或没出现）后，回此终端按回车继续")
    input()

    # 再访问一个笔记页（进一步建立信任）
    try:
        page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
        time.sleep(3)
    except Exception:
        pass

    cookies = ctx.cookies()
    xhs = [c for c in cookies if "xiaohongshu.com" in c["domain"]]
    names = ("a1", "web_session", "webId")
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in xhs if c["name"] in names)
    print("=== RESULT ===")
    print("XHS_COOKIE=" + cookie_str)
    print(">>> 设给后端：")
    print("    sudo bash -c 'echo \"XHS_COOKIE=" + cookie_str + "\" >> /etc/media-downloader.env'")
    print("    sudo systemctl restart media-downloader")
    browser.close()
