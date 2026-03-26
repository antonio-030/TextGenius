# TextGenius -- Projektplan

> KI-gestuetzter Rechtschreib- und Grammatikpruefer fuer Windows
> Version: 1.0.0 | Python + CustomTkinter

---

## Vision

TextGenius prueft Texte auf Rechtschreib- und Grammatikfehler mithilfe von KI.
Der Nutzer waehlt sein bevorzugtes KI-Backend -- alles wird automatisch eingerichtet.

**Zielgruppe:** Windows-Nutzer die schnell Texte verbessern wollen -- ohne technisches Wissen.

---

## Backends

| Backend       | Methode                         | Kosten         | Key noetig? |
|---------------|----------------------------------|----------------|-------------|
| Ollama        | Laeuft lokal auf dem PC          | Kostenlos       | Nein        |
| Claude API    | Anthropic API-Key                | ~Cent/Nutzung   | API-Key     |
| Claude Abo    | Direkt ueber claude.ai Login     | Abo (~20/Mo)    | Nur Login   |

### Claude Abo -- So funktioniert es

TextGenius liest den OAuth-Token direkt aus `~/.claude/.credentials.json`
und ruft die Anthropic API direkt auf. Kein Proxy, kein CLI-Subprocess.

**Einmalig:** Claude CLI installieren + `claude auth login` im Browser.
Danach startet alles automatisch -- ~3s Antwortzeit.

---

## Projektstruktur

```
TextGenius/
├── CLAUDE.md                    <- Regeln fuer Claude Code
├── Abo_PLAN.md                  <- Dieser Plan
├── README.md                    <- Nutzerdokumentation
├── requirements.txt             <- Python-Abhaengigkeiten
├── version.py                   <- APP_VERSION + APP_NAME
├── main.py                      <- Einstiegspunkt
│
├── app/
│   ├── __init__.py
│   ├── checker.py               <- Prompt-Logik + JSON-Parsing
│   ├── settings.py              <- Einstellungen laden/speichern
│   ├── logger.py                <- Logging mit Sensitive-Data-Filter
│   ├── clipboard.py             <- Clipboard-Monitor + Hotkey
│   │
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── base.py              <- Abstrakte Backend-Klasse
│   │   ├── ollama.py            <- Ollama Backend (lokal)
│   │   ├── claude.py            <- Claude API Backend (API-Key)
│   │   └── claude_oauth.py      <- Claude Abo Backend (OAuth direkt)
│   │
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py       <- Hauptfenster (Sidebar + Editor + Ergebnis)
│       └── settings_dialog.py   <- Einstellungs-Dialog mit Usage-HUD
│
├── assets/
│   ├── icon.ico                 <- App-Icon (Windows)
│   └── icon.png                 <- App-Icon (PNG)
│
├── docs/
│   └── claude-abo-setup.md      <- Anleitung: Claude Abo einrichten
│
├── tools/
│   └── create_icon.py           <- Icon-Generator (Pillow)
│
├── build/
│   └── textgenius.spec          <- PyInstaller Spec-Datei
│
└── installer/
    └── setup.iss                <- Inno Setup Script
```

---

## Phasen

### Phase 1 -- MVP: Grundgeruest + Ollama ✅ FERTIG

- [x] Projektstruktur anlegen
- [x] `settings.py` -- Einstellungen laden/speichern
- [x] `base.py` -- Abstrakte Backend-Klasse
- [x] `ollama.py` -- Ollama Backend mit Modell-Erkennung
- [x] `checker.py` -- Prompt-Logik + robustes JSON-Parsing
- [x] `main_window.py` -- Hauptfenster mit Sidebar + Editor + Tabs
- [x] `main.py` -- App starten

---

### Phase 2 -- Backends + Einstellungen ✅ FERTIG

- [x] `claude.py` -- Claude API Backend (Anthropic SDK)
- [x] `claude_oauth.py` -- Claude Abo Backend (OAuth direkt, ~3s)
- [x] `settings_dialog.py` -- Einstellungs-Dialog
- [x] Backend-Wechsel zur Laufzeit
- [x] Verbindungstest-Button (Ollama)
- [x] Claude Login via Browser
- [x] Usage-HUD (5h/7d Nutzung + Reset-Timer)
- [x] Ollama Modelle automatisch erkennen

---

### Phase 3 -- Clipboard, Hotkeys & Fehler-Markierung

- [ ] `clipboard.py` -- Clipboard-Monitor
- [ ] Hotkey `Ctrl+Shift+P` -> Clipboard direkt pruefen
- [ ] Fehler im Editor farblich markieren
- [ ] Tooltip bei Hover ueber Fehler
- [ ] Sprache waehlbar: DE / EN / DE+EN
- [ ] Copy-Button fuer korrigierten Text ✅
- [ ] Undo/Redo im Editor ✅ (CTkTextbox)

---

### Phase 4 -- Polish, Build & Installer

- [ ] About-Dialog (Version, Links)
- [ ] App-Icon ✅
- [ ] Theme hell/dunkel ✅ (CustomTkinter)
- [ ] `requirements.txt` ✅
- [ ] PyInstaller `.spec` Datei
- [ ] `TextGenius.exe` bauen
- [ ] Inno Setup Script (`setup.iss`)
- [ ] `README.md` schreiben

---

## Technische Entscheidungen

### Warum CustomTkinter statt Tkinter?
CustomTkinter bietet moderne Widgets mit abgerundeten Ecken, automatischem DPI-Scaling
und Dark/Light Theme -- ohne manuelles CSS oder Canvas-Rendering.

### Warum OAuth direkt statt Proxy?
Der `claude-max-api-proxy` brauchte ~13s pro Anfrage (CLI-Subprocess-Overhead).
Durch direkten OAuth-API-Call (wie OpenClaw es macht) nur ~3s.
Entdeckt durch Analyse des pi-ai Quellcodes: `User-Agent: claude-cli`,
`anthropic-beta: oauth-2025-04-20`, System-Prompt "You are Claude Code".

### Warum kein OpenAI Backend?
Fokus auf Ollama (kostenlos/lokal) und Claude (Abo oder API-Key).
OpenAI kann bei Bedarf spaeter ergaenzt werden.
