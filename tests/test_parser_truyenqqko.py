"""Offline parser tests for TruyenQQKo plugin using HTML fixtures."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest
from bs4 import BeautifulSoup

from app.sites.truyenqqko import TruyenQQKo
from app.core.models import Manga, Chapter


@pytest.fixture
def site() -> TruyenQQKo:
    return TruyenQQKo()


def test_matches_url(site):
    assert site.matches("https://truyenqqko.com/truyen-tranh/abc")
    assert site.matches("https://www.truyenqqko.com/abc")
    assert not site.matches("https://nettruyen.com/abc")
    assert not site.matches("https://example.com")


def test_parse_title(site, sample_manga_html):
    soup = BeautifulSoup(sample_manga_html, "lxml")
    assert site._parse_title(soup) == "Hoa Phụng Liêu Nguyện"


def test_parse_cover(site, sample_manga_html):
    soup = BeautifulSoup(sample_manga_html, "lxml")
    cover = site._parse_cover(soup)
    assert cover == "https://cdn.example.com/cover.jpg"


def test_parse_author(site, sample_manga_html):
    soup = BeautifulSoup(sample_manga_html, "lxml")
    author = site._parse_author(soup)
    assert author == "Tác Giả Nào Đó"


def test_parse_chapters_order(site, sample_manga_html):
    soup = BeautifulSoup(sample_manga_html, "lxml")
    chapters = site._parse_chapters(soup)
    # Should be oldest-first (chapter 1 before chapter 2)
    assert len(chapters) == 2
    assert chapters[0].number == 1.0
    assert chapters[1].number == 2.0


def test_parse_chapter_urls_absolute(site, sample_manga_html):
    soup = BeautifulSoup(sample_manga_html, "lxml")
    chapters = site._parse_chapters(soup)
    for ch in chapters:
        assert ch.url.startswith("http")


def test_parse_images(site, sample_chapter_html):
    soup = BeautifulSoup(sample_chapter_html, "lxml")
    images = site._parse_images(soup)
    assert len(images) == 3
    assert all(img.startswith("http") for img in images)
    assert "001.jpg" in images[0]
    assert "002.jpg" in images[1]
    assert "003.jpg" in images[2]


def test_extract_chapter_number(site):
    assert site._extract_chapter_number("Chapter 1") == 1.0
    assert site._extract_chapter_number("Chap 12.5") == 12.5
    assert site._extract_chapter_number("Ch 100") == 100.0
    assert site._extract_chapter_number("42 - Some title") == 42.0


@pytest.mark.asyncio
async def test_parse_manga_info_mocked(site, sample_manga_html):
    with patch.object(site, "_fetch_html", new=AsyncMock(return_value=sample_manga_html)):
        manga = await site.parse_manga_info("https://truyenqqko.com/truyen/test")
    assert manga.title == "Hoa Phụng Liêu Nguyện"
    assert len(manga.chapters) == 2
    assert manga.cover_url is not None


@pytest.mark.asyncio
async def test_parse_chapter_images_mocked(site, sample_chapter_html):
    with patch.object(site, "_fetch_html", new=AsyncMock(return_value=sample_chapter_html)):
        images = await site.parse_chapter_images("https://truyenqqko.com/truyen/test/chapter-1")
    assert len(images) == 3
