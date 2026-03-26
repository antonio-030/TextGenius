# TextGenius

KI-gestuetzter Rechtschreib- und Grammatikpruefer fuer Windows.

## Features

- **Text pruefen** -- Rechtschreibung, Grammatik und Stil
- **3 KI-Backends** -- Ollama (lokal/kostenlos), Claude API (API-Key), Claude Abo (Pro/Max Login)
- **Hotkey** -- `Ctrl+Shift+P` prueft den Text aus der Zwischenablage
- **Fehler markieren** -- Fehler werden direkt im Editor farblich hervorgehoben
- **Dark/Light Mode** -- Umschaltbar in der Sidebar
- **Schnell** -- ~3s Antwortzeit mit Claude Abo

## Installation

### Option 1: Installer
1. Lade `TextGenius-Setup-1.0.0.exe` herunter
2. Installiere und starte

### Option 2: Aus dem Quellcode
```bash
pip install -r requirements.txt
python main.py
```

## Backend einrichten

### Ollama (kostenlos, lokal)
1. Installiere [Ollama](https://ollama.ai)
2. Lade ein Modell: `ollama pull llama3.1`
3. In TextGenius Einstellungen: Backend = `ollama`

### Claude Abo (Pro/Max)
1. Installiere [Claude CLI](https://claude.ai/download)
2. In TextGenius Einstellungen: Backend = `claude_abo`
3. Klicke auf "Mit claude.ai einloggen"
4. Fertig -- kein API-Key noetig

Mehr Details: [docs/claude-abo-setup.md](docs/claude-abo-setup.md)

### Claude API (API-Key)
1. Hole einen API-Key von [console.anthropic.com](https://console.anthropic.com)
2. In TextGenius Einstellungen: Backend = `claude_api`, Key eingeben

## Tastenkuerzel

| Kuerzel | Aktion |
|---------|--------|
| `Ctrl+Shift+P` | Zwischenablage pruefen (global) |

## Technologie

- Python 3.10+ mit CustomTkinter
- Anthropic SDK fuer Claude API
- OAuth-Token fuer Claude Abo (direkte API-Anbindung, kein Proxy)
- pynput fuer globale Hotkeys

## Lizenz

MIT
