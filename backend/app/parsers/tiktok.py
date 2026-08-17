import re

from app.models import MediaItem, MediaResult, MediaType, Platform
from app.parsers.base import BaseParser
from app.utils.http_client import get_client, resolve_redirect


class TiktokParser(BaseParser):
    platform_name = "tiktok"
    url_patterns = [
        re.compile(r"vm\.tiktok\.com/\w+"),
        re.compile(r"www\.tiktok\.com/@[^/]+/video/(\d+)"),
        re.compile(r"www\.tiktok\.com/t/\w+"),
    ]

    async def parse(self, url: str) -> MediaResult:
        video_id = await self._extract_video_id(url)
        detail = await self._fetch_detail(video_id)
        return self._build_result(detail, url)

    async def _extract_video_id(self, url: str) -> str:
        if "vm.tiktok.com" in url or "/t/" in url:
            url = await resolve_redirect(url)

        match = re.search(r"/video/(\d+)", url)
        if match:
            return match.group(1)

        raise ValueError(f"Cannot extract video_id from: {url}")

    async def _fetch_detail(self, video_id: str) -> dict:
        client = await get_client()
        resp = await client.get(
            f"https://www.tiktok.com/@placeholder/video/{video_id}",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            },
        )
        resp.raise_for_status()

        # Extract from __UNIVERSAL_DATA_FOR_REHYDRATION__
        match = re.search(
            r"<script id=\"__UNIVERSAL_DATA_FOR_REHYDRATION__\"[^>]*>(.+?)</script>",
            resp.text,
        )
        if not match:
            raise ValueError("Cannot find TikTok page data")

        import json

        data = json.loads(match.group(1))
        default_scope = data.get("__DEFAULT_SCOPE__", {})
        item_module = default_scope.get("webapp.video-detail", {})
        item_info = item_module.get("itemInfo", {}).get("itemStruct", {})

        if not item_info:
            raise ValueError(f"Cannot extract video info for: {video_id}")

        return item_info

    def _build_result(self, item: dict, original_url: str) -> MediaResult:
        video = item.get("video", {})
        play_addr = video.get("playAddr", "")
        if not play_addr:
            play_addr = video.get("downloadAddr", "")

        title = item.get("desc", "")
        author = item.get("author", {}).get("nickname", "")
        cover = video.get("cover", "")
        duration = video.get("duration", 0)

        return MediaResult(
            platform=Platform.TIKTOK,
            media_type=MediaType.VIDEO,
            title=title,
            author=author,
            cover=cover,
            items=[MediaItem(url=play_addr, duration=float(duration))],
            original_url=original_url,
        )
