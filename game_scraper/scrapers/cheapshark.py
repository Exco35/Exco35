"""
CheapShark API scraper — aggregates deals from 30+ PC game stores.
API docs: https://apidocs.cheapshark.com/
"""

from .base import BaseScraper, GameDeal

API_BASE = "https://www.cheapshark.com/api/1.0"
STORE_URL = "https://www.cheapshark.com/redirect?dealID={deal_id}"

# CheapShark store IDs for the most popular stores
STORE_MAP = {
    "1": "Steam",
    "7": "GOG",
    "11": "Humble",
    "25": "Epic Games",
    "13": "GamersGate",
    "15": "Fanatical",
}


class CheapSharkScraper(BaseScraper):
    name = "cheapshark"

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def search(self, query: str, limit: int = 20) -> list[GameDeal]:
        """Search by game title across all tracked stores."""
        data = self._get(
            f"{API_BASE}/games",
            params={"title": query, "limit": limit, "exact": 0},
        ).json()
        deals: list[GameDeal] = []
        for item in data:
            deal = self._game_to_deal(item)
            if deal:
                deals.append(deal)
        return deals

    def get_deals(self, min_discount: int = 50, limit: int = 50) -> list[GameDeal]:
        """Fetch current deals with at least *min_discount* % off."""
        data = self._get(
            f"{API_BASE}/deals",
            params={
                "sortBy": "savings",
                "desc": 1,
                "pageSize": limit,
                "lowerPrice": 0,
                "upperPrice": 60,
            },
        ).json()
        deals: list[GameDeal] = []
        for item in data:
            savings_pct = int(float(item.get("savings", 0)))
            if savings_pct < min_discount:
                continue
            deals.append(self._deal_item_to_deal(item))
        return deals

    def get_game_by_id(self, game_id: str) -> dict | None:
        """Fetch detailed info for a specific CheapShark game ID."""
        data = self._get(f"{API_BASE}/games", params={"id": game_id}).json()
        return data if data else None

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _game_to_deal(self, item: dict) -> GameDeal | None:
        try:
            cheapest = item.get("cheapest", "0")
            lowest = item.get("cheapestDealID", "")
            title = item.get("external", item.get("internalName", "Unknown"))
            return GameDeal(
                title=title,
                platform="cheapshark",
                store_url=STORE_URL.format(deal_id=lowest),
                current_price=float(cheapest),
                original_price=float(cheapest),  # no original in list view
                discount_pct=0,
                game_id=str(item.get("gameID", "")),
                thumb_url=item.get("thumb", ""),
            )
        except (KeyError, ValueError):
            return None

    def _deal_item_to_deal(self, item: dict) -> GameDeal:
        current = float(item.get("salePrice", 0))
        original = float(item.get("normalPrice", current))
        discount = int(float(item.get("savings", 0)))
        store_id = str(item.get("storeID", ""))
        platform = STORE_MAP.get(store_id, f"store_{store_id}")
        return GameDeal(
            title=item.get("title", "Unknown"),
            platform=platform,
            store_url=STORE_URL.format(deal_id=item.get("dealID", "")),
            current_price=current,
            original_price=original,
            discount_pct=discount,
            game_id=str(item.get("gameID", "")),
            thumb_url=item.get("thumb", ""),
        )
