"""服务器登录小红书，生成 XHS_COOKIE（手机号+短信验证码）。

用法：
  export STEALTH_JS_PATH=$(pwd)/stealth.min.js
  python xhs_login.py
  # 输入手机号 → 收短信验证码 → 输入 → 登录成功导出 XHS_COOKIE
  # 设：export XHS_COOKIE='...'; sudo systemctl restart media-downloader
"""
import os
import time
from playwright.sync_api import sync_playwright

STEALTH = os.environ.get("STEALTH_JS_PATH", "stealth.min.js")
PHONE = input("小红书手机号: ").strip()


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

    # 点登录按钮
    click_first(page, ['text=登录', 'button:has-text("登录")'], "login-btn")
    time.sleep(3)

    # 切到手机号登录 tab（若默认二维码）
    click_first(page, ['text="手机号"', 'text="手机号登录"', '[class*="phone"]:not(input)'], "phone-tab")
    time.sleep(1)

    # 填手机号
    try:
        page.fill('input[placeholder="输入手机号"]', PHONE)
        print("手机号已填")
    except Exception as e:
        print("填手机号失败:", e)
    time.sleep(1)

    # 点获取验证码
    if not click_first(page, [
        'button:has-text("获取验证码")', 'text="获取验证码"',
        'button:has-text("获取")', '[class*="send"]', '[class*="code-btn"]',
    ], "get-code"):
        print("⚠️ 没点到获取验证码按钮，请看 /tmp/xhs_login.png")
    page.screenshot(path="/tmp/xhs_login.png")

    # 等用户收验证码
    code = input("输入收到的短信验证码: ").strip()
    try:
        page.fill('input[placeholder="输入验证码"]', code)
        print("验证码已填")
    except Exception as e:
        print("填验证码失败:", e)
    time.sleep(1)

    # 点登录提交（登录框内的登录按钮，选最后一个可见的）
    btns = page.locator('button:has-text("登录")').all()
    clicked = False
    for b in reversed(btns):
        try:
            if b.is_visible():
                b.click(timeout=3000)
                print("clicked 登录提交")
                clicked = True
                break
        except Exception:
            pass
    if not clicked:
        page.keyboard.press("Enter")

    # 等 web_session cookie（30s）
    logged = False
    for i in range(30):
        time.sleep(1)
        cookies = ctx.cookies()
        ws = next((c for c in cookies if c["name"] == "web_session" and c.get("value")), None)
        if ws:
            logged = True
            print("✅ 登录成功")
            break
    if not logged:
        print("❌ 30s 内未检测到登录，可能验证码错或需滑块验证，看 /tmp/xhs_login.png")
        page.screenshot(path="/tmp/xhs_login.png")

    cookies = ctx.cookies()
    xhs = [c for c in cookies if "xiaohongshu.com" in c["domain"]]
    names = ("a1", "web_session", "webId")
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in xhs if c["name"] in names)
    print("=== RESULT ===")
    print("XHS_COOKIE=" + cookie_str)
    browser.close()
