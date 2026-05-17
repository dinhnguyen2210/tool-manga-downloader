from __future__ import annotations
import re
import unicodedata


def zero_pad(n: int, width: int = 3) -> str:
    return str(n).zfill(width)


def sanitize_filename(name: str) -> str:
    """Convert string to a safe filesystem name (ASCII, no special chars)."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r'\s+', "_", name.strip())
    name = name.strip("._")
    return name[:200] or "unnamed"


def chapter_folder_name(number: float, title: str = "") -> str:
    n = int(number)
    if title:
        safe_title = sanitize_filename(title)
        return f"Chapter_{zero_pad(n, 4)}_{safe_title}"
    return f"Chapter_{zero_pad(n, 4)}"


def image_filename(index: int, ext: str = "jpg") -> str:
    return f"{zero_pad(index, 3)}.{ext}"
