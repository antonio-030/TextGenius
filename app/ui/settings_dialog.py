"""Settings dialog for TextGenius - modal window with tabbed sections.

Backends: Ollama (lokal), Claude API (API-Key), Claude Abo (OAuth direkt).
"""

import logging
import subprocess
import threading

import customtkinter as ctk
import requests

from app.backends.ollama import OllamaBackend
from app.backends.claude_oauth import load_oauth_token, is_token_expired, _get_valid_token
from app.settings import save_settings, DEFAULTS

logger = logging.getLogger(__name__)


class SettingsDialog(ctk.CTkToplevel):
    """Modal settings dialog with Backend and General tabs."""

    def __init__(self, parent, settings: dict):
        super().__init__(parent)

        # Work on a copy so cancel discards changes
        self.settings = dict(settings)
        self.result = None
        self._destroyed = False

        # Window setup
        self.title("Einstellungen")
        self.geometry("560x520")
        self.minsize(500, 440)

        # Modal: block main window
        self.transient(parent)
        self.grab_set()
        self.focus()

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_tabs()
        self._build_bottom_buttons()
        self._load_current_values()

    # ── Tabs ───────────────────────────────────────────────────

    def _build_tabs(self):
        """Create the tabbed sections."""
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")

        self._build_backend_tab()
        self._build_general_tab()

    def _build_backend_tab(self):
        """Backend tab with three options: Ollama, Claude API, Claude Abo."""
        tab = self.tabview.add("Backend")
        tab.grid_columnconfigure(1, weight=1)

        # Backend dropdown
        ctk.CTkLabel(tab, text="KI-Backend:", anchor="w").grid(
            row=0, column=0, padx=12, pady=(16, 8), sticky="w",
        )
        self.backend_menu = ctk.CTkOptionMenu(
            tab,
            values=["ollama", "claude_api", "claude_abo"],
            command=self._on_backend_changed,
            width=200,
        )
        self.backend_menu.grid(row=0, column=1, padx=12, pady=(16, 8), sticky="w")

        # ── Ollama ──
        self._build_ollama_section(tab, row=1)

        # ── Claude API ──
        self._build_claude_api_section(tab, row=2)

        # ── Claude Abo (Proxy) ──
        self._build_claude_abo_section(tab, row=3)

    def _build_ollama_section(self, tab, row):
        """Ollama: Server-URL, Modell-Dropdown, Verbindungstest."""
        self.ollama_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.ollama_frame.grid(row=row, column=0, columnspan=2, padx=8, pady=4, sticky="ew")
        self.ollama_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.ollama_frame, text="Server URL:").grid(
            row=0, column=0, padx=12, pady=6, sticky="w",
        )
        self.ollama_url_entry = ctk.CTkEntry(
            self.ollama_frame, placeholder_text="http://localhost:11434",
        )
        self.ollama_url_entry.grid(row=0, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self.ollama_frame, text="Modell:").grid(
            row=1, column=0, padx=12, pady=6, sticky="w",
        )
        self.ollama_model_menu = ctk.CTkOptionMenu(
            self.ollama_frame, values=["(wird geladen...)"], width=200,
        )
        self.ollama_model_menu.grid(row=1, column=1, padx=12, pady=6, sticky="w")

        # Buttons: test + refresh
        btn_row = ctk.CTkFrame(self.ollama_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, padx=8, pady=4, sticky="ew")

        self.ollama_test_btn = ctk.CTkButton(
            btn_row, text="Verbindung testen", width=150,
            command=self._test_ollama,
        )
        self.ollama_test_btn.pack(side="left", padx=4, pady=4)

        self.ollama_refresh_btn = ctk.CTkButton(
            btn_row, text="\u21BB  Modelle laden", width=130,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            border_color=("gray70", "gray30"),
            command=self._refresh_ollama_models,
        )
        self.ollama_refresh_btn.pack(side="left", padx=4, pady=4)

        self.ollama_status = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=12),
        )
        self.ollama_status.pack(side="left", padx=8, pady=4)

    def _build_claude_api_section(self, tab, row):
        """Claude API: API-Key + Modell-Auswahl."""
        self.claude_api_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.claude_api_frame.grid(
            row=row, column=0, columnspan=2, padx=8, pady=4, sticky="ew",
        )
        self.claude_api_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.claude_api_frame, text="API Key:").grid(
            row=0, column=0, padx=12, pady=6, sticky="w",
        )
        self.claude_key_entry = ctk.CTkEntry(
            self.claude_api_frame, placeholder_text="sk-ant-...", show="*",
        )
        self.claude_key_entry.grid(row=0, column=1, padx=12, pady=6, sticky="ew")

        ctk.CTkLabel(self.claude_api_frame, text="Modell:").grid(
            row=1, column=0, padx=12, pady=6, sticky="w",
        )
        self.claude_api_model_menu = ctk.CTkOptionMenu(
            self.claude_api_frame,
            values=["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"],
            width=240,
        )
        self.claude_api_model_menu.grid(row=1, column=1, padx=12, pady=6, sticky="w")

    def _build_claude_abo_section(self, tab, row):
        """Claude Abo: OAuth-Login direkt, kein Proxy noetig."""
        self.claude_abo_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.claude_abo_frame.grid(
            row=row, column=0, columnspan=2, padx=8, pady=4, sticky="ew",
        )
        self.claude_abo_frame.grid_columnconfigure(1, weight=1)

        # Info text
        ctk.CTkLabel(
            self.claude_abo_frame,
            text="Nutzt dein Claude Pro/Max Abo direkt.\n"
                 "Kein API-Key nötig – einfach mit claude.ai einloggen.",
            font=ctk.CTkFont(size=11),
            text_color="gray50",
            justify="left",
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(8, 6), sticky="w")

        # ── Login section ──
        login_row = ctk.CTkFrame(self.claude_abo_frame, fg_color="transparent")
        login_row.grid(row=1, column=0, columnspan=2, padx=8, pady=4, sticky="ew")

        self.login_btn = ctk.CTkButton(
            login_row, text="Mit claude.ai einloggen", width=180,
            command=self._start_claude_login,
        )
        self.login_btn.pack(side="left", padx=4, pady=4)

        self.logout_btn = ctk.CTkButton(
            login_row, text="Ausloggen", width=90,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            border_color=("gray70", "gray30"),
            hover_color=("#D32F2F", "#D32F2F"),
            command=self._claude_logout,
        )
        self.logout_btn.pack(side="left", padx=4, pady=4)

        self.login_status = ctk.CTkLabel(
            login_row, text="Prüfe...", font=ctk.CTkFont(size=12),
            text_color="gray50",
        )
        self.login_status.pack(side="left", padx=8, pady=4)

        # Modell
        ctk.CTkLabel(self.claude_abo_frame, text="Modell:").grid(
            row=2, column=0, padx=12, pady=6, sticky="w",
        )
        # Models for direct OAuth API access
        abo_models = [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
        ]
        self.proxy_model_menu = ctk.CTkOptionMenu(
            self.claude_abo_frame,
            values=abo_models,
            width=240,
        )
        self.proxy_model_menu.grid(row=2, column=1, padx=12, pady=6, sticky="w")

        # ── Usage HUD ──
        hud_frame = ctk.CTkFrame(self.claude_abo_frame, corner_radius=8)
        hud_frame.grid(row=3, column=0, columnspan=2, padx=12, pady=(8, 4), sticky="ew")
        hud_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            hud_frame, text="Nutzung", font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(8, 4), sticky="w")

        # 5-hour usage bar
        ctk.CTkLabel(hud_frame, text="5 Stunden:", font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, padx=12, pady=2, sticky="w",
        )
        self.usage_5h_bar = ctk.CTkProgressBar(hud_frame, height=14, corner_radius=4)
        self.usage_5h_bar.set(0)
        self.usage_5h_bar.grid(row=1, column=1, padx=(0, 12), pady=2, sticky="ew")

        self.usage_5h_label = ctk.CTkLabel(
            hud_frame, text="--", font=ctk.CTkFont(size=11), text_color="gray50",
        )
        self.usage_5h_label.grid(row=2, column=1, padx=(0, 12), pady=(0, 4), sticky="w")

        # 7-day usage bar
        ctk.CTkLabel(hud_frame, text="7 Tage:", font=ctk.CTkFont(size=11)).grid(
            row=3, column=0, padx=12, pady=2, sticky="w",
        )
        self.usage_7d_bar = ctk.CTkProgressBar(hud_frame, height=14, corner_radius=4)
        self.usage_7d_bar.set(0)
        self.usage_7d_bar.grid(row=3, column=1, padx=(0, 12), pady=2, sticky="ew")

        self.usage_7d_label = ctk.CTkLabel(
            hud_frame, text="--", font=ctk.CTkFont(size=11), text_color="gray50",
        )
        self.usage_7d_label.grid(row=4, column=1, padx=(0, 12), pady=(0, 8), sticky="w")

    def _build_general_tab(self):
        """General tab: language, font size, clipboard toggle."""
        tab = self.tabview.add("Allgemein")
        tab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="Sprache:").grid(
            row=0, column=0, padx=12, pady=(16, 8), sticky="w",
        )
        self.language_menu = ctk.CTkOptionMenu(
            tab, values=["auto", "de", "en", "de+en"], width=120,
        )
        self.language_menu.grid(row=0, column=1, padx=12, pady=(16, 8), sticky="w")

        ctk.CTkLabel(tab, text="Schriftgröße:").grid(
            row=1, column=0, padx=12, pady=8, sticky="w",
        )
        self.fontsize_menu = ctk.CTkOptionMenu(
            tab, values=["10", "11", "12", "13", "14", "15", "16"], width=120,
        )
        self.fontsize_menu.grid(row=1, column=1, padx=12, pady=8, sticky="w")

        self.clipboard_switch = ctk.CTkSwitch(
            tab, text="Zwischenablage überwachen",
        )
        self.clipboard_switch.grid(
            row=2, column=0, columnspan=2, padx=12, pady=8, sticky="w",
        )

        self.update_switch = ctk.CTkSwitch(
            tab, text="Automatisch nach Updates suchen",
        )
        self.update_switch.grid(
            row=3, column=0, columnspan=2, padx=12, pady=(0, 16), sticky="w",
        )

    # ── Bottom buttons ─────────────────────────────────────────

    def _build_bottom_buttons(self):
        """Save and cancel buttons."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            frame, text="Abbrechen", width=110,
            fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"),
            border_color=("gray70", "gray30"),
            command=self._on_cancel,
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            frame, text="Speichern", width=110,
            command=self._on_save,
        ).grid(row=0, column=2)

    # ── Load values ────────────────────────────────────────────

    def _load_current_values(self):
        """Fill all fields from current settings."""
        self.backend_menu.set(self.settings.get("backend", "ollama"))

        self.ollama_url_entry.insert(0, self.settings.get("ollama_url", ""))

        self.claude_key_entry.insert(0, self.settings.get("claude_api_key", ""))
        self.claude_api_model_menu.set(
            self.settings.get("claude_model", "claude-sonnet-4-20250514"),
        )

        self.proxy_model_menu.set(
            self.settings.get("proxy_model", "claude-sonnet-4-20250514"),
        )

        self.language_menu.set(self.settings.get("language", "de"))
        self.fontsize_menu.set(str(self.settings.get("font_size", 12)))

        if self.settings.get("clipboard_monitor"):
            self.clipboard_switch.select()
        if self.settings.get("update_check", True):
            self.update_switch.select()

        self._on_backend_changed(self.settings.get("backend", "ollama"))

        # Check login status in background
        self._check_claude_login()

    # ── Backend switching ──────────────────────────────────────

    def _on_backend_changed(self, choice: str):
        """Show only the selected backend's settings."""
        self.ollama_frame.grid_remove()
        self.claude_api_frame.grid_remove()
        self.claude_abo_frame.grid_remove()

        if choice == "ollama":
            self.ollama_frame.grid()
            self._refresh_ollama_models()
        elif choice == "claude_api":
            self.claude_api_frame.grid()
        elif choice == "claude_abo":
            self.claude_abo_frame.grid()
            self._fetch_usage()

    # ── Ollama handlers ────────────────────────────────────────

    def _test_ollama(self):
        """Test Ollama connection in background."""
        self.ollama_test_btn.configure(state="disabled", text="Teste...")
        self.ollama_status.configure(text="", text_color="gray60")

        url = self.ollama_url_entry.get() or DEFAULTS["ollama_url"]

        def run():
            backend = OllamaBackend(base_url=url)
            ok = backend.test_connection()
            models = backend.list_models() if ok else []
            self.after(0, self._on_ollama_tested, ok, models)

        threading.Thread(target=run, daemon=True).start()

    def _on_ollama_tested(self, ok: bool, models: list[str]):
        """Show Ollama test result."""
        if not self._is_alive():
            return
        self.ollama_test_btn.configure(state="normal", text="Verbindung testen")
        if ok:
            count = len(models)
            self.ollama_status.configure(
                text=f"Verbunden! ({count} Modelle)", text_color="#2E7D32",
            )
            if models:
                self._update_ollama_dropdown(models)
        else:
            self.ollama_status.configure(text="Nicht erreichbar", text_color="#D32F2F")

    def _refresh_ollama_models(self):
        """Fetch Ollama models in background."""
        self.ollama_refresh_btn.configure(state="disabled", text="\u23F3  Lade...")
        url = self.ollama_url_entry.get() or DEFAULTS["ollama_url"]

        def fetch():
            models = OllamaBackend(base_url=url).list_models()
            self.after(0, self._on_ollama_models, models)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_ollama_models(self, models: list[str]):
        """Fill Ollama model dropdown."""
        if not self._is_alive():
            return
        self.ollama_refresh_btn.configure(state="normal", text="\u21BB  Modelle laden")
        if models:
            self._update_ollama_dropdown(models)
        else:
            self.ollama_model_menu.configure(values=["(keine Modelle)"])
            self.ollama_model_menu.set("(keine Modelle)")

    def _update_ollama_dropdown(self, models: list[str]):
        """Update Ollama dropdown and keep current selection."""
        self.ollama_model_menu.configure(values=models)
        current = self.settings.get("ollama_model", "")
        if current in models:
            self.ollama_model_menu.set(current)
        elif models:
            self.ollama_model_menu.set(models[0])

    # ── Claude Login handlers ────────────────────────────────────

    # ── Usage HUD handlers ──────────────────────────────────────

    def _fetch_usage(self):
        """Fetch usage data from Anthropic OAuth API (background)."""
        def fetch():
            try:
                token = _get_valid_token()
                resp = requests.get(
                    "https://api.anthropic.com/api/oauth/usage",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "claude-cli/2.1.75",
                        "Accept": "application/json",
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "oauth-2025-04-20",
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    self.after(0, self._on_usage_loaded, resp.json())
            except Exception as e:
                logger.warning("Usage-Abfrage fehlgeschlagen: %s", e)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_usage_loaded(self, data: dict):
        """Update the usage bars with real data."""
        if not self._is_alive():
            return

        # 5-hour usage
        five_h = data.get("five_hour", {})
        pct_5h = five_h.get("utilization", 0) or 0
        reset_5h = five_h.get("resets_at", "")
        self.usage_5h_bar.set(pct_5h / 100)
        self._color_bar(self.usage_5h_bar, pct_5h)
        reset_text_5h = self._format_reset(reset_5h)
        self.usage_5h_label.configure(text=f"{pct_5h:.0f}% verbraucht{reset_text_5h}")

        # 7-day usage
        seven_d = data.get("seven_day", {})
        pct_7d = seven_d.get("utilization", 0) or 0
        reset_7d = seven_d.get("resets_at", "")
        self.usage_7d_bar.set(pct_7d / 100)
        self._color_bar(self.usage_7d_bar, pct_7d)
        reset_text_7d = self._format_reset(reset_7d)
        self.usage_7d_label.configure(text=f"{pct_7d:.0f}% verbraucht{reset_text_7d}")

    def _color_bar(self, bar, pct):
        """Set bar color based on usage percentage."""
        if pct >= 80:
            bar.configure(progress_color="#D32F2F")
        elif pct >= 50:
            bar.configure(progress_color="#EF6C00")
        else:
            bar.configure(progress_color=("#3B82F6", "#3B82F6"))

    def _format_reset(self, reset_str: str) -> str:
        """Format ISO reset time as relative time."""
        if not reset_str:
            return ""
        try:
            from datetime import datetime, timezone
            reset_dt = datetime.fromisoformat(reset_str)
            now = datetime.now(timezone.utc)
            diff = reset_dt - now
            hours = int(diff.total_seconds() / 3600)
            minutes = int((diff.total_seconds() % 3600) / 60)
            if hours > 0:
                return f"  (Reset in {hours}h {minutes}m)"
            elif minutes > 0:
                return f"  (Reset in {minutes}m)"
            else:
                return "  (Reset bald)"
        except Exception:
            return ""

    # ── Claude Login handlers ────────────────────────────────────

    def _check_claude_login(self):
        """Check OAuth credentials + fetch email via CLI (background)."""
        def check():
            try:
                oauth = load_oauth_token()
                expired = is_token_expired(oauth)
                sub_type = oauth.get("subscriptionType", "")
                email = self._get_claude_email()
                self.after(0, self._on_login_checked, True, expired, sub_type, email)
            except ValueError:
                self.after(0, self._on_login_checked, False, False, "", "")

        threading.Thread(target=check, daemon=True).start()

    def _get_claude_email(self) -> str:
        """Get the logged-in email from Claude CLI (may be slow)."""
        import json as json_mod
        try:
            result = subprocess.run(
                ["claude", "auth", "status", "--json"],
                capture_output=True, text=True, timeout=10,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json_mod.loads(result.stdout)
                return data.get("email", "")
        except Exception:
            pass
        return ""

    def _on_login_checked(self, has_token: bool, expired: bool, sub_type: str, email: str = ""):
        """Show login status with email and subscription type."""
        if not self._is_alive():
            return
        if has_token and not expired:
            parts = []
            if email:
                parts.append(email)
            if sub_type:
                parts.append(sub_type)
            label = "Eingeloggt"
            if parts:
                label += f" ({', '.join(parts)})"
            self.login_status.configure(text=label, text_color="#2E7D32")
            self.login_btn.configure(text="\u2714  Eingeloggt")
        elif has_token and expired:
            self.login_status.configure(
                text="Token abgelaufen -- neu einloggen", text_color="#EF6C00",
            )
        else:
            self.login_status.configure(
                text="Nicht eingeloggt", text_color="#D32F2F",
            )
            self.login_btn.configure(text="Mit claude.ai einloggen")

    def _claude_logout(self):
        """Loggt aus Claude aus und löscht den Token."""
        self.logout_btn.configure(state="disabled", text="...")

        def run():
            try:
                # Claude CLI Logout
                result = subprocess.run(
                    ["claude", "auth", "logout"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=0x08000000,
                )
                # Credentials-Datei bereinigen
                from pathlib import Path
                creds_path = Path.home() / ".claude" / ".credentials.json"
                if creds_path.exists():
                    import json
                    with open(creds_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "claudeAiOauth" in data:
                        del data["claudeAiOauth"]
                    with open(creds_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)

                self.after(0, self._on_logout_done, True)
            except Exception as e:
                logger.error("Logout fehlgeschlagen: %s", e)
                self.after(0, self._on_logout_done, False)

        threading.Thread(target=run, daemon=True).start()

    def _on_logout_done(self, success: bool):
        if not self._is_alive():
            return
        self.logout_btn.configure(state="normal", text="Ausloggen")
        if success:
            self.login_status.configure(text="Ausgeloggt", text_color="#EF6C00")
            self.login_btn.configure(text="Mit claude.ai einloggen")
        else:
            self.login_status.configure(text="Logout fehlgeschlagen", text_color="#D32F2F")

    def _start_claude_login(self):
        """Open browser for Claude OAuth login (background)."""
        self.login_btn.configure(state="disabled", text="\u23F3  Browser öffnet sich...")
        self.login_status.configure(text="Warte auf Login im Browser...", text_color="gray50")

        def run_login():
            try:
                # Start claude auth login -- opens browser
                proc = subprocess.Popen(
                    ["claude", "auth", "login"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
                # Wait for the login process to complete
                proc.communicate(timeout=120)
                success = proc.returncode == 0

                # Verify by checking credentials + fetch email
                if success:
                    try:
                        oauth = load_oauth_token()
                        expired = is_token_expired(oauth)
                        sub = oauth.get("subscriptionType", "")
                        email = self._get_claude_email()
                        self.after(0, self._on_login_checked, True, expired, sub, email)
                    except ValueError:
                        self.after(0, self._on_login_checked, False, False, "", "")
                else:
                    self.after(0, self._on_login_failed)
            except Exception as e:
                logger.error("Claude Login fehlgeschlagen: %s", e)
                self.after(0, self._on_login_failed)

        threading.Thread(target=run_login, daemon=True).start()

    def _on_login_failed(self):
        """Handle failed login attempt."""
        if not self._is_alive():
            return
        self.login_btn.configure(state="normal", text="Mit claude.ai einloggen")
        self.login_status.configure(
            text="Login fehlgeschlagen. Ist Claude CLI installiert?",
            text_color="#D32F2F",
        )

    # ── Save / Cancel ──────────────────────────────────────────

    def _on_save(self):
        """Collect values and persist to disk."""
        self.settings["backend"] = self.backend_menu.get()
        self.settings["ollama_url"] = self.ollama_url_entry.get()
        self.settings["ollama_model"] = self.ollama_model_menu.get()
        self.settings["claude_api_key"] = self.claude_key_entry.get()
        self.settings["claude_model"] = self.claude_api_model_menu.get()
        self.settings["proxy_model"] = self.proxy_model_menu.get()
        self.settings["language"] = self.language_menu.get()
        self.settings["font_size"] = int(self.fontsize_menu.get())
        self.settings["clipboard_monitor"] = bool(self.clipboard_switch.get())
        self.settings["update_check"] = bool(self.update_switch.get())

        save_settings(self.settings)
        self.result = self.settings
        self._destroyed = True
        self.destroy()

    def _on_cancel(self):
        """Close without saving."""
        self.result = None
        self._destroyed = True
        self.destroy()

    def _is_alive(self) -> bool:
        """Check if this dialog still exists (not destroyed)."""
        return not self._destroyed
