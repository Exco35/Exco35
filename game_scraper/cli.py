"""
game-scraper CLI — main entry point.

Commands
--------
  search <query>       Search for a game across all scrapers
  deals                Show current deals
  free                 Show currently free games
  wishlist add         Add game to wishlist
  wishlist list        Show wishlist
  wishlist remove      Remove item from wishlist
  wishlist check       Check wishlist against live prices
  gog login            Authenticate with GOG
  gog buy <game_id>    Purchase a specific GOG game
  download <game_id>   Download a purchased GOG game
  config show          Show current config
  config set <k> <v>   Update a config value
  watch                Run continuous deal monitor (daemon mode)
  history              Show purchase history
"""

import sys
import time
import webbrowser

import click
from rich.console import Console

from . import __version__
from .config import (
    load_config, save_config,
    load_wishlist, save_wishlist,
    load_history,
)
from .scrapers import CheapSharkScraper, GOGScraper, SteamScraper, EpicScraper
from .scrapers.base import GameDeal
from .purchaser import GOGPurchaser
from .downloader import DownloadManager
from .utils import notify
from .utils.table import print_deals_table, print_wishlist_table, console

# ---------------------------------------------------------------------------


def _get_scrapers(platforms: list[str]) -> list:
    all_scrapers = {
        "cheapshark": CheapSharkScraper,
        "gog": GOGScraper,
        "steam": SteamScraper,
        "epic": EpicScraper,
    }
    active = platforms or list(all_scrapers.keys())
    return [cls() for name, cls in all_scrapers.items() if name in active]


# ---------------------------------------------------------------------------
#  Root group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(__version__, prog_name="game-scraper")
def cli():
    """game-scraper: find deals, auto-purchase, and download PC games on Linux."""


# ---------------------------------------------------------------------------
#  Search
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option("--platform", "-p", multiple=True,
              help="Platforms to search (cheapshark, gog, steam, epic). Repeatable.")
@click.option("--limit", "-l", default=10, show_default=True, help="Results per platform.")
def search(query: str, platform: tuple, limit: int):
    """Search for a game across stores."""
    cfg = load_config()
    platforms = list(platform) or cfg.get("platforms", [])
    scrapers = _get_scrapers(platforms)
    all_deals: list[GameDeal] = []

    for scraper in scrapers:
        try:
            results = scraper.search(query, limit=limit)
            all_deals.extend(results)
        except Exception as exc:
            console.print(f"[red]{scraper.name} error:[/red] {exc}")

    all_deals.sort(key=lambda d: d.current_price)
    print_deals_table(all_deals, title=f'Search: "{query}"')


# ---------------------------------------------------------------------------
#  Deals
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--platform", "-p", multiple=True)
@click.option("--min-discount", "-d", default=50, show_default=True)
@click.option("--limit", "-l", default=20, show_default=True)
@click.option("--max-price", "-m", default=0.0, type=float, help="Max price in USD (0 = any)")
def deals(platform: tuple, min_discount: int, limit: int, max_price: float):
    """Show current deals across stores."""
    cfg = load_config()
    platforms = list(platform) or cfg.get("platforms", [])
    scrapers = _get_scrapers(platforms)
    all_deals: list[GameDeal] = []

    for scraper in scrapers:
        try:
            results = scraper.get_deals(min_discount=min_discount, limit=limit)
            all_deals.extend(results)
        except Exception as exc:
            console.print(f"[red]{scraper.name} error:[/red] {exc}")

    if max_price > 0:
        all_deals = [d for d in all_deals if d.current_price <= max_price]

    all_deals.sort(key=lambda d: (-d.discount_pct, d.current_price))
    print_deals_table(all_deals[:limit], title=f"Deals (≥{min_discount}% off)")


# ---------------------------------------------------------------------------
#  Free games
# ---------------------------------------------------------------------------

@cli.command("free")
@click.option("--platform", "-p", multiple=True)
def free_games(platform: tuple):
    """Show currently free games."""
    cfg = load_config()
    platforms = list(platform) or cfg.get("platforms", [])
    scrapers = _get_scrapers(platforms)
    all_free: list[GameDeal] = []

    for scraper in scrapers:
        try:
            all_free.extend(scraper.get_free_games())
        except Exception as exc:
            console.print(f"[red]{scraper.name} error:[/red] {exc}")

    print_deals_table(all_free, title="Free Games Right Now")


# ---------------------------------------------------------------------------
#  Wishlist
# ---------------------------------------------------------------------------

@cli.group()
def wishlist():
    """Manage your game wishlist."""


