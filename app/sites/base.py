from __future__ import annotations
from abc import ABC, abstractmethod

from app.core.models import Manga, Chapter
from app.utils.headers import get_default_headers, get_image_headers, get_random_ua


class BaseSite(ABC):
    name: str = ""
    base_url: str = ""

    @classmethod
    @abstractmethod
    def matches(cls, url: str) -> bool:
        """Return True if this plugin handles the given URL."""

    @abstractmethod
    async def parse_manga_info(self, url: str) -> Manga:
        """Fetch and parse manga metadata + chapter list from the manga page URL."""

    @abstractmethod
    async def parse_chapter_images(self, chapter_url: str) -> list[str]:
        """Fetch and return ordered list of image URLs for a chapter."""

    def get_image_headers(self, image_url: str) -> dict[str, str]:
        return get_image_headers(referer=self.base_url)

    def get_fetch_headers(self) -> dict[str, str]:
        return get_default_headers(referer=self.base_url)
