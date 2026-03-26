# CLAUDE.md -- TextGenius Projektregeln

## Projektuebersicht
**TextGenius** ist eine KI-basierte Rechtschreib- und Grammatikpruefung fuer Windows.
Gebaut mit Python + CustomTkinter. Unterstuetzt Ollama und Claude (API-Key oder Abo) als KI-Backend.

---

## Technologie-Stack
- **Sprache:** Python 3.10+
- **GUI:** CustomTkinter (modernes Tkinter mit DPI-Support, Dark/Light Theme)
- **Packaging:** PyInstaller -> .exe, Inno Setup -> Installer
- **KI-Backends:** Ollama (lokal), Claude API (API-Key), Claude Abo (OAuth direkt)
- **Clipboard:** pyperclip
- **HTTP:** requests
- **Hotkeys:** pynput (keine Admin-Rechte noetig)
- **KI-SDK:** anthropic (fuer Claude API Backend)

---

## Projektstruktur
```
TextGenius/
├── CLAUDE.md              <- Diese Datei
├── Abo_PLAN.md            <- Projektplan & Roadmap
├── README.md              <- Nutzerdokumentation
├── requirements.txt       <- Python-Abhaengigkeiten
├── version.py             <- APP_VERSION + APP_NAME
├── main.py                <- Einstiegspunkt
├── app/
│   ├── __init__.py
│   ├── checker.py         <- Prompt-Logik + JSON-Parsing
│   ├── settings.py        <- Einstellungen laden/speichern
│   ├── logger.py          <- Logging mit Sensitive-Data-Filter
│   ├── clipboard.py       <- Clipboard-Monitor + Hotkey
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── base.py        <- Abstrakte Backend-Klasse
│   │   ├── ollama.py      <- Ollama Backend (lokal)
│   │   ├── claude.py      <- Claude API Backend (API-Key)
│   │   └── claude_oauth.py <- Claude Abo Backend (OAuth direkt)
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py <- Hauptfenster (Sidebar + Content)
│       └── settings_dialog.py <- Einstellungen + Usage-HUD
├── assets/
│   ├── icon.ico
│   └── icon.png
├── docs/
│   └── claude-abo-setup.md
├── tools/
│   └── create_icon.py
├── build/
│   └── textgenius.spec
└── installer/
    └── setup.iss
```

---

## Coding-Regeln

### Grundprinzipien
- **Nie raten** -- Bei technischer Unsicherheit IMMER recherchieren. Erst verstehen, dann implementieren.
- **Lesbarer Code** -- Business-Logik, kein Maschinencode. Sprechende Namen, klare Struktur.
- **Kommentieren** -- Wichtige Abschnitte und Entscheidungen kommentieren. Nicht jede Zeile, aber jeden Block.
- **Kurze Dateien** -- Unter ~200 Zeilen halten. Bei Bedarf aufteilen.
- **Best Practices** -- Keine selbsterfundenen Patterns. Erst Docs lesen.
- **Logging** -- Immer mit Logs arbeiten damit man weiss wenn was nicht geht. Aber keine sensiblen Daten loggen (API-Keys, Tokens).

### Allgemein
- **Sprache im Code:** Englisch (Variablen, Funktionen, Kommentare)
- **Sprache in der UI:** Deutsch (Standard), wählbar DE/EN
- **Deutsche Umlaute PFLICHT** -- In allen UI-Texten, Fehlermeldungen und Statusmeldungen IMMER echte Umlaute verwenden: ä, ö, ü, ß. NIEMALS ae, oe, ue, ss als Ersatz. Beispiel: "Prüfen" nicht "Pruefen", "Größe" nicht "Groesse".
- **Python-Version:** 3.10+
- **Kein** `*`-Import -- immer explizit
- Jede Datei hat einen kurzen Docstring am Anfang

### Architektur
- Backends implementieren die abstrakte `BaseBackend`-Klasse
- Settings nur ueber `settings.py` lesen/schreiben
- KI-Aufrufe IMMER in einem Thread (nie den GUI-Thread blockieren)
- Thread-Kommunikation mit GUI ueber `self.after()` (CustomTkinter)

### Fehlerbehandlung
- Alle API-Aufrufe in `try/except` mit benutzerfreundlichen Meldungen
- Verbindungsfehler -> klare Meldung in der UI
- JSON-Parsing-Fehler -> Fallback mit Rohtext + Warnung
- Nie `print()` -> immer `logging`

### Logging
- Alle Module: `logging.getLogger(__name__)`
- Log-Datei: `%APPDATA%/TextGenius/textgenius.log`
- SensitiveDataFilter maskiert API-Keys automatisch (sk-**** etc.)
- Rotation: 5 MB, 3 Backups
- Timing-Logs bei allen Backend-Anfragen (Dauer, Zeichenlaenge)

### UI-Regeln (CustomTkinter)
- Layout mit `grid()` und `sticky="nsew"` fuer Responsiveness
- Sidebar mit fester Breite (200px), Content expandiert
- `CTkToplevel` fuer modale Dialoge (Settings)
- Dark/Light Mode ueber `ctk.set_appearance_mode()`

---

## KI-Prompt-Regeln
- Prompts zentralisiert in `checker.py`
- Sprache explizit im Prompt
- JSON-Ausgabe ohne Markdown-Wrapping gefordert
- Robustes Parsing: direkt -> Fence-Strip -> Rohtext-Fallback

---

## Claude OAuth (Abo-Backend)
- Token aus `~/.claude/.credentials.json` lesen
- Pflicht-Headers: `anthropic-beta: oauth-2025-04-20,claude-code-20250219`
- `User-Agent: claude-cli/2.1.75` + `x-app: cli`
- System-Prompt muss "You are Claude Code" enthalten
- Token-Refresh ueber `platform.claude.com/v1/oauth/token`
- Usage-Daten von `api.anthropic.com/api/oauth/usage`

---

## Build-Regeln
- PyInstaller: `--onefile --windowed --icon=assets/icon.ico`
- `.exe` in `dist/TextGenius.exe`
- Inno Setup Script mit Version aus `version.py`

---

## Versionierung
- Format: `MAJOR.MINOR.PATCH` (Start: `1.0.0`)
- **Single Source of Truth:** `version.py`
