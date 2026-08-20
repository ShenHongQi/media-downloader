"""XHS backend runtime: 常驻 Playwright 浏览器调用小红书 _webmsxyw 生成签名，
通过 xhs 库的 XhsClient 获取笔记数据。

仅在服务端运行（云主机），App 端通过 /api/xhs 远程调用。
抖音/B站等平台不走此模块，不受影响。

cookie 策略：
- 匿名 a1 会被风控（code -1 / 300011）。需登录态 XHS_COOKIE（a1+web_session+webId）。
- a1 必须与 web_session 登录设备一致 → 用 xhs_login.py 在服务器本地登录生成。
- 设 cookie 后不 reload（reload 触发 _webmsxyw 浏览器检测 SignError）。
"""
import os
import re
from urllib.parse import urlparse, parse_qs

STEALTH_JS_PATH = os.environ.get("STEALTH_JS_PATH", "/app/stealth.min.js")
HOME = "https://www.xiaohongshu.com"

_playwright = None
_browser = None
_global_page = None
_client = None


def init():
    """启动时常驻初始化：启动 Chromium、设 cookie（若有）、等 _webmsxyw 挂载、建 XhsClient。"""
    global _playwright, _browser, _global_page, _client
    from playwright.sync_api import sync_playwright
    from xhs import XhsClient

    _playwright = sync_playwright().start()
    headless = os.environ.get("XHS_HEADLESS", "1") == "1"
    _browser = _playwright.chromium.launch(headless=headless)
    ctx = _browser.new_context()
    if os.path.exists(STEALTH_JS_PATH):
        ctx.add_init_script(path=STEALTH_JS_PATH)

    user_cookie = os.environ.get("XHS_COOKIE", "")
    if user_cookie:
        for pair in user_cookie.split(";"):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                ctx.add_cookies([{"name": k.strip(), "value": v.strip(), "domain": ".xiaohongshu.com", "path": "/"}])

    _global_page = ctx.new_page()
    _global_page.goto(HOME, wait_until="domcontentloaded")
    _global_page.wait_for_function("typeof window._webmsxyw === 'function'", timeout=30000)
    _global_page.wait_for_timeout(2000)

    if user_cookie:
        cookie_str = user_cookie
    else:
        a1 = next((c["value"] for c in ctx.cookies() if c["name"] == "a1"), "")
        cookie_str = f"a1={a1}"
    _client = XhsClient(cookie_str, sign=_sign)


def close():
    global _playwright, _browser
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    try:
        if _playwright:
            _playwright.stop()
    except Exception:
        pass


def _sign(api, data=None, a1="", web_session=""):
    """xhs 库要求的签名函数：返回 {'x-s','x-t'}。用常驻 page 调 _webmsxyw（不 reload）。"""
    encrypt = _global_page.evaluate(
        "([url, data]) => window._webmsxyw(url, data)", [api, data]
    )
    return {"x-s": encrypt["X-s"], "x-t": str(encrypt["X-t"])}


def _resolve(url):
    """跟随短链重定向，提取 note_id 和 xsec_token。"""
    import httpx

    with httpx.Client(
        follow_redirects=True,
        timeout=15,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
            )
        },
    ) as c:
        r = c.get(url)
        final = str(r.url)

    m = re.search(r"/(?:explore|discovery/item|item|notes?)/([A-Za-z0-9_-]{16,32})", final)
    if not m:
        raise ValueError("无法提取 note_id: " + final[:120])
    note_id = m.group(1)
    xsec_token = parse_qs(urlparse(final).query).get("xsec_token", [""])[0]
    return note_id, xsec_token


def parse(url):
    """解析小红书链接，返回 MediaResult 字典。在线程池中调用（同步阻塞）。"""
    from xhs import help as xhs_help

    note_id, xsec_token = _resolve(url)
    try:
        note = _client.get_note_by_id(note_id, xsec_token)
    except TypeError:
        note = _client.get_note_by_id(note_id)

    title = (note.get("title") or note.get("desc") or "") or ""
    author = (note.get("user") or {}).get("nickname", "") or ""

    image_list = note.get("image_list") or []
    cover = ""
    if image_list:
        first = image_list[0] or {}
        cover = first.get("url_default") or first.get("url", "") or ""

    try:
        video_url = xhs_help.get_video_url_from_note(note)
    except Exception:
        video_url = None

    if video_url:
        return {
            "platform": "xiaohongshu",
            "media_type": "video",
            "title": title,
            "author": author,
            "cover": cover,
            "items": [{"url": video_url}],
            "original_url": url,
        }

    img_urls = xhs_help.get_imgs_url_from_note(note) or []
    return {
        "platform": "xiaohongshu",
        "media_type": "album" if len(img_urls) > 1 else "image",
        "title": title,
        "author": author,
        "cover": img_urls[0] if img_urls else cover,
        "items": [{"url": u} for u in img_urls],
        "original_url": url,
    }
