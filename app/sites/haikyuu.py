from __future__ import annotations
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from app.sites.base import BaseSite
from app.core.models import Manga, Chapter
from app.utils.logger import logger


class _FetchMixin:
    """Shared aiohttp + cloudscraper fetch helpers for Haikyuu plugins."""

    def get_fetch_headers(self) -> dict[str, str]: ...  # provided by BaseSite

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
                import asyncio
                logger.warning(f"Got {e.status}, trying cloudscraper for {url}")
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_cloudscraper, url
                )
            raise

    def _fetch_cloudscraper(self, url: str) -> str:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text


class ReadHaikyuuCom(_FetchMixin, BaseSite):
    """Plugin for read-haikyuu.com (color edition).

    Images are lazy-loaded via JS — uses WordPress REST API (/wp-json/wp/v2/comic)
    to retrieve actual image URLs from the post content.
    """

    name = "read-haikyuu"
    base_url = "https://www.read-haikyuu.com"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "read-haikyuu.com" in url.lower()

    async def parse_manga_info(self, url: str) -> Manga:
        html = await self._fetch_html(url)
        soup = BeautifulSoup(html, "lxml")

        title = self._parse_title(soup)
        cover_url = self._parse_cover(soup)
        author = self._parse_author(soup)
        description = self._parse_description(soup)
        chapters = await self._fetch_all_chapters()

        if not chapters:
            raise ValueError(
                "No chapters found. Use the manga index page URL "
                "(e.g. https://www.read-haikyuu.com/)."
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
        slug = chapter_url.rstrip("/").rsplit("/", 1)[-1]
        api_url = f"{self.base_url}/wp-json/wp/v2/comic?slug={slug}&_fields=content"
        headers = self.get_fetch_headers()
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, ssl=False, timeout=timeout) as resp:
                resp.raise_for_status()
                data = await resp.json()
        if not data:
            return []
        content_html = data[0].get("content", {}).get("rendered", "")
        soup = BeautifulSoup(content_html, "lxml")
        images: list[str] = []
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if src and not src.startswith("data:") and not src.endswith(".gif"):
                images.append(src)
        return images

    # ─── chapter list via REST API ───────────────────────────────────────────

    async def _fetch_all_chapters(self) -> list[Chapter]:
        chapters: list[Chapter] = []
        headers = self.get_fetch_headers()
        timeout = aiohttp.ClientTimeout(total=30)
        page = 1
        while True:
            api_url = (
                f"{self.base_url}/wp-json/wp/v2/comic"
                f"?per_page=100&page={page}&orderby=date&order=asc"
                f"&_fields=slug,title,link"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, ssl=False, timeout=timeout) as resp:
                    if resp.status == 400:
                        break
                    resp.raise_for_status()
                    data = await resp.json()
            if not data:
                break
            for item in data:
                raw_title = item.get("title", {}).get("rendered", "")
                title = BeautifulSoup(raw_title, "lxml").get_text(strip=True)
                link = item.get("link", "")
                number = self._extract_number(title, link)
                chapters.append(Chapter(title=title, url=link, number=number))
            page += 1
        return chapters

    # ─── HTML helpers ────────────────────────────────────────────────────────

    def _parse_title(self, soup: BeautifulSoup) -> str:
        el = soup.select_one("h1")
        return el.get_text(strip=True) if el else "Haikyu!! (Color)"

    def _parse_cover(self, soup: BeautifulSoup) -> Optional[str]:
        for selector in (".wp-post-image", ".summary_image img", "img[src*='uploads']"):
            el = soup.select_one(selector)
            if el:
                src = el.get("data-src") or el.get("src") or ""
                if src and src.startswith("http"):
                    return src
        return None

    def _parse_author(self, soup: BeautifulSoup) -> Optional[str]:
        for selector in (".author-content a", ".manga-authors a"):
            el = soup.select_one(selector)
            if el:
                return el.get_text(strip=True)
        return "Haruichi Furudate"

    def _parse_description(self, soup: BeautifulSoup) -> Optional[str]:
        for selector in (".summary__content p", ".description-summary p", ".manga-summary p"):
            el = soup.select_one(selector)
            if el:
                return el.get_text(strip=True)
        return None

    def _extract_number(self, title: str, url: str) -> float:
        # "Haikyu!! (Color) – Chapter 207.5"
        m = re.search(r'chapter\s+(\d+(?:[.,]\d+)?)', title, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", "."))
        # URL slug: "chapter-207-5" → 207.5, "chapter-207" → 207.0
        m = re.search(r'chapter-(\d+)(?:-(\d+))?', url, re.IGNORECASE)
        if m:
            n, frac = m.group(1), m.group(2)
            return float(f"{n}.{frac}") if frac else float(n)
        return 0.0


class ReadHaikyuOnline(_FetchMixin, BaseSite):
    """Plugin for readhaikyu.online / w1.readhaikyu.online.

    Standard HTML-parsed site; images served directly from Google's Blogger CDN.
    """

    name = "readhaikyu-online"
    base_url = "https://w1.readhaikyu.online"

    @classmethod
    def matches(cls, url: str) -> bool:
        return "readhaikyu.online" in url.lower()

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
                "No chapters found. Use the manga index page URL "
                "(e.g. https://w1.readhaikyu.online/)."
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

    # ─── HTML helpers ────────────────────────────────────────────────────────

    def _parse_title(self, soup: BeautifulSoup) -> str:
        el = soup.select_one("h1")
        return el.get_text(strip=True) if el else "Haikyuu!!"

    def _parse_cover(self, soup: BeautifulSoup) -> Optional[str]:
        for selector in (".wp-post-image", ".summary_image img", "img[src*='uploads']"):
            el = soup.select_one(selector)
            if el:
                src = el.get("data-src") or el.get("src") or ""
                if src and src.startswith("http"):
                    return src
        return None

    def _parse_author(self, soup: BeautifulSoup) -> Optional[str]:
        m = re.search(
            r'(?:written and illustrated by|illustrated by|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            soup.get_text(),
        )
        return m.group(1).strip() if m else "Haruichi Furudate"

    def _parse_description(self, soup: BeautifulSoup) -> Optional[str]:
        for selector in (".summary__content p", ".description-summary p"):
            el = soup.select_one(selector)
            if el:
                return el.get_text(strip=True)
        # Fallback: first <p> longer than 80 chars
        for p in soup.select("p"):
            text = p.get_text(strip=True)
            if len(text) > 80:
                return text
        return None

    def _parse_chapters(self, soup: BeautifulSoup) -> list[Chapter]:
        chapters: list[Chapter] = []
        link_els = (
            soup.select(".wp-manga-chapter a")
            or soup.select("ul li a[href*='/manga/haikyuu-chapter']")
            or soup.select("ul li a[href*='chapter']")
        )

        seen: set[str] = set()
        for a in link_els:
            href = a.get("href", "")
            if not href or href in seen:
                continue
            if not href.startswith("http"):
                href = self.base_url.rstrip("/") + "/" + href.lstrip("/")
            seen.add(href)
            title = a.get_text(strip=True)
            number = self._extract_number(title, href)
            chapters.append(Chapter(title=title, url=href, number=number))

        chapters.reverse()  # Site lists newest first
        return chapters

    def _extract_number(self, title: str, url: str) -> float:
        # "Haikyuu!!, Chapter 402.6"
        m = re.search(r'chapter[\s,]+(\d+(?:[.,]\d+)?)', title, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", "."))
        # URL: "haikyuu-chapter-402.6"
        m = re.search(r'chapter-(\d+(?:[.]\d+)?)', url, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return 0.0

    def _parse_images(self, soup: BeautifulSoup) -> list[str]:
        images: list[str] = []

        # Full-size images in <a href="...blogger..."><img ...>
        for a in soup.select("a[href*='blogger.googleusercontent.com']"):
            href = (a.get("href") or "").strip()
            if href and not href.endswith(".gif"):
                images.append(href)

        if not images:
            # Compressed images via img src
            for img in soup.select("img[src*='blogger.googleusercontent.com']"):
                src = (img.get("src") or "").strip()
                if src and not src.endswith(".gif"):
                    images.append(src)

        if not images:
            # Generic fallback with lazy-load support
            for selector in (".reading-content img", ".page-break img", "img.wp-manga-chapter-img"):
                for img in soup.select(selector):
                    src = (img.get("data-src") or img.get("src") or "").strip()
                    if src and not src.startswith("data:") and not src.endswith(".gif"):
                        images.append(src)

        return images
