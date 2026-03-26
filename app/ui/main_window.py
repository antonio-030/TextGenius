"""Main application window layout and logic."""

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import customtkinter as ctk
import pyperclip

from app.backends.base import BaseBackend
from app.backends.ollama import OllamaBackend
from app.backends.claude import ClaudeBackend
from app.backends.claude_oauth import ClaudeOAuthBackend
from app.checker import (
    check_text, build_translate_prompt, build_chat_prompt,
    build_tone_prompt, build_shorten_prompt, build_expand_prompt,
    build_rephrase_prompt, build_email_prompt, build_analyze_prompt,
    build_brainstorm_prompt, build_plan_prompt, TONE_OPTIONS,
)
from app.agent_memory import (
    load_memory, learn_from_check, record_acceptance,
    get_smart_tip, get_glossary_suggestions, add_to_glossary,
)
from app.clipboard import ClipboardMonitor
from app.history import save_draft, load_draft, add_to_history, get_history
from app.settings import get_setting
from app.templates import TEMPLATES
from app.ui.settings_dialog import SettingsDialog
from version import APP_NAME, APP_VERSION

logger = logging.getLogger(__name__)

# Sidebar icon/text pairs for collapsed/expanded state
SIDEBAR_BUTTONS = {
    "check":     ("✔", "✔  Text prüfen"),
    "paste":     ("⌘", "⌘  Einfügen"),
    "copy":      ("◐", "◐  Kopieren"),
    "clear":     ("✕", "✕  Leeren"),
    "translate": ("🌐", "🌐  Übersetzen"),
    "tools":     ("🔧", "🔧  KI-Werkzeuge"),
    "settings":  ("⚙", "⚙  Einstellungen"),
}
SIDEBAR_EXPANDED = 200
SIDEBAR_COLLAPSED = 56


