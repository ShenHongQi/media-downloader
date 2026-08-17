import re
from abc import ABC, abstractmethod

from app.models import MediaResult


class BaseParser(ABC):
    platform_name: str = ""
    url_patterns: list[re.Pattern] = []

    def detect(self, url: str) -> bool:
        return any(pattern.search(url) for pattern in self.url_patterns)

    @abstractmethod
    async def parse(self, url: str) -> MediaResult:
        ...
