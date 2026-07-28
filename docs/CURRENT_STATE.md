# Aktueller Projektstand

## Gültigkeit

Dieses Dokument beschreibt den verifizierten Stand vom 28. Juli 2026 auf dem
Branch `local/qwen3-ollama` bis einschließlich Commit `a375683`.

Der Stand dient als Ausgangsbasis für die weitere fachliche und technische
Ausarbeitung. Nicht in diesem Dokument beschriebene Funktionen gelten nicht als
zugesichert.

## Produktiver Betrieb

Die Anwendung läuft als Docker-Compose-Stack mit folgenden Diensten:

- FastAPI-Anwendung
- Celery-Worker
- PostgreSQL
- Redis
- Ollama

Der produktive Readiness-Endpunkt meldet Datenbank, Redis, Paperless, OCR und
Ollama als bereit. Ollama bleibt Bestandteil des Stacks, wird bei der
automatischen Feldzuordnung für verwaltete Paperless-Instanzen jedoch nicht
verwendet.

## Paperless-Instanzen

Mehrere Paperless-Instanzen können getrennt verwaltet werden. Pro Instanz werden
folgende Angaben gespeichert:

- Name
- Paperless-Basis-URL
- API-Token
- Webhook-Secret

API-Token und Webhook-Secret werden verschlüsselt in PostgreSQL gespeichert.
Dokumente, Ereignisse und Aufträge werden anhand der Instanzkennung getrennt.

Der öffentliche Webhook ist instanzbezogen oder kann die Instanz anhand eines
eindeutigen Webhook-Secrets bestimmen. Der Webhook akzeptiert ausschließlich
authentifizierte Anfragen.

## Verarbeitungsablauf

Der derzeitige Standardablauf für verwaltete Paperless-Instanzen ist:

1. Webhook authentifizieren und Instanz bestimmen.
2. Dokumentmetadaten und vorhandenen Inhalt über die Paperless-API laden.
3. Vorhandenen Paperless-OCR-Inhalt als primäre Textquelle verwenden.
4. Originaldownload und PaddleOCR überspringen, wenn Paperless bereits Inhalt
   bereitstellt.
5. Nur bei fehlendem Paperless-Inhalt das Original laden und PaddleOCR
   ausführen.
6. Custom Fields der jeweiligen Paperless-Instanz laden und anhand ihrer Namen
   zuordnen.
7. Werte mit deterministischen regulären Ausdrücken unmittelbar hinter
   bekannten Feldbezeichnungen suchen.
8. Kandidaten validieren und normalisieren.
9. Nur leere Paperless-Custom-Fields beschreiben.
10. Jeden Verarbeitungsschritt und jede Schreiboperation protokollieren.

Bei diesem Ablauf wird keine generative KI zur Bestimmung von Rechnungsnummern
oder Rechnungsbeträgen eingesetzt. Ein nicht eindeutig im Dokument vorhandener
Wert wird nicht geschrieben.

## Unterstützte automatische Felder

Die automatische Zuordnung erkennt derzeit Custom Fields mit diesen Namen:

- `Rechnungsnummer`
- `Rechnungsbetrag`
- `Lieferscheinnummer`

Für Rechnungsnummern werden unter anderem folgende Bezeichnungen erkannt:

- `Rechnungsnummer`
- `Rechnung-Nr.`
- `Rechnung Nr.`
- `Rechnungs-Nr.`
- `Rechnung <Kennung>`, wenn die Kennung mindestens eine Ziffer enthält
- `Bon-Nr.` für Kassenbelege

Für Brutto-Rechnungsbeträge werden folgende Bezeichnungen erkannt:

- `Brutto-Rechnungsbetrag`
- `Bruttobetrag`
- `Gesamtbetrag`
- `Gesamtbetrag brutto`
- `Gesamtsumme`
- `Endsumme brutto`
- `Rechnungswert (brutto)`
- `Zahlbetrag`
- `Endbetrag`
- `Zu zahlen`
- `Brutto`, wenn direkt anschließend ein Geldbetrag steht
- `Total` in eindeutig bezeichneten Kassenbeleg-Summenzeilen
- `Summe` zusammen mit einem Fälligkeitsdatum

Das Eurozeichen oder `EUR` darf vor oder hinter dem Betrag stehen.
Dezimalpunkt und Dezimalkomma sowie deutsche und englische
Tausendertrennzeichen werden unterstützt.
`Netto-Rechnungsbetrag` wird ausdrücklich nicht als Bruttobetrag übernommen.

Die Erkennung ist absichtlich konservativ. Noch nicht hinterlegte
Bezeichnungen führen zu einem fehlenden Feld und nicht zu einem geratenen Wert.

## Read-only-Regelaudit der Instanz Timo

