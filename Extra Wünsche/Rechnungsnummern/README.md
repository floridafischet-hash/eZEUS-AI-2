# Rechnungsnummern

## Standardfall

### Empfohlene Feldkonfiguration

- Feldname: `Rechnungsnummer`
- Feldtyp: `Text`
- Pflichtfeld: abhängig vom Kundenprozess
- OCR: aktiviert
- KI: bei uneindeutigen Layouts zusätzlich aktiviert

### Kopierfertiger Extraktionshinweis

> Lies ausschließlich die vom Rechnungsaussteller vergebene Rechnungsnummer aus.
> Bevorzuge Werte unmittelbar hinter oder neben „Rechnungsnummer“, „Rechnungs-Nr.“,
> „Re.-Nr.“, „Belegnummer“ oder „Invoice Number“. Verwechsle sie nicht mit
> Kunden-, Auftrags-, Bestell-, Liefer-, Debitoren- oder Vertragsnummern. Übernimm
> Buchstaben, Ziffern und enthaltene Trennzeichen vollständig. Wenn keine
> eindeutige Rechnungsnummer vorhanden ist, gib keinen Wert zurück.

### Bekannte Bezeichnungen

- Rechnungsnummer
- Rechnungs-Nr.
- Re.-Nr.
- Belegnummer
- Invoice Number
- Invoice No.

### Bereinigung und Validierung

- Führende und abschließende Leerzeichen entfernen.
- Innere Bindestriche, Schrägstriche und Punkte nicht ungeprüft entfernen.
- Nicht allein aufgrund einer langen Ziffernfolge entscheiden.
- Nummer muss im Dokumenttext vorkommen.

### Typische Verwechslungen

- Kundennummer
- Bestellnummer
- Auftragsnummer
- Lieferscheinnummer
- Vertragsnummer
- IBAN oder Steuernummer

Für stark abweichende Lieferantenlayouts einen eigenen Eintrag in diesem Ordner
anlegen und die Dokumentbezeichnung im Dateinamen verwenden.

