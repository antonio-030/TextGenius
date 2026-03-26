"""Text checking logic with centralized prompts and robust JSON parsing."""

import json
import logging
import re
import time
from typing import Any

from app.backends.base import BaseBackend

logger = logging.getLogger(__name__)

# Supported languages for prompts
LANGUAGES = {
    "de": "Deutsch",
    "en": "Englisch",
    "de+en": "Deutsch und Englisch (gemischt)",
}

PROMPT_TEMPLATE = """Du bist ein professioneller Lektor und Korrekturleser.
Prüfe den folgenden Text auf Rechtschreibung, Grammatik und Stil.
Die Sprache des Textes ist: {language}.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt (KEIN Markdown, KEINE Code-Fences).
Das JSON muss exakt dieses Format haben:
{{
  "corrected_text": "Der vollständig korrigierte Text",
  "errors": [
    {{
      "original": "Das falsche Wort oder die falsche Passage",
      "suggestion": "Die Korrektur",
      "type": "spelling|grammar|style",
      "explanation": "Kurze Erklärung des Fehlers"
    }}
  ],
  "summary": "Kurze Zusammenfassung der gefundenen Fehler"
}}

Falls keine Fehler gefunden werden, gib ein leeres errors-Array zurück und
setze corrected_text auf den Originaltext.

Hier ist der zu prüfende Text:

{text}"""


TRANSLATE_TEMPLATE = """Übersetze den folgenden Text nach {target}.
Erkenne die Ausgangssprache automatisch.
Gib NUR die Übersetzung zurück, keine Erklärungen.

{text}"""

CHAT_TEMPLATE = """Du bist ein hilfreicher Schreibassistent.
Der Nutzer arbeitet an folgendem Text:

---
{context}
---

Beantworte die Frage des Nutzers kurz und hilfreich.
Nutzer: {question}"""


def build_prompt(text: str, language: str = "de") -> str:
    """Build the full prompt for the KI backend."""
    lang_name = LANGUAGES.get(language, "Deutsch")
    return PROMPT_TEMPLATE.format(language=lang_name, text=text)


def build_translate_prompt(text: str, target_language: str = "Englisch") -> str:
    """Build a translation prompt with the target language."""
    return TRANSLATE_TEMPLATE.format(target=target_language, text=text)


def build_chat_prompt(question: str, context: str) -> str:
    """Build a chat prompt with the current editor text as context."""
    ctx = context.strip() if context.strip() else "(kein Text eingegeben)"
    return CHAT_TEMPLATE.format(context=ctx, question=question)


# ── KI-Tools Prompts ──────────────────────────────────────────

TONE_TEMPLATE = """Schreibe den folgenden Text um im Ton: {tone}.
Behalte den Inhalt und die Bedeutung bei, ändere nur den Stil/Ton.
Gib NUR den umgeschriebenen Text zurück.

{text}"""

SHORTEN_TEMPLATE = """Kürze den folgenden Text auf die Kernaussagen.
Behalte die wichtigsten Informationen, entferne Füllwörter und Wiederholungen.
Gib NUR den gekürzten Text zurück.

{text}"""

EXPAND_TEMPLATE = """Erweitere den folgenden Text zu einem ausführlichen Fließtext.
Füge Details, Erklärungen und Übergänge hinzu.
Behalte den Inhalt und Ton bei.
Gib NUR den erweiterten Text zurück.

{text}"""

REPHRASE_TEMPLATE = """Formuliere den folgenden Text komplett um.
Gleicher Inhalt, aber andere Worte und Satzstrukturen.
Gib NUR den umformulierten Text zurück.

{text}"""

EMAIL_TEMPLATE = """Schreibe eine professionelle Antwort-Email basierend auf dem folgenden Kontext.
Ton: höflich, professionell, auf den Punkt.
Gib NUR die Email zurück (mit Anrede und Grußformel).

Kontext:
{text}"""

ANALYZE_TEMPLATE = """Analysiere den folgenden Text und gib eine strukturierte Bewertung als JSON zurück.
Antworte NUR mit JSON, kein Markdown.

{{
  "wortanzahl": <Anzahl Wörter>,
  "satzanzahl": <Anzahl Sätze>,
  "durchschnittliche_satzlaenge": <Wörter pro Satz>,
  "lesezeit_minuten": <geschätzte Lesezeit>,
  "lesbarkeit": "leicht|mittel|schwer",
  "tonalitaet": "<z.B. formell, neutral, locker, emotional>",
  "verbesserungsvorschlaege": ["<Vorschlag 1>", "<Vorschlag 2>"]
}}

Text:
{text}"""


