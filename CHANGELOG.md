# Changelog

Alle wesentlichen Änderungen an eZEUS-AI-2 werden in dieser Datei dokumentiert.

## Unveröffentlicht

- Fehlerpfade der Dokumentverarbeitung besser diagnostizierbar gemacht: Logs
  enthalten alle strukturierten Zusatzfelder, redigierte Tracebacks sowie
  Auftrags-, Dokument- und Schrittbezug auch für Connector-Meldungen.
  Fehlertexte nennen Anfrage, Feld und Anbieter sowie die redigierte Antwort
  von Paperless oder Ollama. Fehlgeschlagene Metadaten-Schritte erscheinen im
  Log, in den Schrittdaten und als Dashboard-Warnung. Fehler beim Aufbau der
  Paperless-Verbindung beenden den Auftrag jetzt als `FAILED`, statt ihn ohne
  Meldung in `RUNNING` zu belassen.

- Optionales Lieferscheinnummer-Profil für explizite Beschriftungen,
  `LI`-Tabellenlayouts und wiederkehrende OCR-Abweichungen ergänzt; der neue
  Titelplatzhalter `{delivery_note_number}` ermöglicht Titel wie
  `Lieferschein, 123456789`, ohne die Rechnungstitelvorlage zu ersetzen.
  Rechnungsfelder und Lieferscheinnummer sind dabei wechselseitig auf die
  Paperless-Dokumenttypen `Eingangsrechnung` und `Lieferschein` begrenzt.

- Korrespondenten-Matching berücksichtigt den Absenderkontext vollständiger
  Namensfunde, trennt interne vier- bis sechsstellige Verwaltungsnummern vom
  Matchnamen und unterscheidet Unternehmen in rechtlichen Fußzeilen von dort
  lediglich genannten Gerichten.
- Das optionale Bruttobetragsprofil unterstützt zusätzliche zusammengeführte
  Tabellenzeilen sowie Werte in der nächsten oder übernächsten OCR-Zeile;
  Netto-, Rabatt- und Zwischensummenkontexte bleiben ausgeschlossen.
- Verarbeitungsprotokoll mit seitenweiter und filterweiter Auswahl, gebündeltem
  auditierbarem Löschen, echter 50er-Seitennavigation sowie Schutz aktiver
  Aufträge überarbeitet.
- Instanzfilter wird lokal gemerkt und bei entfernten Instanzen kontrolliert auf
  die Gesamtansicht zurückgesetzt.
- Deutsche Status-/Phasenbezeichnungen, strukturierte redigierte
  Fehlererklärungen und deutschsprachige Container-Logmeldungen ergänzt.
- `COMPLETED_WITH_WARNINGS` und `CANCELLED` in manuelle und automatische
  Log-Aufräumvorgänge aufgenommen.
- FF-Rechnungslayouts `Endsumme EUR`, `Summe Brutto Euro` und der Tabellenkopf
  `Kunden-Nr Rechnung Datum` werden für Betrag, Rechnungsnummer und Datum
  zuverlässig ausgewertet.
- Strukturierte Folgezeilen für Rechnungsnummern sowie eindeutig bezeichnete
  Baustellen- und KST-Layouts werden konservativ erkannt; Postleitzahlen und
  Rechnungsnummern bleiben als Baustellennummer ausgeschlossen.
- Optionales IBAN-Extraktionsprofil pro Kundeninstanz ergänzt: Empfänger-IBANs
  werden aus OCR- und Tabellenlayouts gelesen sowie auf Format und bekannte
  Länder-Längen geprüft. Fiktive Prüfziffern sind für Test- und
  Vorführdokumente zulässig; Zahlerkontexte und Mehrdeutigkeiten bleiben ohne
  Rückschreibung.
- Eigene Trigger-Seite ergänzt: Pro Instanz startet die Verarbeitung entweder
  beim Hinzufügen oder erst nach einem frei konfigurierbaren Paperless-Tag.
- Serverseitige Logsuche, manuelles Löschen und automatische Aufbewahrung von
  höchstens 20 Tagen ergänzt.
