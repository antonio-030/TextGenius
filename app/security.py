"""Sicherheitsmaßnahmen für Windows: DLL-Härtung + Integritätsprüfung.

Muss als ERSTES importiert werden in main.py, bevor andere Module geladen werden.
"""

import ctypes
import hashlib
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Windows Konstanten für DLL-Suchpfad
_LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x00000800
_LOAD_LIBRARY_SEARCH_APPLICATION_DIR = 0x00000200


def harden_dll_search_order():
    """Schränkt den DLL-Suchpfad ein um DLL-Hijacking zu verhindern.

    Entfernt das aktuelle Arbeitsverzeichnis und PATH aus der DLL-Suche.
    Nur System32 und das Anwendungsverzeichnis werden durchsucht.
    """
    if sys.platform != "win32":
        return

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # DLL-Suche auf System32 + Anwendungsverzeichnis beschränken
        result = kernel32.SetDefaultDllDirectories(
            _LOAD_LIBRARY_SEARCH_SYSTEM32 | _LOAD_LIBRARY_SEARCH_APPLICATION_DIR
        )
        if not result:
            logger.warning("SetDefaultDllDirectories fehlgeschlagen (Code %d)",
                           ctypes.get_last_error())
            return

        # Bei PyInstaller-Bundle: _internal Verzeichnis explizit hinzufügen
        if getattr(sys, "frozen", False):
            internal_dir = os.path.join(sys._MEIPASS, "")
            kernel32.AddDllDirectory(internal_dir)

        logger.info("DLL-Suchpfad gehärtet")

    except Exception:
        logger.warning("DLL-Härtung nicht möglich", exc_info=True)


def verify_dll_integrity():
    """Prüft ob DLLs im Bundle manipuliert wurden (nur bei .exe).

    Vergleicht SHA-256 Hashes gegen ein Manifest das beim Build erstellt wurde.
    Gibt True zurück wenn alles OK oder kein Bundle.
    """
    if not getattr(sys, "frozen", False):
        return True  # Nur im Bundle relevant

    manifest_path = os.path.join(sys._MEIPASS, "dll_hashes.json")
    if not os.path.exists(manifest_path):
        return True  # Kein Manifest = Prüfung überspringen

    try:
        with open(manifest_path, "r") as f:
            expected = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("DLL-Manifest nicht lesbar")
        return True

    # Jede DLL gegen den erwarteten Hash prüfen
    tampered = []
    for rel_path, expected_hash in expected.items():
        filepath = os.path.join(sys._MEIPASS, rel_path)
        if not os.path.exists(filepath):
            tampered.append(f"FEHLT: {rel_path}")
            continue
        with open(filepath, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        if actual != expected_hash:
            tampered.append(f"GEÄNDERT: {rel_path}")

    if tampered:
        logger.critical("DLL-Integritätsprüfung FEHLGESCHLAGEN: %s", tampered)
        return False

    logger.info("DLL-Integrität OK (%d Dateien geprüft)", len(expected))
    return True