@wishlist.command("add")
@click.argument("title")
@click.option("--target-price", "-t", type=float, default=0.0,
              help="Buy when price drops to this value (0 = any deal).")
@click.option("--min-discount", "-d", type=int, default=0,
              help="Minimum discount percentage to trigger purchase.")
@click.option("--platform", "-p", multiple=True)
def wishlist_add(title: str, target_price: float, min_discount: int, platform: tuple):
    """Add a game to the wishlist."""
    wl = load_wishlist()
    entry = {
        "title": title,
        "target_price": target_price,
        "min_discount": min_discount,
        "platforms": list(platform) or ["any"],
    }
    wl.append(entry)
    save_wishlist(wl)
    console.print(f"[green]Added[/green] '{title}' to wishlist.")


@wishlist.command("list")
def wishlist_list():
    """Show wishlist."""
    print_wishlist_table(load_wishlist())


@wishlist.command("remove")
@click.argument("index", type=int)
def wishlist_remove(index: int):
    """Remove wishlist item by number (1-indexed)."""
    wl = load_wishlist()
    if index < 1 or index > len(wl):
        console.print(f"[red]Invalid index {index}. Wishlist has {len(wl)} items.[/red]")
        sys.exit(1)
    removed = wl.pop(index - 1)
    save_wishlist(wl)
    console.print(f"[green]Removed[/green] '{removed['title']}' from wishlist.")


@wishlist.command("check")
@click.option("--auto-buy", is_flag=True, default=False,
              help="Automatically purchase games that match criteria (requires auto_purchase=true).")
def wishlist_check(auto_buy: bool):
    """Check wishlist items against live prices and optionally auto-purchase."""
    wl = load_wishlist()
    if not wl:
        console.print("[yellow]Wishlist is empty.[/yellow]")
        return

    cfg = load_config()
    gog_purchaser = GOGPurchaser()
    triggered: list[GameDeal] = []

    for item in wl:
        title = item["title"]
        target_price = item.get("target_price", 0.0)
        min_discount = item.get("min_discount", 0)
        item_platforms = item.get("platforms", ["any"])
        active_platforms = (
            item_platforms if "any" not in item_platforms else cfg.get("platforms", [])
        )
        scrapers = _get_scrapers(active_platforms)

        for scraper in scrapers:
            try:
                results = scraper.search(title, limit=5)
            except Exception:
                continue

            for deal in results:
                price_ok = (target_price == 0.0 or deal.current_price <= target_price)
                discount_ok = deal.discount_pct >= min_discount
                title_match = title.lower() in deal.title.lower()

                if title_match and price_ok and discount_ok:
                    triggered.append(deal)
                    console.print(
                        f"[green]Deal found![/green] {deal.title} — ${deal.current_price:.2f} "
                        f"(-{deal.discount_pct}%) on {deal.platform}"
                    )
                    notify(
                        f"Deal: {deal.title}",
                        f"${deal.current_price:.2f} (-{deal.discount_pct}%) on {deal.platform}",
                    )

                    if auto_buy and deal.platform.lower() == "gog":
                        try:
                            bought = gog_purchaser.buy(deal)
                            if bought:
                                console.print(f"  [bold green]Purchased![/bold green] {deal.title}")
                                notify(f"Purchased: {deal.title}", f"${deal.current_price:.2f}")
                        except Exception as exc:
                            console.print(f"  [red]Purchase failed:[/red] {exc}")

    if not triggered:
        console.print("[dim]No wishlist deals found at this time.[/dim]")


# ---------------------------------------------------------------------------
#  GOG auth & purchase
# ---------------------------------------------------------------------------

@cli.group()
def gog():
    """GOG.com account commands."""


@gog.command("login")
def gog_login():
    """Authenticate with GOG.com via OAuth."""
    purchaser = GOGPurchaser()
    auth_url = purchaser.get_auth_url()
    console.print(
        "[bold]Opening GOG login page...[/bold]\n"
        f"If your browser does not open, visit:\n  [blue]{auth_url}[/blue]\n"
    )
    webbrowser.open(auth_url)
    console.print(
        "After logging in, GOG will redirect you to a URL starting with\n"
        "  https://embed.gog.com/on_login_success?code=...\n"
        "Copy the [bold]code[/bold] parameter value from that URL."
    )
    code = click.prompt("Paste the auth code here")
    purchaser.login_with_code(code.strip())
    username = purchaser.get_username()
    console.print(f"[green]Logged in as[/green] {username}")