Am 28. Juli 2026 wurden alle 16 vorhandenen Dokumente ausschließlich lesend
ausgewertet. Paperless-Dokumente, OCR-Inhalte und Custom Fields wurden dabei
nicht verändert.

Von 14 rechnungsartigen Dokumenten konnten nach der Regelerweiterung alle
Rechnungs- beziehungsweise Belegnummern und alle Bruttogesamtbeträge im
vorhandenen OCR-Text nachgewiesen werden. Neue Regressionstests decken die
gefundenen Formate ab. Das Audit erzeugt keine Regeln aus unbelegten Werten und
verwendet vorhandene Custom-Field-Werte nicht als alleinige Wahrheitsquelle.

## Validierung und Schreibschutz

- Geldbeträge werden in ein dezimales Speicherformat normalisiert.
- Mehrere voneinander abweichende gültige Kandidaten gelten als Konflikt.
- Konflikte werden nicht automatisch geschrieben.
- Bereits gefüllte Paperless-Felder werden nicht überschrieben.
- Eine eindeutig erkannte Rechnungsnummer wird zusätzlich als Dokumenttitel
  gesetzt. Ein bereits identischer Titel verursacht keine Schreiboperation.
- Ein Auftrag ist nur `COMPLETED`, wenn alle vorgesehenen Felder eindeutig
  erkannt wurden.
- Fehlende Felder führen zu `COMPLETED_WITH_WARNINGS`.
- Korrekturen und Schreiboperationen werden im Auditprotokoll erfasst.

## Protokollierung

Das Dashboard aktualisiert die Logs automatisch. Manuell aufgeklappte
Logeinträge bleiben dabei geöffnet.

Für den aktuellen Verarbeitungsversuch werden unter anderem angezeigt:

- Paperless-Instanz
- Dokument-ID und Dateiname
- Job-ID und Worker
- Versuchszahl
- Status und Laufzeit
- einzelne Phasen mit Startzeit und Dauer
- verwendete Textquelle
- Anzahl konfigurierter, gefundener und akzeptierter Felder
- fehlende Felder
- Anzahl geschriebener Felder
- technische Fehler

Frühere Phasen bleiben in PostgreSQL erhalten, werden in der normalen
Detailansicht aber nicht mit dem aktuellen Wiederholungsversuch vermischt.

## Verifizierte reale Dokumente

Sechs unterschiedliche Testrechnungen wurden nach der letzten Regelanpassung
erneut verarbeitet:

| Paperless-ID | Rechnungsnummer | Bruttobetrag | Laufzeit |
| --- | --- | ---: | ---: |
| 3472 | 5007 | 480.76 | 0,918 s |
| 3473 | 411 | 1614.83 | 1,219 s |
| 3474 | 19777 | 907.97 | 1,089 s |
| 3475 | 16849 | 342.48 | 1,145 s |
| 3476 | 1088 | 1070.99 | 0,613 s |
| 3477 | 1104 | 1233.88 | 0,556 s |

In allen sechs Fällen wurde vorhandener Paperless-Inhalt verwendet. Download,
PaddleOCR und Ollama wurden übersprungen. Rechnungsnummer und Bruttobetrag
wurden vollständig geschrieben oder als bereits korrekt vorhanden erkannt.

## Abgesicherte OCR-Nachbearbeitung

Wenn Paperless keinen Text bereitstellt, erzeugt PaddleOCR weiterhin den
maßgeblichen Rohtext. Optional bereinigt Qwen anschließend ausschließlich
Darstellungsfehler wie Worttrennungen, Leerzeichen, Zeilenumbrüche und
offensichtliche Buchstabenfehler.

Zahlenhaltige Werte, darunter Beträge, Datumswerte, Rechnungsnummern und IBANs,
müssen im Qwen-Vorschlag exakt und in gleicher Anzahl vorkommen. Entfernt,
verändert oder ergänzt Qwen einen solchen Wert, wird der vollständige Vorschlag
verworfen und der PaddleOCR-Rohtext nach Paperless geschrieben. Auch technische
Fehler und Zeitüberschreitungen führen ohne Jobabbruch zum Rohtext-Fallback.

Rohtext, Qwen-Vorschlag, Annahmestatus und Ablehnungsgrund werden getrennt in
`ocr_artifacts` gespeichert. Die Feldextraktion verwendet unabhängig vom
Annahmestatus immer den unveränderten PaddleOCR-Rohtext. Qwen bestimmt daher
keine Rechnungsbeträge oder anderen fachlichen Feldwerte.

## Mehrseitige Rechnungen

Die automatische Extraktion sammelt alle eindeutig als Brutto-, Gesamt-,
End- oder Zahlbetrag bezeichneten Summen aus dem vollständigen Dokumenttext
und damit aus allen Seiten. Nach Validierung und Normalisierung wird der
höchste dieser Summenkandidaten als Rechnungsbetrag übernommen.

