# TextGenius mit Claude Abo nutzen

Mit einem Claude Pro oder Max Abo kannst du TextGenius nutzen **ohne API-Key** und **ohne extra Kosten** pro Anfrage. Die Verbindung laeuft direkt ueber dein bestehendes claude.ai Konto.

---

## Voraussetzungen

- **Claude Pro oder Max Abo** auf [claude.ai](https://claude.ai)
- **Claude CLI** installiert (wird beim ersten Einloggen benoetigt)

---

## Einrichtung (einmalig)

### 1. Claude CLI installieren

Falls noch nicht installiert, lade die Claude CLI herunter:

- **Windows:** [claude.ai/download](https://claude.ai/download)
- **Oder via npm:** `npm install -g @anthropic-ai/claude-code`

### 2. In TextGenius einloggen

1. Starte TextGenius
2. Klicke auf **Einstellungen** (unten in der Seitenleiste)
3. Waehle als Backend: **claude_abo**
4. Klicke auf **"Mit claude.ai einloggen"**
5. Ein Browser-Fenster oeffnet sich -- logge dich mit deinem claude.ai Konto ein
6. Nach erfolgreichem Login zeigt TextGenius: **"Eingeloggt (deine@email.com, max)"**

Das wars. Du musst dich nur **einmal** einloggen. Der Login bleibt gespeichert.

---

## Benutzung

Nach dem Login einfach:

1. Text eingeben oder einfuegen
2. Auf **"Text pruefen"** klicken
3. Ergebnis erscheint in ~2-4 Sekunden

TextGenius nutzt dein Abo direkt -- keine extra Kosten, kein API-Key, kein Proxy.

---

## Modelle

In den Einstellungen kannst du das Modell waehlen:

| Modell | Beschreibung |
|--------|-------------|
| `claude-sonnet-4-20250514` | Schnell und praezise (empfohlen) |
| `claude-haiku-4-5-20251001` | Am schnellsten, fuer kurze Texte |

---

## Haeufige Fragen

### "Nicht eingeloggt" wird angezeigt

Die Claude CLI ist nicht installiert oder du hast dich noch nicht eingeloggt.

**Loesung:** Installiere die CLI und klicke in den Einstellungen auf "Mit claude.ai einloggen".

### "Token abgelaufen"

Der Login-Token ist abgelaufen (passiert nach einigen Stunden).

**Loesung:** Klicke erneut auf "Mit claude.ai einloggen". TextGenius versucht den Token automatisch zu erneuern -- falls das nicht klappt, einfach neu einloggen.

### "API-Fehler (401)"

Der Token ist ungueltig oder wurde widerrufen.

**Loesung:** Neu einloggen ueber die Einstellungen.

### "Rate-Limit erreicht"

Du hast das Nutzungslimit deines Abos erreicht.

**Loesung:** Kurz warten und es erneut versuchen. Claude Max hat hoehere Limits als Claude Pro.

---

## Technischer Hintergrund

TextGenius verbindet sich direkt mit der Anthropic API ueber OAuth-Token-Authentifizierung. Der Token wird lokal gespeichert unter:

```
~/.claude/.credentials.json
```

Es wird **kein Proxy** und **kein CLI-Subprocess** fuer Anfragen verwendet -- nur ein direkter HTTPS-Aufruf an `api.anthropic.com`. Dadurch sind Antworten genauso schnell wie bei der API-Key-Variante (~2-4 Sekunden).

### Sicherheit

- Der OAuth-Token verliert nie deinen PC
- API-Keys und Tokens werden **nie** in Logs geschrieben (automatisch maskiert)
- Die Credentials-Datei gehoert dem Claude CLI -- TextGenius liest sie nur
