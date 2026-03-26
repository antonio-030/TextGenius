"""TextGenius - KI-basierte Rechtschreib- und Grammatikprüfung."""

import sys

import customtkinter as ctk

from app.logger import setup_logging
from app.settings import load_settings, get_setting
from app.ui.main_window import MainWindow


def main() -> None:
    """Application entry point."""
    settings = load_settings()
    setup_logging(level=get_setting(settings, "log_level"))

    ctk.set_appearance_mode(get_setting(settings, "theme"))
    ctk.set_default_color_theme("blue")

    app = MainWindow(settings)
    app.mainloop()


if __name__ == "__main__":
    sys.exit(main() or 0)
