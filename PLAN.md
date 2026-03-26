# PLAN.md – TextGenius Projektplan

## Vision
TextGenius ist ein KI-gestützter Rechtschreib- und Grammatikprüfer für Windows.
Der Nutzer kann Text eingeben oder aus der Zwischenablage einfügen, und die KI verbessert ihn.
Das KI-Backend ist frei wählbar: lokal (Ollama), OpenAI oder Claude.

---

## Phasen

### Phase 1 – Fundament (MVP)
**Ziel:** App läuft, Text kann geprüft werden

- [ ] Projektstruktur anlegen (Ordner, `__init__.py`)
- [ ] `version.py` – Zentrale Versionsverwaltung
- [ ] `logger.py` – Logging-Konfiguration (`logging`-Modul, Rotation)
- [ ] `settings.py` – Einstellungen laden/speichern (`%APPDATA%` mit Fallback)
- [ ] `BaseBackend` – Abstrakte Backend-Klasse
- [ ] `OllamaBackend` – Lokale KI (erster Backend)
- [ ] `checker.py` – Prompt-Logik + robustes JSON-Parsing (Markdown-Fence-Stripping, Fallback)
- [ ] `tooltip.py` – Tooltip-Hilfsklasse für Tkinter
- [ ] `themes.py` – Theme-Definitionen (Light Theme als Start)
- [ ] `main_window.py` – Hauptfenster mit Editor
- [ ] `result_panel.py` – Fehler-Liste + korrigierter Text
- [ ] `main.py` – App starten

**Ergebnis:** Man kann Text eingeben, auf "Prüfen" klicken und bekommt Korrekturen angezeigt.

---

### Phase 2 – Alle Backends
**Ziel:** OpenAI und Claude funktionieren

- [ ] `OpenAIBackend` – OpenAI API anbinden
- [ ] `ClaudeBackend` – Anthropic API anbinden
- [ ] `settings_dialog.py` – Einstellungs-Fenster (Backend auswählen, API-Keys eingeben)
- [ ] Backend-Wechsel zur Laufzeit möglich
- [ ] Verbindungstest-Button in den Einstellungen

**Ergebnis:** Alle 3 Backends funktionieren und sind über die UI konfigurierbar.

---

### Phase 3 – Clipboard & Komfort
**Ziel:** Clipboard-Monitoring und bessere UX

- [ ] `clipboard.py` – Clipboard-Monitor (automatisch prüfen)
- [ ] Hotkey: `Ctrl+Shift+P` → Clipboard direkt prüfen (via `pynput`, keine Admin-Rechte nötig)
- [ ] Fehler farblich im Editor markieren (rot unterstrichen)
- [ ] Tooltip bei Fehler-Hover (Erklärung) – nutzt `tooltip.py`
- [ ] Sprache wählbar (DE / EN / DE+EN)
- [ ] Copy-Button für korrigierten Text
- [ ] Undo/Redo im Editor

**⚠️ Bekanntes Risiko:** Global-Hotkey-Libraries können auf Windows Probleme machen.
`pynput` ist die empfohlene Wahl (kein Admin nötig). Falls Probleme: Hotkey nur im Fenster-Fokus.

**Ergebnis:** Flüssige, komfortable Nutzung mit allen Features.

---

### Phase 4 – Design & Polish
**Ziel:** Professionelle Optik, Dark Theme, App-Icon

- [ ] Farbpalette definieren (Light + Dark Theme) → `themes.py`
  - Skill-Tipp: **theme-factory** für professionelle Farbpaletten nutzen
- [ ] Dark Theme implementieren (Umschaltbar in Einstellungen)
- [ ] App-Icon erstellen (`icon.ico` + `icon.png`)
  - Skill-Tipp: **canvas-design** für ein hochwertiges Icon nutzen
- [ ] Mindestfenstergröße setzen (800x600)
- [ ] About-Dialog (Version aus `version.py`, Links)
- [ ] UI-Feinschliff: einheitliche Abstände, Farben, Schriftgrößen

