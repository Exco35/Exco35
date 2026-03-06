"""
GOG.com scraper using the public GOG API.
No authentication required for browsing deals.
"""

from urllib.parse import quote
from .base import BaseScraper, GameDeal

API_BASE = "https://catalog.gog.com/v1"
PRODUCT_URL = "https://www.gog.com/en/game/{slug}"
SEARCH_URL = "https://catalog.gog.com/v1/catalog"


class GOGScraper(BaseScraper):
    name = "gog"

    def search(self, query: str, limit: int = 20) -> list[GameDeal]:
        params = {
            "query": f"like:{query}",
            "order": "desc:score",
            "productType": "in:game",
            "limit": min(limit, 48),
            "locale": "en-US",
            "countryCode": "US",
            "currencyCode": "USD",
        }
        data = self._get(SEARCH_URL, params=params).json()
        return [self._to_deal(p) for p in data.get("products", [])]

    def get_deals(self, min_discount: int = 50, limit: int = 50) -> list[GameDeal]:
        params = {
            "query": "price:gt:0",
            "order": "desc:discount",
            "productType": "in:game",
            "limit": min(limit, 48),
            "locale": "en-US",
            "countryCode": "US",
            "currencyCode": "USD",
            "pricingType": "in:sale",
        }
        data = self._get(SEARCH_URL, params=params).json()
        deals = []
        for product in data.get("products", []):
            deal = self._to_deal(product)
            if deal.discount_pct >= min_discount:
                deals.append(deal)
        return deals

    def get_free_games(self) -> list[GameDeal]:
        params = {
            "order": "desc:discount",
            "productType": "in:game",
            "limit": 20,
            "locale": "en-US",
            "countryCode": "US",
            "currencyCode": "USD",
            "maxPrice": "0",
        }
        data = self._get(SEARCH_URL, params=params).json()
        return [self._to_deal(p) for p in data.get("products", [])]

    # ------------------------------------------------------------------ #

    def _to_deal(self, p: dict) -> GameDeal:
        price_info = p.get("price", {})
        final = float(price_info.get("finalMoney", {}).get("amount", 0))
        base = float(price_info.get("baseMoney", {}).get("amount", final))
        discount = int(price_info.get("discount", 0) or 0)
        slug = p.get("slug", "")
        return GameDeal(
            title=p.get("title", "Unknown"),
            platform="GOG",
            store_url=PRODUCT_URL.format(slug=slug),
            current_price=final,
            original_price=base,
            discount_pct=discount,
            game_id=str(p.get("id", "")),
            thumb_url=p.get("coverHorizontal", ""),
            drm_free=True,  # GOG is always DRM-free
            tags=[t.get("name", "") for t in p.get("tags", [])],
        )
