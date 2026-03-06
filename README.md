# game-scraper

A Linux command-line application that scrapes PC game stores for deals, monitors your wishlist, automates purchases, and manages downloads.

## Features

- **Multi-store deal scraping** — CheapShark (30+ stores), GOG, Steam, Epic Games
- **Wishlist monitoring** — set target prices or discount thresholds per game
- **Auto-purchase** — optionally buy GOG games automatically when a deal matches
- **Download manager** — download purchased GOG installers with `aria2c` support
- **Desktop notifications** — `notify-send` integration for deal alerts
- **Daemon/watch mode** — run in the background and check on a schedule

## Installation

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Search for a game
game-scraper search "Witcher 3"

# Browse deals (≥50% off by default)
game-scraper deals --min-discount 60

# Show currently free games
game-scraper free

# Add a game to your wishlist
game-scraper wishlist add "Cyberpunk 2077" --target-price 20 --min-discount 50

# Check wishlist against live prices
game-scraper wishlist check

# Watch wishlist continuously (every 60 minutes by default)
game-scraper watch

# Auto-purchase wishlist deals on GOG (requires login + config)
game-scraper watch --auto-buy
```

## GOG Authentication

```bash
# Open GOG OAuth login in browser
game-scraper gog login

# Purchase a specific game
game-scraper gog buy <game_id>

# Download a purchased game (Linux installer)
game-scraper download <game_id>
```

## Configuration

```bash
# Show config
game-scraper config show

# Enable auto-purchase (disabled by default!)
game-scraper config set auto_purchase true

# Set maximum auto-purchase price
game-scraper config set max_price_usd 15.00

# Set minimum discount to trigger auto-purchase
game-scraper config set min_discount_pct 75

# Change download directory
game-scraper config set download_dir /mnt/games
```

Config file is stored at `~/.config/game_scraper/config.json`.

## Architecture

```
game_scraper/
├── scrapers/
│   ├── cheapshark.py   # CheapShark aggregator API
│   ├── gog.py          # GOG catalog API
│   ├── steam.py        # Steam Store API
│   └── epic.py         # Epic Games GQL API
├── purchaser/
│   └── gog.py          # GOG OAuth + purchase flow
├── downloader/
│   └── manager.py      # Download manager (aria2c / streaming)
├── utils/
│   ├── notify.py       # Desktop notification helper
│   └── table.py        # Rich terminal tables
├── config.py           # Config, wishlist, history management
└── cli.py              # Click CLI
```

## Requirements

- Python 3.11+
- Linux (uses `notify-send` for notifications, `aria2c` for fast downloads — both optional)
- For GOG purchasing: a GOG account with wallet balance

## Safety

- **Auto-purchase is disabled by default.** Enable it explicitly with `config set auto_purchase true`.
- A `max_price_usd` guard prevents runaway spending.
- All purchases are logged to `~/.local/share/game_scraper/purchase_history.json`.
- GOG credentials are stored in your system keyring (not plain text).
