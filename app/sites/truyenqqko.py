from __future__ import annotations
import re
import asyncio
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from app.sites.base import BaseSite
from app.core.models import Manga, Chapter
from app.utils.headers import get_default_headers, get_random_ua
from app.utils.logger import logger

_VI_CHAPTER_RE = re.compile(r'^(chương|chap|ch)\s*', re.IGNORECASE)


def _normalize_chapter_title(title: str) -> str:
    """Replace Vietnamese/short chapter prefixes with 'Chapter'."""
    return _VI_CHAPTER_RE.sub(lambda m: "Chapter ", title).strip()


class TruyenQQKo(BaseSite):
    name = "truyenqqko"
    base_url = "https://truyenqqko.com"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "truyenqqko" in url.lower()

    async def parse_manga_info(self, url: str) -> Manga:
        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        title = self._parse_title(soup)
        cover_url = self._parse_cover(soup)
        author = self._parse_author(soup)
        description = self._parse_description(soup)
        chapters = self._parse_chapters(soup)

        if not chapters:
            raise ValueError(
                "Không tìm thấy danh sách chapter.\n"
                "URL có thể là trang chapter, trang chủ, hoặc trang tìm kiếm — "
                "hãy dùng URL trang thông tin truyện (ví dụ: /truyen-tranh/<tên-truyện>)."
            )

        return Manga(
            title=title,
            url=url,
            cover_url=cover_url,
            author=author,
            description=description,
            site_name=self.name,
            chapters=chapters,
        )

    async def parse_chapter_images(self, chapter_url: str) -> list[str]:
        html = await self._fetch_html(chapter_url)
        soup = BeautifulSoup(html, "lxml")
        return self._parse_images(soup)

    # ─── private helpers ────────────────────────────────────────────────────

    def _parse_title(self, soup: BeautifulSoup) -> str:
        for selector in ("h1.title-detail", ".story-detail h1", "h1.chapter-title", "h1"):
            el = soup.select_one(selector)
            if el:
                return el.get_text(strip=True)
        return "Unknown"

    def _parse_cover(self, soup: BeautifulSoup) -> Optional[str]:
        for selector in (
            ".book_avatar img",
            ".col-image img",
            ".story-detail img",
            ".info-img img",
        ):
            el = soup.select_one(selector)
            if el:
                src = el.get("src") or el.get("data-src", "")
                if src:
                    return src if src.startswith("http") else self.base_url + src
        return None

    def _parse_author(self, soup: BeautifulSoup) -> Optional[str]:
        # Look for <li> containing "tác giả" label
        for li in soup.select(".list-info li, .info li"):
            label = li.select_one(".name, label, b, strong")
            if label and "tác giả" in label.get_text(strip=True).lower():
                link = li.select_one("a")
                if link:
                    return link.get_text(strip=True)
                # Fallback: grab all text after label
                text = li.get_text(strip=True)
                after = text[text.lower().find("tác giả") + 7:].strip(": ")
                return after or None
        return None

    def _parse_description(self, soup: BeautifulSoup) -> Optional[str]:
        for selector in (".detail-content p", "#noidung", ".story-detail .story-detail-info"):
            el = soup.select_one(selector)
            if el:
                return el.get_text(strip=True)
        return None

    def _parse_chapters(self, soup: BeautifulSoup) -> list[Chapter]:
        chapters: list[Chapter] = []

        # Common chapter list selectors for truyenqqko-style sites
        link_els = (
            soup.select("#list-chapter .chapter a")
            or soup.select(".list-chapter li a")
            or soup.select("ul.list-chapter a")
            or soup.select(".works-chapter-item a")
        )

        if not link_els:
            logger.warning("No chapter links found — page structure may have changed")
            return chapters

        # The site usually shows newest chapter first; reverse to get ch1 first
        for a in reversed(link_els):
            href = a.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = self.base_url.rstrip("/") + "/" + href.lstrip("/")
            chap_title = _normalize_chapter_title(a.get_text(strip=True))
            number = self._extract_chapter_number(chap_title, href)
            chapters.append(Chapter(title=chap_title, url=href, number=number))

        return chapters

    def _extract_chapter_number(self, title: str, url: str = "") -> float:
        # Try from title first
        m = re.search(r'(?:chapter|chap|ch)[.\s_-]*(\d+(?:[.,]\d+)?)', title, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", "."))
        # Try from URL
        m = re.search(r'chapter[_-](\d+(?:[_-]\d+)?)', url, re.IGNORECASE)
        if m:
            return float(m.group(1).replace("-", ".").replace("_", "."))
        # Fallback: first standalone number
        m = re.search(r'\b(\d+(?:\.\d+)?)\b', title)
        if m:
            return float(m.group(1))
        return 0.0

    def _parse_images(self, soup: BeautifulSoup) -> list[str]:
        images: list[str] = []

        img_els = (
            soup.select(".page-chapter img")
            or soup.select("#vContent img")
            or soup.select(".reading-detail img")
            or soup.select(".chapter-content img")
        )

        for img in img_els:
            src = img.get("data-src") or img.get("src") or ""
            src = src.strip()
            if not src or src.endswith(".gif"):
                continue
            if not src.startswith("http"):
                src = self.base_url.rstrip("/") + "/" + src.lstrip("/")
            images.append(src)

        return images

    async def _fetch_html(self, url: str) -> str:
        headers = self.get_fetch_headers()
        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=False, timeout=timeout) as resp:
                    resp.raise_for_status()
                    return await resp.text(errors="replace")
        except aiohttp.ClientResponseError as e:
            if e.status in (403, 503):
                logger.warning(f"Got {e.status}, trying cloudscraper fallback for {url}")
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_html_cloudscraper, url
                )
            raise

    def _fetch_html_cloudscraper(self, url: str) -> str:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
