"""Rich table helpers for displaying game deals in the terminal."""

from rich.console import Console
from rich.table import Table
from rich import box

from ..scrapers.base import GameDeal

console = Console()


def print_deals_table(deals: list[GameDeal], title: str = "Game Deals"):
    if not deals:
        console.print(f"[yellow]No deals found.[/yellow]")
        return

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_lines=False,
        highlight=True,
        expand=True,
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Title", style="bold white", min_width=30)
    table.add_column("Store", style="cyan", width=14)
    table.add_column("Price", style="green", width=10, justify="right")
    table.add_column("Was", style="dim", width=10, justify="right")
    table.add_column("Off", style="red bold", width=6, justify="right")
    table.add_column("DRM-free", width=9, justify="center")

    for i, deal in enumerate(deals, 1):
        drm = "[green]Yes[/green]" if deal.drm_free else "[dim]No[/dim]"
        was = f"${deal.original_price:.2f}" if deal.original_price > deal.current_price else "-"
        table.add_row(
            str(i),
            deal.title,
            deal.platform,
            f"${deal.current_price:.2f}" if deal.current_price > 0 else "[green]FREE[/green]",
            was,
            f"-{deal.discount_pct}%" if deal.discount_pct else "-",
            drm,
        )

    console.print(table)


def print_wishlist_table(wishlist: list[dict]):
    if not wishlist:
        console.print("[yellow]Wishlist is empty.[/yellow]")
        return

    table = Table(title="Wishlist", box=box.ROUNDED, show_lines=False, expand=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Title", style="bold white", min_width=30)
    table.add_column("Target Price", style="green", width=14, justify="right")
    table.add_column("Min Discount %", width=15, justify="center")
    table.add_column("Platforms", width=25)

    for i, item in enumerate(wishlist, 1):
        platforms = ", ".join(item.get("platforms", ["any"]))
        target = f"${item['target_price']:.2f}" if item.get("target_price") else "any"
        min_disc = f"{item.get('min_discount', 0)}%"
        table.add_row(str(i), item["title"], target, min_disc, platforms)

    console.print(table)
