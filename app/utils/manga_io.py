from __future__ import annotations
import json
import datetime
from pathlib import Path

from app.core.models import Manga


def save_manga_info(manga: Manga, manga_dir: Path) -> Path:
    """Create manga_dir and write/overwrite manga_info.json with current metadata."""
    manga_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "title": manga.title,
        "url": manga.url,
        "cover_url": manga.cover_url,
        "author": manga.author,
        "description": manga.description,
        "site_name": manga.site_name,
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_chapters": len(manga.chapters),
        "chapters": [
            {"title": ch.title, "url": ch.url, "number": ch.number}
            for ch in manga.chapters
        ],
    }

    path = manga_dir / "manga_info.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
