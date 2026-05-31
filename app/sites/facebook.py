"""Plugin for downloading photo albums from Facebook pages.

Requirements:
    pip install playwright && playwright install chromium

For private/login-required pages, export your cookies to
~/.mangadl/fb_cookies.json via the "Cookie-Editor" browser extension
(Export → JSON).
"""

from __future__ import annotations
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.models import Chapter, Manga
from app.sites.base import BaseSite
from app.utils.logger import logger


_COOKIES_FILE = Path.home() / ".mangadl" / "fb_cookies.json"
_CONCURRENCY = 5  # parallel photo-page requests for og:image
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_SAMESITE_MAP = {
    "no_restriction": "None",
    "lax": "Lax",
    "strict": "Strict",
    "none": "None",
    "Lax": "Lax",
    "Strict": "Strict",
    "None": "None",
}


class FacebookAlbumSite(BaseSite):
    """Plugin for Facebook photo albums.

    Paste the page's photos_albums URL:
        https://web.facebook.com/<page>/photos_albums
    All albums will appear as chapters; select the ones you want.

    Requires playwright (see module docstring for setup).
    """

    name = "Facebook Albums"
    base_url = "https://www.facebook.com"

    @classmethod
    def matches(cls, url: str) -> bool:
        lower = url.lower()
        return "facebook.com" in lower and any(
            k in lower for k in ("photos_albums", "photos?tab=albums", "tab=albums")
        )

    async def parse_manga_info(self, url: str) -> Manga:
        url = _normalize(url)
        cookies = _load_cookies()
        async with _browser_page(cookies) as page:
            albums = await _scrape_album_list(page, url)
        if not albums:
            raise ValueError(
                "Không tìm thấy album nào.\n"
                "• Kiểm tra URL trỏ đến trang photos_albums của page.\n"
                "• Nếu trang yêu cầu đăng nhập, xuất cookies bằng extension "
                "\"Cookie-Editor\" → Export → JSON → lưu vào ~/.mangadl/fb_cookies.json"
            )
        title = _page_name(url)
        return Manga(
            title=title,
            url=url,
            cover_url=None,
            author=None,
            description=None,
            site_name=self.name,
            chapters=albums,
        )

    async def parse_chapter_images(self, album_url: str) -> list[str]:
        cookies = _load_cookies()
        async with _browser_page(cookies) as page:
            imgs = await _scrape_photo_urls_from_album(page, album_url)
        return imgs

    def get_image_headers(self, image_url: str) -> dict[str, str]:
        return {"Referer": "https://www.facebook.com/", "User-Agent": _UA}


# ─── URL helpers ──────────────────────────────────────────────────────────────

def _normalize(url: str) -> str:
    return re.sub(r"https?://(web\.|m\.)?facebook\.com", "https://www.facebook.com", url)


def _page_name(url: str) -> str:
    m = re.search(r"facebook\.com/([^/?#]+)", url)
    return m.group(1) if m else "Facebook"


# ─── Cookie helpers ───────────────────────────────────────────────────────────

def _load_cookies() -> list[dict]:
    if not _COOKIES_FILE.exists():
        return []
    try:
        data = json.loads(_COOKIES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            logger.info(f"Facebook: loaded {len(data)} cookies from {_COOKIES_FILE}")
            return data
    except Exception as e:
        logger.warning(f"Facebook: failed to load cookies: {e}")
    return []



def _to_pw_cookies(raw: list[dict]) -> list[dict]:
    """Convert browser-exported cookie JSON to Playwright's format."""
    result = []
    for c in raw:
        domain = str(c.get("domain", ".facebook.com"))
        if not domain.startswith("."):
            domain = f".{domain}"
        ss_raw = str(c.get("sameSite", "None"))
        entry: dict = {
            "name": str(c.get("name", "")),
            "value": str(c.get("value", "")),
            "domain": domain,
            "path": str(c.get("path", "/")),
            "sameSite": _SAMESITE_MAP.get(ss_raw, "None"),
        }
        result.append(entry)
    return result


# ─── Playwright browser context ───────────────────────────────────────────────

@asynccontextmanager
async def _browser_page(cookies: list[dict]):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ImportError(
            "Playwright chưa được cài đặt.\n"
            "Chạy trong terminal:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=_UA,
            locale="vi-VN",
        )
        if cookies:
            await ctx.add_cookies(_to_pw_cookies(cookies))
        page = await ctx.new_page()
        # Block fonts to reduce load time
        await page.route(r"**/*.{woff,woff2,ttf,otf}", lambda route: route.abort())
        try:
            yield page
        finally:
            await browser.close()


# ─── Page scraping ────────────────────────────────────────────────────────────

async def _scroll_to_bottom(page, max_rounds: int = 25) -> None:
    """Scroll until page height stabilises (all lazy content loaded)."""
    prev_height = 0
    for _ in range(max_rounds):
        cur_height: int = await page.evaluate("document.body.scrollHeight")
        if cur_height == prev_height:
            break
        prev_height = cur_height
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1800)


async def _dismiss_popups(page) -> None:
    """Try to close common Facebook login/cookie dialogs."""
    selectors = [
        "[data-testid='cookie-policy-manage-dialog-accept-button']",
        "[data-cookiebanner='accept_only_essential_cookie_policy_response_button']",
        "[aria-label='Đóng']",
        "[aria-label='Close']",
        "div[role='dialog'] [aria-label='Không cho phép']",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=800):
                await el.click()
                await page.wait_for_timeout(400)
        except Exception:
            pass


