from __future__ import annotations
import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    concurrent_downloads: int = 5
    delay_seconds: float = 1.5
    retry_count: int = 3
    output_format: str = "cbz"
    default_output_dir: str = str(Path(__file__).resolve().parents[2] / "output" / "manga")
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    theme: str = "dark"


def get_config_path() -> Path:
    config_dir = Path.home() / ".mangadl"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_config() -> AppConfig:
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            valid_keys = {f.name for f in fields(AppConfig)}
            return AppConfig(**{k: v for k, v in data.items() if k in valid_keys})
        except Exception:
            pass
    return AppConfig()


def save_config(config: AppConfig) -> None:
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)
