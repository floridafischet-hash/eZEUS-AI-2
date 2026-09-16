# Rechnungsbetrag

## Standardfall

### Empfohlene Feldkonfiguration

- Feldname: `Rechnungsbetrag`
- Feldtyp: `Währung` (bzw. `Text`, falls Paperless-Feld nicht als Währung angelegt ist)
- Pflichtfeld: abhängig vom Kundenprozess
- OCR: aktiviert
- KI: bei uneindeutigen Layouts oder mehreren Summenblöcken zusätzlich aktiviert
- Auswahlstrategie: höchster plausibler Bruttobetrag (`selection_strategy: highest`)
- Validatoren: `not_empty`, `monetary_amount`

### Kopierfertiger Extraktionshinweis

> Lies ausschließlich den vom Rechnungsaussteller ausgewiesenen zu zahlenden
> Gesamtbetrag der Rechnung aus (Bruttobetrag inklusive Umsatzsteuer). Bevorzuge
> Werte unmittelbar hinter oder neben „Rechnungsbetrag“, „Gesamtbetrag“,
> „Gesamtsumme“, „Rechnungssumme“, „Endsumme“, „Endbetrag“, „Zahlbetrag“,
> „Zu zahlen“, „Total inkl. MwSt.“, „Brutto“, „Bruttobetrag“,
> „Brutto-Rechnungsbetrag“ oder „Total Amount“. Übernimm ausschließlich den
> Bruttowert; ignoriere Nettosumme, Zwischensumme, Steuerbetrag, Skonto,
> Rabatt, bereits gezahlte Beträge, Restbetrag, Guthaben, Einzelpositionen
> und Zahlungsbedingungen wie „innerhalb 14 Tagen“. Bei mehreren
> Bruttosummen (z. B. Zwischen- und Endsumme, mehrere Steuersätze) wähle
> den endgültigen, größten am Belegende ausgewiesenen zu zahlenden Betrag.
> Bei Gutschriften oder Storno den Betrag mit korrektem Vorzeichen zurückgeben.
> Übernimm den Wert exakt inklusive Dezimaltrennzeichen (Komma bei deutschen,
> Punkt bei englischen Belegen). Gib die Währung nur zurück, wenn das Feld
> als reines Zahlenfeld eingerichtet ist – sonst als kombinierten Text
> (z. B. `1.234,56 EUR`). Wenn kein eindeutiger Gesamt-Bruttobetrag vorhanden
> ist, gib keinen Wert zurück.

### Bekannte Bezeichnungen

- Rechnungsbetrag
- Brutto-Rechnungsbetrag
- Gesamtrechnungsbetrag
- Gesamtbetrag
- Gesamtbetrag brutto
- Gesamtsumme
- Rechnungssumme
- Rechnungswert (brutto)
- Bruttobetrag
- Brutto
- Endsumme
- Endsumme brutto
- Endbetrag
- Zahlbetrag
- Zu zahlen / Zu zahlender Betrag
- Total / Total inkl. MwSt. / Total EUR inkl. MwSt.
- Total Amount / Amount Due / Grand Total / Invoice Total

### Bereinigung und Validierung

- Führende und abschließende Leerzeichen entfernen.
- Tausendertrennzeichen erhalten (`1.234,56` bzw. `1,234.56`).
- Dezimaltrennzeichen nicht vertauschen; deutsche Belege: Komma als Dezimal-,
  Punkt als Tausendertrennzeichen.
- Immer zwei Nachkommastellen erwarten; abweichende Formate melden.
- Währungssymbole (`€`, `EUR`, `CHF`, `USD`) entweder konsistent mitspeichern
  oder konsequent entfernen – abhängig von der Feldkonfiguration.
- Bei Gutschriften Vorzeichen (`-`) übernehmen.
- Wert muss im Dokumenttext vorkommen und darf keine reine Positionssumme sein.

### Typische Verwechslungen

- Nettobetrag / Zwischensumme / Summe netto
- Umsatzsteuerbetrag / MwSt.-Betrag / 19 % USt.
- Einzelpreis oder Positionssumme
- Rabatt-, Skonto- oder Bonusbetrag
- Bereits gezahlt / Anzahlung / Restbetrag / offener Betrag
- Vorjahres- oder Vergleichsbetrag
- IBAN, Kundennummer oder Rechnungsnummer mit langer Ziffernfolge
- Zahlungsziel („innerhalb 14 Tagen“, „2 % Skonto“)

## Positive Testfälle

| OCR-Text                                | Erwartetes Ergebnis |
| --------------------------------------- | ------------------- |
| `Gesamtbetrag brutto: 1.234,56 EUR`     | `1.234,56 EUR`      |
| `Total EUR inkl. MwSt. 89,90`           | `89,90 EUR`         |
| `Zu zahlen: € 42,00`                    | `42,00 EUR`         |
| `Rechnungsbetrag  2.500,00 €`           | `2.500,00 EUR`      |
| `Gutschrift Gesamtbetrag: -150,00 EUR`  | `-150,00 EUR`       |

## Negative Testfälle

| OCR-Text                          | Erwartetes Ergebnis |
| --------------------------------- | ------------------- |
| `Nettobetrag: 1.000,00 EUR`       | Kein Wert           |
| `MwSt. 19 %: 190,00 EUR`          | Kein Wert           |
| `Zwischensumme: 500,00 EUR`       | Kein Wert           |
| `Bereits gezahlt: 100,00 EUR`     | Kein Wert           |
| `2 % Skonto bei Zahlung in 14 T.` | Kein Wert           |

## Bekannte Grenzen

- Rechnungen mit mehreren Steuersätzen enthalten oft mehrere „Gesamt“-Zeilen.
  Nur die abschließende Endsumme ist der Rechnungsbetrag.
- Bei Sammelrechnungen kann pro Position ein „Gesamt“ ausgewiesen sein –
  hier zählt nur der Beleg-Endbetrag.
- Bei fremdsprachigen oder gemischten Belegen (EN/DE) müssen Bezeichnungen
  wie „Amount Due“, „Grand Total“ zusätzlich getroffen werden.
- Handschriftliche Ergänzungen (z. B. Kürzungen) werden nicht übernommen.

Für stark abweichende Lieferantenlayouts einen eigenen Eintrag in diesem Ordner
anlegen und die Dokumentbezeichnung im Dateinamen verwenden.
