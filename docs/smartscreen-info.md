# SmartScreen Warnung beim ersten Start

## Was passiert?

Beim ersten Start zeigt Windows diese Meldung:

> **Der Computer wurde durch Windows geschützt**
> Von Microsoft Defender SmartScreen wurde der Start einer unbekannten App verhindert.

## Warum?

Windows SmartScreen warnt bei **jeder neuen Software** die es noch nicht kennt – egal ob sicher oder nicht.
TextGenius ist neu und hat noch keine "Reputation" bei Microsoft aufgebaut.

**TextGenius ist sicher:**
- Der gesamte Quellcode ist öffentlich auf [GitHub](https://github.com/antonio-030/TextGenius)
- Keine Viren, keine Malware, kein Tracking
- Gebaut mit Python + CustomTkinter (Standard-Technologie)

## Was tun?

1. Klicke auf **"Weitere Informationen"**
2. Klicke auf **"Trotzdem ausführen"**
3. Die Warnung erscheint nur **beim allerersten Start**

## Für Entwickler

Die exe wird mit PyInstaller im `--onedir` Modus gebaut (kein UPX, keine Komprimierung)
um Antivirus-False-Positives zu minimieren. DLL-Integrität wird beim Start per SHA-256
Hash-Manifest geprüft.

Code Signing mit einem vertrauenswürdigen Zertifikat ist in Arbeit (SignPath.io OSS-Programm).
