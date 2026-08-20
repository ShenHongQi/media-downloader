"""服务器登录小红书，导出 XHS_COOKIE（a1+web_session+webId）。

用法：
  export STEALTH_JS_PATH=$(pwd)/stealth.min.js
  python xhs_login.py

流程：
  1. headless Chromium 导航小红书首页，点登录
  2. 截图二维码到 /tmp/xhs_login.png
  3. 你 scp 下载该图，用手机小红书 App 扫码登录
  4. 脚本检测到 web_session 后导出 XHS_COOKIE
  5. 设 export XHS_COOKIE='...' 给后端用
"""
import os
import time
from playwright.sync_api import sync_playwright

STEALTH = os.environ.get("STEALTH_JS_PATH", "stealth.min.js")


def main():
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

        # 尝试点"登录"按钮
        for sel in ['text=登录', 'button:has-text("登录")', '.login-btn', '[class*="login"]']:
            try:
                loc = page.locator(sel).first
                if loc.count():
                    loc.click(timeout=3000)
                    print("clicked:", sel)
                    time.sleep(3)
                    break
            except Exception:
                pass

        page.screenshot(path="/tmp/xhs_login.png")
        print("截图已保存: /tmp/xhs_login.png")
        print("title:", page.title(), "url:", page.url)
        print(">>> 在本地新终端执行: scp root@服务器IP:/tmp/xhs_login.png .  下载查看")
        print(">>> 用手机小红书 App 扫描截图中的二维码登录（180 秒内）")

        # 轮询 web_session
        logged = False
        for i in range(90):
            time.sleep(2)
            cookies = ctx.cookies()
            ws = next((c for c in cookies if c["name"] == "web_session" and c.get("value")), None)
            if ws:
                logged = True
                print("检测到登录成功")
                break
        if not logged:
            print("超时未登录，退出。可重试。")

        cookies = ctx.cookies()
        xhs = [c for c in cookies if "xiaohongshu.com" in c["domain"]]
        names = ("a1", "web_session", "webId")
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in xhs if c["name"] in names)
        print("=== RESULT ===")
        print("XHS_COOKIE=" + cookie_str)
        browser.close()


if __name__ == "__main__":
    main()