async def _scrape_album_list(page, url: str) -> list[Chapter]:
    logger.info(f"Facebook: loading albums page: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        raise ValueError(f"Không thể tải trang Facebook: {e}") from e

    if "login" in page.url.lower():
        raise ValueError(
            "Facebook yêu cầu đăng nhập.\n"
            "Xuất cookies và lưu vào ~/.mangadl/fb_cookies.json"
        )

    await _dismiss_popups(page)
    await _scroll_to_bottom(page)

    albums: list[Chapter] = []
    seen: set[str] = set()

    # Only match /media/set/ links — not individual photo links which also contain set=a.
    link_els = await page.query_selector_all("a[href*='media/set']")
    for el in link_els:
        raw_href = (await el.get_attribute("href")) or ""
        if not raw_href or "/photo/" in raw_href:
            continue
        href = raw_href if raw_href.startswith("http") else f"https://www.facebook.com{raw_href}"
        # Deduplicate by album set ID
        m = re.search(r"set=(a\.\d+)", href)
        key = m.group(1) if m else href
        if key in seen:
            continue
        seen.add(key)

        title = await _link_title(el)
        number = _extract_number(title)
        # Albums without a chapter number use their title as the folder name
        folder_name = title if number == 0.0 else None
        albums.append(Chapter(title=title, url=href, number=number, folder_name=folder_name))
        logger.debug(f"  album: {title!r} → {href}")

    logger.info(f"Facebook: found {len(albums)} albums")
    return albums


async def _scrape_photo_urls_from_album(page, album_url: str) -> list[str]:
    """Navigate to album, capture full-res image URLs via network interception + DOM fallback."""
    logger.info(f"Facebook: loading album: {album_url}")

    seen: set[str] = set()
    photo_urls: list[str] = []

    async def on_response(response):
        if response.status != 200:
            return
        content_type = response.headers.get("content-type", "")
        # Skip binary/image/CSS/font — only scan text-based responses
        if any(t in content_type for t in ("image/", "text/css", "font/", "audio/", "video/")):
            return
        try:
            text = await response.text()
        except Exception:
            return
        if "scontent" not in text:
            return
        # Primary: JSON "uri" key pattern (GraphQL / API responses)
        for m in re.finditer(r'"uri"\s*:\s*"(https://scontent[^"\\]+)"', text):
            _collect(m.group(1), seen, photo_urls)
        # Secondary: bare scontent URLs in any text/JS/HTML response
        for m in re.finditer(
            r'https://scontent[-\w.]+\.fbcdn\.net/v/[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)',
            text,
        ):
            _collect(m.group(0), seen, photo_urls)

    page.on("response", on_response)
    try:
        await page.goto(album_url, wait_until="domcontentloaded", timeout=30_000)
        if "login" in page.url.lower():
            raise ValueError(
                "Facebook yêu cầu đăng nhập.\n"
                "Xuất cookies và lưu vào ~/.mangadl/fb_cookies.json"
            )
        await _dismiss_popups(page)
        await _scroll_to_bottom(page)
        await page.wait_for_timeout(1500)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Không thể tải album Facebook: {e}") from e
    finally:
        page.remove_listener("response", on_response)

    # DOM fallback: if network interception caught nothing, scan rendered img tags
    if not photo_urls:
        logger.info("Facebook: network captured 0 URLs, trying DOM fallback")
        img_els = await page.query_selector_all("img[src*='scontent']")
        for el in img_els:
            src = (await el.get_attribute("src")) or ""
            _collect(src, seen, photo_urls)
        logger.info(f"Facebook: DOM fallback found {len(photo_urls)} URLs")

    logger.info(f"Facebook: captured {len(photo_urls)} photo URLs from album")
    return photo_urls


def _collect(url: str, seen: set[str], out: list[str]) -> None:
    """Add url to out if it's a full-res scontent URL not yet seen."""
    if not url or not url.startswith("https://scontent"):
        return
    # Drop thumbnail size variants embedded in path (p320x320, s720x720…)
    if re.search(r'/[ps]\d+x\d+/', url):
        return
    if url not in seen:
        seen.add(url)
        out.append(url)


# ─── Text / number helpers ────────────────────────────────────────────────────

async def _link_title(el) -> str:
    """Extract meaningful title text from a Playwright element, skipping photo counts."""
    raw = (await el.inner_text()).strip()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for line in lines:
        # Skip lines that look like "50 ảnh" or "32 photos"
        if re.fullmatch(r'\d+\s*(ảnh|photos?|hình|pic\w*)', line, re.IGNORECASE):
            continue
        if line:
            return line
    return lines[0] if lines else "Album"


def _extract_number(title: str) -> float:
    """Extract chapter number from title like 'Hồi 1', 'Chapter 12', 'Phần 3'."""
    m = re.search(r'(?:hồi|chapter|phần|tập)\s+(\d+(?:[.,]\d+)?)', title, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r'\b(\d+(?:[.,]\d+)?)\b', title)
    if m:
        return float(m.group(1).replace(",", "."))
    return 0.0
