from __future__ import annotations
import json
from pathlib import Path

_HISTORY_PATH = Path.home() / ".mangadl" / "history.json"
_MAX_ENTRIES = 30


def load_history() -> list[str]:
    try:
        if _HISTORY_PATH.exists():
            return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_url(url: str) -> list[str]:
    """Prepend url to history, deduplicate, cap at _MAX_ENTRIES. Returns updated list."""
    url = url.strip()
    if not url:
        return load_history()
    history = [u for u in load_history() if u != url]
    history.insert(0, url)
    history = history[:_MAX_ENTRIES]
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history
