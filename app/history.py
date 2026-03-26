"""Auto-Speichern und Textverlauf für TextGenius.

Speichert den aktuellen Text automatisch und behält die letzten 10 Texte als Verlauf.
Alles in %APPDATA%/TextGenius/history.json.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_HISTORY = 10


def _get_history_path() -> Path:
    """Pfad zur Verlaufs-Datei."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        d = Path(appdata) / "TextGenius"
    else:
        d = Path.home() / ".textgenius"
    d.mkdir(parents=True, exist_ok=True)
    return d / "history.json"


def _load_raw() -> dict:
    """Lädt die rohe History-Datei."""
    path = _get_history_path()
    if not path.exists():
        return {"draft": "", "entries": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"draft": "", "entries": []}


def _save_raw(data: dict) -> None:
    """Speichert die History-Datei."""
    path = _get_history_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("History speichern fehlgeschlagen: %s", e)


# ── Auto-Speichern ────────────────────────────────────────────

def save_draft(text: str) -> None:
    """Speichert den aktuellen Entwurf (wird beim Tippen aufgerufen)."""
    data = _load_raw()
    data["draft"] = text
    _save_raw(data)


def load_draft() -> str:
    """Lädt den gespeicherten Entwurf."""
    return _load_raw().get("draft", "")


# ── Verlauf ───────────────────────────────────────────────────

def add_to_history(text: str, corrected: str = "", errors: int = 0) -> None:
    """Fügt einen geprüften Text zum Verlauf hinzu."""
    if not text.strip():
        return

    data = _load_raw()
    entry = {
        "text": text[:500],  # Max 500 Zeichen speichern
        "corrected": corrected[:500],
        "errors": errors,
        "time": datetime.now().strftime("%d.%m. %H:%M"),
        "words": len(text.split()),
    }

    # Duplikate vermeiden
    entries = data.get("entries", [])
    entries = [e for e in entries if e.get("text", "")[:50] != text[:50]]

    entries.insert(0, entry)
    data["entries"] = entries[:MAX_HISTORY]
    _save_raw(data)


def get_history() -> list[dict]:
    """Gibt die letzten Verlaufseinträge zurück."""
    return _load_raw().get("entries", [])


def clear_history() -> None:
    """Löscht den Verlauf."""
    data = _load_raw()
    data["entries"] = []
    _save_raw(data)
