"""小红书远程解析接口。App 端调用 POST /api/xhs。

注意：此接口依赖 Playwright + xhs 库，仅在服务端运行。
抖音/B站等平台的解析走 /api/parse（本地 parsers），与此无关。
"""
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import xhs_runtime

router = APIRouter()


class XhsRequest(BaseModel):
    url: str


@router.post("/xhs")
async def parse_xhs(req: XhsRequest):
    if xhs_runtime._client is None:
        raise HTTPException(503, "xhs client not initialized (playwright not ready)")
    try:
        result = await asyncio.to_thread(xhs_runtime.parse, req.url)
        return result
    except Exception as e:
        raise HTTPException(400, f"小红书解析失败: {e}")
