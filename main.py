"""TextGenius - KI-basierte Rechtschreib- und Grammatikprüfung."""

import sys

# SICHERHEIT: DLL-Härtung (optional)
try:
    from app.security import harden_dll_search_order, verify_dll_integrity
    harden_dll_search_order()
except Exception:
    pass

# darkdetect kann auf manchen Systemen hängen -- deaktivieren vor CTk Import
import sys
import types
# Dummy darkdetect damit CTk nicht hängt
dd = types.ModuleType("darkdetect")
dd.theme = lambda: "Light"
dd.listener = lambda callback: None
dd.isDark = lambda: False
dd.isLight = lambda: True
sys.modules["darkdetect"] = dd

import customtkinter as ctk

from app.logger import setup_logging
from app.settings import load_settings, get_setting
from app.ui.main_window import MainWindow


def main() -> None:
    """Application entry point mit globalem Fehler-Handler."""
    try:
        settings = load_settings()
        setup_logging(level=get_setting(settings, "log_level"))

        # DLL-Integrität prüfen (nur bei .exe Build)
        if not verify_dll_integrity():
            import logging
            logging.critical("DLL-Manipulation erkannt! App wird beendet.")
            sys.exit(1)

        ctk.set_appearance_mode(get_setting(settings, "theme"))
        ctk.set_default_color_theme("blue")

        app = MainWindow(settings)
        app.mainloop()

    except Exception as e:
        # Globaler Crash-Handler: zeigt Fehlermeldung statt stiller Absturz
        import traceback
        error_text = traceback.format_exc()
        try:
            import logging
            logging.critical("Unerwarteter Fehler:\n%s", error_text)
        except Exception:
            pass

        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "TextGenius - Fehler",
                f"Ein unerwarteter Fehler ist aufgetreten:\n\n{e}\n\n"
                "Bitte melde diesen Fehler:\n"
                "github.com/antonio-030/TextGenius/issues\n\n"
                "Fehlerbericht wurde kopiert (Ctrl+V zum Einfügen)."
            )
            # Fehler in Zwischenablage kopieren
            root.clipboard_clear()
            root.clipboard_append(error_text)
            root.update()
            root.destroy()
        except Exception:
            print(f"FATALER FEHLER: {error_text}", file=sys.stderr)

        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main() or 0)
