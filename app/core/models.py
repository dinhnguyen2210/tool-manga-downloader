from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExportFormat(str, Enum):
    FOLDER = "folder"
    CBZ = "cbz"
    PDF = "pdf"
    EPUB = "epub"


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Chapter:
    title: str
    url: str
    number: float = 0.0
    status: DownloadStatus = DownloadStatus.PENDING
    images: list[str] = field(default_factory=list)
    folder_name: Optional[str] = None  # overrides Chapter_XXXX naming when set


@dataclass
class Manga:
    title: str
    url: str
    cover_url: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    site_name: str = ""
    chapters: list[Chapter] = field(default_factory=list)
