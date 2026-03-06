"""
Download manager for game installers.

Supports:
  - GOG game downloads via the GOG embed API (requires auth).
  - Direct URL downloads (for free/DRM-free installers).
  - Progress display via tqdm.
  - aria2c integration for multi-connection downloads (if installed).
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote

import requests
from tqdm import tqdm

from ..config import load_config

GOG_CONTENT_SYSTEM = "https://content-system.gog.com"
GOG_CDN = "https://cdn.gog.com"


class DownloadError(Exception):
    pass


class DownloadManager:
    """
    Downloads game installers to the configured download directory.

    If ``aria2c`` is detected on PATH it will be used automatically for
    faster, multi-threaded downloads; otherwise falls back to streaming
    HTTP with a tqdm progress bar.
    """

    def __init__(self, access_token: Optional[str] = None):
        self.cfg = load_config()
        self.download_dir = Path(self.cfg.get("download_dir", str(Path.home() / "Games")))
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        if access_token:
            self.session.headers["Authorization"] = f"Bearer {access_token}"
        self._has_aria2c = shutil.which("aria2c") is not None

    # ------------------------------------------------------------------ #
    #  GOG downloads                                                       #
    # ------------------------------------------------------------------ #

    def get_gog_download_links(self, game_id: str) -> list[dict]:
        """
        Fetch the list of installer download links for a GOG game.
        Returns a list of {name, url, size, os} dicts.
        """
        url = f"https://embed.gog.com/account/gameDetails/{game_id}.json"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        links = []
        for dl in data.get("downloads", []):
            # Each download is [name, {"manualUrl": ..., "name": ..., "size": ...}]
            if not isinstance(dl, list) or len(dl) < 2:
                continue
            category = dl[0]  # "Installer", "DLC", etc.
            details = dl[1]
            if not isinstance(details, dict):
                continue
            for platform, files in details.items():
                if not isinstance(files, list):
                    continue
                for f in files:
                    manual_url = f.get("manualUrl", "")
                    if manual_url:
                        links.append(
                            {
                                "name": f.get("name", category),
                                "url": f"https://www.gog.com{manual_url}",
                                "size": f.get("size", "unknown"),
                                "os": platform,
                                "category": category,
                            }
                        )
        return links

    def download_gog_game(self, game_id: str, os_filter: str = "linux") -> list[Path]:
        """
        Download GOG installer(s) for *game_id*, filtered to *os_filter*.
        Returns a list of downloaded file paths.
        """
        links = self.get_gog_download_links(game_id)
        linux_links = [l for l in links if l["os"].lower() == os_filter.lower()]
        if not linux_links:
            # Fall back to any OS
            linux_links = links
        downloaded = []
        for link in linux_links:
            path = self.download_url(link["url"], filename=self._url_to_filename(link["url"]))
            downloaded.append(path)
        return downloaded

    # ------------------------------------------------------------------ #
    #  Generic download                                                    #
    # ------------------------------------------------------------------ #

    def download_url(self, url: str, filename: Optional[str] = None) -> Path:
        """
        Download *url* to the download directory.
        Uses aria2c if available; otherwise streams with progress bar.
        """
        if not filename:
            filename = self._url_to_filename(url)
        dest = self.download_dir / filename

        if self._has_aria2c:
            return self._download_aria2c(url, dest)
        return self._download_streaming(url, dest)

    def _download_aria2c(self, url: str, dest: Path) -> Path:
        cmd = [
            "aria2c",
            "--split=8",
            "--max-connection-per-server=8",
            "--min-split-size=10M",
            "--continue=true",
            f"--dir={dest.parent}",
            f"--out={dest.name}",
            url,
        ]
        # Pass auth header if present
        auth_header = self.session.headers.get("Authorization")
        if auth_header:
            cmd += [f"--header=Authorization: {auth_header}"]

        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            raise DownloadError(f"aria2c failed with exit code {result.returncode}")
        return dest

    def _download_streaming(self, url: str, dest: Path) -> Path:
        # Follow redirects (GOG uses signed CDN URLs)
        resp = self.session.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        tmp = dest.with_suffix(dest.suffix + ".part")

        try:
            with open(tmp, "wb") as f, tqdm(
                desc=dest.name,
                total=total,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))
            tmp.rename(dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

        return dest

    # ------------------------------------------------------------------ #

    @staticmethod
    def _url_to_filename(url: str) -> str:
        path = urlparse(url).path
        name = unquote(path.split("/")[-1])
        return name or "installer.bin"
