# TextGenius

KI-gestützter Rechtschreib- und Grammatikprüfer für Windows.

Ein kostenloses Produkt von [techlogia.de](https://techlogia.de)

## Features

- ✔ **Text prüfen** – Rechtschreibung, Grammatik und Stil
- 💬 **Chat-Assistent** – KI-Fragen zum Text mit Streaming-Antworten
- 📋 **Planer** – Projekte planen im Interview-Modus
- 🔧 **KI-Werkzeuge** – Ton anpassen, Kürzen, Erweitern, Umformulieren, E-Mail, Analyse
- 🌐 **Übersetzer** – 15 Sprachen mit automatischer Erkennung
- 🧠 **Agent** – Lernt aus deinen Fehlern und passt sich an
- 📊 **Live-Statistik** – Wörter, Zeichen, Lesezeit beim Tippen
- 💾 **Auto-Speichern** – Text wird automatisch gesichert
- 🔄 **Auto-Update** – Prüft automatisch auf neue Versionen

## Download

**[TextGenius-Setup-2.0.0.exe herunterladen](https://github.com/antonio-030/TextGenius/releases/latest)**

> **Hinweis:** Beim ersten Start zeigt Windows SmartScreen "Unbekannte App".
> Das ist normal bei neuer Software und passiert nur einmal.
> Klicke auf **"Weitere Informationen"** → **"Trotzdem ausführen"**.
> TextGenius ist Open Source – du kannst den gesamten Quellcode hier einsehen.

### Aus dem Quellcode
```bash
pip install -r requirements.txt
python main.py
```

## Backends

| Backend | Kosten | Geschwindigkeit |
|---------|--------|----------------|
| **Ollama** (lokal) | Kostenlos | ~5s |
| **Claude Abo** (Pro/Max) | Abo ~20€/Mo | ~3s |
| **Claude API** (API-Key) | ~Cent/Anfrage | ~3s |

### Ollama einrichten
1. [Ollama installieren](https://ollama.ai)
2. `ollama pull llama3.1`
3. In TextGenius: Backend = `ollama`

### Claude Abo einrichten
1. [Claude CLI installieren](https://claude.ai/download)
2. Backend = `claude_abo` → "Mit claude.ai einloggen"
3. Fertig – kein API-Key nötig

[Ausführliche Anleitung](docs/claude-abo-setup.md)

## Tastenkürzel

| Kürzel | Aktion |
|--------|--------|
| `Ctrl+Enter` | Text prüfen |
| `Ctrl+Shift+P` | Zwischenablage prüfen (global) |
| `Ctrl+T` | Übersetzen |
| `Ctrl+K` | Kürzen |
| `Ctrl+E` | Erweitern |

## Technologie

- Python 3.12 + CustomTkinter
- Anthropic SDK / OAuth für Claude
- DLL-Härtung + Certificate Pinning
- DPAPI-Verschlüsselung für API-Keys
- Globaler Crash-Handler mit Fehlerbericht

## Lizenz

MIT – © 2026 [techlogia](https://techlogia.de)
