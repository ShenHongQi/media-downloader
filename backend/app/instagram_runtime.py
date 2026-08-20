"""Instagram backend runtime: 用 instaloader 库解析公开帖。

服务端运行。instaloader 基于 requests，尊重 HTTPS_PROXY 环境变量（阿里云国内需配代理才能访问 instagram）。
匿名可能被限，建议配 INSTAGRAM_COOKIE 环境变量（浏览器登录后复制的完整 cookie）。
"""
import os
import re

_L = None


def init():
    """启动时初始化 Instaloader 实例并加载 cookie/session（若有）。"""
    global _L
    from instaloader import Instaloader

    _L = Instaloader(
        quiet=True,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
    )
    # 优先加载 instaloader session 文件（用 instaloader -l 用户名 登录生成）
    session_user = os.environ.get("INSTAGRAM_USERNAME", "")
    if session_user:
        try:
            _L.load_session_from_file(session_user)
            print(f"[instagram] loaded session for {session_user}")
        except Exception as e:
            print(f"[instagram] session load failed (non-fatal): {e}")
    # 兼容：直接设 cookie 字符串
    cookie_str = os.environ.get("INSTAGRAM_COOKIE", "")
    if cookie_str:
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                _L.context._session.cookies.set(k.strip(), v.strip(), domain=".instagram.com")


def parse(url):
    """解析 Instagram 链接，返回 MediaResult 字典。在线程池调用。"""
    from instaloader import Post

    m = re.search(r"/(?:p|reel)/([\w-]+)", url)
    if not m:
        raise ValueError("无法提取 shortcode")
    shortcode = m[1]

    post = Post.from_shortcode(_L.context, shortcode)
    node = post._node
    title = post.caption or ""
    try:
        author = post.owner_profile.username if post.owner_profile else ""
    except Exception:
        author = ""

    # 优先用 edge_sidecar_to_children（图集/多图多视频，4.15.3 无 get_sidecar_edges）
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
                "original_url": url,
            }

    # 单视频：优先新版 video_versions，回退 post.video_url
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
            "original_url": url,
        }

    # 单图
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
        "original_url": url,
    }
