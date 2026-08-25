# Fahrzeug-Identifizierungsnummer (FIN/VIN)

## Zweck

Die Fahrzeug-Identifizierungsnummer aus Feld `E` der deutschen
Zulassungsbescheinigung Teil I auslesen.

## Feldkonfiguration

- Paperless-Feldname: `Fahrzeug-ID`
- eZEUS-Feldtyp: `Text`
- Pflichtfeld: empfohlen
- OCR: aktiviert
- KI: aktiviert, solange keine kundenspezifische OCR-Regel konfigurierbar ist

## Kopierfertiger Extraktionshinweis

> Lies ausschließlich die Fahrzeug-Identifizierungsnummer (FIN/VIN) aus Feld E
> der Zulassungsbescheinigung Teil I aus. Die FIN besteht aus genau 17 Buchstaben
> und Ziffern. Übernimm sie vollständig und ohne Leerzeichen oder Trennzeichen.
> Verwechsle sie nicht mit Kennzeichen, Dokumentnummer, HSN oder TSN. Wenn der
> Wert nicht eindeutig lesbar ist oder nach der Bereinigung nicht genau 17
> Zeichen enthält, gib keinen Wert zurück.

## Vorgesehene OCR-Regel

Diese Regel ist dokumentiert, aber derzeit nicht automatisch aktiv:

```regex
(?im)^\s*E\s*[:.]?\s*((?:[A-HJ-NPR-Z0-9][ \t-]?){16}[A-HJ-NPR-Z0-9])(?:\s|$)
```

Sie erkennt die FIN auf derselben oder der folgenden OCR-Zeile und toleriert
Leerzeichen beziehungsweise Bindestriche innerhalb des Wertes.

## Bereinigung

1. Leerzeichen entfernen.
2. Bindestriche entfernen.
3. Buchstaben in Großbuchstaben umwandeln.

## Validierung

```regex
^[A-HJ-NPR-Z0-9]{17}$
```

- exakt 17 Zeichen
- nur Buchstaben und Ziffern
- `I`, `O` und `Q` sind ausgeschlossen

## Positive Testfälle

| OCR-Text | Erwartetes Ergebnis |
| --- | --- |
| `E` + Zeilenumbruch + `LGXCE4CB9P2209189` | `LGXCE4CB9P2209189` |
| `E: LGXCE4CB9P2209189` | `LGXCE4CB9P2209189` |
| `E` + Zeilenumbruch + `LGX CE4 CB9 P22 09189` | `LGXCE4CB9P2209189` |

## Negative Testfälle

| OCR-Text | Erwartetes Ergebnis |
| --- | --- |
| nur 16 Zeichen hinter Feld E | Kein Wert |
| 18 Zeichen hinter Feld E | Kein Wert |
| Wert enthält `I`, `O` oder `Q` | Kein Wert beziehungsweise manuelle Prüfung |
| 17 Zeichen bei Kennzeichen oder Dokumentnummer | Kein Wert |

## Aktuelle technische Grenze

eZEUS speichert derzeit Extraktionshinweise pro Kundeninstanz, aber keine frei
konfigurierbaren OCR- und Validierungsregeln. Bis diese Funktion existiert, dient
die Regel als getestete Spezifikation und der KI-Hinweis als Übergangslösung.

## Änderungsverlauf

- 2026-08-25: Erster Eintrag mit OCR-Regel, Bereinigung und Testfällen angelegt.

