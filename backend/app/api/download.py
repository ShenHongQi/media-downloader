from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.models import Platform
from app.utils.http_client import get_client

router = APIRouter()

PLATFORM_HEADERS = {
    Platform.DOUYIN: {"Referer": "https://www.douyin.com/"},
    Platform.TIKTOK: {"Referer": "https://www.tiktok.com/"},
    Platform.INSTAGRAM: {"Referer": "https://www.instagram.com/"},
    Platform.XIAOHONGSHU: {"Referer": "https://www.xiaohongshu.com/"},
    Platform.KUAISHOU: {"Referer": "https://www.kuaishou.com/"},
    Platform.BILIBILI: {"Referer": "https://www.bilibili.com/"},
}


@router.get("/download")
async def download_proxy(
    url: str = Query(...),
    platform: Platform = Query(...),
    filename: str = Query(default=""),
):
    client = await get_client()
    headers = PLATFORM_HEADERS.get(platform, {})

    req = client.build_request("GET", url, headers=headers)
    resp = await client.send(req, stream=True)

    content_type = resp.headers.get("content-type", "application/octet-stream")
    content_length = resp.headers.get("content-length")

    response_headers = {}
    if content_length:
        response_headers["content-length"] = content_length
    if filename:
        response_headers["content-disposition"] = f'attachment; filename="{filename}"'

    async def stream():
        async for chunk in resp.aiter_bytes(chunk_size=65536):
            yield chunk
        await resp.aclose()

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers=response_headers,
    )