class MainWindow(ctk.CTk):
    """The main TextGenius application window."""

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self._checking = False
        self._chatting = False
        self._chat_count = 0          # Chat-Nachrichten Zähler
        self._settings_dialog = None
        self._sidebar_open = True
        self._sidebar_poll_id = None  # für after_cancel
        self._pool = ThreadPoolExecutor(max_workers=3)  # Zentraler Thread-Pool
        self._clipboard = ClipboardMonitor(self._on_hotkey_check)

        # Window setup
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1050x700")
        self.minsize(620, 500)

        # Window icon
        try:
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.iconbitmap(os.path.join(base_path, "assets", "icon.ico"))
        except Exception:
            logger.debug("Icon not found")

        # Grid: sidebar (col 0) + content (col 1)
        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_EXPANDED)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()

        # Tastenkürzel
        self.bind("<Control-Return>", lambda e: self._on_check())
        self.bind("<Control-t>", lambda e: self._on_translate())
        self.bind("<Control-k>", lambda e: self._on_tool_quick("shorten"))
        self.bind("<Control-e>", lambda e: self._on_tool_quick("expand"))

        # Auto-collapse sidebar -- starte verzögert nach dem Fenster-Aufbau
        self._last_width = 0
        self.after(500, self._check_sidebar_size)

        # Hotkey listener + clean shutdown
        self._clipboard.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Sidebar ────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        """Build the collapsible left sidebar."""
        self.sidebar = ctk.CTkFrame(self, width=SIDEBAR_EXPANDED, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)  # spacer before bottom
        self.sidebar.grid_propagate(False)

        # Toggle button (row 0)
        self.toggle_btn = ctk.CTkButton(
            self.sidebar, text="☰", width=30, height=30,
            font=ctk.CTkFont(size=16), corner_radius=6,
            fg_color="transparent", hover_color=("gray85", "gray25"),
            text_color=("gray30", "gray70"),
            command=self._toggle_sidebar,
        )
        self.toggle_btn.grid(row=0, column=0, padx=12, pady=(12, 0), sticky="w")

        # App title (row 1)
        self.title_label = ctk.CTkLabel(
            self.sidebar, text=APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.title_label.grid(row=1, column=0, padx=20, pady=(4, 16), sticky="w")

        # Action buttons (rows 2-6)
        self.check_button = self._sidebar_btn(
            "check", row=2, primary=True, command=self._on_check
        )
        self.paste_button = self._sidebar_btn(
            "paste", row=3, command=self._on_paste
        )
        self.copy_button = self._sidebar_btn(
            "copy", row=4, command=self._on_copy
        )
        self.clear_button = self._sidebar_btn(
            "clear", row=5, command=self._on_clear, ghost=True
        )
        self.translate_button = self._sidebar_btn(
            "translate", row=6, command=self._on_translate
        )

        # KI-Werkzeuge Button (row 7)
        self.tools_button = self._sidebar_btn(
            "tools", row=7, command=self._open_tools_panel
        )

        # Status (row 8)
        self.status_label = ctk.CTkLabel(
            self.sidebar, text="", font=ctk.CTkFont(size=11),
            text_color="gray60", wraplength=160,
        )
        self.status_label.grid(row=8, column=0, padx=16, pady=(8, 0), sticky="w")

        # Usage bar in sidebar (row 9, only visible for claude_abo)
        self.sidebar_usage_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_usage_bar = ctk.CTkProgressBar(
            self.sidebar_usage_frame, height=8, corner_radius=4, width=140,
        )
        self.sidebar_usage_bar.set(0)
        self.sidebar_usage_label = ctk.CTkLabel(
            self.sidebar_usage_frame, text="", font=ctk.CTkFont(size=10),
            text_color="gray50",
        )
        self.sidebar_usage_bar.pack(padx=16, pady=(4, 0), anchor="w")
        self.sidebar_usage_label.pack(padx=16, anchor="w")

        if get_setting(self.settings, "backend") == "claude_abo":
            self.sidebar_usage_frame.grid(row=9, column=0, sticky="ew")
            self._fetch_sidebar_usage()

        # Bottom: settings + theme + about (rows 11-13)
        self.settings_button = self._sidebar_btn(
            "settings", row=11, command=self._open_settings
        )

        self.theme_switch = ctk.CTkSwitch(
            self.sidebar, text="Dark Mode", font=ctk.CTkFont(size=11),
            command=self._toggle_theme, onvalue="dark", offvalue="light",
        )
        if ctk.get_appearance_mode().lower() == "dark":
            self.theme_switch.select()
        self.theme_switch.grid(row=12, column=0, padx=20, pady=(0, 4), sticky="w")

        self.about_label = ctk.CTkLabel(
            self.sidebar, text="ℹ  Info",
            font=ctk.CTkFont(size=11), text_color="gray45", cursor="hand2",
        )
        self.about_label.grid(row=13, column=0, padx=20, pady=(0, 12), sticky="w")
        self.about_label.bind("<Button-1>", lambda e: self._show_about())

    def _sidebar_btn(self, key, row, command, primary=False, ghost=False):
        """Create a sidebar button with icon/text pair for collapse support."""
        text = SIDEBAR_BUTTONS[key][1]
        kwargs = {
            "font": ctk.CTkFont(size=13, weight="bold" if primary else "normal"),
            "height": 40 if primary else 34, "corner_radius": 8,
            "command": command,
        }
        if primary:
            pass  # default blue style
        elif ghost:
            kwargs.update(fg_color="transparent", text_color=("gray40", "gray60"),
                          hover_color=("gray85", "gray25"))
        else:
            kwargs.update(fg_color="transparent", border_width=1,
                          text_color=("gray10", "gray90"),
                          border_color=("gray70", "gray30"),
                          hover_color=("gray85", "gray25"))

        btn = ctk.CTkButton(self.sidebar, text=text, **kwargs)
        btn.grid(row=row, column=0, padx=12, pady=(0, 5), sticky="ew")
        btn._sidebar_key = key  # store key for toggle
        return btn

    def _check_sidebar_size(self) -> None:
        """Periodically check window width and auto-collapse/expand sidebar."""
        try:
            width = self.winfo_width()
        except Exception:
            return  # Window destroyed

        threshold = 750

        if width != self._last_width:
            if width < threshold and self._sidebar_open:
                self._toggle_sidebar()
            elif width >= threshold and not self._sidebar_open:
                self._toggle_sidebar()
            self._last_width = width

        # Vorherigen Callback canceln, dann neuen planen
        if self._sidebar_poll_id is not None:
            self.after_cancel(self._sidebar_poll_id)
        self._sidebar_poll_id = self.after(300, self._check_sidebar_size)

    def _toggle_sidebar(self) -> None:
        """Collapse or expand the sidebar."""
        self._sidebar_open = not self._sidebar_open
        all_btns = [self.check_button, self.paste_button, self.copy_button,
                    self.clear_button, self.translate_button, self.tools_button,
                    self.settings_button]

        if self._sidebar_open:
            # ── Expand: full width, text + icons ──
            self.sidebar.configure(width=SIDEBAR_EXPANDED)
            self.grid_columnconfigure(0, minsize=SIDEBAR_EXPANDED)
            self.title_label.grid()
            pass  # tools_button handled by all_btns
            self.theme_switch.grid()
            self.about_label.grid()
            self.status_label.grid()
            if get_setting(self.settings, "backend") == "claude_abo":
                self.sidebar_usage_frame.grid()
            for btn in all_btns:
                key = btn._sidebar_key
                btn.configure(
                    text=SIDEBAR_BUTTONS[key][1],
                    width=0,  # auto width
                    font=ctk.CTkFont(size=13, weight="bold" if key == "check" else "normal"),
                )
                btn.grid_configure(padx=12)
        else:
            # ── Collapse: narrow, only centered icons ──
            self.sidebar.configure(width=SIDEBAR_COLLAPSED)
            self.grid_columnconfigure(0, minsize=SIDEBAR_COLLAPSED)
            self.title_label.grid_remove()
            pass  # tools_button handled by all_btns
            self.theme_switch.grid_remove()
            self.about_label.grid_remove()
            self.status_label.grid_remove()
            self.sidebar_usage_frame.grid_remove()
            for btn in all_btns:
                key = btn._sidebar_key
                btn.configure(
                    text=SIDEBAR_BUTTONS[key][0],
                    width=36,
                    font=ctk.CTkFont(size=16),
                )
                btn.grid_configure(padx=6)

    # ── Content Area ───────────────────────────────────────────

    def _build_content(self) -> None:
        """Build the main content area with editor, results, and chat."""
        content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)  # editor
        content.grid_rowconfigure(3, weight=1)  # result tabs

        # Editor header: Titel links, Live-Stats rechts
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(10, 2), sticky="ew")

        # Links: Titel + Vorlagen + Verlauf Buttons
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(
            left, text="Text eingeben",
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
        ).pack(side="left")
        ctk.CTkButton(
            left, text="📋", width=28, height=24, corner_radius=4,
            font=ctk.CTkFont(size=13),
            fg_color="transparent", hover_color=("gray85", "gray25"),
            text_color=("gray40", "gray60"),
            command=self._show_templates,
        ).pack(side="left", padx=(6, 0))
        ctk.CTkButton(
            left, text="🕐", width=28, height=24, corner_radius=4,
            font=ctk.CTkFont(size=13),
            fg_color="transparent", hover_color=("gray85", "gray25"),
            text_color=("gray40", "gray60"),
            command=self._show_history,
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            left, text="💾", width=28, height=24, corner_radius=4,
            font=ctk.CTkFont(size=13),
            fg_color="transparent", hover_color=("gray85", "gray25"),
            text_color=("gray40", "gray60"),
            command=self._export_text,
        ).pack(side="left", padx=2)

        # Rechts: Live-Statistik
        self.stats_label = ctk.CTkLabel(
            header, text="0 Wörter  |  0 Zeichen  |  ~0 Min.",
            font=ctk.CTkFont(size=10), text_color="gray50", anchor="e",
        )
        self.stats_label.pack(side="right")

        # Editor
        self.editor = ctk.CTkTextbox(
            content, font=ctk.CTkFont(size=14),
            corner_radius=8, border_width=1, border_color=("gray75", "gray25"),
        )
        self.editor.grid(row=1, column=0, padx=20, pady=(0, 6), sticky="nsew")

        # Live-Statistik + Auto-Speichern per KeyRelease
        self.editor.bind("<KeyRelease>", self._on_editor_change)

        # Gespeicherten Entwurf laden
        draft = load_draft()
        if draft:
            self.editor.insert("0.0", draft)
            self._update_stats()

        # Result header
        ctk.CTkLabel(
            content, text="Ergebnis",
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
        ).grid(row=2, column=0, padx=20, pady=(6, 4), sticky="w")

        # Result tabs (Korrektur + Fehler + Chat)
        self.result_tabs = ctk.CTkTabview(
            content, corner_radius=8, border_width=1,
            border_color=("gray75", "gray25"),
        )
        self.result_tabs.grid(row=3, column=0, padx=20, pady=(0, 6), sticky="nsew")

        # Tab 1: Korrigierter Text
        tab_corrected = self.result_tabs.add("Korrektur")
        tab_corrected.grid_columnconfigure(0, weight=1)
        tab_corrected.grid_rowconfigure(0, weight=1)
        self.corrected_text = ctk.CTkTextbox(
            tab_corrected, font=ctk.CTkFont(size=14),
            corner_radius=6, state="disabled",
        )
        self.corrected_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Tab 2: Fehler
        tab_errors = self.result_tabs.add("Fehler")
        tab_errors.grid_columnconfigure(0, weight=1)
        tab_errors.grid_rowconfigure(0, weight=1)
        self.errors_text = ctk.CTkTextbox(
            tab_errors, font=ctk.CTkFont(size=13),
            corner_radius=6, state="disabled",
        )
        self.errors_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Tab 3: Chat -- einzelne CTkTextbox mit Tags (schnell, smooth, auto-wrap)
        tab_chat = self.result_tabs.add("💬 Chat")
        tab_chat.grid_columnconfigure(0, weight=1)
        tab_chat.grid_rowconfigure(0, weight=1)

        # Chat-Verlauf als einzelnes Textbox-Widget
        self.chat_display = ctk.CTkTextbox(
            tab_chat, font=ctk.CTkFont(family="Segoe UI", size=13),
            corner_radius=6, state="disabled", wrap="word",
            fg_color=("gray96", "gray12"),
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 0))

        # Text-Tags für unterschiedliche Formatierung
        tw = self.chat_display._textbox
        tw.tag_config("user_name", foreground="#2563EB",
                      font=("Segoe UI", 11, "bold"))
        tw.tag_config("bot_name", foreground="#10B981",
                      font=("Segoe UI", 11, "bold"))
        tw.tag_config("time", foreground="gray50",
                      font=("Segoe UI", 9))
        tw.tag_config("user_msg", lmargin1=12, lmargin2=12, spacing3=6)
        tw.tag_config("bot_msg", lmargin1=12, lmargin2=12, spacing3=6)
        tw.tag_config("system", foreground="gray50",
                      font=("Segoe UI", 11, "italic"),
                      lmargin1=12, lmargin2=12, spacing3=8)
        tw.tag_config("sep", font=("Segoe UI", 4), spacing1=4, spacing3=4)

        # Willkommensnachricht
        self.chat_display.configure(state="normal")
        self.chat_display._textbox.insert(
            "end",
            "Schreibassistent – Stelle Fragen zu deinem Text, "
            "z.B. \"Warum ist das falsch?\", \"Schreib das formeller\" "
            "oder \"Erkläre die Grammatikregel\".\n\n",
            "system",
        )
        self.chat_display.configure(state="disabled")

        # Eingabezeile
        chat_input = ctk.CTkFrame(tab_chat, fg_color="transparent")
        chat_input.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        chat_input.grid_columnconfigure(0, weight=1)

        self.chat_entry = ctk.CTkEntry(
            chat_input, placeholder_text="Nachricht eingeben...",
            font=ctk.CTkFont(size=13), height=36, corner_radius=18,
        )
        self.chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.chat_entry.bind("<Return>", lambda e: self._on_chat_send())

        self.chat_send_btn = ctk.CTkButton(
            chat_input, text="➤", width=36, height=36,
            corner_radius=18, font=ctk.CTkFont(size=15),
            command=self._on_chat_send,
        )
        self.chat_send_btn.grid(row=0, column=1)

        # Tab 4: Planer -- Brainstorming mit Checkboxen
        tab_plan = self.result_tabs.add("📋 Planer")
        tab_plan.grid_columnconfigure(0, weight=1)
        tab_plan.grid_rowconfigure(1, weight=1)

        # Planer-Header: Thema eingeben
        plan_top = ctk.CTkFrame(tab_plan, fg_color="transparent")
        plan_top.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        plan_top.grid_columnconfigure(0, weight=1)

        self.plan_topic = ctk.CTkEntry(
            plan_top, placeholder_text="Projektidee, Script, Aufgabe beschreiben...",
            font=ctk.CTkFont(size=13), height=36, corner_radius=18,
        )
        self.plan_topic.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.plan_topic.bind("<Return>", lambda e: self._on_plan_start())

        self.plan_start_btn = ctk.CTkButton(
            plan_top, text="Brainstorming", width=120, height=36,
            corner_radius=18, command=self._on_plan_start,
        )
        self.plan_start_btn.grid(row=0, column=1)

        # Planer-Inhalt: scrollbar für Fragen/Checkboxen
        self.plan_scroll = ctk.CTkScrollableFrame(
            tab_plan, corner_radius=6,
            fg_color=("gray96", "gray12"),
        )
        self.plan_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.plan_scroll.grid_columnconfigure(0, weight=1)
        self._plan_row = 0
        self._plan_checks = []  # (checkbox_var, text) Paare
        self._plan_topic_text = ""

        # Planer-Footer: MD generieren
        plan_bottom = ctk.CTkFrame(tab_plan, fg_color="transparent")
        plan_bottom.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        plan_bottom.grid_columnconfigure(0, weight=1)

        self.plan_generate_btn = ctk.CTkButton(
            plan_bottom, text="📄 Plan als Markdown generieren",
            height=36, corner_radius=18, state="disabled",
            command=self._on_plan_generate,
        )
        self.plan_generate_btn.grid(row=0, column=0, sticky="ew")

        # Tab 5: Agent -- Gedächtnis + Profil (transparent)
        tab_agent = self.result_tabs.add("🧠 Agent")
        tab_agent.grid_columnconfigure(0, weight=1)
        tab_agent.grid_rowconfigure(1, weight=1)

        # Agent-Header
        agent_header = ctk.CTkFrame(tab_agent, fg_color="transparent")
        agent_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
        ctk.CTkLabel(
            agent_header, text="Agent-Gedächtnis",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            agent_header, text="🔄 Aktualisieren", width=100, height=26,
            corner_radius=6, font=ctk.CTkFont(size=11),
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), border_color=("gray70", "gray30"),
            command=self._refresh_agent_tab,
        ).pack(side="right")

        # Agent-Info als scrollbare Textbox
        self.agent_display = ctk.CTkTextbox(
            tab_agent, font=ctk.CTkFont(family="Segoe UI", size=12),
            corner_radius=6, state="disabled", wrap="word",
            fg_color=("gray96", "gray12"),
        )
        self.agent_display.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        # Agent-Tags für Formatierung
        atw = self.agent_display._textbox
        atw.tag_config("heading", font=("Segoe UI", 13, "bold"), spacing3=4)
        atw.tag_config("label", font=("Segoe UI", 11, "bold"), foreground="#2563EB")
        atw.tag_config("value", font=("Segoe UI", 11))
        atw.tag_config("weak", foreground="#D32F2F", font=("Segoe UI", 11))
        atw.tag_config("strong", foreground="#2E7D32", font=("Segoe UI", 11))
        atw.tag_config("tip", foreground="#EF6C00", font=("Segoe UI", 11, "italic"))
        atw.tag_config("glossary", font=("Segoe UI", 11), foreground="gray50")

        # Agent-Footer: Glossar hinzufügen + Gedächtnis leeren
        agent_footer = ctk.CTkFrame(tab_agent, fg_color="transparent")
        agent_footer.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        agent_footer.grid_columnconfigure(0, weight=1)

        self.glossary_entry = ctk.CTkEntry(
            agent_footer, placeholder_text="Wort zum Glossar hinzufügen...",
            font=ctk.CTkFont(size=12), height=32, corner_radius=16,
        )
        self.glossary_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.glossary_entry.bind("<Return>", lambda e: self._add_glossary_word())

        ctk.CTkButton(
            agent_footer, text="+", width=32, height=32,
            corner_radius=16, font=ctk.CTkFont(size=14),
            command=self._add_glossary_word,
        ).grid(row=0, column=1, padx=(0, 4))

        ctk.CTkButton(
            agent_footer, text="🗑", width=32, height=32,
            corner_radius=16, font=ctk.CTkFont(size=14),
            fg_color=("gray85", "gray25"), hover_color=("#D32F2F", "#D32F2F"),
            text_color=("gray40", "gray60"),
            command=self._clear_agent_memory,
        ).grid(row=0, column=2)

        # Agent-Tab verzögert füllen (nach Fenster-Aufbau)
        self.after(300, self._refresh_agent_tab)

        # Summary
        self.summary_label = ctk.CTkLabel(
            content, text="", font=ctk.CTkFont(size=11),
            text_color="gray50", anchor="w",
        )
        self.summary_label.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="w")

    # ── Sidebar actions ────────────────────────────────────────

    def _toggle_theme(self) -> None:
        ctk.set_appearance_mode(self.theme_switch.get())

    def _on_hotkey_check(self, text: str) -> None:
        self.after(0, self._do_hotkey_check, text)

    def _do_hotkey_check(self, text: str) -> None:
        self.editor.delete("0.0", "end")
        self.editor.insert("0.0", text)
        self._on_check()
        self.lift()
        self.focus_force()

    def _show_about(self) -> None:
        """Info-Seite: Über uns, Copyright, Links, Tastenkürzel."""
        about = ctk.CTkToplevel(self)
        about.title(f"Über {APP_NAME}")
        about.geometry("420x480")
        about.resizable(False, False)
        about.transient(self)
        about.grab_set()

        # App-Name + Version
        ctk.CTkLabel(about, text=APP_NAME,
                     font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(24, 2))
        ctk.CTkLabel(about, text=f"Version {APP_VERSION}",
                     font=ctk.CTkFont(size=13), text_color="gray50").pack()
        ctk.CTkLabel(about, text="KI-gestützter Rechtschreib- und Grammatikprüfer",
                     font=ctk.CTkFont(size=12), text_color="gray60").pack(pady=(4, 0))

        # Trennlinie
        ctk.CTkFrame(about, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=30, pady=16)

        # Über uns / Copyright
        info_frame = ctk.CTkFrame(about, fg_color="transparent")
        info_frame.pack(fill="x", padx=30)

        ctk.CTkLabel(info_frame, text="Herausgeber",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray50").pack(anchor="w")
        ctk.CTkLabel(info_frame, text="techlogia – Technologie & Automation",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(2, 0))

        # Link zu techlogia.de
        link = ctk.CTkLabel(info_frame, text="www.techlogia.de",
                            font=ctk.CTkFont(size=13), text_color="#2563EB",
                            cursor="hand2")
        link.pack(anchor="w", pady=(2, 0))
        link.bind("<Button-1>", lambda e: self._open_url("https://techlogia.de"))

        ctk.CTkLabel(info_frame, text=f"© 2026 techlogia. Alle Rechte vorbehalten.",
                     font=ctk.CTkFont(size=11), text_color="gray50").pack(anchor="w", pady=(8, 0))

        # Trennlinie
        ctk.CTkFrame(about, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=30, pady=16)

        # Tastenkürzel
        shortcuts_frame = ctk.CTkFrame(about, fg_color="transparent")
        shortcuts_frame.pack(fill="x", padx=30)

        ctk.CTkLabel(shortcuts_frame, text="Tastenkürzel",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray50").pack(anchor="w")

        for shortcut, action in [
            ("Ctrl + Enter", "Text prüfen"),
            ("Ctrl + Shift + P", "Zwischenablage prüfen (global)"),
            ("Ctrl + V", "Text einfügen"),
        ]:
            row = ctk.CTkFrame(shortcuts_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=shortcut, font=ctk.CTkFont(size=11, weight="bold"),
                         width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=action, font=ctk.CTkFont(size=11),
                         text_color="gray60", anchor="w").pack(side="left")

        # Trennlinie
        ctk.CTkFrame(about, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=30, pady=16)

        # Links
        links_frame = ctk.CTkFrame(about, fg_color="transparent")
        links_frame.pack(fill="x", padx=30)

        gh_link = ctk.CTkLabel(links_frame, text="GitHub: antonio-030/TextGenius",
                               font=ctk.CTkFont(size=11), text_color="#2563EB",
                               cursor="hand2")
        gh_link.pack(anchor="w")
        gh_link.bind("<Button-1>", lambda e: self._open_url(
            "https://github.com/antonio-030/TextGenius"))

        issue_link = ctk.CTkLabel(links_frame, text="Fehler melden / Feature anfragen",
                                  font=ctk.CTkFont(size=11), text_color="#2563EB",
                                  cursor="hand2")
        issue_link.pack(anchor="w", pady=(2, 0))
        issue_link.bind("<Button-1>", lambda e: self._open_url(
            "https://github.com/antonio-030/TextGenius/issues"))

        # Schließen
        ctk.CTkButton(about, text="Schließen", width=100,
                      command=about.destroy).pack(pady=(16, 20))

    def _open_url(self, url: str) -> None:
        """Öffnet eine URL im Standard-Browser."""
        import webbrowser
        webbrowser.open(url)

    def _on_close(self) -> None:
        # Entwurf speichern beim Schließen
        try:
            text = self.editor.get("0.0", "end").strip()
            save_draft(text)
        except Exception:
            pass
        self._clipboard.stop()
        self._pool.shutdown(wait=False)
        if self._sidebar_poll_id is not None:
            self.after_cancel(self._sidebar_poll_id)
        self.destroy()

    # ── Live-Statistik + Auto-Speichern ───────────────────────

    _save_counter = 0  # Nur alle 10 Tastenschläge speichern

    def _on_editor_change(self, event=None) -> None:
        """Wird bei jedem Tastendruck im Editor aufgerufen."""
        self._update_stats()
        # Auto-Speichern alle 10 Tastenschläge (nicht bei jedem)
        self._save_counter += 1
        if self._save_counter >= 10:
            self._save_counter = 0
            text = self.editor.get("0.0", "end").strip()
            save_draft(text)

    def _update_stats(self) -> None:
        """Aktualisiert die Live-Statistik im Header."""
        text = self.editor.get("0.0", "end").strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        read_min = max(1, round(words / 200)) if words > 0 else 0
        self.stats_label.configure(
            text=f"{words} Wörter  |  {chars} Zeichen  |  ~{read_min} Min."
        )

    # ── Vorlagen ──────────────────────────────────────────────

    def _show_templates(self) -> None:
        """Zeigt Vorlagen-Auswahl als Dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Vorlagen")
        dialog.geometry("420x400")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="📋 Vorlage wählen",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(padx=16, pady=(16, 8), anchor="w")

        scroll = ctk.CTkScrollableFrame(dialog, corner_radius=6)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=1)

        for i, (name, icon, desc, text) in enumerate(TEMPLATES):
            def make_cb(t=text):
                def cb():
                    dialog.destroy()
                    self.editor.delete("0.0", "end")
                    self.editor.insert("0.0", t)
                    self._update_stats()
                return cb

            btn = ctk.CTkButton(
                scroll, text=f"{icon}  {name}", anchor="w",
                font=ctk.CTkFont(size=13), height=42, corner_radius=8,
                fg_color=("gray92", "gray18"),
                hover_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                command=make_cb(),
            )
            btn.grid(row=i, column=0, sticky="ew", padx=4, pady=2)

    # ── Verlauf ───────────────────────────────────────────────

    def _show_history(self) -> None:
        """Zeigt die letzten geprüften Texte als Dialog."""
        entries = get_history()

        dialog = ctk.CTkToplevel(self)
        dialog.title("Verlauf")
        dialog.geometry("450x380")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="🕐 Letzte Texte",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(padx=16, pady=(16, 8), anchor="w")

        if not entries:
            ctk.CTkLabel(
                dialog, text="Noch keine Texte geprüft.",
                font=ctk.CTkFont(size=12), text_color="gray50",
            ).pack(padx=16, pady=20)
            return

        scroll = ctk.CTkScrollableFrame(dialog, corner_radius=6)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=1)

        for i, entry in enumerate(entries):
            preview = entry.get("text", "")[:80].replace("\n", " ")
            time_str = entry.get("time", "")
            words = entry.get("words", 0)
            errors = entry.get("errors", 0)
            info = f"{time_str}  •  {words} Wörter  •  {errors} Fehler"

            card = ctk.CTkFrame(scroll, corner_radius=8, border_width=1,
                                border_color=("gray80", "gray25"))
            card.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card, text=preview + "...", font=ctk.CTkFont(size=12),
                anchor="w", wraplength=320,
            ).grid(row=0, column=0, padx=10, pady=(8, 0), sticky="w")
            ctk.CTkLabel(
                card, text=info, font=ctk.CTkFont(size=10),
                text_color="gray50", anchor="w",
            ).grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")

            def make_cb(t=entry.get("text", "")):
                def cb():
                    dialog.destroy()
                    self.editor.delete("0.0", "end")
                    self.editor.insert("0.0", t)
                    self._update_stats()
                return cb

            ctk.CTkButton(
                card, text="Laden", width=60, height=28, corner_radius=6,
                font=ctk.CTkFont(size=11), command=make_cb(),
            ).grid(row=0, column=1, rowspan=2, padx=8, pady=8)

    # ── Export ────────────────────────────────────────────────

    def _export_text(self) -> None:
        """Exportiert den Text als Datei (.txt oder .md)."""
        from tkinter import filedialog

        # Was exportieren: korrigierten Text wenn vorhanden, sonst Editor
        self.corrected_text.configure(state="normal")
        corrected = self.corrected_text.get("0.0", "end").strip()
        self.corrected_text.configure(state="disabled")
        text = corrected if corrected else self.editor.get("0.0", "end").strip()

        if not text:
            self._set_status("Kein Text zum Exportieren.", "warning")
            return

        path = filedialog.asksaveasfilename(
            title="Text exportieren",
            defaultextension=".txt",
            filetypes=[
                ("Textdatei", "*.txt"),
                ("Markdown", "*.md"),
                ("Alle Dateien", "*.*"),
            ],
            initialfile="TextGenius-Export",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self._set_status(f"✔ Exportiert: {os.path.basename(path)}", "success")
            except OSError as e:
                self._set_status(f"Export fehlgeschlagen: {e}", "error")

    # ── Schnelltasten für Tools ───────────────────────────────

    def _on_tool_quick(self, tool_key: str) -> None:
        """Führt ein KI-Tool direkt aus (für Tastenkürzel)."""
        text = self.editor.get("0.0", "end").strip()
        if not text or self._checking:
            return
        if tool_key == "shorten":
            self._run_tool("Kürze...", build_shorten_prompt(text))
        elif tool_key == "expand":
            self._run_tool("Erweitere...", build_expand_prompt(text))

    def _open_settings(self) -> None:
        if self._settings_dialog is not None and self._settings_dialog.winfo_exists():
            self._settings_dialog.focus()
            return
        self._settings_dialog = SettingsDialog(self, self.settings)
        self.wait_window(self._settings_dialog)
        if self._settings_dialog.result is not None:
            self.settings = self._settings_dialog.result
            logger.info("Settings updated by user")
            # Update sidebar usage if backend changed
            if get_setting(self.settings, "backend") == "claude_abo":
                self.sidebar_usage_frame.grid(row=9, column=0, sticky="ew")
                self._fetch_sidebar_usage()
            else:
                self.sidebar_usage_frame.grid_remove()

    # ── Usage in Sidebar ───────────────────────────────────────

    def _fetch_sidebar_usage(self) -> None:
        """Fetch usage data for sidebar display (background)."""
        def fetch():
            try:
                import requests
                from app.backends.claude_oauth import _get_valid_token, _VERIFY
                token = _get_valid_token()
                resp = requests.get(
                    "https://api.anthropic.com/api/oauth/usage",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "claude-cli/2.1.75",
                        "Accept": "application/json",
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "oauth-2025-04-20",
                    }, timeout=8, verify=_VERIFY,
                )
                if resp.status_code == 200:
                    self.after(0, self._on_sidebar_usage, resp.json())
            except Exception:
                pass
        self._pool.submit(fetch)

    def _on_sidebar_usage(self, data: dict) -> None:
        pct = data.get("five_hour", {}).get("utilization", 0) or 0
        self.sidebar_usage_bar.set(pct / 100)
        color = "#D32F2F" if pct >= 80 else "#EF6C00" if pct >= 50 else "#3B82F6"
        self.sidebar_usage_bar.configure(progress_color=color)
        self.sidebar_usage_label.configure(text=f"Nutzung: {pct:.0f}%")

    # ── Backend ────────────────────────────────────────────────

    def _create_backend(self) -> BaseBackend:
        backend_type = get_setting(self.settings, "backend")
        if backend_type == "claude_api":
            return ClaudeBackend(
                api_key=get_setting(self.settings, "claude_api_key"),
                model=get_setting(self.settings, "claude_model"),
            )
        if backend_type == "claude_abo":
            model = self.settings.get("proxy_model", "claude-sonnet-4-20250514")
            if model == "claude-sonnet-4":
                model = "claude-sonnet-4-20250514"
            elif model == "claude-haiku-4":
                model = "claude-haiku-4-5-20251001"
            return ClaudeOAuthBackend(model=model)
        return OllamaBackend(
            base_url=get_setting(self.settings, "ollama_url"),
            model=get_setting(self.settings, "ollama_model"),
        )

    # ── Text Check ─────────────────────────────────────────────

    MAX_TEXT_LENGTH = 50_000  # ~25 Seiten, verhindert API-Kostenexplosion

    def _on_check(self) -> None:
        text = self.editor.get("0.0", "end").strip()
        if not text:
            self._set_status("Bitte Text eingeben.", "warning")
            return
        if len(text) > self.MAX_TEXT_LENGTH:
            self._set_status(
                f"Text zu lang ({len(text)} Zeichen, max {self.MAX_TEXT_LENGTH}).", "warning"
            )
            return
        if self._checking:
            return

        self._checking = True
        self.check_button.configure(state="disabled", text="⏳  Prüfe...")
        self._set_status("Text wird geprüft...", "info")
        language = get_setting(self.settings, "language")

        self._pool.submit(self._run_check, text, language)

    def _run_check(self, text: str, language: str) -> None:
        try:
            backend = self._create_backend()
            # Agent-Kontext aus Gedächtnis laden
            memory = load_memory()
            agent_ctx = {
                "glossary": memory.get("glossary", []),
                "weak_areas": memory.get("weak_areas", []),
                "style": memory.get("style", ""),
                "show_reasoning": memory.get("show_reasoning", True),
            }
            result = check_text(backend, text, language, agent_context=agent_ctx)
            self.after(0, self._on_check_done, result)
        except (ConnectionError, ValueError, RuntimeError) as e:
            self.after(0, self._on_check_error, str(e))
        except Exception as e:
            logger.exception("Unexpected error during text check")
            self.after(0, self._on_check_error, f"Unerwarteter Fehler: {e}")

    def _on_check_done(self, result: dict[str, Any]) -> None:
        self._checking = False
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.check_button.configure(state="normal", text=SIDEBAR_BUTTONS["check"][1])

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
            for i, err in enumerate(errors):
                typ = {"spelling": "Rechtschreibung", "grammar": "Grammatik",
                       "style": "Stil"}.get(err.get("type", "grammar"), err.get("type", ""))
                if i > 0:
                    self.errors_text.insert("end", "\n\n")
                self.errors_text.insert("end",
                    f"[{typ}] \"{err.get('original', '')}\" → \"{err.get('suggestion', '')}\"\n")
                if err.get("explanation"):
                    self.errors_text.insert("end", f"  {err['explanation']}")
        self.errors_text.configure(state="disabled")

        self._highlight_errors(errors)
        self.summary_label.configure(text=result.get("summary", ""))

        # Zum Verlauf hinzufügen
        original = self.editor.get("0.0", "end").strip()
        add_to_history(original, result.get("corrected_text", ""), len(errors))

        # Agent lernt aus der Prüfung
        word_count = len(original.split())
        memory = learn_from_check(errors, word_count)

        n = len(errors)
        if n == 0:
            self._set_status("✔ Keine Fehler gefunden!", "success")
            self.result_tabs.set("Korrektur")
        else:
            # Smarten Tipp anzeigen wenn vorhanden
            tip = get_smart_tip(memory)
            status = f"✔ {n} Fehler gefunden."
            if tip:
                status += f"  {tip}"
            self._set_status(status, "info")
            self.result_tabs.set("Fehler")

        # Glossar-Vorschläge prüfen
        suggestions = get_glossary_suggestions(errors)
        if suggestions:
            self._show_glossary_suggestion(suggestions)

    def _highlight_errors(self, errors: list[dict]) -> None:
        try:
            if not self.winfo_exists():
                return
            tw = self.editor._textbox
        except Exception:
            return  # Widget zerstört
        for tag in ("error_spelling", "error_grammar", "error_style"):
            tw.tag_remove(tag, "1.0", "end")
        tw.tag_configure("error_spelling", underline=True, foreground="#D32F2F")
        tw.tag_configure("error_grammar", underline=True, foreground="#EF6C00")
        tw.tag_configure("error_style", underline=True, foreground="#1565C0")

        for err in errors:
            original = err.get("original", "")
            if not original:
                continue
            t = err.get("type", "grammar")
            tag = f"error_{t}" if t in ("spelling", "grammar", "style") else "error_grammar"
            idx = "1.0"
            while True:
                pos = tw.search(original, idx, stopindex="end", nocase=True)
                if not pos:
                    break
                tw.tag_add(tag, pos, f"{pos}+{len(original)}c")
                idx = f"{pos}+{len(original)}c"

    def _on_check_error(self, message: str) -> None:
        self._checking = False
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.check_button.configure(state="normal", text=SIDEBAR_BUTTONS["check"][1])
        self._set_status(message, "error")

    # ── Translate ──────────────────────────────────────────────

    TRANSLATE_LANGUAGES = [
        "Englisch", "Deutsch", "Französisch", "Spanisch",
        "Italienisch", "Portugiesisch", "Türkisch", "Russisch",
        "Chinesisch", "Japanisch", "Koreanisch", "Arabisch",
        "Polnisch", "Niederländisch", "Schwedisch",
    ]

    def _on_translate(self) -> None:
        """Open language picker, then translate."""
        text = self.editor.get("0.0", "end").strip()
        if not text:
            self._set_status("Bitte Text eingeben.", "warning")
            return
        if self._checking:
            return

        # Small dialog to pick target language
        dialog = ctk.CTkToplevel(self)
        dialog.title("Übersetzen nach...")
        dialog.geometry("300x160")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Zielsprache wählen:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(16, 8))

        lang_menu = ctk.CTkOptionMenu(
            dialog, values=self.TRANSLATE_LANGUAGES, width=220,
        )
        lang_menu.set("Englisch")
        lang_menu.pack(pady=(0, 12))

        def start():
            target = lang_menu.get()
            dialog.destroy()
            self._run_translate(text, target)

        ctk.CTkButton(
            dialog, text="Übersetzen", width=120, command=start,
        ).pack()

    def _run_translate(self, text: str, target_language: str) -> None:
        """Run translation in background thread."""
        self._checking = True
        self.translate_button.configure(state="disabled")
        self._set_status(f"Übersetze nach {target_language}...", "info")

        def run():
            try:
                backend = self._create_backend()
                prompt = build_translate_prompt(text, target_language)
                result = backend.check_text(prompt)
                self.after(0, self._on_translate_done, result, target_language)
            except Exception as e:
                self.after(0, self._on_translate_error, str(e))

        self._pool.submit(run)

    def _on_translate_done(self, result: str, target: str) -> None:
        self._checking = False
        self.translate_button.configure(state="normal")
        self.corrected_text.configure(state="normal")
        self.corrected_text.delete("0.0", "end")
        self.corrected_text.insert("0.0", result)
        self.corrected_text.configure(state="disabled")
        self.result_tabs.set("Korrektur")
        self._set_status(f"Übersetzung fertig (→ {target})", "success")

    def _on_translate_error(self, message: str) -> None:
        self._checking = False
        self.translate_button.configure(state="normal")
        self._set_status(f"Übersetzung fehlgeschlagen: {message}", "error")

    # ── KI-Werkzeuge Panel ─────────────────────────────────────

    # Jedes Tool: (icon, name, beschreibung, callback_key)
    TOOLS = [
        ("✏️", "Ton anpassen", "Text in einen anderen Stil umschreiben", "tone"),
        ("📝", "Kürzen", "Auf die Kernaussagen komprimieren", "shorten"),
        ("📖", "Erweitern", "Stichpunkte zu Fließtext ausbauen", "expand"),
        ("🔄", "Umformulieren", "Gleicher Inhalt, andere Worte", "rephrase"),
        ("✉️", "E-Mail verfassen", "Professionelle E-Mail aus Kontext", "email"),
        ("📊", "Analysieren", "Statistiken, Lesbarkeit, Tonalität", "analyze"),
    ]

    def _open_tools_panel(self) -> None:
        """Öffnet ein Werkzeug-Panel mit detaillierten Einstellungen pro Tool."""
        panel = ctk.CTkToplevel(self)
        panel.title("KI-Werkzeuge")
        panel.geometry("520x600")
        panel.minsize(480, 500)
        panel.transient(self)
        panel.grab_set()

        # Header
        ctk.CTkLabel(
            panel, text="🔧 KI-Werkzeuge",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(
            panel, text="Konfiguriere und starte ein Werkzeug für deinen Text.",
            font=ctk.CTkFont(size=12), text_color="gray50",
        ).pack(padx=20, pady=(0, 8), anchor="w")

        # Tabs für jedes Tool
        tabs = ctk.CTkTabview(panel, corner_radius=8)
        tabs.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self._build_tone_tab(tabs, panel)
        self._build_shorten_tab(tabs, panel)
        self._build_expand_tab(tabs, panel)
        self._build_rephrase_tab(tabs, panel)
        self._build_email_tab(tabs, panel)
        self._build_analyze_tab(tabs, panel)

    # ── Ton anpassen Tab ──

    def _build_tone_tab(self, tabs, panel):
        tab = tabs.add("✏️ Ton")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="Ton anpassen",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        ctk.CTkLabel(tab, text="Schreibe den Text in einem anderen Stil um.",
                     font=ctk.CTkFont(size=11), text_color="gray50").grid(
            row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        # Ton-Auswahl
        ctk.CTkLabel(tab, text="Ziel-Ton:").grid(row=2, column=0, padx=12, sticky="w")
        tone_var = ctk.CTkOptionMenu(tab, values=[
            "Formell / Geschäftlich",
            "Freundlich / Warm",
            "Professionell / Sachlich",
            "Locker / Umgangssprachlich",
            "Akademisch / Wissenschaftlich",
            "Überzeugend / Werblich",
            "Diplomatisch / Vorsichtig",
        ], width=280)
        tone_var.grid(row=3, column=0, padx=12, pady=(4, 8), sticky="w")

        # Zusatzanweisungen
        ctk.CTkLabel(tab, text="Zusätzliche Anweisungen (optional):").grid(
            row=4, column=0, padx=12, pady=(4, 0), sticky="w")
        extra_entry = ctk.CTkEntry(tab, placeholder_text="z.B. 'Kurze Sätze verwenden'")
        extra_entry.grid(row=5, column=0, padx=12, pady=(4, 8), sticky="ew")

        # Formelle Anrede
        formal_switch = ctk.CTkSwitch(tab, text="Sie-Form verwenden")
        formal_switch.grid(row=6, column=0, padx=12, pady=4, sticky="w")

        def run():
            text = self.editor.get("0.0", "end").strip()
            if not text:
                return
            tone = tone_var.get()
            extra = extra_entry.get().strip()[:200]  # Länge begrenzen
            # Verdächtige Injection-Patterns entfernen
            for bad in ("ignore", "vergiss", "system prompt", "forget", "disregard"):
                extra = extra.replace(bad, "")
            sie = "Verwende die Sie-Form." if formal_switch.get() else ""
            prompt = f"Schreibe den folgenden Text um im Ton: {tone}.\n{sie}\n"
            if extra:
                prompt += f"Stilhinweis: {extra}\n"
            prompt += f"Gib NUR den umgeschriebenen Text zurück.\n\n{text}"
            panel.destroy()
            self._run_tool(f"Ton → {tone}...", prompt)

        ctk.CTkButton(tab, text="Anwenden", width=140, height=36,
                      command=run).grid(row=7, column=0, padx=12, pady=(12, 0), sticky="w")

    # ── Kürzen Tab ──

    def _build_shorten_tab(self, tabs, panel):
        tab = tabs.add("📝 Kürzen")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="Text kürzen",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        # Ziel-Länge
        ctk.CTkLabel(tab, text="Kürzen auf:").grid(row=1, column=0, padx=12, sticky="w")
        length_var = ctk.CTkOptionMenu(tab, values=[
            "Kernaussagen (so kurz wie möglich)",
            "Ungefähr die Hälfte",
            "Ein Drittel der Länge",
            "Maximal 3 Sätze",
            "Maximal 1 Satz (Zusammenfassung)",
        ], width=300)
        length_var.grid(row=2, column=0, padx=12, pady=(4, 8), sticky="w")

        # Was beibehalten
        ctk.CTkLabel(tab, text="Beibehalten:").grid(row=3, column=0, padx=12, pady=(4, 0), sticky="w")
        keep_facts = ctk.CTkSwitch(tab, text="Fakten und Zahlen")
        keep_facts.select()
        keep_facts.grid(row=4, column=0, padx=12, pady=2, sticky="w")
        keep_names = ctk.CTkSwitch(tab, text="Namen und Orte")
        keep_names.select()
        keep_names.grid(row=5, column=0, padx=12, pady=2, sticky="w")
        keep_structure = ctk.CTkSwitch(tab, text="Absatzstruktur")
        keep_structure.grid(row=6, column=0, padx=12, pady=2, sticky="w")

        def run():
            text = self.editor.get("0.0", "end").strip()
            if not text:
                return
            target = length_var.get()
            keep = []
            if keep_facts.get():
                keep.append("Fakten und Zahlen beibehalten")
            if keep_names.get():
                keep.append("Namen und Orte beibehalten")
            if keep_structure.get():
                keep.append("Absatzstruktur beibehalten")
            keep_str = ". ".join(keep) + "." if keep else ""
            prompt = (f"Kürze den folgenden Text. Ziel: {target}.\n{keep_str}\n"
                      f"Gib NUR den gekürzten Text zurück.\n\n{text}")
            panel.destroy()
            self._run_tool("Kürze...", prompt)

        ctk.CTkButton(tab, text="Kürzen", width=140, height=36,
                      command=run).grid(row=7, column=0, padx=12, pady=(12, 0), sticky="w")

    # ── Erweitern Tab ──

    def _build_expand_tab(self, tabs, panel):
        tab = tabs.add("📖 Erweitern")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="Text erweitern",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        ctk.CTkLabel(tab, text="Erweiterungsart:").grid(row=1, column=0, padx=12, sticky="w")
        expand_var = ctk.CTkOptionMenu(tab, values=[
            "Details und Erklärungen hinzufügen",
            "Beispiele ergänzen",
            "Übergänge und Fließtext erstellen",
            "Einleitung und Fazit hinzufügen",
        ], width=300)
        expand_var.grid(row=2, column=0, padx=12, pady=(4, 8), sticky="w")

        ctk.CTkLabel(tab, text="Ungefähre Ziellänge:").grid(row=3, column=0, padx=12, sticky="w")
        target_len = ctk.CTkOptionMenu(tab, values=[
            "Doppelt so lang", "Dreifach", "Ein Absatz mehr", "Frei (so viel wie nötig)",
        ], width=250)
        target_len.grid(row=4, column=0, padx=12, pady=(4, 8), sticky="w")

        def run():
            text = self.editor.get("0.0", "end").strip()
            if not text:
                return
            how = expand_var.get()
            length = target_len.get()
            prompt = (f"Erweitere den folgenden Text. Art: {how}. Ziellänge: {length}.\n"
                      f"Behalte Inhalt und Ton bei.\nGib NUR den erweiterten Text zurück.\n\n{text}")
            panel.destroy()
            self._run_tool("Erweitere...", prompt)

        ctk.CTkButton(tab, text="Erweitern", width=140, height=36,
                      command=run).grid(row=5, column=0, padx=12, pady=(12, 0), sticky="w")

    # ── Umformulieren Tab ──

    def _build_rephrase_tab(self, tabs, panel):
        tab = tabs.add("🔄 Umformulieren")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="Text umformulieren",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        ctk.CTkLabel(tab, text="Stil:").grid(row=1, column=0, padx=12, sticky="w")
        style_var = ctk.CTkOptionMenu(tab, values=[
            "Komplett anders formulieren",
            "Nur einzelne Wörter ersetzen",
            "Satzstruktur ändern, Worte behalten",
            "Aktiv statt Passiv",
            "Einfacher ausdrücken",
        ], width=300)
        style_var.grid(row=2, column=0, padx=12, pady=(4, 8), sticky="w")

        keep_meaning = ctk.CTkSwitch(tab, text="Exakte Bedeutung beibehalten")
        keep_meaning.select()
        keep_meaning.grid(row=3, column=0, padx=12, pady=4, sticky="w")

        keep_length = ctk.CTkSwitch(tab, text="Ungefähr gleiche Länge")
        keep_length.select()
        keep_length.grid(row=4, column=0, padx=12, pady=4, sticky="w")

        def run():
            text = self.editor.get("0.0", "end").strip()
            if not text:
                return
            style = style_var.get()
            rules = []
            if keep_meaning.get():
                rules.append("Die exakte Bedeutung muss erhalten bleiben")
            if keep_length.get():
                rules.append("Die Länge soll ungefähr gleich bleiben")
            rules_str = ". ".join(rules) + "." if rules else ""
            prompt = (f"Formuliere den folgenden Text um. Stil: {style}.\n{rules_str}\n"
                      f"Gib NUR den umformulierten Text zurück.\n\n{text}")
            panel.destroy()
            self._run_tool("Formuliere um...", prompt)

        ctk.CTkButton(tab, text="Umformulieren", width=140, height=36,
                      command=run).grid(row=5, column=0, padx=12, pady=(12, 0), sticky="w")

    # ── E-Mail Tab ──

    def _build_email_tab(self, tabs, panel):
        tab = tabs.add("✉️ E-Mail")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="E-Mail verfassen",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        ctk.CTkLabel(tab, text="Erstellt eine E-Mail basierend auf deinem Text.",
                     font=ctk.CTkFont(size=11), text_color="gray50").grid(
            row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        ctk.CTkLabel(tab, text="E-Mail-Typ:").grid(row=2, column=0, padx=12, sticky="w")
        email_type = ctk.CTkOptionMenu(tab, values=[
            "Antwort auf eine Nachricht",
            "Neue E-Mail / Anfrage",
            "Beschwerde",
            "Bewerbung / Anschreiben",
            "Terminbestätigung",
            "Absage (höflich)",
            "Dankesschreiben",
        ], width=280)
        email_type.grid(row=3, column=0, padx=12, pady=(4, 8), sticky="w")

        ctk.CTkLabel(tab, text="Anrede:").grid(row=4, column=0, padx=12, sticky="w")
        greeting = ctk.CTkEntry(tab, placeholder_text="z.B. Sehr geehrte Frau Müller")
        greeting.grid(row=5, column=0, padx=12, pady=(4, 8), sticky="ew")

        formal_email = ctk.CTkSwitch(tab, text="Formell (Sie-Form)")
        formal_email.select()
        formal_email.grid(row=6, column=0, padx=12, pady=4, sticky="w")

        def run():
            text = self.editor.get("0.0", "end").strip()
            if not text:
                return
            typ = email_type.get()
            anrede = greeting.get().strip()
            sie = "Verwende die Sie-Form." if formal_email.get() else "Verwende die Du-Form."
            prompt = (f"Schreibe eine {typ} als E-Mail. {sie}\n")
            if anrede:
                prompt += f"Beginne mit: '{anrede}'\n"
            prompt += f"Ton: höflich, professionell.\nGib NUR die E-Mail zurück.\n\nKontext:\n{text}"
            panel.destroy()
            self._run_tool("Schreibe E-Mail...", prompt)

        ctk.CTkButton(tab, text="E-Mail erstellen", width=140, height=36,
                      command=run).grid(row=7, column=0, padx=12, pady=(12, 0), sticky="w")

    # ── Analysieren Tab ──

    def _build_analyze_tab(self, tabs, panel):
        tab = tabs.add("📊 Analyse")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="Text analysieren",
                     font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        ctk.CTkLabel(tab, text="Statistiken + KI-Bewertung deines Textes.",
                     font=ctk.CTkFont(size=11), text_color="gray50").grid(
            row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        # Vorschau: Live-Statistiken
        text = self.editor.get("0.0", "end").strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        sents = len([s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]) if text else 0
        read_min = max(1, round(words / 200))

        stats_frame = ctk.CTkFrame(tab, corner_radius=8)
        stats_frame.grid(row=2, column=0, padx=12, pady=8, sticky="ew")
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        for col, (val, label) in enumerate([
            (str(chars), "Zeichen"), (str(words), "Wörter"),
            (str(sents), "Sätze"), (f"~{read_min} Min", "Lesezeit"),
        ]):
            ctk.CTkLabel(stats_frame, text=val,
                         font=ctk.CTkFont(size=18, weight="bold")).grid(
                row=0, column=col, padx=8, pady=(8, 0))
            ctk.CTkLabel(stats_frame, text=label,
                         font=ctk.CTkFont(size=10), text_color="gray50").grid(
                row=1, column=col, padx=8, pady=(0, 8))

        ctk.CTkLabel(tab, text="Die KI-Analyse bewertet zusätzlich:",
                     font=ctk.CTkFont(size=11), text_color="gray50").grid(
            row=3, column=0, padx=12, pady=(4, 0), sticky="w")
        ctk.CTkLabel(tab, text="• Lesbarkeit  • Tonalität  • Verbesserungsvorschläge",
                     font=ctk.CTkFont(size=11), text_color="gray50").grid(
            row=4, column=0, padx=12, pady=(0, 8), sticky="w")

        def run():
            panel.destroy()
            t = self.editor.get("0.0", "end").strip()
            if t:
                self._run_analyze(t)

        ctk.CTkButton(tab, text="Analyse starten", width=140, height=36,
                      command=run).grid(row=5, column=0, padx=12, pady=(8, 0), sticky="w")

    def _run_tool(self, status_text: str, prompt: str) -> None:
        """Führt ein KI-Tool im Hintergrund aus, Ergebnis im Korrektur-Tab."""
        self._checking = True
        self._set_status(status_text, "info")

        def run():
            try:
                backend = self._create_backend()
                result = backend.check_text(prompt)
                self.after(0, self._on_tool_done, result)
            except Exception as e:
                self.after(0, self._on_tool_error, str(e))

        self._pool.submit(run)

    def _on_tool_done(self, result: str) -> None:
        self._checking = False
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.corrected_text.configure(state="normal")
        self.corrected_text.delete("0.0", "end")
        self.corrected_text.insert("0.0", result)
        self.corrected_text.configure(state="disabled")
        self.result_tabs.set("Korrektur")
        self._set_status("Fertig!", "success")

    def _on_tool_error(self, message: str) -> None:
        self._checking = False
        self._set_status(f"Fehler: {message}", "error")

    def _run_analyze(self, text: str) -> None:
        """Textanalyse: lokale Statistiken sofort + KI-Bewertung im Hintergrund."""
        import json as json_mod

        # Lokale Statistiken sofort berechnen
        words = text.split()
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".")
                     if s.strip()]
        word_count = len(words)
        sentence_count = max(len(sentences), 1)
        avg_len = round(word_count / sentence_count, 1)
        char_count = len(text)
        read_min = max(1, round(word_count / 200))

        local_stats = (
            f"📊 Textanalyse\n\n"
            f"  Zeichen:       {char_count}\n"
            f"  Wörter:        {word_count}\n"
            f"  Sätze:         {sentence_count}\n"
            f"  Ø Satzlänge:   {avg_len} Wörter\n"
            f"  Lesezeit:      ~{read_min} Min.\n"
        )

        # Sofort anzeigen
        self.errors_text.configure(state="normal")
        self.errors_text.delete("0.0", "end")
        self.errors_text.insert("0.0", local_stats + "\n⏳ KI-Bewertung wird geladen...")
        self.errors_text.configure(state="disabled")
        self.result_tabs.set("Fehler")
        self._set_status("KI-Analyse läuft...", "info")

        # KI im Hintergrund
        self._checking = True

        def run():
            try:
                backend = self._create_backend()
                raw = backend.check_text(build_analyze_prompt(text))
                try:
                    data = json_mod.loads(raw.strip())
                except json_mod.JSONDecodeError:
                    import re
                    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
                    data = json_mod.loads(m.group(1)) if m else {}
                self.after(0, self._on_analyze_done, local_stats, data)
            except Exception as e:
                self.after(0, self._on_analyze_error, local_stats, str(e))

        self._pool.submit(run)

    def _on_analyze_done(self, stats: str, ki: dict) -> None:
        self._checking = False
        result = stats + "\n── KI-Bewertung ──\n\n"
        result += f"  Lesbarkeit:    {ki.get('lesbarkeit', '–')}\n"
        result += f"  Tonalität:     {ki.get('tonalitaet', '–')}\n"
        tips = ki.get("verbesserungsvorschlaege", [])
        if tips:
            result += "\n  Verbesserungsvorschläge:\n"
            for t in tips:
                result += f"    • {t}\n"
        self.errors_text.configure(state="normal")
        self.errors_text.delete("0.0", "end")
        self.errors_text.insert("0.0", result)
        self.errors_text.configure(state="disabled")
        self._set_status("Analyse fertig!", "success")

    def _on_analyze_error(self, stats: str, msg: str) -> None:
        self._checking = False
        self.errors_text.configure(state="normal")
        self.errors_text.delete("0.0", "end")
        self.errors_text.insert("0.0", stats + f"\n⚠ KI-Analyse fehlgeschlagen: {msg}")
        self.errors_text.configure(state="disabled")
        self._set_status("KI-Analyse fehlgeschlagen.", "warning")

    # ── Chat ───────────────────────────────────────────────────

    def _chat_write(self, *parts) -> None:
        """Schreibt mehrere (text, tag) Paare in einem Batch in den Chat.

        Nur 1x state-toggle statt pro Aufruf -- viel flüssiger.
        """
        tw = self.chat_display._textbox
        self.chat_display.configure(state="normal")
        for text, tag in parts:
            tw.insert("end", text, tag)
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _on_chat_send(self) -> None:
        from datetime import datetime
        question = self.chat_entry.get().strip()
        if not question or self._chatting:
            return

        self._chatting = True
        self.chat_send_btn.configure(state="disabled", text="...")
        self.chat_entry.delete(0, "end")
        context = self.editor.get("0.0", "end").strip()

        # User-Nachricht + KI-Header in einem Batch anzeigen
        now = datetime.now().strftime("%H:%M")
        self._chat_write(
            (f"Du  ", "user_name"),
            (f"{now}\n", "time"),
            (f"{question}\n", "user_msg"),
            ("\n", "sep"),
            ("KI-Assistent  ", "bot_name"),
            (f"{now}\n", "time"),
        )

        # Automatisch zum Chat-Tab wechseln
        self.result_tabs.set("💬 Chat")

        def run():
            try:
                backend = self._create_backend()
                prompt = build_chat_prompt(question, context)
                answer = backend.check_text(prompt)
                self.after(0, self._stream_response, answer)
            except Exception as e:
                self.after(0, self._stream_response, f"⚠ {e}")

        self._pool.submit(run)

    def _stream_response(self, answer: str) -> None:
        """Streamt die Antwort in Chunks -- natürlicher als Wort-für-Wort."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        # In Chunks aufteilen: 3-5 Wörter pro Chunk = natürliches Tempo
        words = answer.split(" ")
        self._stream_chunks = []
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            # Leerzeichen am Ende außer beim letzten Chunk
            if i + chunk_size < len(words):
                chunk += " "
            self._stream_chunks.append(chunk)
        self._stream_idx = 0
        self._do_stream()

    def _do_stream(self) -> None:
        """Zeigt den nächsten Chunk an -- rekursiv via after()."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        if self._stream_idx < len(self._stream_chunks):
            chunk = self._stream_chunks[self._stream_idx]

            # Direkt ins Textwidget schreiben (schneller als _chat_write)
            tw = self.chat_display._textbox
            self.chat_display.configure(state="normal")
            tw.insert("end", chunk, "bot_msg")
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")

            self._stream_idx += 1
            # 50ms pro Chunk (= ~12 Wörter/Sekunde, natürliches Lesetempo)
            self.after(50, self._do_stream)
        else:
            # Fertig -- Abschluss und Eingabe wieder freigeben
            self._chat_write(
                ("\n", "bot_msg"),
                ("\n", "sep"),
            )
            self._chatting = False
            self.chat_send_btn.configure(state="normal", text="➤")
            self.chat_entry.focus()
            self._chat_count += 1

    # ── Planer ────────────────────────────────────────────────

    def _on_plan_start(self) -> None:
        """Starte Brainstorming: KI generiert Fragen als Checkboxen."""
        topic = self.plan_topic.get().strip()
        if not topic:
            self._set_status("Bitte Projekt/Aufgabe beschreiben.", "warning")
            return

        self._plan_topic_text = topic
        self.plan_start_btn.configure(state="disabled", text="Denkt nach...")
        self.plan_generate_btn.configure(state="disabled")
        self.result_tabs.set("📋 Planer")

        # Alte Checkboxen leeren
        for child in self.plan_scroll.winfo_children():
            child.destroy()
        self._plan_row = 0
        self._plan_checks = []

        # Info-Label
        info = ctk.CTkLabel(
            self.plan_scroll, text="KI erstellt Fragen für dein Projekt...",
            font=ctk.CTkFont(size=12, slant="italic"), text_color="gray50",
        )
        info.grid(row=0, column=0, padx=12, pady=8, sticky="w")
        self._plan_row = 1

        def run():
            try:
                backend = self._create_backend()
                prompt = build_brainstorm_prompt(topic)
                raw = backend.check_text(prompt)
                # JSON-Array parsen
                import json
                try:
                    questions = json.loads(raw.strip())
                except json.JSONDecodeError:
                    import re
                    m = re.search(r"\[.*\]", raw, re.DOTALL)
                    questions = json.loads(m.group(0)) if m else []
                self.after(0, self._on_plan_questions, questions)
            except Exception as e:
                self.after(0, self._on_plan_error, str(e))

        self._pool.submit(run)

    def _on_plan_questions(self, questions: list[str]) -> None:
        """Zeigt die KI-Fragen als Checkboxen an."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        # Info-Label entfernen
        for child in self.plan_scroll.winfo_children():
            child.destroy()
        self._plan_row = 0
        self._plan_checks = []

        self.plan_start_btn.configure(state="normal", text="Brainstorming")

        if not questions:
            ctk.CTkLabel(
                self.plan_scroll, text="Keine Fragen generiert. Versuche eine andere Beschreibung.",
                font=ctk.CTkFont(size=12), text_color="gray50",
            ).grid(row=0, column=0, padx=12, pady=8, sticky="w")
            return

        # Header
        ctk.CTkLabel(
            self.plan_scroll,
            text="Wähle die relevanten Punkte für deinen Plan:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")
        self._plan_row = 1

        # Checkboxen für jede Frage
        for question in questions:
            if not isinstance(question, str) or not question.strip():
                continue
            var = ctk.StringVar(value="on")  # Standard: angehakt
            cb = ctk.CTkCheckBox(
                self.plan_scroll, text=question.strip(),
                font=ctk.CTkFont(size=12), variable=var,
                onvalue="on", offvalue="off",
                corner_radius=4, border_width=2,
            )
            cb.grid(row=self._plan_row, column=0, padx=12, pady=3, sticky="w")
            self._plan_checks.append((var, question.strip()))
            self._plan_row += 1

        # Alles auswählen / Nichts auswählen Buttons
        btn_row = ctk.CTkFrame(self.plan_scroll, fg_color="transparent")
        btn_row.grid(row=self._plan_row, column=0, padx=12, pady=(8, 4), sticky="w")

        ctk.CTkButton(
            btn_row, text="Alle", width=60, height=28, corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), border_color=("gray70", "gray30"),
            command=lambda: [v.set("on") for v, _ in self._plan_checks],
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_row, text="Keine", width=60, height=28, corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), border_color=("gray70", "gray30"),
            command=lambda: [v.set("off") for v, _ in self._plan_checks],
        ).pack(side="left")

        # Generieren-Button aktivieren
        self.plan_generate_btn.configure(state="normal")
        self._set_status(f"{len(self._plan_checks)} Fragen generiert. Auswählen und Plan erstellen.", "info")

    def _on_plan_error(self, msg: str) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.plan_start_btn.configure(state="normal", text="Brainstorming")
        self._set_status(f"Planer-Fehler: {msg}", "error")

    def _on_plan_generate(self) -> None:
        """Generiert den Markdown-Plan basierend auf den Checkboxen."""
        if not self._plan_checks:
            return

        selected = [text for var, text in self._plan_checks if var.get() == "on"]
        deselected = [text for var, text in self._plan_checks if var.get() == "off"]

        if not selected:
            self._set_status("Bitte mindestens einen Punkt auswählen.", "warning")
            return

        self.plan_generate_btn.configure(state="disabled", text="Erstelle Plan...")
        self._set_status("Markdown-Plan wird generiert...", "info")

        def run():
            try:
                backend = self._create_backend()
                prompt = build_plan_prompt(self._plan_topic_text, selected, deselected)
                md = backend.check_text(prompt)
                self.after(0, self._on_plan_generated, md)
            except Exception as e:
                self.after(0, self._on_plan_gen_error, str(e))

        self._pool.submit(run)

    def _on_plan_generated(self, markdown: str) -> None:
        """Zeigt den generierten Plan im Korrektur-Tab + kopiert in Zwischenablage."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.plan_generate_btn.configure(state="normal", text="📄 Plan als Markdown generieren")

        # Plan im Korrektur-Tab anzeigen
        self.corrected_text.configure(state="normal")
        self.corrected_text.delete("0.0", "end")
        self.corrected_text.insert("0.0", markdown)
        self.corrected_text.configure(state="disabled")
        self.result_tabs.set("Korrektur")

        # In Zwischenablage kopieren
        try:
            pyperclip.copy(markdown)
            self._set_status("✔ Plan erstellt und in Zwischenablage kopiert!", "success")
        except Exception:
            self._set_status("✔ Plan erstellt! (Kopieren in Zwischenablage fehlgeschlagen)", "success")

    def _on_plan_gen_error(self, msg: str) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.plan_generate_btn.configure(state="normal", text="📄 Plan als Markdown generieren")
        self._set_status(f"Plan-Erstellung fehlgeschlagen: {msg}", "error")

    # ── Agent-Tab Methoden ──────────────────────────────────────

    def _refresh_agent_tab(self) -> None:
        """Aktualisiert die Agent-Anzeige mit aktuellem Gedächtnis."""
        from app.agent_memory import load_memory
        memory = load_memory()
        tw = self.agent_display._textbox

        self.agent_display.configure(state="normal")
        tw.delete("1.0", "end")

        # Profil
        tw.insert("end", "📊 Schreibprofil\n", "heading")
        checks = memory.get("total_checks", 0)
        words = memory.get("total_words", 0)
        errors = memory.get("total_errors", 0)
        accepted = memory.get("corrections_accepted", 0)
        rejected = memory.get("corrections_rejected", 0)

        tw.insert("end", "  Prüfungen:  ", "label")
        tw.insert("end", f"{checks}\n", "value")
        tw.insert("end", "  Geprüfte Wörter:  ", "label")
        tw.insert("end", f"{words:,}\n".replace(",", "."), "value")
        tw.insert("end", "  Gefundene Fehler:  ", "label")
        tw.insert("end", f"{errors}\n", "value")
        if checks > 0:
            avg = round(errors / checks, 1)
            tw.insert("end", "  Ø Fehler/Text:  ", "label")
            tw.insert("end", f"{avg}\n", "value")
        if accepted + rejected > 0:
            rate = round(accepted / (accepted + rejected) * 100)
            tw.insert("end", "  Akzeptanzrate:  ", "label")
            tw.insert("end", f"{rate}% ({accepted} akzeptiert, {rejected} abgelehnt)\n", "value")

        # Stil
        style = memory.get("style", "")
        if style:
            tw.insert("end", "\n  Bevorzugter Stil:  ", "label")
            tw.insert("end", f"{style}\n", "value")

        # Schwächen
        weak = memory.get("weak_areas", [])
        if weak:
            tw.insert("end", "\n⚠ Schwächen\n", "heading")
            for w in weak:
                tw.insert("end", f"  • {w}\n", "weak")

        # Stärken
        strong = memory.get("strong_areas", [])
        if strong:
            tw.insert("end", "\n✔ Stärken\n", "heading")
            for s in strong:
                tw.insert("end", f"  • {s}\n", "strong")

        # Top Fehlerpatterns
        patterns = memory.get("patterns", [])
        if patterns:
            tw.insert("end", "\n📈 Häufigste Fehler\n", "heading")
            for p in patterns[:5]:
                count = p.get("count", 0)
                pattern = p.get("pattern", "")
                tw.insert("end", f"  {count}x  ", "label")
                tw.insert("end", f"{pattern}\n", "value")

        # Glossar
        glossary = memory.get("glossary", [])
        tw.insert("end", f"\n📖 Glossar ({len(glossary)} Wörter)\n", "heading")
        if glossary:
            tw.insert("end", f"  {', '.join(glossary)}\n", "glossary")
        else:
            tw.insert("end", "  (leer -- Wörter hinzufügen die nie korrigiert werden sollen)\n", "glossary")

        # Tipp
        tip = get_smart_tip(memory)
        if tip:
            tw.insert("end", f"\n{tip}\n", "tip")

        # Letztes Update
        updated = memory.get("last_updated", "")
        if updated:
            tw.insert("end", f"\nLetzte Aktualisierung: {updated}\n", "glossary")

        self.agent_display.configure(state="disabled")

    def _add_glossary_word(self) -> None:
        """Fügt ein Wort aus dem Eingabefeld zum Glossar hinzu."""
        word = self.glossary_entry.get().strip()
        if not word:
            return
        add_to_glossary(word)
        self.glossary_entry.delete(0, "end")
        self._refresh_agent_tab()
        self._set_status(f"'{word}' zum Glossar hinzugefügt.", "success")

    def _clear_agent_memory(self) -> None:
        """Setzt das Agent-Gedächtnis zurück."""
        from app.agent_memory import clear_memory
        clear_memory()
        self._refresh_agent_tab()
        self._set_status("Agent-Gedächtnis zurückgesetzt.", "info")

    def _show_glossary_suggestion(self, suggestions: list[str]) -> None:
        """Zeigt Glossar-Vorschläge für erkannte Eigennamen."""
        if not suggestions:
            return
        words = ", ".join(suggestions)
        # Info in der Statusleiste
        self.summary_label.configure(
            text=f"📖 Neue Wörter erkannt: {words} — Im 🧠 Agent-Tab zum Glossar hinzufügen"
        )

    # ── Clipboard / Paste / Copy / Clear ───────────────────────

    def _on_paste(self) -> None:
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
        self._highlight_errors([])
        self.editor.delete("0.0", "end")
        self.corrected_text.configure(state="normal")
        self.corrected_text.delete("0.0", "end")
        self.corrected_text.configure(state="disabled")
        self.errors_text.configure(state="normal")
        self.errors_text.delete("0.0", "end")
        self.errors_text.configure(state="disabled")
        # Chat leeren
        self.chat_display.configure(state="normal")
        self.chat_display.delete("0.0", "end")
        self.chat_display.configure(state="disabled")
        self._chat_count = 0
        self.summary_label.configure(text="")
        self._set_status("", "info")

    def _on_copy(self) -> None:
        self.corrected_text.configure(state="normal")
        text = self.corrected_text.get("0.0", "end").strip()
        self.corrected_text.configure(state="disabled")
        if text:
            try:
                pyperclip.copy(text)
                record_acceptance(True)  # Agent merkt sich: Korrektur akzeptiert
                self._set_status("Korrektur kopiert!", "success")
            except Exception as e:
                logger.error("Clipboard copy error: %s", e)
                self._set_status("Fehler beim Kopieren.", "error")
        else:
            self._set_status("Kein korrigierter Text.", "warning")

    def _set_status(self, message: str, level: str = "info") -> None:
        colors = {"info": "gray60", "success": "#2E7D32",
                  "warning": "#EF6C00", "error": "#D32F2F"}
        self.status_label.configure(text=message,
                                    text_color=colors.get(level, "gray60"))
