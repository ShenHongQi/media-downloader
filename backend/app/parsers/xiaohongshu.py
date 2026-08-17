import json
import re

from app.models import MediaItem, MediaResult, MediaType, Platform
from app.parsers.base import BaseParser
from app.utils.http_client import get_client, resolve_redirect


class XiaohongshuParser(BaseParser):
    platform_name = "xiaohongshu"
    url_patterns = [
        re.compile(r"www\.xiaohongshu\.com/explore/([a-f0-9]+)"),
        re.compile(r"www\.xiaohongshu\.com/discovery/item/([a-f0-9]+)"),
        re.compile(r"xhslink\.com/\w+"),
        re.compile(r"xhslink\.cn/\w+"),
    ]

    async def parse(self, url: str) -> MediaResult:
        note_url = await self._resolve_url(url)
        note_id = self._extract_note_id(note_url)
        page_data = await self._fetch_page_data(note_id)
        return self._build_result(page_data, url)

    async def _resolve_url(self, url: str) -> str:
        if "xhslink.com" in url or "xhslink.cn" in url:
            return await resolve_redirect(url)
        return url

    def _extract_note_id(self, url: str) -> str:
        for pattern in [
            r"/explore/([a-f0-9]+)",
            r"/discovery/item/([a-f0-9]+)",
        ]:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"Cannot extract note_id from: {url}")

    async def _fetch_page_data(self, note_id: str) -> dict:
        client = await get_client()
        resp = await client.get(
            f"https://www.xiaohongshu.com/explore/{note_id}",
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

        match = re.search(
            r"window\.__INITIAL_STATE__\s*=\s*(.+?)</script>", resp.text
        )
        if not match:
            raise ValueError("Cannot find __INITIAL_STATE__ in page")

        raw = match.group(1)
        # Xiaohongshu uses undefined as value in some places
        raw = raw.replace("undefined", "null")
        data = json.loads(raw)

        note_data = data.get("note", {}).get("noteDetailMap", {})
        if not note_data:
            raise ValueError(f"No note detail found for: {note_id}")

        # noteDetailMap is keyed by note_id
        detail = None
        for key in note_data:
            detail = note_data[key].get("note")
            break

        if not detail:
            raise ValueError(f"Cannot extract note content for: {note_id}")

        return detail

    def _build_result(self, note: dict, original_url: str) -> MediaResult:
        note_type = note.get("type", "")

        if note_type == "video":
            return self._build_video_result(note, original_url)
        return self._build_image_result(note, original_url)

    def _build_video_result(self, note: dict, original_url: str) -> MediaResult:
        video = note.get("video", {})
        media = video.get("media", {})
        stream = media.get("stream", {})

        video_url = ""
        # Try h264 streams first
        for quality in ("h264", "h265", "av1"):
            streams = stream.get(quality, [])
            if streams:
                video_url = streams[0].get("masterUrl", "")
                break

        if not video_url:
            # Fallback to consumer key
            key = video.get("consumer", {}).get("originVideoKey", "")
            if key:
                video_url = f"https://sns-video-bd.xhscdn.com/{key}"

        title = note.get("title", "") or note.get("desc", "")
        author = note.get("user", {}).get("nickname", "")
        cover = note.get("imageList", [{}])[0].get("urlDefault", "")

        return MediaResult(
            platform=Platform.XIAOHONGSHU,
            media_type=MediaType.VIDEO,
            title=title,
            author=author,
            cover=cover,
            items=[MediaItem(url=video_url)],
            original_url=original_url,
        )

    def _build_image_result(self, note: dict, original_url: str) -> MediaResult:
        image_list = note.get("imageList", [])
        media_items = []

        for img in image_list:
            # urlDefault is the original quality without watermark
            url = img.get("urlDefault", "")
            if not url:
                # Fallback to infoList highest quality
                info_list = img.get("infoList", [])
                if info_list:
                    url = info_list[-1].get("url", "")
            if url:
                if url.startswith("//"):
                    url = "https:" + url
                width = img.get("width")
                height = img.get("height")
                media_items.append(MediaItem(url=url, width=width, height=height))

        title = note.get("title", "") or note.get("desc", "")
        author = note.get("user", {}).get("nickname", "")

        return MediaResult(
            platform=Platform.XIAOHONGSHU,
            media_type=MediaType.ALBUM if len(media_items) > 1 else MediaType.IMAGE,
            title=title,
            author=author,
            cover=media_items[0].url if media_items else None,
            items=media_items,
            original_url=original_url,
        )