**Ergebnis:** App sieht professionell aus mit Light/Dark Theme und eigenem Icon.

---

### Phase 5 – Build & Installer
**Ziel:** Fertige .exe und Installer

- [ ] `requirements.txt` finalisieren
- [ ] PyInstaller `.spec` Datei erstellen
- [ ] `TextGenius.exe` bauen
- [ ] Inno Setup Installer Script (`setup.iss`) – Version aus `version.py`
- [ ] Installer testen
- [ ] README.md schreiben

**Ergebnis:** Fertiger Installer den man an Windows-Nutzer weitergeben kann.

---

## Feature-Übersicht

| Feature                        | Phase | Status |
|-------------------------------|-------|--------|
| Text eingeben & prüfen        | 1     | ⏳     |
| Ollama Backend                | 1     | ⏳     |
| Korrekturvorschläge anzeigen  | 1     | ⏳     |
| Grammatikprüfung              | 1     | ⏳     |
| Robustes JSON-Parsing         | 1     | ⏳     |
| Logging-System                | 1     | ⏳     |
| OpenAI Backend                | 2     | ⏳     |
| Claude Backend                | 2     | ⏳     |
| Einstellungs-Dialog           | 2     | ⏳     |
| Clipboard-Monitor             | 3     | ⏳     |
| Hotkey Ctrl+Shift+P           | 3     | ⏳     |
| Fehler farblich markieren     | 3     | ⏳     |
| Mehrsprachig (DE/EN)          | 3     | ⏳     |
| Farbpalette (Light/Dark)      | 4     | ⏳     |
| Dunkles Theme                 | 4     | ⏳     |
| App-Icon Design               | 4     | ⏳     |
| .exe Build                    | 5     | ⏳     |
| Installer                     | 5     | ⏳     |

---

## Technische Entscheidungen

### Warum Tkinter?
- In Python eingebaut → keine Extra-Abhängigkeit für die GUI
- Funktioniert gut mit PyInstaller
- Ausreichend für dieses Projekt

### Warum JSON als KI-Antwort?
- Strukturierte Daten leicht zu parsen
- Fehler können einzeln in der UI angezeigt werden
- Backend-unabhängig (alle 3 liefern dasselbe Format)
- **Wichtig:** LLMs liefern nicht immer sauberes JSON → robustes Parsing nötig

### Warum `%APPDATA%/TextGenius/settings.json`?
- Standard-Pfad für User-Settings auf Windows
- Keine Admin-Rechte nötig
- Einfach zu sichern/migrieren
- Fallback auf `~/.textgenius/` für plattformübergreifende Kompatibilität

### Warum `pynput` statt `keyboard`?
- `keyboard` braucht oft Admin-Rechte auf Windows (Low-Level-Hook)
- `pynput` funktioniert ohne Admin-Rechte
- Falls Probleme: Hotkey nur bei Fenster-Fokus als Fallback

### Warum `version.py` als Single Source of Truth?
- Version wird an mehreren Stellen gebraucht: `main.py`, `setup.iss`, About-Dialog
- Eine zentrale Datei verhindert Inkonsistenzen
- PyInstaller und Inno Setup können den Wert auslesen

---

## Abhängigkeiten (requirements.txt)

```
requests>=2.31.0        # HTTP für Ollama & APIs
pyperclip>=1.8.2        # Clipboard lesen/schreiben
anthropic>=0.25.0       # Claude API
openai>=1.12.0          # OpenAI API
pynput>=1.7.6           # Hotkeys (Ctrl+Shift+P) – kein Admin nötig
Pillow>=10.0.0          # PNG-Icon in UI-Elementen anzeigen
pyinstaller>=6.0.0      # .exe bauen (dev only)
```

---

## Nächster Schritt
👉 **Phase 1 starten:** Projektstruktur anlegen und MVP bauen.
