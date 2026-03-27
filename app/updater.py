"""Auto-Update Checker: Prüft GitHub Releases auf neue Versionen.

Vergleicht die aktuelle APP_VERSION mit dem neuesten GitHub Release.
Prüfung maximal alle 24 Stunden, läuft im Hintergrund-Thread.
"""

import logging
import time
from datetime import datetime

import requests

from version import APP_VERSION

logger = logging.getLogger(__name__)

# GitHub API Endpoint für das neueste Release
GITHUB_API = "https://api.github.com/repos/antonio-030/TextGenius/releases/latest"
DOWNLOAD_URL = "https://techlogia.de/produkte/textgenius"
GITHUB_RELEASE_URL = "https://github.com/antonio-030/TextGenius/releases/latest"

# Alle 24 Stunden prüfen
CHECK_INTERVAL_HOURS = 24


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parst eine Versionsnummer wie 'v2.0.0' oder '2.0.0' in ein Tupel."""
    clean = version_str.strip().lstrip("v")
    try:
        return tuple(int(x) for x in clean.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def is_newer(remote: str, local: str) -> bool:
    """Prüft ob die Remote-Version neuer ist als die lokale."""
    return parse_version(remote) > parse_version(local)


def should_check(last_check: str) -> bool:
    """Prüft ob genug Zeit seit dem letzten Check vergangen ist."""
    if not last_check:
        return True
    try:
        last = datetime.strptime(last_check, "%Y-%m-%d %H:%M")
        hours_passed = (datetime.now() - last).total_seconds() / 3600
        return hours_passed >= CHECK_INTERVAL_HOURS
    except (ValueError, TypeError):
        return True


def check_for_update() -> dict:
    """Prüft ob ein Update verfügbar ist.

    Returns:
        {
            "available": True/False,
            "current": "2.0.0",
            "latest": "2.1.0",
            "download_url": "https://...",
            "release_notes": "...",
            "checked_at": "2026-03-27 08:30"
        }
    """
    result = {
        "available": False,
        "current": APP_VERSION,
        "latest": APP_VERSION,
        "download_url": DOWNLOAD_URL,
        "release_notes": "",
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    try:
        logger.info("Prüfe auf Updates...")
        t0 = time.time()

        resp = requests.get(
            GITHUB_API,
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        latest_tag = data.get("tag_name", "")
        result["latest"] = latest_tag.lstrip("v")
        result["release_notes"] = data.get("body", "")[:200]

        # Download-URL aus den Assets extrahieren (Setup exe)
        assets = data.get("assets", [])
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith(".exe") and "Setup" in name:
                result["download_url"] = asset.get("browser_download_url", DOWNLOAD_URL)
                break

        # Version vergleichen
        if is_newer(latest_tag, APP_VERSION):
            result["available"] = True
            logger.info(
                "Update verfügbar: %s → %s (%.1fs)",
                APP_VERSION, result["latest"], time.time() - t0,
            )
        else:
            logger.info("App ist aktuell (v%s, %.1fs)", APP_VERSION, time.time() - t0)

    except requests.ConnectionError:
        logger.info("Update-Check: Keine Internetverbindung")
    except requests.HTTPError as e:
        logger.warning("Update-Check fehlgeschlagen: %s", e)
    except Exception as e:
        logger.warning("Update-Check Fehler: %s", e)

    return result
