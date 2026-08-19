"""Instagram 远程解析接口。App 端调用 POST /api/instagram。

依赖 instaloader + 服务器能访问 instagram（阿里云国内需配 HTTPS_PROXY 代理）。
"""
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import instagram_runtime

router = APIRouter()


class InstagramRequest(BaseModel):
    url: str


@router.post("/instagram")
async def parse_instagram(req: InstagramRequest):
    if instagram_runtime._L is None:
        raise HTTPException(503, "instagram client not initialized")
    try:
        result = await asyncio.to_thread(instagram_runtime.parse, req.url)
        return result
    except Exception as e:
        raise HTTPException(400, f"Instagram 解析失败: {e}")
