"""
Configuration management for game_scraper.
Stores user preferences, credentials (via keyring), and app settings.
"""

import json
import os
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

APP_NAME = "game_scraper"
CONFIG_DIR = Path(user_config_dir(APP_NAME))
DATA_DIR = Path(user_data_dir(APP_NAME))
WISHLIST_FILE = DATA_DIR / "wishlist.json"
HISTORY_FILE = DATA_DIR / "purchase_history.json"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    # GAME_SCRAPER_DOWNLOAD_DIR env var lets Docker users override via compose
    "download_dir": os.environ.get("GAME_SCRAPER_DOWNLOAD_DIR", str(Path.home() / "Games")),
    "auto_purchase": False,
    "max_price_usd": 0.0,
    "notify_on_deal": True,
    "check_interval_minutes": 60,
    "platforms": ["gog", "steam", "humble", "epic"],
    "min_discount_pct": 50,
}


def _ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    _ensure_dirs()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            stored = json.load(f)
        return {**DEFAULT_CONFIG, **stored}
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    _ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def load_wishlist() -> list[dict]:
    _ensure_dirs()
    if WISHLIST_FILE.exists():
        with open(WISHLIST_FILE) as f:
            return json.load(f)
    return []


def save_wishlist(wishlist: list[dict]):
    _ensure_dirs()
    with open(WISHLIST_FILE, "w") as f:
        json.dump(wishlist, f, indent=2)


def load_history() -> list[dict]:
    _ensure_dirs()
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def append_history(entry: dict):
    history = load_history()
    history.append(entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
