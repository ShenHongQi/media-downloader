"""XHS backend runtime: 持久化 profile，登录与签名同一浏览器实例。

a1 绑定浏览器设备指纹，必须登录和签名用同一 persistent profile：
- xhs_login.py 在图形界面登录，profile 保存 a1+web_session+指纹
- 后端 init 加载同 profile，_webmsxyw 签名用一致 a1+指纹，不 SignError
"""
import os
import re
from urllib.parse import urlparse, parse_qs

STEALTH_JS_PATH = os.environ.get("STEALTH_JS_PATH", "/app/stealth.min.js")
PERSISTENT_PROFILE = os.environ.get("XHS_PROFILE_DIR", "/root/.xhs_profile")
HOME = "https://www.xiaohongshu.com"

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_playwright = None
_global_context = None
_global_page = None
_client = None


def init():
    """加载持久化 profile（xhs_login 登录过），等 _webmsxyw，用 profile 内 a1+web_session 建 XhsClient。"""
    global _playwright, _global_context, _global_page, _client
    from playwright.sync_api import sync_playwright
    from xhs import XhsClient

    _playwright = sync_playwright().start()
    headless = os.environ.get("XHS_HEADLESS", "1") == "1"
    _global_context = _playwright.chromium.launch_persistent_context(
        user_data_dir=PERSISTENT_PROFILE,
        headless=headless,
        user_agent=DESKTOP_UA,
        viewport={"width": 1280, "height": 800},
    )
    if os.path.exists(STEALTH_JS_PATH):
        _global_context.add_init_script(path=STEALTH_JS_PATH)

    _global_page = _global_context.pages[0] if _global_context.pages else _global_context.new_page()
    _global_page.goto(HOME, wait_until="domcontentloaded")
    _global_page.wait_for_function("typeof window._webmsxyw === 'function'", timeout=30000)
    _global_page.wait_for_timeout(2000)

    cookies = _global_context.cookies()
    a1 = next((c["value"] for c in cookies if c["name"] == "a1"), "")
    ws = next((c["value"] for c in cookies if c["name"] == "web_session"), "")
    webid = next((c["value"] for c in cookies if c["name"] == "webId"), "")
    if ws:
        cookie_str = f"a1={a1}; web_session={ws}"
        if webid:
            cookie_str += f"; webId={webid}"
    else:
        cookie_str = f"a1={a1}"
    _client = XhsClient(cookie_str, sign=_sign)


def close():
    try:
        if _global_context:
            _global_context.close()
    except Exception:
        pass
    try:
        if _playwright:
            _playwright.stop()
    except Exception:
        pass


def _sign(api, data=None, a1="", web_session=""):
    """签名：用同 profile 的 _webmsxyw（a1+指纹一致，不 SignError）。"""
    encrypt = _global_page.evaluate(
        "([url, data]) => window._webmsxyw(url, data)", [api, data]
    )
    return {"x-s": encrypt["X-s"], "x-t": str(encrypt["X-t"])}


def _resolve(url):
    import httpx
    with httpx.Client(
        follow_redirects=True,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"},
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
        return {"platform": "xiaohongshu", "media_type": "video", "title": title, "author": author, "cover": cover, "items": [{"url": video_url}], "original_url": url}
    img_urls = xhs_help.get_imgs_url_from_note(note) or []
    return {"platform": "xiaohongshu", "media_type": "album" if len(img_urls) > 1 else "image", "title": title, "author": author, "cover": img_urls[0] if img_urls else cover, "items": [{"url": u} for u in img_urls], "original_url": url}
