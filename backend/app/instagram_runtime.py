"""Instagram backend runtime: instaloader 解析 + 缓存 + 限流缓解。

限流缓解：
- 内存缓存 shortcode→result（TTL 1h），重复解析不请求 Instagram
- 请求间隔 ≥8s，降低累积触发
- embed 优先（单视频帖省 graphql）
- 401 限流友好错误（不重试轰炸）
"""
import os
import re
import time
from urllib.parse import urlparse, parse_qs

_L = None
_cache = {}  # shortcode -> (result, timestamp)
_last_request_ts = 0
CACHE_TTL = 3600
REQUEST_INTERVAL = 8

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def init():
    """启动时初始化 Instaloader 实例并加载 cookie/session（若有）。"""
    global _L
    from instaloader import Instaloader

    _L = Instaloader(quiet=True, user_agent=DESKTOP_UA)
    session_user = os.environ.get("INSTAGRAM_USERNAME", "")
    if session_user:
        try:
            _L.load_session_from_file(session_user)
            print(f"[instagram] loaded session for {session_user}")
        except Exception as e:
            print(f"[instagram] session load failed (non-fatal): {e}")
    cookie_str = os.environ.get("INSTAGRAM_COOKIE", "")
    if cookie_str:
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                _L.context._session.cookies.set(k.strip(), v.strip(), domain=".instagram.com")


