"""Base scraper interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 15


@dataclass
class GameDeal:
    title: str
    platform: str
    store_url: str
    current_price: float
    original_price: float
    discount_pct: int
    currency: str = "USD"
    game_id: str = ""
    thumb_url: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    drm_free: bool = False

    @property
    def savings(self) -> float:
        return round(self.original_price - self.current_price, 2)

    def __str__(self) -> str:
        return (
            f"{self.title} [{self.platform}] "
            f"{self.currency} {self.current_price:.2f} "
            f"(-{self.discount_pct}%)"
        )


class BaseScraper(ABC):
    name: str = "base"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, url: str, **kwargs) -> requests.Response:
        resp = self.session.get(url, timeout=TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> list[GameDeal]:
        """Search for games by title."""

    @abstractmethod
    def get_deals(self, min_discount: int = 50, limit: int = 50) -> list[GameDeal]:
        """Fetch current deals filtered by minimum discount percentage."""

    def get_free_games(self) -> list[GameDeal]:
        """Return currently free games (default: filter deals at 100%)."""
        return [d for d in self.get_deals(min_discount=100, limit=50) if d.current_price == 0]
