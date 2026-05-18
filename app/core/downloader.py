from __future__ import annotations
import asyncio
import datetime
from pathlib import Path
from typing import Callable, Optional

import aiohttp

from app.core.models import Manga, Chapter, DownloadStatus
from app.core.config import AppConfig
from app.utils.naming import zero_pad, sanitize_filename, chapter_stem
from app.utils.headers import get_random_ua
from app.utils.logger import logger


class DownloadSignals:
    """Plain callback container — no Qt dependency, so MangaDownloader stays testable."""
    on_total_progress: Optional[Callable[[int, int], None]] = None
    on_chapter_progress: Optional[Callable[[int, int], None]] = None
    on_log: Optional[Callable[[str], None]] = None
    on_chapter_status: Optional[Callable[[int, DownloadStatus], None]] = None
    on_finished: Optional[Callable[[], None]] = None


class MangaDownloader:
    def __init__(self, config: AppConfig, signals: DownloadSignals) -> None:
        self.config = config
        self.signals = signals
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    async def download_manga(
        self,
        manga: Manga,
        selected_chapters: list[Chapter],
        output_dir: Path,
        export_format: str,
    ) -> None:
        self._cancelled = False
        total = len(selected_chapters)

        for i, chapter in enumerate(selected_chapters):
            if self._cancelled:
                self._log("Download cancelled by user.")
                break

            self._emit_chapter_status(chapter, DownloadStatus.DOWNLOADING)
            self._log(f"Downloading {chapter.title} ({i+1}/{total})...")

            try:
                images = await self._get_chapter_images(manga, chapter)
                if not images:
                    raise ValueError("No images found in chapter")

                chapter.images = images
                chapter_dir = self._get_chapter_dir(manga, chapter, output_dir, export_format)

                await self._download_images(images, chapter_dir, manga.url)

                if export_format != "folder":
                    manga_out_dir = output_dir / sanitize_filename(manga.title) / export_format
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        _export_chapter,
                        chapter_dir,
                        manga_out_dir,
                        chapter,
                        export_format,
                    )

                self._emit_chapter_status(chapter, DownloadStatus.DONE)
                self._emit_total_progress(i + 1, total)
                self._log(f"✓ {chapter.title} done")

            except Exception as e:
                self._emit_chapter_status(chapter, DownloadStatus.FAILED)
                self._log(f"✗ {chapter.title} failed: {e}")
                logger.error(f"Chapter failed: {e}", exc_info=True)

            if i < total - 1 and not self._cancelled:
                await asyncio.sleep(self.config.delay_seconds)

        if self.signals.on_finished:
            self.signals.on_finished()

    # ─── private ────────────────────────────────────────────────────────────

    async def _get_chapter_images(self, manga: Manga, chapter: Chapter) -> list[str]:
        from app.sites.registry import get_site_for_url
        site = get_site_for_url(manga.url)
        if not site:
            raise ValueError(f"No plugin for URL: {manga.url}")
        return await site.parse_chapter_images(chapter.url)

    def _get_chapter_dir(self, manga: Manga, chapter: Chapter, base_dir: Path, export_format: str) -> Path:
        chapter_dir = (
            base_dir
            / sanitize_filename(manga.title)
            / export_format
            / f"Chapter_{chapter_stem(chapter.number)}"
        )
        chapter_dir.mkdir(parents=True, exist_ok=True)
        return chapter_dir

    async def _download_images(
        self, image_urls: list[str], chapter_dir: Path, referer: str
    ) -> None:
        semaphore = asyncio.Semaphore(self.config.concurrent_downloads)
        total = len(image_urls)
        progress = {"done": 0}

        def on_image_done() -> None:
            progress["done"] += 1
            self._emit_chapter_progress(progress["done"], total)

        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [
                self._download_single_image(
                    session, url, chapter_dir, semaphore, referer, idx, on_image_done
                )
                for idx, url in enumerate(image_urls)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Image download error: {r}")

    async def _download_single_image(
        self,
        session: aiohttp.ClientSession,
        url: str,
        chapter_dir: Path,
        semaphore: asyncio.Semaphore,
        referer: str,
        idx: int,
        on_done: Callable[[], None],
    ) -> None:
        ext = _url_ext(url)
        filepath = chapter_dir / f"{zero_pad(idx + 1, 3)}.{ext}"

        # Resume: skip if already downloaded
        if filepath.exists() and filepath.stat().st_size > 100:
            on_done()
            return

        headers = {
            "User-Agent": get_random_ua(),
            "Referer": referer,
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }

        for attempt in range(self.config.retry_count + 1):
            try:
                async with semaphore:
                    async with session.get(url, headers=headers) as resp:
                        resp.raise_for_status()
                        content = await resp.read()

                if len(content) < 100:
                    raise ValueError(f"Image too small ({len(content)} bytes): {url}")

                filepath.write_bytes(content)
                on_done()
                return

            except Exception as e:
                if attempt < self.config.retry_count:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Failed after {attempt+1} attempts: {url}") from e

    def _log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        full = f"[{ts}] {msg}"
        logger.info(msg)
        if self.signals.on_log:
            self.signals.on_log(full)

    def _emit_total_progress(self, done: int, total: int) -> None:
        if self.signals.on_total_progress:
            self.signals.on_total_progress(done, total)

    def _emit_chapter_progress(self, done: int, total: int) -> None:
        if self.signals.on_chapter_progress:
            self.signals.on_chapter_progress(done, total)

    def _emit_chapter_status(self, chapter: Chapter, status: DownloadStatus) -> None:
        chapter.status = status
        if self.signals.on_chapter_status:
            self.signals.on_chapter_status(id(chapter), status)


# ─── export helper (called in thread pool) ──────────────────────────────────

def _export_chapter(
    chapter_dir: Path,
    manga_out_dir: Path,
    chapter: Chapter,
    fmt: str,
) -> None:
    from app.core.exporter import export_chapter
    export_chapter(chapter_dir, manga_out_dir, chapter, fmt)


def _url_ext(url: str) -> str:
    path = url.split("?")[0].rstrip("/")
    ext = path.rsplit(".", 1)[-1].lower()
    return ext if ext in {"jpg", "jpeg", "png", "webp", "gif"} else "jpg"
