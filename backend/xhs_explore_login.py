"""探索小红书登录页结构（headless），看登录方式（二维码/手机号）。
跑：export STEALTH_JS_PATH=$(pwd)/stealth.min.js && python xhs_explore_login.py
"""
import os
import time
from playwright.sync_api import sync_playwright

STEALTH = os.environ.get("STEALTH_JS_PATH", "stealth.min.js")

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
    time.sleep(5)

    # 尝试点登录按钮
    clicked = None
    for sel in ['text=登录', 'button:has-text("登录")', '[class*="login-btn"]', '[class*="login"]', '#login-btn']:
        try:
            loc = page.locator(sel).first
            if loc.count():
                loc.click(timeout=3000)
                clicked = sel
                time.sleep(3)
                break
        except Exception:
            pass
    print("clicked login btn:", clicked)

    page.screenshot(path="/tmp/xhs_login.png", full_page=False)
    print("screenshot: /tmp/xhs_login.png  (scp root@server:/tmp/xhs_login.png . 下载查看)")

    # 检测登录方式
    qr = page.locator('img[src*="qrcode"], img[src*="qr"], canvas, [class*="qr"], [class*="QRCode"]').count()
    phone = page.locator('input[type="tel"], input[name*="phone"], input[placeholder*="手机"], input[placeholder*="phone"]').count()
    code_input = page.locator('input[placeholder*="验证码"], input[name*="code"], input[placeholder*="code"]').count()
    print("qr_elements:", qr)
    print("phone_inputs:", phone)
    print("code_inputs:", code_input)

    # 打印所有可见 input
    inputs = page.locator('input').all()
    print("all inputs:", len(inputs))
    for i, inp in enumerate(inputs[:8]):
        try:
            print(f"  input[{i}] type={inp.get_attribute('type')} name={inp.get_attribute('name')} placeholder={inp.get_attribute('placeholder')}")
        except Exception:
            pass

    # 打印所有可见 button
    btns = page.locator('button').all()
    print("all buttons:", len(btns))
    for i, b in enumerate(btns[:8]):
        try:
            print(f"  btn[{i}] text={b.text_content()[:20]}")
        except Exception:
            pass

    print("title:", page.title())
    print("url:", page.url)
    browser.close()
