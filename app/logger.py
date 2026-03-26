"""Logging configuration with file rotation and sensitive data filtering."""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path


# Patterns that should be anonymized in log output
_SENSITIVE_PATTERNS = [
    # OAuth tokens: sk-ant-oat... (längste Patterns zuerst)
    (re.compile(r"(sk-ant-oat[a-zA-Z0-9_-]{2})[a-zA-Z0-9_-]+"), r"\1****"),
    # API keys: sk-ant-api..., sk-ant-...
    (re.compile(r"(sk-ant-[a-zA-Z0-9_-]{4})[a-zA-Z0-9_-]+"), r"\1****"),
    # Allgemeine API keys: sk-...
    (re.compile(r"(sk-[a-zA-Z0-9_-]{4})[a-zA-Z0-9_-]{4,}"), r"\1****"),
    # Key-Prefixes
    (re.compile(r"(key-[a-zA-Z0-9_-]{4})[a-zA-Z0-9_-]{4,}"), r"\1****"),
    # Bearer tokens (min 8 Zeichen nach Bearer)
    (re.compile(r"(Bearer\s+[a-zA-Z0-9_-]{4})[a-zA-Z0-9_-]{4,}"), r"\1****"),
    # DPAPI/B64 verschlüsselte Werte in Settings
    (re.compile(r"(DPAPI:[a-zA-Z0-9+/=]{8})[a-zA-Z0-9+/=]+"), r"\1****"),
    (re.compile(r"(B64:[a-zA-Z0-9+/=]{8})[a-zA-Z0-9+/=]+"), r"\1****"),
]


class SensitiveDataFilter(logging.Filter):
    """Filter that anonymizes API keys and tokens in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from the log message."""
        if record.msg and isinstance(record.msg, str):
            record.msg = _redact(record.msg)

        # Also redact formatted args
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _redact(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )

        return True


def _redact(text: str) -> str:
    """Replace sensitive patterns in text with masked versions."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _get_log_dir() -> Path:
    """Return the application log directory (%APPDATA%/TextGenius)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        log_dir = Path(appdata) / "TextGenius"
    else:
        log_dir = Path.home() / ".textgenius"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with console output, file rotation, and data filtering."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_file = _get_log_dir() / "textgenius.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-init
    root_logger.handlers.clear()

    # Add sensitive data filter to root logger
    root_logger.addFilter(SensitiveDataFilter())

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler: 5 MB max, 3 backups
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).debug(
        "Logging initialisiert (level=%s, file=%s)", level, log_file,
    )
