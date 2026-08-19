import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import download, instagram, parse, xhs
from app.parsers.registry import get_all_parsers
from app.utils.http_client import close_client
from app import xhs_runtime
from app import instagram_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_all_parsers()
    # XHS backend (Playwright + xhs). Failures here are non-fatal for other platforms.
    if os.environ.get("XHS_BACKEND", "1") == "1":
        try:
            await asyncio.to_thread(xhs_runtime.init)
            print("[xhs] backend initialized")
        except Exception as e:
            print(f"[xhs] backend init failed (non-fatal): {e}")
    # Instagram backend (instaloader). Non-fatal.
    if os.environ.get("INSTAGRAM_BACKEND", "1") == "1":
        try:
            await asyncio.to_thread(instagram_runtime.init)
            print("[instagram] backend initialized")
        except Exception as e:
            print(f"[instagram] backend init failed (non-fatal): {e}")
    yield
    await close_client()
    await asyncio.to_thread(xhs_runtime.close)


app = FastAPI(title="Media Downloader", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router, prefix="/api")
app.include_router(download.router, prefix="/api")
app.include_router(xhs.router, prefix="/api")
app.include_router(instagram.router, prefix="/api")


@app.get("/api/platforms")
async def list_platforms():
    parsers = get_all_parsers()
    return [
        {"name": p.platform_name, "patterns": [pat.pattern for pat in p.url_patterns]}
        for p in parsers
    ]


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "xhs_ready": xhs_runtime._client is not None,
        "instagram_ready": instagram_runtime._L is not None,
    }


# Serve frontend static files (for standalone exe mode)
_frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="static")
