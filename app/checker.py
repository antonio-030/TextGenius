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


def build_prompt(text: str, language: str = "de") -> str:
    """Build the full prompt for the KI backend."""
    lang_name = LANGUAGES.get(language, "Deutsch")
    return PROMPT_TEMPLATE.format(language=lang_name, text=text)


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
