"""Clipboard monitor with global hotkey (Ctrl+Shift+P).

Listens for the hotkey globally using pynput (no admin rights needed).
When triggered, reads the clipboard and sends it for checking.
"""

import logging

import pyperclip
from pynput.keyboard import GlobalHotKeys

logger = logging.getLogger(__name__)


class ClipboardMonitor:
    """Global hotkey listener that triggers text checking from clipboard."""

    def __init__(self, on_check_clipboard):
        """Initialize with a callback that receives clipboard text.

        Args:
            on_check_clipboard: Function(text: str) called on the hotkey.
                                Must be thread-safe (use self.after() inside).
        """
        self._on_check = on_check_clipboard
        self._listener = None

    def start(self):
        """Start listening for Ctrl+Shift+P in a background thread."""
        self._listener = GlobalHotKeys({
            "<ctrl>+<shift>+p": self._on_hotkey,
        })
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey Ctrl+Shift+P registriert")

    def stop(self):
        """Stop listening and clean up."""
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=2.0)
            self._listener = None
            logger.info("Hotkey-Listener gestoppt")

    def _on_hotkey(self):
        """Called from listener thread when Ctrl+Shift+P is pressed."""
        try:
            text = pyperclip.paste()
            if text and text.strip():
                logger.info("Hotkey: Clipboard-Text erkannt (%d zeichen)", len(text))
                self._on_check(text)
            else:
                logger.info("Hotkey: Zwischenablage leer")
        except Exception as e:
            logger.error("Hotkey: Clipboard-Fehler: %s", e)
