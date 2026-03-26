"""Textvorlagen für häufige Schreibaufgaben."""

# Jede Vorlage: (name, icon, beschreibung, text)
TEMPLATES = [
    (
        "Geschäftliche E-Mail",
        "✉️",
        "Formelle E-Mail an Geschäftspartner",
        "Sehr geehrte Damen und Herren,\n\n"
        "ich wende mich an Sie bezüglich...\n\n"
        "Für Rückfragen stehe ich Ihnen gerne zur Verfügung.\n\n"
        "Mit freundlichen Grüßen\n"
        "[Name]",
    ),
    (
        "Bewerbungsanschreiben",
        "📄",
        "Anschreiben für eine Stellenbewerbung",
        "Sehr geehrte Frau / Sehr geehrter Herr [Name],\n\n"
        "mit großem Interesse habe ich Ihre Stellenanzeige für die Position als "
        "[Position] gelesen. Hiermit möchte ich mich bei Ihnen bewerben.\n\n"
        "Derzeit bin ich als [aktuelle Position] bei [Unternehmen] tätig und bringe "
        "[X] Jahre Erfahrung in [Bereich] mit.\n\n"
        "[Warum dieses Unternehmen? Was können Sie beitragen?]\n\n"
        "Über die Einladung zu einem persönlichen Gespräch würde ich mich sehr freuen.\n\n"
        "Mit freundlichen Grüßen\n"
        "[Name]",
    ),
    (
        "Beschwerde",
        "⚠️",
        "Formelle Beschwerde an ein Unternehmen",
        "Sehr geehrte Damen und Herren,\n\n"
        "am [Datum] habe ich [Produkt/Dienstleistung] bei Ihnen [gekauft/in Anspruch genommen].\n\n"
        "Leider muss ich Ihnen mitteilen, dass [Problem beschreiben].\n\n"
        "Ich bitte Sie daher um [Erstattung/Umtausch/Nachbesserung] bis zum [Frist].\n\n"
        "Sollte ich bis dahin keine Rückmeldung erhalten, sehe ich mich gezwungen, "
        "weitere Schritte einzuleiten.\n\n"
        "Mit freundlichen Grüßen\n"
        "[Name]\n\n"
        "Anlagen: [Rechnung, Fotos, etc.]",
    ),
    (
        "Angebot / Kostenvoranschlag",
        "💰",
        "Angebot an einen Kunden",
        "Sehr geehrte(r) [Name],\n\n"
        "vielen Dank für Ihre Anfrage vom [Datum]. Gerne unterbreite ich Ihnen "
        "folgendes Angebot:\n\n"
        "Leistung: [Beschreibung]\n"
        "Umfang: [Details]\n"
        "Preis: [Betrag] EUR (zzgl. MwSt.)\n"
        "Lieferzeit: [Zeitraum]\n\n"
        "Dieses Angebot ist gültig bis zum [Datum].\n\n"
        "Bei Fragen stehe ich Ihnen gerne zur Verfügung.\n\n"
        "Mit freundlichen Grüßen\n"
        "[Name]",
    ),
    (
        "Kündigung",
        "📋",
        "Kündigung eines Vertrags oder Abos",
        "Sehr geehrte Damen und Herren,\n\n"
        "hiermit kündige ich meinen Vertrag / mein Abonnement mit der "
        "Vertragsnummer [Nummer] fristgerecht zum nächstmöglichen Termin.\n\n"
        "Bitte bestätigen Sie mir den Eingang der Kündigung sowie das "
        "Datum der Vertragsbeendigung schriftlich.\n\n"
        "Mit freundlichen Grüßen\n"
        "[Name]\n"
        "[Adresse]\n"
        "[Kundennummer]",
    ),
    (
        "Meeting-Protokoll",
        "📝",
        "Vorlage für ein Besprechungsprotokoll",
        "# Meeting-Protokoll\n\n"
        "**Datum:** [Datum]\n"
        "**Teilnehmer:** [Namen]\n"
        "**Protokollführer:** [Name]\n\n"
        "## Tagesordnung\n"
        "1. [Thema 1]\n"
        "2. [Thema 2]\n"
        "3. [Thema 3]\n\n"
        "## Ergebnisse\n"
        "- [Ergebnis 1]\n"
        "- [Ergebnis 2]\n\n"
        "## Aufgaben\n"
        "- [ ] [Aufgabe] – verantwortlich: [Name] – bis: [Datum]\n"
        "- [ ] [Aufgabe] – verantwortlich: [Name] – bis: [Datum]\n\n"
        "## Nächster Termin\n"
        "[Datum und Uhrzeit]",
    ),
]
