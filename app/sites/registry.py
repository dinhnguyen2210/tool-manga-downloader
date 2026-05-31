from __future__ import annotations
from typing import Optional

from app.sites.base import BaseSite
from app.sites.truyenqqko import TruyenQQKo
from app.sites.haikyuu import ReadHaikyuuCom, ReadHaikyuOnline
from app.sites.facebook import FacebookAlbumSite

SITES: list[type[BaseSite]] = [
    TruyenQQKo,
    ReadHaikyuuCom,
    ReadHaikyuOnline,
    FacebookAlbumSite,
]


def get_site_for_url(url: str) -> Optional[BaseSite]:
    """Return an instantiated site plugin that handles the given URL, or None."""
    for site_cls in SITES:
        if site_cls.matches(url):
            return site_cls()
    return None