def _wait_interval():
    """连续请求间隔，降低限流触发。"""
    global _last_request_ts
    now = time.time()
    wait = REQUEST_INTERVAL - (now - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


def _meta(html, prop):
    import re as _re
    m = _re.search(rf'<meta[^>]*(?:property|name)=["\']{_re.escape(prop)}["\'][^>]*content=["\']([^"\']+)["\']', html, _re.I)
    if m:
        return m[1]
    m = _re.search(rf'<meta[^>]*content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{_re.escape(prop)}["\']', html, _re.I)
    return m[1] if m else None


def _try_embed(shortcode, original_url):
    """embed 页拿 og:video（单视频帖直接返回，不限流）。单图/图集返回 None 走 graphql。"""
    import httpx
    try:
        r = httpx.get(
            f"https://www.instagram.com/p/{shortcode}/embed/",
            timeout=15,
            headers={"User-Agent": DESKTOP_UA},
        )
        html = r.text
        og_video = _meta(html, "og:video") or _meta(html, "og:video:url") or _meta(html, "og:video:secure_url")
        if og_video:
            og_image = _meta(html, "og:image") or ""
            og_title = _meta(html, "og:title") or _meta(html, "og:description") or ""
            return {
                "platform": "instagram",
                "media_type": "video",
                "title": og_title,
                "author": "",
                "cover": og_image,
                "items": [{"url": og_video}],
                "original_url": original_url,
            }
    except Exception:
        pass
    return None


def _shortcode_to_media_id(shortcode):
    """Instagram shortcode -> media_id (base64url 解码)。"""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    num = 0
    for c in shortcode:
        if c in alphabet:
            num = num * 64 + alphabet.index(c)
    return num


def _ig_cookies():
    """从 instaloader session 取 instagram cookie dict。"""
    return {c.name: c.value for c in _L.context._session.cookies if "instagram.com" in (c.domain or "")}


def _try_private_api(shortcode, original_url):
    """私有 API i.instagram.com/api/v1/media/{id}/info/（不同端点类，限流可能更宽松）。"""
    import httpx
    media_id = _shortcode_to_media_id(shortcode)
    if not media_id:
        return None
    try:
        r = httpx.get(
            f"https://i.instagram.com/api/v1/media/{media_id}/info/",
            timeout=15,
            headers={
                "User-Agent": "Instagram 76.0.0.15.395 Android (default)",
                "x-ig-app-id": "936619743392459",
            },
            cookies=_ig_cookies(),
        )
        if r.status_code != 200:
            return None
        data = r.json()
        items = data.get("items") or []
        if not items:
            return None
        item = items[0]
        media_type = item.get("media_type")
        title = item.get("caption", "") if isinstance(item.get("caption"), str) else ""
        user = item.get("user") or {}
        author = user.get("username", "")

        def best_img(versions):
            cands = (versions or {}).get("candidates") or []
            if not cands:
                return ""
            # 取最大 width 的（高清原图），不是 [-1]（可能是缩略图）
            best = max(cands, key=lambda c: c.get("width", 0) or 0)
            return best.get("url", "")

        def best_vid(versions_list):
            vv = versions_list or []
            if not vv:
                return ""
            best = max(vv, key=lambda c: c.get("width", 0) or 0)
            return best.get("url", "")

        # 图集 carousel_media
        carousel = item.get("carousel_media")
        if carousel:
            media_items = []
            for cm in carousel:
                if cm.get("video_versions"):
                    media_items.append({"url": best_vid(cm.get("video_versions"))})
                else:
                    media_items.append({"url": best_img(cm.get("image_versions2"))})
            media_items = [m for m in media_items if m["url"]]
            if media_items:
                return {
                    "platform": "instagram",
                    "media_type": "album",
                    "title": title,
                    "author": author,
                    "cover": media_items[0]["url"],
                    "items": media_items,
                    "original_url": original_url,
                }

        # 单视频
        if media_type == 2 or item.get("video_versions"):
            vurl = best_vid(item.get("video_versions"))
            cover = best_img(item.get("image_versions2"))
            return {
                "platform": "instagram",
                "media_type": "video",
                "title": title,
                "author": author,
                "cover": cover,
                "items": [{"url": vurl}],
                "original_url": original_url,
            }

        # 单图
        img = best_img(item.get("image_versions2"))
        return {
            "platform": "instagram",
            "media_type": "image",
            "title": title,
            "author": author,
            "cover": img,
            "items": [{"url": img}],
            "original_url": original_url,
        }
    except Exception:
        return None


def _parse_graphql(shortcode, original_url):
    """instaloader graphql 解析（单图/图集）。"""
    from instaloader import Post
    post = Post.from_shortcode(_L.context, shortcode)
    node = post._node
    title = post.caption or ""
    try:
        author = post.owner_profile.username if post.owner_profile else ""
    except Exception:
        author = ""

    sidecar = node.get("edge_sidecar_to_children")
    if sidecar:
        items = []
        for e in sidecar.get("edges", []):
            n = e.get("node", {}) or {}
            u = n.get("video_url") if n.get("is_video") else n.get("display_url")
            if u:
                items.append({"url": u})
        if items:
            return {
                "platform": "instagram",
                "media_type": "album",
                "title": title,
                "author": author,
                "cover": items[0]["url"],
                "items": items,
                "original_url": original_url,
            }

    vurl = ""
    vv = node.get("video_versions")
    if vv:
        vurl = (vv[0] or {}).get("url", "") or ""
    if not vurl:
        try:
            vurl = post.video_url or ""
        except Exception:
            vurl = ""
    is_vid = False
    try:
        is_vid = post.is_video
    except Exception:
        pass
    if is_vid or vurl:
        cover = ""
        try:
            cover = post.url or ""
        except Exception:
            pass
        return {
            "platform": "instagram",
            "media_type": "video",
            "title": title,
            "author": author,
            "cover": cover,
            "items": [{"url": vurl}],
            "original_url": original_url,
        }

    img = ""
    try:
        img = post.url or ""
    except Exception:
        pass
    if not img:
        cands = (node.get("image_versions2") or {}).get("candidates", [])
        if cands:
            img = (cands[0] or {}).get("url", "") or ""
    return {
        "platform": "instagram",
        "media_type": "image",
        "title": title,
        "author": author,
        "cover": img,
        "items": [{"url": img}],
        "original_url": original_url,
    }


def parse(url):
    """解析 Instagram 链接。缓存 + 间隔 + embed 优先 + graphql + 401 友好。"""
    m = re.search(r"/(?:p|reel)/([\w-]+)", url)
    if not m:
        raise ValueError("无法提取 shortcode")
    shortcode = m[1]

    # 缓存命中（不请求网络，不计间隔）
    now = time.time()
    cached = _cache.get(shortcode)
    if cached and now - cached[1] < CACHE_TTL:
        return cached[0]

    # 请求间隔
    _wait_interval()

    # embed 优先（单视频帖）
    embed_result = _try_embed(shortcode, url)
    if embed_result:
        _cache[shortcode] = (embed_result, time.time())
        return embed_result

    # 私有 API（不同端点类，限流可能更宽松），失败回退 graphql
    private_result = _try_private_api(shortcode, url)
    if private_result:
        _cache[shortcode] = (private_result, time.time())
        return private_result

    # graphql（单图/图集）
    try:
        result = _parse_graphql(shortcode, url)
        _cache[shortcode] = (result, time.time())
        return result
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Please wait" in msg or "Unauthorized" in msg or "rate" in msg.lower():
            raise RuntimeError("Instagram 限流，请稍后重试（几分钟到几小时）") from e
        raise
