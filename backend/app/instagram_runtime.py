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
    shortcode = m[2]

    post = Post.from_shortcode(_L.context, shortcode)
    title = post.caption or ""
    author = post.owner_profile.username if post.owner_profile else ""
    typename = post.typename

    if typename == "GraphVideo" or post.is_video:
        return {
            "platform": "instagram",
            "media_type": "video",
            "title": title,
            "author": author,
            "cover": post.url or "",
            "items": [{"url": post.video_url}],
            "original_url": url,
        }

    if typename == "GraphSidecar":
        items = []
        for edge in post.get_sidecar_edges():
            node = edge["node"]
            if node.get("is_video"):
                items.append({"url": node.get("video_url")})
            else:
                items.append({"url": node.get("display_url")})
        return {
            "platform": "instagram",
            "media_type": "album",
            "title": title,
            "author": author,
            "cover": items[0]["url"] if items else "",
            "items": items,
            "original_url": url,
        }

    # GraphImage
    return {
        "platform": "instagram",
        "media_type": "image",
        "title": title,
        "author": author,
        "cover": post.url or "",
        "items": [{"url": post.url or ""}],
        "original_url": url,
    }
