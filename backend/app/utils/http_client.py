from contextlib import asynccontextmanager
from typing import Optional

import httpx

from app.config import settings

_client: Optional[httpx.AsyncClient] = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout),
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Mobile/15E148 Safari/604.1"
                )
            },
        )
    return _client


async def close_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None


async def resolve_redirect(url: str) -> str:
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(10),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            )
        },
    ) as client:
        response = await client.head(url)
        if response.status_code in (301, 302, 303, 307, 308):
            return response.headers.get("location", url)
        return url
