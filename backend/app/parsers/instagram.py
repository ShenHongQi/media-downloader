import json
import re

from app.models import MediaItem, MediaResult, MediaType, Platform
from app.parsers.base import BaseParser
from app.utils.http_client import get_client


class InstagramParser(BaseParser):
    platform_name = "instagram"
    url_patterns = [
        re.compile(r"www\.instagram\.com/p/([\w-]+)"),
        re.compile(r"www\.instagram\.com/reel/([\w-]+)"),
        re.compile(r"instagram\.com/p/([\w-]+)"),
        re.compile(r"instagram\.com/reel/([\w-]+)"),
    ]

    async def parse(self, url: str) -> MediaResult:
        shortcode = self._extract_shortcode(url)
        detail = await self._fetch_detail(shortcode)
        return self._build_result(detail, url)

    def _extract_shortcode(self, url: str) -> str:
        match = re.search(r"/(?:p|reel)/([\w-]+)", url)
        if match:
            return match.group(1)
        raise ValueError(f"Cannot extract shortcode from: {url}")

    async def _fetch_detail(self, shortcode: str) -> dict:
        client = await get_client()

        # Method: use the embed page which doesn't require auth
        resp = await client.get(
            f"https://www.instagram.com/p/{shortcode}/embed/captioned/",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        resp.raise_for_status()

        # Try to extract media from embed page
        # Look for video URL
        video_match = re.search(r'"video_url":"([^"]+)"', resp.text)
        # Look for display URL (image)
        image_match = re.search(r'"display_url":"([^"]+)"', resp.text)
        # Look for caption
        caption_match = re.search(
            r'<div class="Caption"[^>]*>.*?<span[^>]*>(.*?)</span>',
            resp.text,
            re.DOTALL,
        )

        # Also try GraphQL approach via the page source
        gql_match = re.search(
            r'window\.__additionalDataLoaded\([^,]+,\s*({.+?})\);', resp.text
        )

        media_data = {}
        if gql_match:
            try:
                data = json.loads(gql_match.group(1))
                media = data.get("shortcode_media", {})
                if media:
                    media_data = media
            except json.JSONDecodeError:
                pass

        if media_data:
            return media_data

        # Fallback: build from regex matches
        result = {"shortcode": shortcode}
        if video_match:
            result["video_url"] = video_match.group(1).replace("\\u0026", "&")
            result["is_video"] = True
        if image_match:
            result["display_url"] = image_match.group(1).replace("\\u0026", "&")
        if caption_match:
            result["caption"] = re.sub(r"<[^>]+>", "", caption_match.group(1)).strip()

        if not result.get("video_url") and not result.get("display_url"):
            raise ValueError(
                f"Cannot extract media from Instagram post: {shortcode}. "
                "This may require authentication cookies."
            )

        return result

    def _build_result(self, data: dict, original_url: str) -> MediaResult:
        # Full GraphQL response
        if "edge_sidecar_to_children" in data:
            return self._build_album_result(data, original_url)

        if data.get("is_video") or data.get("video_url"):
            return self._build_video_result(data, original_url)

        return self._build_image_result(data, original_url)

    def _build_video_result(self, data: dict, original_url: str) -> MediaResult:
        video_url = data.get("video_url", "")
        title = data.get("caption", "") or data.get(
            "edge_media_to_caption", {}
        ).get("edges", [{}])[0].get("node", {}).get("text", "")
        author = data.get("owner", {}).get("username", "")
        cover = data.get("display_url", "") or data.get("thumbnail_src", "")

        return MediaResult(
            platform=Platform.INSTAGRAM,
            media_type=MediaType.VIDEO,
            title=title[:200] if title else "",
            author=author,
            cover=cover,
            items=[MediaItem(url=video_url)],
            original_url=original_url,
        )

    def _build_image_result(self, data: dict, original_url: str) -> MediaResult:
        display_url = data.get("display_url", "")
        title = data.get("caption", "") or data.get(
            "edge_media_to_caption", {}
        ).get("edges", [{}])[0].get("node", {}).get("text", "")
        author = data.get("owner", {}).get("username", "")

        return MediaResult(
            platform=Platform.INSTAGRAM,
            media_type=MediaType.IMAGE,
            title=title[:200] if title else "",
            author=author,
            cover=display_url,
            items=[MediaItem(url=display_url)],
            original_url=original_url,
        )

    def _build_album_result(self, data: dict, original_url: str) -> MediaResult:
        edges = data["edge_sidecar_to_children"].get("edges", [])
        items = []
        for edge in edges:
            node = edge.get("node", {})
            if node.get("is_video"):
                items.append(MediaItem(url=node.get("video_url", "")))
            else:
                items.append(MediaItem(url=node.get("display_url", "")))

        title = data.get("edge_media_to_caption", {}).get("edges", [{}])[0].get(
            "node", {}
        ).get("text", "")
        author = data.get("owner", {}).get("username", "")

        return MediaResult(
            platform=Platform.INSTAGRAM,
            media_type=MediaType.ALBUM,
            title=title[:200] if title else "",
            author=author,
            cover=items[0].url if items else None,
            items=items,
            original_url=original_url,
        )
