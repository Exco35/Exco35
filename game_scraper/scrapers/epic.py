"""
Epic Games Store scraper.
Fetches the weekly free games and current promotions from the public
Epic GraphQL storefront API (no auth required).
"""

from .base import BaseScraper, GameDeal

EPIC_GQL = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
EPIC_SEARCH = "https://store-site-backend-static.ak.epicgames.com/graphql"
EPIC_URL = "https://store.epicgames.com/en-US/p/{slug}"

SEARCH_QUERY = """
query searchStoreQuery($keywords: String!, $count: Int) {
  Catalog {
    searchStore(keywords: $keywords, count: $count, category: "games/edition/base") {
      elements {
        title
        id
        namespace
        description
        keyImages { type url }
        price(country: "US") {
          totalPrice {
            discountPrice
            originalPrice
            discount
          }
        }
        catalogNs { mappings(pageType: "productHome") { pageSlug } }
      }
    }
  }
}
"""


class EpicScraper(BaseScraper):
    name = "epic"

    def search(self, query: str, limit: int = 20) -> list[GameDeal]:
        payload = {
            "query": SEARCH_QUERY,
            "variables": {"keywords": query, "count": limit},
        }
        resp = self.session.post(EPIC_SEARCH, json=payload, timeout=15)
        resp.raise_for_status()
        elements = (
            resp.json()
            .get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )
        return [self._element_to_deal(e) for e in elements]

    def get_deals(self, min_discount: int = 50, limit: int = 50) -> list[GameDeal]:
        # Epic doesn't expose a simple "all sales" endpoint; use free games + free promotions
        free = self.get_free_games()
        return [d for d in free if d.discount_pct >= min_discount][:limit]

    def get_free_games(self) -> list[GameDeal]:
        params = {"locale": "en-US", "country": "US", "allowCountries": "US"}
        data = self._get(EPIC_GQL, params=params).json()
        elements = (
            data.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )
        free = []
        for el in elements:
            promotions = el.get("promotions") or {}
            offers = promotions.get("promotionalOffers", [])
            if not offers:
                continue
            for offer_group in offers:
                for offer in offer_group.get("promotionalOffers", []):
                    if offer.get("discountSetting", {}).get("discountPercentage", 100) == 0:
                        deal = self._element_to_deal(el)
                        deal.discount_pct = 100
                        deal.current_price = 0.0
                        free.append(deal)
                        break
        return free

    # ------------------------------------------------------------------ #

    def _element_to_deal(self, el: dict) -> GameDeal:
        price_obj = el.get("price", {}).get("totalPrice", {})
        original = price_obj.get("originalPrice", 0) / 100
        final = price_obj.get("discountPrice", original) / 100
        discount = price_obj.get("discount", 0)
        discount_pct = int((discount / (original * 100)) * 100) if original > 0 else 0

        mappings = (
            el.get("catalogNs", {}).get("mappings") or [{}]
        )
        slug = mappings[0].get("pageSlug", el.get("id", ""))
        thumb = next(
            (img["url"] for img in el.get("keyImages", []) if img.get("type") == "Thumbnail"),
            "",
        )
        return GameDeal(
            title=el.get("title", "Unknown"),
            platform="Epic Games",
            store_url=EPIC_URL.format(slug=slug),
            current_price=final,
            original_price=original,
            discount_pct=discount_pct,
            game_id=el.get("id", ""),
            thumb_url=thumb,
            description=el.get("description", ""),
        )