- Mindestwert für das regelbasierte Korrespondenten-Matching von 75 auf
  60 Prozent reduziert.
- Metadaten werden fehlertolerant in der festen Reihenfolge Korrespondent,
  Titel und benutzerdefinierte Felder geschrieben. Ohne sicheren
  Korrespondenten-Treffer wird `(noch nicht angelegt)` verwendet; fehlerhafte
  Einzelwerte blockieren die nachfolgenden Schreibversuche nicht.
- Optionale OCR- und manuelle Tag-Trigger pro Instanz getrennt sowie eine
  serverseitige Fail-closed-Prüfung ergänzt, damit gelöschte Paperless-Tags
  keine ungefilterten Wiederholungsjobs auslösen.
- Produktionsnahes Kubernetes-/Helm-Chart für API, Worker, Queue-Outbox,
  PostgreSQL, Redis, Ollama, Migrationen, Ingress/OIDC, HPA/PDB und
  NetworkPolicies ergänzt.
- Transaktionale PostgreSQL-Outbox mit wiederholbarer Celery-Zustellung und
  idempotentem Worker-Claim ergänzt.
- Host-Allowlisting, DNS-/Privatnetz- und Pagination-Origin-Schutz für
  Paperless-/Ollama-Aufrufe ergänzt.
- Harte Streaming-Grenzen, MIME-/OCR-Textgrenzen, echte Regex-Timeouts und
  strukturierte Fehlerredaktion ergänzt.
- Hash-basierte Runtime-/Development-Lockfiles sowie einen digest-gepinnten,
  CVE-geprüften Non-Root-Container-Build ergänzt.
- CI für Tests, Ruff, mypy, Bandit, `pip-audit`, Gitleaks, Trivy,
  CycloneDX-SBOM, Helm/kubeconform und vollständigen Compose-Smoke-Test ergänzt.
- Verwaltete Paperless-Workflows auf den sicheren Trigger „Dokument
  hinzugefügt“ beschränkt, damit eZEUS-Rückschreibungen keine Schleife auslösen.
- Proprietären/source-available Lizenzstatus ausdrücklich dokumentiert.
- Mandantenbezogene Feldkonfiguration mit Standardvorlage, Custom-Feldern,
  Feldtypen, Pflichtstatus, Sortierung sowie OCR-/KI-Schaltern ergänzt.
- Geschützte Feldkonfigurations-API und Weboberfläche mit Vorschau ergänzt.
- Verarbeitungs-Pipeline an die dauerhaft gespeicherte Instanzkonfiguration
  gebunden.
- Konfigurationsänderungen um mandantenbezogene Auditdaten erweitert.
- Individuelle Administratorkonten mit Scrypt-Passwörtern und den Rollen
  `admin` und `viewer` ergänzt; das gemeinsame Secret ist nur noch Bootstrap.
- Fehlende Paperless-Custom-Fields werden automatisch angelegt und verknüpft.
- Mandantenbezogene KI-Felder aktivieren Ollama ohne zusätzlichen globalen
  Extraktionsschalter.

## 0.2.0 - 2026-07-27

### Hinzugefügt

- lokaler Ollama-Provider für strukturierte Feldextraktion
- Unterstützung für das lokale Modell `qwen3:4b`
- Betriebsdashboard am Startpfad `/`
- Reiter `Übersicht`, `Logs` und `API`
- bereinigte Log-API `GET /api/logs`
- automatische Aktualisierung des Log-Reiters
- Tests für Dashboard und Log-API

### Sicherheit

- `.env` aus der Versionsverwaltung entfernt
- `.env` und lokale Varianten in `.gitignore` aufgenommen
- Beispielkonfiguration auf eindeutig nicht produktive Standardwerte umgestellt
- Log-Ausgabe auf technische Metadaten ohne Dokumentinhalt und Secrets begrenzt

### Betrieb

- lokale KI bleibt ausschließlich über das private Container-Netz erreichbar
- produktive Reverse-Proxy-, Server- und Secret-Werte bleiben außerhalb des
  Repositorys
