from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import download, parse
from app.parsers.registry import get_all_parsers
from app.utils.http_client import close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_all_parsers()
    yield
    await close_client()


app = FastAPI(title="Media Downloader", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router, prefix="/api")
app.include_router(download.router, prefix="/api")


@app.get("/api/platforms")
async def list_platforms():
    parsers = get_all_parsers()
    return [
        {"name": p.platform_name, "patterns": [pat.pattern for pat in p.url_patterns]}
        for p in parsers
    ]


@app.get("/api/health")
async def health():
    return {"status": "ok"}
