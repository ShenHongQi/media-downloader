import re

from app.models import MediaItem, MediaResult, MediaType, Platform
from app.parsers.base import BaseParser
from app.utils.http_client import get_client, resolve_redirect


class KuaishouParser(BaseParser):
    platform_name = "kuaishou"
    url_patterns = [
        re.compile(r"v\.kuaishou\.com/\w+"),
        re.compile(r"www\.kuaishou\.com/short-video/(\w+)"),
        re.compile(r"m\.gifshow\.com/\w+"),
    ]

    async def parse(self, url: str) -> MediaResult:
        photo_id = await self._extract_photo_id(url)
        detail = await self._fetch_detail(photo_id)
        return self._build_result(detail, url)

    async def _extract_photo_id(self, url: str) -> str:
        if "v.kuaishou.com" in url or "m.gifshow.com" in url:
            url = await resolve_redirect(url)

        match = re.search(r"/short-video/(\w+)", url)
        if match:
            return match.group(1)

        match = re.search(r"photoId=(\w+)", url)
        if match:
            return match.group(1)

        match = re.search(r"/fw/photo/(\w+)", url)
        if match:
            return match.group(1)

        raise ValueError(f"Cannot extract photo_id from: {url}")

    async def _fetch_detail(self, photo_id: str) -> dict:
        client = await get_client()
        resp = await client.post(
            "https://v.m.chenzhongtech.com/rest/wd/photo/info",
            json={"photoId": photo_id, "isLongVideo": False},
            headers={
                "Referer": "https://v.kuaishou.com/",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") != 1:
            raise ValueError(f"Kuaishou API error: {data}")

        return data

    def _build_result(self, data: dict, original_url: str) -> MediaResult:
        photo = data.get("photo", {})
        main_url = photo.get("mainMvUrl", "")
        if not main_url:
            main_url = photo.get("photoUrl", "")

        title = photo.get("caption", "")
        author = data.get("user", {}).get("userName", "")
        cover = photo.get("coverUrl", "")
        duration = photo.get("duration", 0) / 1000.0

        return MediaResult(
            platform=Platform.KUAISHOU,
            media_type=MediaType.VIDEO,
            title=title,
            author=author,
            cover=cover,
            items=[MediaItem(url=main_url, duration=duration)],
            original_url=original_url,
        )
