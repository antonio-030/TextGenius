"""Application settings management with encrypted key storage."""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Felder die sensibel sind und verschlüsselt gespeichert werden
_SENSITIVE_KEYS = {"claude_api_key"}

DEFAULTS = {
    "backend": "ollama",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3",
    "claude_api_key": "",
    "claude_model": "claude-sonnet-4-20250514",
    "proxy_model": "claude-sonnet-4-20250514",
    "language": "de",
    "theme": "light",
    "log_level": "INFO",
    "clipboard_monitor": False,
    "font_size": 12,
}


def _get_settings_path() -> Path:
    """Return the path to the settings file."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        settings_dir = Path(appdata) / "TextGenius"
    else:
        settings_dir = Path.home() / ".textgenius"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "settings.json"


# ── Verschlüsselung (Windows DPAPI) ──────────────────────────

def _encrypt_value(value: str) -> str:
    """Verschlüsselt einen String mit Windows DPAPI.

    Nur der aktuelle Windows-User kann entschlüsseln.
    Fallback: base64-Encoding wenn DPAPI nicht verfügbar.
    """
    if not value:
        return ""
    try:
        import win32crypt
        # DPAPI verschlüsselt mit dem Windows-User-Profil
        encrypted = win32crypt.CryptProtectData(
            value.encode("utf-8"), "TextGenius", None, None, None, 0
        )
        return "DPAPI:" + base64.b64encode(encrypted).decode("ascii")
    except ImportError:
        # win32crypt nicht verfügbar -- base64 als Fallback
        return "B64:" + base64.b64encode(value.encode("utf-8")).decode("ascii")


def _decrypt_value(stored: str) -> str:
    """Entschlüsselt einen gespeicherten Wert."""
    if not stored:
        return ""
    # DPAPI-verschlüsselt
    if stored.startswith("DPAPI:"):
        try:
            import win32crypt
            raw = base64.b64decode(stored[6:])
            _, decrypted = win32crypt.CryptUnprotectData(raw, None, None, None, 0)
            return decrypted.decode("utf-8")
        except Exception:
            logger.warning("DPAPI-Entschlüsselung fehlgeschlagen")
            return ""
    # Base64-Fallback
    if stored.startswith("B64:"):
        try:
            return base64.b64decode(stored[4:]).decode("utf-8")
        except Exception:
            return ""
    # Klartext (alte Settings vor der Verschlüsselung)
    return stored


# ── Load / Save ───────────────────────────────────────────────

def load_settings() -> dict[str, Any]:
    """Load settings from disk. Sensible Werte werden entschlüsselt."""
    path = _get_settings_path()
    settings = dict(DEFAULTS)

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)

            # Nur bekannte Keys übernehmen (Whitelist)
            for key in DEFAULTS:
                if key in saved:
                    settings[key] = saved[key]

            # Sensible Werte entschlüsseln
            for key in _SENSITIVE_KEYS:
                if settings.get(key):
                    settings[key] = _decrypt_value(settings[key])

            logger.debug("Settings loaded from %s", path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load settings (%s), using defaults", e)
    else:
        logger.info("No settings file found, using defaults")

    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """Save settings to disk. Sensible Werte werden verschlüsselt."""
    path = _get_settings_path()

    # Symlink-Schutz: nicht in Symlinks schreiben
    if path.is_symlink():
        logger.error("Settings-Datei ist ein Symlink -- Schreiben verweigert")
        return

    # Kopie erstellen und sensible Werte verschlüsseln
    to_save = dict(settings)
    for key in _SENSITIVE_KEYS:
        value = to_save.get(key, "")
        if value and not value.startswith(("DPAPI:", "B64:")):
            to_save[key] = _encrypt_value(value)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2, ensure_ascii=False)
        logger.debug("Settings saved to %s", path)
    except OSError as e:
        logger.error("Could not save settings: %s", e)


def get_setting(settings: dict[str, Any], key: str) -> Any:
    """Get a setting value with default fallback."""
    return settings.get(key, DEFAULTS.get(key))
