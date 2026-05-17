"""Tests for core data models."""
from __future__ import annotations

from app.core.models import Chapter, DownloadStatus, ExportFormat, Manga


def test_chapter_defaults():
    ch = Chapter(title="Chapter 1", url="http://example.com/ch1")
    assert ch.number == 0.0
    assert ch.status == DownloadStatus.PENDING
    assert ch.images == []


def test_manga_defaults():
    m = Manga(title="Test Manga", url="http://example.com/manga")
    assert m.author is None
    assert m.cover_url is None
    assert m.chapters == []
    assert m.site_name == ""


def test_export_format_values():
    assert ExportFormat.CBZ.value == "cbz"
    assert ExportFormat.PDF.value == "pdf"
    assert ExportFormat.EPUB.value == "epub"
    assert ExportFormat.FOLDER.value == "folder"


def test_download_status_enum():
    assert DownloadStatus("done") == DownloadStatus.DONE
    assert DownloadStatus("pending") == DownloadStatus.PENDING
