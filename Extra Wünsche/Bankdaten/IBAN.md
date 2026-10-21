# IBAN des Rechnungsstellers

## Zweck

Die IBAN des Rechnungsstellers beziehungsweise Zahlungsempfängers aus Rechnungen
und Gutschriften lesen. Konten des Kunden oder Zahlers werden nicht übernommen.

## Feldkonfiguration

- Paperless-Feldname: `IBAN`
- eZEUS-Feldtyp: `Text`
- Pflichtfeld: Nein, nur bei fachlicher Notwendigkeit aktivieren
- OCR: Ja
- KI: optional als Fallback
- Spezialregel: `IBAN`

## Kopierfertiger Extraktionshinweis

> Lies ausschließlich die IBAN des Rechnungsstellers beziehungsweise
> Zahlungsempfängers aus. Bevorzuge einen eindeutig beschrifteten Bankblock mit
> „IBAN“, „IBAN-Nr.“, „IBAN/BIC“, „Kontonummer (IBAN)“ oder „Bankverbindung“.
> Entferne Leerzeichen und gib Buchstaben großgeschrieben zurück. Die IBAN muss
> mit einem zweibuchstabigen Ländercode und zwei Prüfziffern beginnen und die
> MOD-97-10-Prüfung bestehen. Übernimm niemals BIC, SWIFT-Code oder Bankname als
> Teil der IBAN. Ignoriere Konten des Zahlers in Zusammenhängen wie
> „Lastschrift“, „abgebucht“, „von Ihrem Konto“ oder „Mandat“. Wenn keine
> eindeutige gültige Empfänger-IBAN vorhanden ist oder mehrere verschiedene
> gültige Empfänger-IBANs gleichwertig bleiben, gib keinen Wert zurück.

## Bekannte Bezeichnungen

- `IBAN`, `IBAN:`, `IBAN-Nr.`
- `IBAN/BIC`
- `Kontonummer (IBAN)`
- `Bankverbindung`, `Kontoverbindung`

## Bereinigung

- Leerzeichen: alle normalen und geschützten Leerzeichen entfernen
- Trennzeichen: keine Trennzeichen im gespeicherten Wert
- Groß-/Kleinschreibung: in Großbuchstaben umwandeln
- Datums-/Zahlenformat: nicht anwendbar

## Validierung

- Länge: allgemein 15 bis 34 Zeichen; zusätzlich DE 22, AT 20, CH/LI 21,
  NL 18 und GB 22 Zeichen
- erlaubte Zeichen: `^[A-Z]{2}\d{2}[A-Z0-9]+$`
- Wertebereich: Prüfziffer nach ISO 7064 MOD 97-10 muss gültig sein
- Ausschlussregeln: BIC/Bankname abschneiden; Zahlerkontexte und mehrdeutige
  unterschiedliche gültige IBANs nicht übernehmen

Grundlage sind ISO 13616 (Aufbau), ISO 7064 MOD 97-10 (Prüfziffer),
ISO 3166-1 alpha-2 (Ländercode) und ISO 9362 (BIC mit 8 oder 11 Zeichen).
Quelle der verwendeten Längen ist die von SWIFT als ISO-Registrierungsstelle
veröffentlichte [IBAN Registry](https://www.swift.com/standards/standards-resources),
**Release 103, Stand 17. September 2026**. Das
Profil prüft nur die oben aufgeführten, durch die Anforderung und öffentliche
Beispiele belegten Länder längenspezifisch; andere Ländercodes erhalten weiter
nur Format-, Gesamtlängen- und Prüfzifferprüfung.

## Positive Testfälle

| OCR-Text | Erwartetes Ergebnis |
| --- | --- |
| `IBAN: DE89 3704 0044 0532 0130 00` | `DE89370400440532013000` |
| `IBAN-Nr. AT61 1904 3002 3457 3201` | `AT611904300234573201` |
| `IBAN/BIC \| CH93 0076 2011 6238 5295 7 \| POFICHBEXXX` | `CH9300762011623852957` |
| `Kontonummer (IBAN): NL91 ABNA 0417 1643 00` | `NL91ABNA0417164300` |
| `IBAN: gb82 west 1234 5698 7654 32` | `GB82WEST12345698765432` |

## Negative Testfälle

| OCR-Text | Erwartetes Ergebnis |
| --- | --- |
| `IBAN: DE90 3704 0044 0532 0130 00` | Kein Wert, Prüfziffer falsch |
| `IBAN:` | Kein Wert |
| `Kontonummer: 370400440532013000` | Kein Wert |
| `Lastschrift von Ihrem Konto, IBAN: DE89 ...` | Kein Wert |
| zwei verschiedene gültige Empfänger-IBANs | Kein Wert, mehrdeutig |

## Bekannte Grenzen

- Eine unbeschriftete IBAN wird nur direkt nach einem eindeutig benannten
  Bankverbindungsblock erkannt.
- Zahlerkontexte werden in derselben oder unmittelbar vorherigen OCR-Zeile
  ausgeschlossen. Weit entfernte oder semantisch ungewöhnliche Hinweise können
  nur durch den optionalen KI-Fallback beurteilt werden.
- Für nicht aufgeführte Länder wird keine nationale BBAN-Struktur geprüft.

## Kundeneinsatz

- Kunde/Instanz: bei Aktivierung eintragen
- Paperless-Feld-ID: bei Aktivierung prüfen und eintragen
- Eingeführt am: bei Aktivierung eintragen
- Getestete Dokument-ID: nur interne Referenz, keine Dokumentinhalte eintragen

Keine Zugangsdaten, Tokens, Webhook-Secrets oder personenbezogenen Dokumentinhalte
in dieser Bibliothek speichern.

## Änderungsverlauf

- 2026-10-21: Opt-in-Profil, Validierung, Ausschlussregeln und Tests angelegt.
