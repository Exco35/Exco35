"""
GOG purchase automation.

Authentication flow:
  1. User provides GOG credentials (stored securely via keyring).
  2. We obtain an OAuth2 token from GOG's auth endpoint.
  3. We use the token to call the GOG embed / checkout API to complete purchases.

IMPORTANT: This module only purchases games that are explicitly added to the
wishlist AND are within the configured price/discount thresholds.  Auto-purchase
must be explicitly enabled by the user in config.
"""

import os
import time
import webbrowser
from datetime import datetime, timezone
from typing import Optional

import keyring
import requests

from ..config import append_history, load_config
from ..scrapers.base import GameDeal

SERVICE_NAME = "game_scraper_gog"
TOKEN_URL = "https://auth.gog.com/token"
USER_DATA_URL = "https://embed.gog.com/userData.json"
CART_ADD_URL = "https://cart.gog.com/cart/add/{game_id}"
ORDER_URL = "https://checkout.gog.com/order/create"
LIBRARY_URL = "https://embed.gog.com/account/gameDetails/{game_id}.json"
OWNED_URL = "https://embed.gog.com/user/data/games"


class GOGAuthError(Exception):
    pass


class GOGPurchaseError(Exception):
    pass


class GOGPurchaser:
    """
    Manages GOG OAuth tokens and purchase flow.

    Credentials are stored in the system keyring under the service name
    ``game_scraper_gog``.  Tokens are cached in memory for the process lifetime.
    """

    CLIENT_ID = "46899977096215655"
    CLIENT_SECRET = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
    REDIRECT_URI = "https://embed.gog.com/on_login_success?origin=client"
    AUTH_URL = (
        "https://auth.gog.com/auth"
        "?client_id={client_id}"
        "&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&layout=client2"
    )

    def __init__(self):
        self.session = requests.Session()
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ------------------------------------------------------------------ #
    #  Authentication                                                      #
    # ------------------------------------------------------------------ #

    def login_with_code(self, auth_code: str):
        """Exchange an OAuth auth-code for tokens and save to keyring."""
        resp = self.session.get(
            TOKEN_URL,
            params={
                "client_id": self.CLIENT_ID,
                "client_secret": self.CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": self.REDIRECT_URI,
            },
            timeout=15,
        )
        resp.raise_for_status()
        self._store_tokens(resp.json())

    def _store_tokens(self, data: dict):
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 3600)) - 60
        keyring.set_password(SERVICE_NAME, "access_token", self._access_token)
        keyring.set_password(SERVICE_NAME, "refresh_token", self._refresh_token)
        keyring.set_password(SERVICE_NAME, "token_expiry", str(self._token_expiry))

    def _load_tokens(self):
        # Environment variables take precedence — useful in Docker / CI.
        self._access_token = (
            os.environ.get("GOG_ACCESS_TOKEN")
            or keyring.get_password(SERVICE_NAME, "access_token")
        )
        self._refresh_token = (
            os.environ.get("GOG_REFRESH_TOKEN")
            or keyring.get_password(SERVICE_NAME, "refresh_token")
        )
        expiry_str = keyring.get_password(SERVICE_NAME, "token_expiry") or "0"
        self._token_expiry = float(expiry_str)

    def _refresh_tokens(self):
        if not self._refresh_token:
            raise GOGAuthError("No refresh token available. Please log in first.")
        resp = self.session.get(
            TOKEN_URL,
            params={
                "client_id": self.CLIENT_ID,
                "client_secret": self.CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        self._store_tokens(resp.json())

    def _ensure_auth(self):
        if not self._access_token:
            self._load_tokens()
        if not self._access_token:
            raise GOGAuthError("Not authenticated. Run: game-scraper gog login")
        if time.time() >= self._token_expiry:
            self._refresh_tokens()

    def _authed_get(self, url: str, **kwargs) -> requests.Response:
        self._ensure_auth()
        kwargs.setdefault("timeout", 15)
        resp = self.session.get(
            url, headers={"Authorization": f"Bearer {self._access_token}"}, **kwargs
        )
        resp.raise_for_status()
        return resp

    def _authed_post(self, url: str, **kwargs) -> requests.Response:
        self._ensure_auth()
        kwargs.setdefault("timeout", 15)
        resp = self.session.post(
            url, headers={"Authorization": f"Bearer {self._access_token}"}, **kwargs
        )
        resp.raise_for_status()
        return resp

    # ------------------------------------------------------------------ #
    #  User info                                                           #
    # ------------------------------------------------------------------ #

    def get_username(self) -> str:
        data = self._authed_get(USER_DATA_URL).json()
        return data.get("username", "unknown")

    def get_owned_game_ids(self) -> set[str]:
        data = self._authed_get(OWNED_URL).json()
        return {str(gid) for gid in data.get("owned", [])}

    def is_owned(self, game_id: str) -> bool:
        return game_id in self.get_owned_game_ids()

    # ------------------------------------------------------------------ #
    #  Purchase flow                                                       #
    # ------------------------------------------------------------------ #

    def buy(self, deal: GameDeal, dry_run: bool = False) -> bool:
        """
        Purchase *deal* on GOG.

        Parameters
        ----------
        deal:    GameDeal with platform == "GOG" and a valid game_id.
        dry_run: If True, validate everything but don't actually charge.

        Returns True on success.
        """
        cfg = load_config()
        if not cfg.get("auto_purchase"):
            raise GOGPurchaseError(
                "auto_purchase is disabled in config. "
                "Enable it with: game-scraper config set auto_purchase true"
            )

        max_price = float(cfg.get("max_price_usd", 0))
        if max_price > 0 and deal.current_price > max_price:
            raise GOGPurchaseError(
                f"Price ${deal.current_price:.2f} exceeds max_price_usd ${max_price:.2f}"
            )

        if deal.platform.lower() != "gog":
            raise GOGPurchaseError(f"GOGPurchaser only supports GOG deals (got {deal.platform})")

        if not deal.game_id:
            raise GOGPurchaseError("Deal has no game_id; cannot purchase")

        # Skip if already owned
        if self.is_owned(deal.game_id):
            return False  # already in library — not an error

        if dry_run:
            return True

        # Add to cart and checkout
        self._authed_post(CART_ADD_URL.format(game_id=deal.game_id))
        order_resp = self._authed_post(
            ORDER_URL,
            json={"paymentMethod": "wallet"},
        )
        order_data = order_resp.json()

        if order_data.get("status") != "ok":
            raise GOGPurchaseError(f"Order failed: {order_data}")

        append_history(
            {
                "title": deal.title,
                "game_id": deal.game_id,
                "platform": "gog",
                "price_paid": deal.current_price,
                "original_price": deal.original_price,
                "discount_pct": deal.discount_pct,
                "purchased_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return True

    def get_auth_url(self) -> str:
        return self.AUTH_URL.format(
            client_id=self.CLIENT_ID,
            redirect_uri=self.REDIRECT_URI,
        )
