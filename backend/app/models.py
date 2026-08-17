from enum import Enum
from typing import Optional

from pydantic import BaseModel


class MediaType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    ALBUM = "album"


class Platform(str, Enum):
    DOUYIN = "douyin"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    XIAOHONGSHU = "xiaohongshu"
    KUAISHOU = "kuaishou"
    BILIBILI = "bilibili"


class MediaItem(BaseModel):
    url: str
    thumbnail: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    size: Optional[int] = None


class MediaResult(BaseModel):
    platform: Platform
    media_type: MediaType
    title: Optional[str] = None
    author: Optional[str] = None
    cover: Optional[str] = None
    items: list[MediaItem]
    original_url: str


class ParseRequest(BaseModel):
    urls: list[str]


class ParseResponse(BaseModel):
    results: list[Optional[MediaResult]]
    errors: list[Optional[dict]]
