"""服务器图形界面登录小红书，保存到持久化 profile（后端签名共用同一浏览器实例）。

用法（图形桌面终端跑，不是 SSH 无图形）：
  export STEALTH_JS_PATH=$(pwd)/stealth.min.js
  python xhs_login.py
  # 浏览器窗口弹出 → 扫码登录 → 出验证码手动过 → 回终端按回车
  # profile 保存在 /root/.xhs_profile，后端 init 加载同一 profile

之后后端：
  sudo systemctl restart media-downloader
"""
import os
import time
from playwright.sync_api import sync_playwright

STEALTH = os.environ.get("STEALTH_JS_PATH", "stealth.min.js")
PROFILE = os.environ.get("XHS_PROFILE_DIR", "/root/.xhs_profile")


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
    # 持久化 profile（与后端 xhs_runtime 同一 profile，a1+指纹一致）
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE,
        headless=False,  # 图形界面显示，可手动过验证码
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    if os.path.exists(STEALTH):
        ctx.add_init_script(path=STEALTH)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded")
    time.sleep(4)

    # 点登录（默认二维码扫码）
    click_first(page, ['text=登录', 'button:has-text("登录")'], "login-btn")
    time.sleep(4)
    print(">>> 浏览器已打开，用手机小红书 App 扫码登录")

    # 等扫码登录
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

    # 导航笔记页，触发可能的验证码，手动过
    print(">>> 导航笔记页，如出验证码/滑块请在浏览器手动过")
    try:
        page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
    except Exception:
        pass
    time.sleep(2)
    print(">>> 验证码过了（或没出现）后，回此终端按回车继续")
    input()

    # 多浏览建立信任
    try:
        page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
        time.sleep(3)
    except Exception:
        pass

    cookies = ctx.cookies()
    xhs = [c for c in cookies if "xiaohongshu.com" in c["domain"]]
    print("=== profile 已保存（后端自动加载）===")
    print("a1:", next((c["value"][:20] for c in xhs if c["name"] == "a1"), "无"))
    print("web_session:", next((c["value"][:20] for c in xhs if c["name"] == "web_session"), "无"))
    print(">>> 重启后端：sudo systemctl restart media-downloader")
    ctx.close()
