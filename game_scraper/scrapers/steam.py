"""
Steam scraper using the public Steam Store API and Storefront API.
No authentication required for browsing deals.
"""

from bs4 import BeautifulSoup
from .base import BaseScraper, GameDeal

STORE_SEARCH = "https://store.steampowered.com/api/storesearch/"
FEATURED_URL = "https://store.steampowered.com/api/featured/"
SPECIALS_URL = "https://store.steampowered.com/api/featuredcategories/"
APP_URL = "https://store.steampowered.com/app/{app_id}/"


class SteamScraper(BaseScraper):
    name = "steam"

    def search(self, query: str, limit: int = 20) -> list[GameDeal]:
        data = self._get(
            STORE_SEARCH,
            params={"term": query, "l": "english", "cc": "us"},
        ).json()
        items = data.get("items", [])[:limit]
        return [self._search_item_to_deal(i) for i in items]

    def get_deals(self, min_discount: int = 50, limit: int = 50) -> list[GameDeal]:
        data = self._get(SPECIALS_URL, params={"cc": "us", "l": "english"}).json()
        specials = data.get("specials", {}).get("items", [])
        deals = []
        for item in specials:
            discount = item.get("discount_percent", 0)
            if discount < min_discount:
                continue
            deals.append(self._featured_item_to_deal(item))
            if len(deals) >= limit:
                break
        return deals

    def get_app_details(self, app_id: int) -> dict | None:
        url = f"https://store.steampowered.com/api/appdetails"
        data = self._get(url, params={"appids": app_id, "cc": "us", "l": "english"}).json()
        app_data = data.get(str(app_id), {})
        if app_data.get("success"):
            return app_data.get("data")
        return None

    # ------------------------------------------------------------------ #

    def _search_item_to_deal(self, item: dict) -> GameDeal:
        price_obj = item.get("price", {})
        original = price_obj.get("original", 0) / 100
        final = price_obj.get("final", original) / 100
        discount = price_obj.get("discount_percent", 0)
        app_id = item.get("id", "")
        return GameDeal(
            title=item.get("name", "Unknown"),
            platform="Steam",
            store_url=APP_URL.format(app_id=app_id),
            current_price=final,
            original_price=original,
            discount_pct=discount,
            game_id=str(app_id),
            thumb_url=item.get("tiny_image", ""),
        )

    def _featured_item_to_deal(self, item: dict) -> GameDeal:
        original = item.get("original_price", 0) / 100
        final = item.get("final_price", original) / 100
        discount = item.get("discount_percent", 0)
        app_id = item.get("id", "")
        return GameDeal(
            title=item.get("name", "Unknown"),
            platform="Steam",
            store_url=APP_URL.format(app_id=app_id),
            current_price=final,
            original_price=original,
            discount_pct=discount,
            game_id=str(app_id),
            thumb_url=item.get("header_image", ""),
        )
