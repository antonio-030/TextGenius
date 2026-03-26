"""Application settings management (load/save to JSON)."""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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


def load_settings() -> dict[str, Any]:
    """Load settings from disk, falling back to defaults."""
    path = _get_settings_path()
    settings = dict(DEFAULTS)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
            logger.debug("Settings loaded from %s", path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load settings (%s), using defaults", e)
    else:
        logger.info("No settings file found, using defaults")
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """Save settings to disk. API keys are stored but never logged."""
    path = _get_settings_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        logger.debug("Settings saved to %s", path)
    except OSError as e:
        logger.error("Could not save settings: %s", e)


def get_setting(settings: dict[str, Any], key: str) -> Any:
    """Get a setting value with default fallback."""
    return settings.get(key, DEFAULTS.get(key))
