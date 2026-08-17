import re

from app.models import MediaItem, MediaResult, MediaType, Platform
from app.parsers.base import BaseParser
from app.utils.http_client import get_client, resolve_redirect


class BilibiliParser(BaseParser):
    platform_name = "bilibili"
    url_patterns = [
        re.compile(r"www\.bilibili\.com/video/(BV\w+)"),
        re.compile(r"b23\.tv/\w+"),
        re.compile(r"m\.bilibili\.com/video/(BV\w+)"),
    ]

    async def parse(self, url: str) -> MediaResult:
        bvid = await self._extract_bvid(url)
        video_info = await self._fetch_video_info(bvid)
        cid = video_info["cid"]
        play_url = await self._fetch_play_url(bvid, cid)
        return self._build_result(video_info, play_url, url)

    async def _extract_bvid(self, url: str) -> str:
        if "b23.tv" in url:
            url = await resolve_redirect(url)

        match = re.search(r"/(BV\w+)", url)
        if match:
            return match.group(1)
        raise ValueError(f"Cannot extract BV id from: {url}")

    async def _fetch_video_info(self, bvid: str) -> dict:
        client = await get_client()
        resp = await client.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            headers={"Referer": "https://www.bilibili.com/"},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise ValueError(f"Bilibili API error: {data.get('message')}")

        info = data["data"]
        return {
            "bvid": bvid,
            "cid": info["cid"],
            "title": info.get("title", ""),
            "author": info.get("owner", {}).get("name", ""),
            "cover": info.get("pic", ""),
            "duration": info.get("duration", 0),
        }

    async def _fetch_play_url(self, bvid: str, cid: int) -> str:
        client = await get_client()
        resp = await client.get(
            "https://api.bilibili.com/x/player/playurl",
            params={
                "bvid": bvid,
                "cid": cid,
                "qn": 80,
                "fnval": 1,
                "fourk": 1,
            },
            headers={"Referer": "https://www.bilibili.com/"},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise ValueError(f"Bilibili playurl error: {data.get('message')}")

        durl = data["data"].get("durl", [])
        if durl:
            return durl[0].get("url", "")

        raise ValueError("No play URL found")

    def _build_result(
        self, info: dict, play_url: str, original_url: str
    ) -> MediaResult:
        return MediaResult(
            platform=Platform.BILIBILI,
            media_type=MediaType.VIDEO,
            title=info["title"],
            author=info["author"],
            cover=info["cover"],
            items=[MediaItem(url=play_url, duration=float(info["duration"]))],
            original_url=original_url,
        )