Netto-, Steuer-, Positions- und unbeschriftete Beträge werden dadurch nicht
automatisch zu Gesamtsummen. Alle gefundenen Gesamtsummenkandidaten bleiben im
Extraktionsprotokoll erhalten; niedrigere Kandidaten werden mit einem
nachvollziehbaren Ablehnungsgrund markiert.

Für das Zielfeld `Rechnungsnummer` gilt folgende verbindliche Priorität:

1. Eine ausdrücklich bezeichnete Rechnungsnummer, beispielsweise
   `Rechnungsnummer` oder `Rechnung-Nr.`
2. Falls keine Rechnungsnummer erkannt wird, eine ausdrücklich bezeichnete
   BV- oder Baustellennummer

Eine BV- oder Baustellennummer wird nur akzeptiert, wenn sie genau fünfstellig
ist und mit `24`, `25` oder `26` beginnt. `Kundennummer` und `Kunden-Nr.` sind
als Ersatzwerte vollständig ausgeschlossen. Fehlen Rechnungsnummer und gültige
BV-/Baustellennummer, bleibt das Zielfeld leer und der Job meldet eine Warnung.

Der zusammengefallene OCR-Spaltenaufbau
`Datum: Rechnungsnr.: Kunden-Nr.:` wird gesondert ausgewertet. Dabei wird der
Wert unter `Rechnungsnr.` übernommen und der Wert unter `Kunden-Nr.` ignoriert.
Dokument `3555` dient als produktiv bestätigter Referenzfall:

- Rechnungsnummer: `5799588`
- Kundennummer: `2011452`, nicht übernommen
- BV-/Baustellennummer: `25164`, nur Ersatzkandidat
- Rechnungsbetrag: `531,93`

## Qualitätssicherung

Der dokumentierte Stand wurde mit folgenden Prüfungen validiert:

- 52 Python-Tests erfolgreich
- Ruff erfolgreich
- mypy erfolgreich
- produktiver Readiness-Test erfolgreich
- End-to-End-Verarbeitung über Webhook, Worker und Paperless-API erfolgreich

Eine externe Starlette-Abkündigungswarnung im TestClient bleibt bestehen. Sie
beeinflusst den Betrieb nicht.

## Bekannte Grenzen

- Die automatische Regelliste deckt nur die dokumentierten Feldnamen und
  Bezeichnungen ab.
- Weitere Dokumentarten und kundenspezifische Formulierungen benötigen
  zusätzliche, getestete Regeln.
- Eine fachliche Dokumentklassifikation ist noch nicht Bestandteil des
  automatischen Standardablaufs.
- Instanzspezifisch konfigurierbare Keyword-Regeln besitzen noch keine
  Verwaltungsoberfläche.
- Bereits gefüllte, aber fachlich falsche Werte werden wegen des Schreibschutzes
  nicht automatisch ersetzt.
- PaddleOCR bleibt ein langsamer Rückfall, wenn Paperless keinen Inhalt liefert.
- Das Datenmodell speichert frühere Phasen eines Wiederholungsversuchs, besitzt
  aber noch keine eigene persistente Versuchsentität.
- Lasttests, Rollen- und Rechteverwaltung sowie ein vollständiges
  Produktions-Sicherheitsaudit stehen noch aus.

## Offene fachliche Klärungspunkte

Vor weiteren Erweiterungen sind insbesondere diese Entscheidungen zu treffen:

- Welche Dokumentarten sollen verarbeitet werden?
- Welche Ziel-Custom-Fields werden je Dokumentart benötigt?
- Welche Schreibweisen und Synonyme gelten je Feld?
- Sollen Regeln global oder pro Paperless-Instanz konfiguriert werden?
- Wie sollen Mehrdeutigkeiten zur manuellen Prüfung vorgelegt werden?
- Welche bereits gefüllten Felder dürfen unter welchen Bedingungen korrigiert
  werden?
- Welche Ereignisse sollen einen erneuten Verarbeitungsversuch auslösen?
- Wie lange sollen Jobs, Phasen, Extraktionsergebnisse und Auditdaten
  aufbewahrt werden?
- Welche Status- oder Benachrichtigungswege werden benötigt?

## Änderungsgrundlage

Die wesentlichen letzten Korrekturen sind:

- `41dc00c`: vorhandenen Paperless-OCR-Inhalt priorisieren und deterministische
  Extraktion einführen
- `9530876`: live geladene Feldzuordnungen vor alten Templates verwenden
- `66b6d79`: reale Bezeichnungen für Brutto-Gesamtbeträge ergänzen
- `a375683`: Wiederholungsversuche und Laufzeiten korrekt protokollieren

Weitere Arbeiten sollen diesen Stand als Referenz verwenden und Änderungen an
Verhalten, Regeln oder Sicherheitsgrenzen ausdrücklich dokumentieren.
