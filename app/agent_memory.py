"""Agent-Gedächtnis: Lernt aus Korrekturen und merkt sich Nutzerpräferenzen.

Speichert Schreibstil, Glossar, Fehlerpatterns und Statistiken.
Alles in %APPDATA%/TextGenius/agent_memory.json.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_memory_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        d = Path(appdata) / "TextGenius"
    else:
        d = Path.home() / ".textgenius"
    d.mkdir(parents=True, exist_ok=True)
    return d / "agent_memory.json"


# Standard-Gedächtnis für neue Nutzer
_DEFAULT_MEMORY = {
    "style": "",
    "glossary": [],
    "weak_areas": [],
    "strong_areas": [],
    "show_reasoning": True,
    "corrections_accepted": 0,
    "corrections_rejected": 0,
    "total_checks": 0,
    "total_words": 0,
    "total_errors": 0,
    "patterns": [],
    "last_updated": "",
}


def load_memory() -> dict:
    """Lädt das Agent-Gedächtnis."""
    path = _get_memory_path()
    memory = dict(_DEFAULT_MEMORY)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Nur bekannte Keys übernehmen
            for key in _DEFAULT_MEMORY:
                if key in saved:
                    memory[key] = saved[key]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Agent-Gedächtnis nicht lesbar: %s", e)
    return memory


def save_memory(memory: dict) -> None:
    """Speichert das Agent-Gedächtnis."""
    path = _get_memory_path()
    memory["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Agent-Gedächtnis speichern fehlgeschlagen: %s", e)


def clear_memory() -> None:
    """Setzt das Gedächtnis komplett zurück."""
    save_memory(dict(_DEFAULT_MEMORY))
    logger.info("Agent-Gedächtnis zurückgesetzt")


# ── Lernfunktionen ────────────────────────────────────────────

def learn_from_check(errors: list[dict], word_count: int) -> dict:
    """Lernt aus einer Textprüfung. Gibt das aktualisierte Gedächtnis zurück."""
    memory = load_memory()

    # Statistiken aktualisieren
    memory["total_checks"] += 1
    memory["total_words"] += word_count
    memory["total_errors"] += len(errors)

    # Fehlerpatterns zählen
    patterns = {p["pattern"]: p for p in memory.get("patterns", [])}
    for error in errors:
        error_type = error.get("type", "grammar")
        explanation = error.get("explanation", "")
        # Kurzes Pattern aus Typ + Erklärung
        pattern_key = f"{error_type}: {explanation[:60]}" if explanation else error_type

        if pattern_key in patterns:
            patterns[pattern_key]["count"] += 1
        else:
            patterns[pattern_key] = {
                "type": error_type,
                "pattern": pattern_key,
                "count": 1,
            }

    # Top-Patterns sortiert speichern (max 20)
    sorted_patterns = sorted(patterns.values(), key=lambda p: p["count"], reverse=True)
    memory["patterns"] = sorted_patterns[:20]

    # Schwächen/Stärken alle 5 Prüfungen neu berechnen
    if memory["total_checks"] % 5 == 0:
        _recalculate_areas(memory)

    save_memory(memory)
    return memory


def record_acceptance(accepted: bool) -> None:
    """Merkt sich ob der User eine Korrektur akzeptiert oder abgelehnt hat."""
    memory = load_memory()
    if accepted:
        memory["corrections_accepted"] += 1
    else:
        memory["corrections_rejected"] += 1
    save_memory(memory)


def add_to_glossary(word: str) -> None:
    """Fügt ein Wort zum Glossar hinzu (wird nie korrigiert)."""
    memory = load_memory()
    glossary = memory.get("glossary", [])
    if word not in glossary:
        glossary.append(word)
        memory["glossary"] = glossary
        save_memory(memory)
        logger.info("Glossar: '%s' hinzugefügt", word)


def remove_from_glossary(word: str) -> None:
    """Entfernt ein Wort aus dem Glossar."""
    memory = load_memory()
    glossary = memory.get("glossary", [])
    if word in glossary:
        glossary.remove(word)
        memory["glossary"] = glossary
        save_memory(memory)


def _recalculate_areas(memory: dict) -> None:
    """Berechnet Schwächen und Stärken aus den Fehlerpatterns."""
    patterns = memory.get("patterns", [])
    if not patterns:
        return

    # Schwächen: häufigste Patterns (top 3)
    weak = [p["pattern"] for p in patterns[:3] if p["count"] >= 2]
    memory["weak_areas"] = weak

    # Stärken: Fehlertypen die kaum vorkommen
    type_counts = {}
    for p in patterns:
        t = p.get("type", "grammar")
        type_counts[t] = type_counts.get(t, 0) + p["count"]

    all_types = {"spelling", "grammar", "style"}
    strong = [t for t in all_types if type_counts.get(t, 0) <= 1]
    memory["strong_areas"] = [
        {"spelling": "Rechtschreibung", "grammar": "Grammatik", "style": "Stil"}.get(t, t)
        for t in strong
    ]


def get_smart_tip(memory: dict) -> str:
    """Generiert einen smarten Tipp basierend auf den Patterns."""
    patterns = memory.get("patterns", [])
    total = memory.get("total_checks", 0)

    if total < 3:
        return ""

    if patterns:
        top = patterns[0]
        count = top["count"]
        pattern = top["pattern"]
        if count >= 3:
            return f"💡 Häufigster Fehler ({count}x): {pattern}"

    # Verbesserung erkennen
    if total >= 5:
        avg_errors = memory.get("total_errors", 0) / total
        if avg_errors < 1:
            return "🌟 Sehr gut! Durchschnittlich weniger als 1 Fehler pro Text."

    return ""


def get_glossary_suggestions(errors: list[dict]) -> list[str]:
    """Findet Wörter in den Fehlern die möglicherweise ins Glossar gehören.

    Erkennt Eigennamen und Fachbegriffe die fälschlicherweise korrigiert wurden.
    """
    memory = load_memory()
    glossary = set(memory.get("glossary", []))
    suggestions = []

    for error in errors:
        original = error.get("original", "")
        # Wörter die mit Großbuchstaben anfangen und nicht im Glossar sind
        if original and original[0].isupper() and original not in glossary:
            # Nur wenn es ein einzelnes Wort ist (kein Satz)
            if " " not in original and len(original) >= 3:
                suggestions.append(original)

    return list(set(suggestions))[:3]  # Max 3 Vorschläge
