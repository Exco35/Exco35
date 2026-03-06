"""
Desktop notification helper (Linux).
Uses notify-send if available; falls back to printing to stdout.
"""

import shutil
import subprocess


def notify(title: str, body: str, urgency: str = "normal"):
    """Send a desktop notification."""
    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-u", urgency, title, body],
            check=False,
        )
    else:
        print(f"[NOTIFY] {title}: {body}")
