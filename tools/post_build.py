"""Post-Build Script: Erstellt DLL-Hash-Manifest für Integritätsprüfung.

Ausführen nach PyInstaller Build:
  python tools/post_build.py
"""

import hashlib
import json
import os
import sys


def generate_dll_manifest(internal_dir: str) -> dict:
    """Erstellt SHA-256 Hashes aller DLL/PYD Dateien."""
    manifest = {}
    for root, _dirs, files in os.walk(internal_dir):
        for name in files:
            if name.lower().endswith((".dll", ".pyd")):
                filepath = os.path.join(root, name)
                rel_path = os.path.relpath(filepath, internal_dir)
                with open(filepath, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                manifest[rel_path] = file_hash
    return manifest


def main():
    internal_dir = os.path.join("dist", "TextGenius", "_internal")
    if not os.path.exists(internal_dir):
        print(f"FEHLER: {internal_dir} nicht gefunden. Erst PyInstaller ausführen.")
        sys.exit(1)

    manifest = generate_dll_manifest(internal_dir)
    output_path = os.path.join(internal_dir, "dll_hashes.json")

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"DLL-Manifest erstellt: {len(manifest)} Dateien -> {output_path}")


if __name__ == "__main__":
    main()
