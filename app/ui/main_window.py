"""Main application window layout and logic."""

import logging
import os
import sys
import threading
from typing import Any

import customtkinter as ctk
import pyperclip

from app.backends.base import BaseBackend
from app.backends.ollama import OllamaBackend
from app.backends.claude import ClaudeBackend
from app.backends.claude_oauth import ClaudeOAuthBackend
from app.checker import check_text
from app.clipboard import ClipboardMonitor
from app.settings import get_setting
from app.ui.settings_dialog import SettingsDialog
from version import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)


class MainWindow(ctk.CTk):
    """The main TextGenius application window."""

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self._checking = False
        self._settings_dialog = None
        self._clipboard = ClipboardMonitor(self._on_hotkey_check)

        # Window setup
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1000x680")
        self.minsize(800, 550)

        # Set window icon -- resolve path relative to exe/script location
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            icon_path = os.path.join(base_path, "assets", "icon.ico")
            self.iconbitmap(icon_path)
        except Exception:
            logger.debug("Icon file not found, using default")

        # Grid layout: sidebar (col 0) + content (col 1)
        self.grid_columnconfigure(0, weight=0)  # sidebar fixed
        self.grid_columnconfigure(1, weight=1)  # content expands
        self.grid_rowconfigure(0, weight=1)      # full height

        self._build_sidebar()
        self._build_content()

        # Start hotkey listener + clean shutdown
        self._clipboard.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_sidebar(self) -> None:
        """Build the left sidebar with navigation and info."""
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)  # push bottom items down
        self.sidebar.grid_propagate(False)

        # App title
        ctk.CTkLabel(
            self.sidebar, text=APP_NAME,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(24, 4), sticky="w")

        ctk.CTkLabel(
            self.sidebar, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        ).grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # Action buttons in sidebar
        self.check_button = ctk.CTkButton(
            self.sidebar, text="\u2714  Text prüfen",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40, corner_radius=8,
            command=self._on_check,
        )
        self.check_button.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        self.paste_button = ctk.CTkButton(
            self.sidebar, text="\u2398  Einfügen",
            font=ctk.CTkFont(size=13),
            height=36, corner_radius=8,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            border_color=("gray70", "gray30"),
            hover_color=("gray85", "gray25"),
            command=self._on_paste,
        )
        self.paste_button.grid(row=3, column=0, padx=16, pady=(0, 6), sticky="ew")

        self.copy_button = ctk.CTkButton(
            self.sidebar, text="\u2750  Kopieren",
            font=ctk.CTkFont(size=13),
            height=36, corner_radius=8,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            border_color=("gray70", "gray30"),
            hover_color=("gray85", "gray25"),
            command=self._on_copy,
        )
        self.copy_button.grid(row=4, column=0, padx=16, pady=(0, 6), sticky="ew")

        self.clear_button = ctk.CTkButton(
            self.sidebar, text="\u2715  Leeren",
            font=ctk.CTkFont(size=13),
            height=36, corner_radius=8,
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            hover_color=("gray85", "gray25"),
            command=self._on_clear,
        )
        self.clear_button.grid(row=5, column=0, padx=16, pady=(0, 6), sticky="ew")

        # Status label (in sidebar, above bottom info)
        self.status_label = ctk.CTkLabel(
            self.sidebar, text="",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
            wraplength=170,
        )
        self.status_label.grid(row=6, column=0, padx=16, pady=(12, 0), sticky="w")

        # Bottom: settings button + theme switch
        self.settings_button = ctk.CTkButton(
            self.sidebar, text="⚙  Einstellungen",
            font=ctk.CTkFont(size=13),
            height=36, corner_radius=8,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            border_color=("gray70", "gray30"),
            hover_color=("gray85", "gray25"),
            command=self._open_settings,
        )
        self.settings_button.grid(row=11, column=0, padx=16, pady=(0, 8), sticky="ew")

        self.theme_switch = ctk.CTkSwitch(
            self.sidebar, text="Dark Mode",
            font=ctk.CTkFont(size=11),
            command=self._toggle_theme,
            onvalue="dark", offvalue="light",
        )
        current_mode = ctk.get_appearance_mode().lower()
        if current_mode == "dark":
            self.theme_switch.select()
        self.theme_switch.grid(row=12, column=0, padx=20, pady=(0, 8), sticky="w")

        # About label at the very bottom
        about_label = ctk.CTkLabel(
            self.sidebar,
            text=f"{APP_NAME} v{APP_VERSION}  \u2139",
            font=ctk.CTkFont(size=10),
            text_color="gray45",
            cursor="hand2",
        )
        about_label.grid(row=13, column=0, padx=20, pady=(0, 12), sticky="w")
        about_label.bind("<Button-1>", lambda e: self._show_about())

    def _build_content(self) -> None:
        """Build the main content area with editor and results."""
        content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)  # editor expands
        content.grid_rowconfigure(3, weight=1)  # results expand

        # Editor label
        ctk.CTkLabel(
            content, text="Text eingeben",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(16, 6), sticky="w")

        # Editor textbox
        self.editor = ctk.CTkTextbox(
            content,
            font=ctk.CTkFont(size=14),
            corner_radius=8,
            border_width=1,
            border_color=("gray75", "gray25"),
        )
        self.editor.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="nsew")

        # Results label
        self.result_header = ctk.CTkLabel(
            content, text="Ergebnis",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        self.result_header.grid(row=2, column=0, padx=20, pady=(8, 6), sticky="w")

        # Results area (tabview with corrected text + errors)
        self.result_tabs = ctk.CTkTabview(
            content,
            corner_radius=8,
            border_width=1,
            border_color=("gray75", "gray25"),
        )
        self.result_tabs.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="nsew")

        tab_corrected = self.result_tabs.add("Korrigierter Text")
        tab_corrected.grid_columnconfigure(0, weight=1)
        tab_corrected.grid_rowconfigure(0, weight=1)

        self.corrected_text = ctk.CTkTextbox(
            tab_corrected,
            font=ctk.CTkFont(size=14),
            corner_radius=6,
            state="disabled",
        )
        self.corrected_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        tab_errors = self.result_tabs.add("Fehler")
        tab_errors.grid_columnconfigure(0, weight=1)
        tab_errors.grid_rowconfigure(0, weight=1)

        self.errors_text = ctk.CTkTextbox(
            tab_errors,
            font=ctk.CTkFont(size=13),
            corner_radius=6,
            state="disabled",
        )
        self.errors_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Summary label
        self.summary_label = ctk.CTkLabel(
            content, text="",
            font=ctk.CTkFont(size=12),
            text_color="gray50",
            anchor="w",
        )
        self.summary_label.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="w")

    def _toggle_theme(self) -> None:
        """Toggle between light and dark mode."""
        mode = self.theme_switch.get()
        ctk.set_appearance_mode(mode)

    def _on_hotkey_check(self, text: str) -> None:
        """Called from clipboard monitor thread when Ctrl+Shift+P is pressed."""
        # Bounce to GUI thread
        self.after(0, self._do_hotkey_check, text)

    def _do_hotkey_check(self, text: str) -> None:
        """Insert clipboard text into editor and start check (GUI thread)."""
        self.editor.delete("0.0", "end")
        self.editor.insert("0.0", text)
        self._on_check()
        # Bring window to front
        self.lift()
        self.focus_force()

    def _show_about(self) -> None:
        """Show a simple about dialog."""
        about = ctk.CTkToplevel(self)
        about.title(f"Über {APP_NAME}")
        about.geometry("340x200")
        about.resizable(False, False)
        about.transient(self)
        about.grab_set()

        ctk.CTkLabel(
            about, text=APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            about, text=f"Version {APP_VERSION}",
            font=ctk.CTkFont(size=13), text_color="gray50",
        ).pack()

        ctk.CTkLabel(
            about,
            text="KI-gestützter Rechtschreib-\nund Grammatikprüfer für Windows",
            font=ctk.CTkFont(size=12), text_color="gray60",
            justify="center",
        ).pack(pady=(8, 0))

        ctk.CTkButton(
            about, text="Schließen", width=100,
            command=about.destroy,
        ).pack(pady=(16, 0))

    def _on_close(self) -> None:
        """Clean up hotkey listener and close app."""
        self._clipboard.stop()
        self.destroy()

    def _open_settings(self) -> None:
        """Open the settings dialog (singleton pattern)."""
        # If dialog already open, just focus it
        if self._settings_dialog is not None and self._settings_dialog.winfo_exists():
            self._settings_dialog.focus()
            return

        # Open modal dialog and wait until it closes
        self._settings_dialog = SettingsDialog(self, self.settings)
        self.wait_window(self._settings_dialog)

        # Apply new settings if user clicked Save
        if self._settings_dialog.result is not None:
            self.settings = self._settings_dialog.result
            logger.info("Settings updated by user")

    def _create_backend(self) -> BaseBackend:
        """Create the backend based on current settings."""
        backend_type = get_setting(self.settings, "backend")

        if backend_type == "claude_api":
            return ClaudeBackend(
                api_key=get_setting(self.settings, "claude_api_key"),
                model=get_setting(self.settings, "claude_model"),
            )

        if backend_type == "claude_abo":
            # Ensure full model ID (old settings may have short names)
            model = self.settings.get("proxy_model", "claude-sonnet-4-20250514")
            if model == "claude-sonnet-4":
                model = "claude-sonnet-4-20250514"
            elif model == "claude-haiku-4":
                model = "claude-haiku-4-5-20251001"
            return ClaudeOAuthBackend(model=model)

        # Default: Ollama
        return OllamaBackend(
            base_url=get_setting(self.settings, "ollama_url"),
            model=get_setting(self.settings, "ollama_model"),
        )

    def _on_check(self) -> None:
        """Handle the check button click."""
        text = self.editor.get("0.0", "end").strip()
        if not text:
            self._set_status("Bitte Text eingeben.", "warning")
            return

        if self._checking:
            return

        self._checking = True
        self.check_button.configure(state="disabled", text="\u23F3  Prüfe...")
        self._set_status("Text wird geprüft...", "info")

        language = get_setting(self.settings, "language")

        thread = threading.Thread(
            target=self._run_check, args=(text, language), daemon=True
        )
        thread.start()

    def _run_check(self, text: str, language: str) -> None:
        """Run the text check in a background thread."""
        try:
            backend = self._create_backend()
            result = check_text(backend, text, language)
            self.after(0, self._on_check_done, result)
        except (ConnectionError, ValueError, RuntimeError) as e:
            self.after(0, self._on_check_error, str(e))
        except Exception as e:
            logger.exception("Unexpected error during text check")
            self.after(0, self._on_check_error, f"Unerwarteter Fehler: {e}")

    def _on_check_done(self, result: dict[str, Any]) -> None:
        """Handle successful check result (called on GUI thread)."""
        self._checking = False
        self.check_button.configure(state="normal", text="\u2714  Text prüfen")

        # Summary
        summary = result.get("summary", "")
        self.summary_label.configure(text=summary)

        # Corrected text
        self.corrected_text.configure(state="normal")
        self.corrected_text.delete("0.0", "end")
        self.corrected_text.insert("0.0", result.get("corrected_text", ""))
        self.corrected_text.configure(state="disabled")

        # Errors
        self.errors_text.configure(state="normal")
        self.errors_text.delete("0.0", "end")

        errors = result.get("errors", [])
        if not errors:
            self.errors_text.insert("0.0", "Keine Fehler gefunden!")
        else:
            for i, error in enumerate(errors):
                error_type = error.get("type", "grammar")
                type_labels = {
                    "spelling": "Rechtschreibung",
                    "grammar": "Grammatik",
                    "style": "Stil",
                }
                type_label = type_labels.get(error_type, error_type)

                if i > 0:
                    self.errors_text.insert("end", "\n\n")

                self.errors_text.insert(
                    "end",
                    f"[{type_label}] \"{error.get('original', '')}\" "
                    f"\u2192 \"{error.get('suggestion', '')}\"\n",
                )
                explanation = error.get("explanation", "")
                if explanation:
                    self.errors_text.insert("end", f"  {explanation}")

        self.errors_text.configure(state="disabled")

        # Highlight errors in the editor
        self._highlight_errors(errors)

        error_count = len(errors)
        if error_count == 0:
            self._set_status("Keine Fehler gefunden!", "success")
        else:
            self._set_status(f"{error_count} Fehler gefunden.", "info")

    def _highlight_errors(self, errors: list[dict]) -> None:
        """Mark error words in the editor with colored underlines."""
        # Access the internal tk.Text widget of CTkTextbox
        text_widget = self.editor._textbox

        # Remove old highlights
        text_widget.tag_remove("error_spelling", "1.0", "end")
        text_widget.tag_remove("error_grammar", "1.0", "end")
        text_widget.tag_remove("error_style", "1.0", "end")

        # Configure tag styles (underline + color)
        text_widget.tag_configure("error_spelling", underline=True, foreground="#D32F2F")
        text_widget.tag_configure("error_grammar", underline=True, foreground="#EF6C00")
        text_widget.tag_configure("error_style", underline=True, foreground="#1565C0")

        # Search and highlight each error in the editor text
        editor_text = self.editor.get("0.0", "end")
        for error in errors:
            original = error.get("original", "")
            if not original:
                continue

            error_type = error.get("type", "grammar")
            tag = f"error_{error_type}" if error_type in ("spelling", "grammar", "style") else "error_grammar"

            # Find all occurrences of the error text
            start_idx = "1.0"
            while True:
                pos = text_widget.search(original, start_idx, stopindex="end", nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(original)}c"
                text_widget.tag_add(tag, pos, end_pos)
                start_idx = end_pos

    def _on_check_error(self, message: str) -> None:
        """Handle check error (called on GUI thread)."""
        self._checking = False
        self.check_button.configure(state="normal", text="\u2714  Text prüfen")
        self._set_status(message, "error")

    def _on_paste(self) -> None:
        """Paste text from clipboard into the editor."""
        try:
            text = pyperclip.paste()
            if text:
                self.editor.delete("0.0", "end")
                self.editor.insert("0.0", text)
                self._set_status("Text eingefügt.", "success")
            else:
                self._set_status("Zwischenablage ist leer.", "warning")
        except Exception as e:
            logger.error("Clipboard paste error: %s", e)
            self._set_status("Fehler beim Einfügen.", "error")

    def _on_clear(self) -> None:
        """Clear editor, results, and error highlights."""
        self._highlight_errors([])  # remove highlights
        self.editor.delete("0.0", "end")
        self.corrected_text.configure(state="normal")
        self.corrected_text.delete("0.0", "end")
        self.corrected_text.configure(state="disabled")
        self.errors_text.configure(state="normal")
        self.errors_text.delete("0.0", "end")
        self.errors_text.configure(state="disabled")
        self.summary_label.configure(text="")
        self._set_status("", "info")

    def _on_copy(self) -> None:
        """Copy corrected text to clipboard."""
        self.corrected_text.configure(state="normal")
        text = self.corrected_text.get("0.0", "end").strip()
        self.corrected_text.configure(state="disabled")
        if text:
            try:
                pyperclip.copy(text)
                self._set_status("Korrektur kopiert!", "success")
            except Exception as e:
                logger.error("Clipboard copy error: %s", e)
                self._set_status("Fehler beim Kopieren.", "error")
        else:
            self._set_status("Kein korrigierter Text.", "warning")

    def _set_status(self, message: str, level: str = "info") -> None:
        """Update the status label with colored text."""
        color_map = {
            "info": "gray60",
            "success": "#2E7D32",
            "warning": "#EF6C00",
            "error": "#D32F2F",
        }
        self.status_label.configure(
            text=message,
            text_color=color_map.get(level, "gray60"),
        )
