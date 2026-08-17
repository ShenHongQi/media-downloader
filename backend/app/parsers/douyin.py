import re

import httpx

from app.models import MediaItem, MediaResult, MediaType, Platform
from app.parsers.base import BaseParser
from app.utils.http_client import get_client, resolve_redirect


class DouyinParser(BaseParser):
    platform_name = "douyin"
    url_patterns = [
        re.compile(r"v\.douyin\.com/\w+"),
        re.compile(r"www\.douyin\.com/video/(\d+)"),
        re.compile(r"www\.douyin\.com/note/(\d+)"),
        re.compile(r"www\.iesdouyin\.com/share/(?:video|note)/(\d+)"),
    ]

    async def parse(self, url: str) -> MediaResult:
        aweme_id = await self._extract_aweme_id(url)
        ttwid = await self._get_ttwid()
        detail = await self._fetch_detail(aweme_id, ttwid)
        return self._build_result(detail, url)

    async def _extract_aweme_id(self, url: str) -> str:
        if "v.douyin.com" in url:
            url = await resolve_redirect(url)

        for pattern in [r"/video/(\d+)", r"/note/(\d+)", r"modal_id=(\d+)"]:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Cannot extract aweme_id from: {url}")

    async def _get_ttwid(self) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://ttwid.bytedance.com/ttwid/union/register/",
                json={
                    "region": "cn",
                    "aid": 1128,
                    "needFid": False,
                    "service": "www.douyin.com",
                    "migrate_info": {"ticket": "", "source": "node"},
                    "cbUrlProtocol": "https",
                    "union": True,
                },
            )
            ttwid = resp.cookies.get("ttwid")
            if not ttwid:
                raise ValueError("Failed to obtain ttwid")
            return ttwid

    async def _fetch_detail(self, aweme_id: str, ttwid: str) -> dict:
        client = await get_client()
        resp = await client.get(
            "https://www.douyin.com/aweme/v1/web/aweme/detail/",
            params={"aweme_id": aweme_id, "aid": "6383"},
            headers={
                "Referer": "https://www.douyin.com/",
                "Cookie": f"ttwid={ttwid}",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        detail = data.get("aweme_detail")
        if not detail:
            raise ValueError(f"No detail found for aweme_id: {aweme_id}")
        return detail

    def _build_result(self, detail: dict, original_url: str) -> MediaResult:
        images = detail.get("images")
        if images:
            return self._build_album_result(detail, original_url)
        return self._build_video_result(detail, original_url)

    def _build_video_result(self, detail: dict, original_url: str) -> MediaResult:
        video = detail.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])

        video_url = url_list[0] if url_list else ""

        cover = video.get("cover", {}).get("url_list", [""])[0]
        title = detail.get("desc", "")
        author = detail.get("author", {}).get("nickname", "")
        duration = video.get("duration", 0) / 1000.0

        return MediaResult(
            platform=Platform.DOUYIN,
            media_type=MediaType.VIDEO,
            title=title,
            author=author,
            cover=cover,
            items=[MediaItem(url=video_url, duration=duration)],
            original_url=original_url,
        )

    def _build_album_result(self, detail: dict, original_url: str) -> MediaResult:
        images = detail.get("images", [])
        media_items = []
        for img in images:
            url_list = img.get("url_list", [])
            if url_list:
                media_items.append(MediaItem(url=url_list[-1]))

        title = detail.get("desc", "")
        author = detail.get("author", {}).get("nickname", "")

        return MediaResult(
            platform=Platform.DOUYIN,
            media_type=MediaType.ALBUM,
            title=title,
            author=author,
            cover=media_items[0].url if media_items else None,
            items=media_items,
            original_url=original_url,
        )