# Verfügbare Ton-Optionen
TONE_OPTIONS = [
    "Formell / Geschäftlich",
    "Locker / Umgangssprachlich",
    "Professionell / Sachlich",
    "Freundlich / Warm",
    "Akademisch / Wissenschaftlich",
    "Überzeugend / Werblich",
    "Diplomatisch / Vorsichtig",
]


def build_tone_prompt(text: str, tone: str) -> str:
    return TONE_TEMPLATE.format(tone=tone, text=text)


def build_shorten_prompt(text: str) -> str:
    return SHORTEN_TEMPLATE.format(text=text)


def build_expand_prompt(text: str) -> str:
    return EXPAND_TEMPLATE.format(text=text)


def build_rephrase_prompt(text: str) -> str:
    return REPHRASE_TEMPLATE.format(text=text)


def build_email_prompt(text: str) -> str:
    return EMAIL_TEMPLATE.format(text=text)


def build_analyze_prompt(text: str) -> str:
    return ANALYZE_TEMPLATE.format(text=text)


def parse_response(raw: str) -> dict[str, Any]:
    """Parse the KI response into a structured result dict.

    Tries multiple strategies:
    1. Direct JSON parse
    2. Strip markdown code fences and retry
    3. Fallback with raw text and warning
    """
    # Strategy 1: Direct parse
    try:
        result = json.loads(raw.strip())
        logger.debug("JSON parsed directly")
        return _validate_result(result)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown code fences
    stripped = _strip_code_fences(raw)
    if stripped != raw:
        try:
            result = json.loads(stripped.strip())
            logger.debug("JSON parsed after stripping code fences")
            return _validate_result(result)
        except json.JSONDecodeError:
            pass

    # Strategy 3: Fallback
    logger.warning("Could not parse KI response as JSON, using raw text fallback")
    return {
        "corrected_text": raw,
        "errors": [],
        "summary": "Hinweis: Die KI-Antwort konnte nicht als JSON verarbeitet werden. "
                   "Der Rohtext wird angezeigt.",
        "_parse_warning": True,
    }


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from text."""
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def _validate_result(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure required keys exist in the result."""
    result = {
        "corrected_text": data.get("corrected_text", ""),
        "errors": data.get("errors", []),
        "summary": data.get("summary", ""),
    }
    # Validate each error entry
    valid_errors = []
    for error in result["errors"]:
        if isinstance(error, dict) and "original" in error and "suggestion" in error:
            valid_errors.append({
                "original": error.get("original", ""),
                "suggestion": error.get("suggestion", ""),
                "type": error.get("type", "grammar"),
                "explanation": error.get("explanation", ""),
            })
    result["errors"] = valid_errors
    return result


def check_text(backend: BaseBackend, text: str, language: str = "de") -> dict[str, Any]:
    """Run a full text check using the given backend."""
    backend_name = type(backend).__name__
    text_len = len(text)
    logger.info(
        "Starte Pruefung: backend=%s, sprache=%s, textlaenge=%d zeichen",
        backend_name, language, text_len,
    )

    # Build prompt
    t0 = time.time()
    prompt = build_prompt(text, language)
    prompt_len = len(prompt)
    logger.info("Prompt erstellt: %d zeichen (%.1fms)", prompt_len, (time.time() - t0) * 1000)

    # Send to backend
    t1 = time.time()
    raw_response = backend.check_text(prompt)
    api_duration = time.time() - t1
    response_len = len(raw_response)
    logger.info(
        "Backend-Antwort erhalten: %d zeichen in %.1fs",
        response_len, api_duration,
    )

    # Parse response
    t2 = time.time()
    result = parse_response(raw_response)
    error_count = len(result.get("errors", []))
    logger.info(
        "Ergebnis: %d fehler gefunden, parsing %.1fms, gesamt %.1fs",
        error_count, (time.time() - t2) * 1000, time.time() - t0,
    )

    return result
