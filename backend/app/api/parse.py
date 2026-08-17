import asyncio
import re
from typing import Optional

from fastapi import APIRouter, Query

from app.models import MediaResult, ParseRequest, ParseResponse
from app.parsers.registry import get_parser_for_url

router = APIRouter()

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def extract_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text)


async def _parse_single(url: str) -> tuple[Optional[MediaResult], Optional[dict]]:
    parser = get_parser_for_url(url)
    if not parser:
        return None, {"url": url, "error": "unsupported platform"}
    try:
        result = await asyncio.wait_for(parser.parse(url), timeout=15)
        return result, None
    except asyncio.TimeoutError:
        return None, {"url": url, "error": "timeout"}
    except Exception as e:
        return None, {"url": url, "error": str(e)}


@router.post("/parse", response_model=ParseResponse)
async def parse_urls(request: ParseRequest):
    tasks = [_parse_single(url) for url in request.urls]
    pairs = await asyncio.gather(*tasks)
    results = [r for r, _ in pairs]
    errors = [e for _, e in pairs]
    return ParseResponse(results=results, errors=errors)


@router.get("/parse")
async def parse_single_url(url: str = Query(...)):
    result, error = await _parse_single(url)
    if error:
        return {"result": None, "error": error}
    return {"result": result, "error": None}