@gog.command("buy")
@click.argument("game_id")
@click.option("--dry-run", is_flag=True, default=False,
              help="Validate but do not charge.")
def gog_buy(game_id: str, dry_run: bool):
    """Purchase a GOG game by its store ID."""
    purchaser = GOGPurchaser()
    gog_scraper = GOGScraper()

    # Look up game info
    results = gog_scraper.search(game_id, limit=1)
    if not results:
        console.print(f"[red]Game ID {game_id} not found on GOG.[/red]")
        sys.exit(1)
    deal = results[0]
    deal.game_id = game_id

    label = "[dim](dry run)[/dim] " if dry_run else ""
    console.print(f"{label}Purchasing [bold]{deal.title}[/bold] for ${deal.current_price:.2f}...")
    try:
        ok = purchaser.buy(deal, dry_run=dry_run)
        if ok:
            console.print(f"[green]Success![/green]")
        else:
            console.print("[yellow]Already owned.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Failed:[/red] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
#  Download
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("game_id")
@click.option("--os", "os_filter", default="linux", show_default=True,
              type=click.Choice(["linux", "windows", "mac"], case_sensitive=False))
@click.option("--url", "direct_url", default="", help="Direct URL to download instead.")
def download(game_id: str, os_filter: str, direct_url: str):
    """Download a purchased GOG game (or a direct URL)."""
    from .purchaser.gog import GOGAuthError
    import keyring

    access_token = keyring.get_password("game_scraper_gog", "access_token")
    mgr = DownloadManager(access_token=access_token)

    if direct_url:
        console.print(f"Downloading [bold]{direct_url}[/bold]...")
        path = mgr.download_url(direct_url)
        console.print(f"[green]Saved to:[/green] {path}")
        return

    console.print(f"Fetching download links for game ID [bold]{game_id}[/bold] ({os_filter})...")
    try:
        paths = mgr.download_gog_game(game_id, os_filter=os_filter)
        for p in paths:
            console.print(f"[green]Downloaded:[/green] {p}")
    except Exception as exc:
        console.print(f"[red]Download failed:[/red] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
#  Config
# ---------------------------------------------------------------------------

@cli.group()
def config():
    """View and update configuration."""


@config.command("show")
def config_show():
    """Print current configuration."""
    import json
    cfg = load_config()
    console.print_json(json.dumps(cfg, indent=2))


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a config value (e.g. 'auto_purchase true')."""
    cfg = load_config()
    # Type coercion
    if value.lower() in ("true", "false"):
        cfg[key] = value.lower() == "true"
    else:
        try:
            cfg[key] = float(value) if "." in value else int(value)
        except ValueError:
            cfg[key] = value
    save_config(cfg)
    console.print(f"[green]Set[/green] {key} = {cfg[key]!r}")


# ---------------------------------------------------------------------------
#  History
# ---------------------------------------------------------------------------

@cli.command()
def history():
    """Show purchase history."""
    from rich.table import Table
    from rich import box as rbox

    hist = load_history()
    if not hist:
        console.print("[yellow]No purchase history.[/yellow]")
        return

    table = Table(title="Purchase History", box=rbox.ROUNDED, expand=True)
    table.add_column("#", width=4, justify="right", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Platform", width=10)
    table.add_column("Paid", width=10, justify="right", style="green")
    table.add_column("Discount", width=9, justify="center", style="red")
    table.add_column("Date", width=22)

    for i, h in enumerate(hist, 1):
        table.add_row(
            str(i),
            h.get("title", "?"),
            h.get("platform", "?"),
            f"${h.get('price_paid', 0):.2f}",
            f"-{h.get('discount_pct', 0)}%",
            h.get("purchased_at", "?")[:19],
        )
    console.print(table)


# ---------------------------------------------------------------------------
#  Watch (daemon mode)
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--interval", "-i", default=0,
              help="Check interval in minutes (0 = use config value).")
@click.option("--auto-buy", is_flag=True, default=False)
def watch(interval: int, auto_buy: bool):
    """
    Continuously monitor wishlist for deals.
    Press Ctrl+C to stop.
    """
    import schedule

    cfg = load_config()
    minutes = interval or cfg.get("check_interval_minutes", 60)

    def _check():
        console.rule("[bold]Checking wishlist...[/bold]")
        ctx = click.Context(wishlist_check)
        with ctx:
            wishlist_check.invoke(ctx, auto_buy=auto_buy)

    _check()  # run immediately
    schedule.every(minutes).minutes.do(_check)
    console.print(f"[dim]Watching every {minutes} minutes. Ctrl+C to stop.[/dim]")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
