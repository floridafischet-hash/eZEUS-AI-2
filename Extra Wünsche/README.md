# Extra Wünsche

Diese Bibliothek sammelt wiederverwendbare Kundenanforderungen für eZEUS.
Sie verhindert, dass Extraktionshinweise, Prüfregeln und Testfälle bei jedem
Kunden neu entwickelt werden müssen.

## Verwendung

1. Passende Kategorie öffnen.
2. Einen vorhandenen Eintrag kopieren und an das Kundendokument anpassen.
3. Den Extraktionshinweis in der Feldkonfiguration der Kundeninstanz eintragen.
4. Mit anonymisierten positiven und negativen Beispielen testen.
5. Erkenntnisse und neue Schreibweisen in diesem Eintrag ergänzen.

Eine hier dokumentierte Regel ist nicht automatisch für alle Kunden aktiv.
Sie wird erst wirksam, wenn sie bewusst in einer Kundeninstanz konfiguriert
oder kundenspezifisch implementiert wird.

## Aufbau eines Eintrags

Jeder Eintrag sollte enthalten:

- Zweck und Dokumentarten
- kopierfertiger Extraktionshinweis
- bekannte Bezeichnungen und Schreibweisen
- Bereinigung und Validierung
- positive und negative Testfälle
- bekannte Grenzen
- Änderungsverlauf

Für neue Einträge liegt unter [`Vorlagen/Neuer Wunsch.md`](Vorlagen/Neuer%20Wunsch.md)
eine ausfüllbare Vorlage.

## Kategorien

- [`Fahrzeugdaten`](Fahrzeugdaten/README.md)
- [`Korrespondenten`](Korrespondenten/README.md)
- [`Rechnungsnummern`](Rechnungsnummern/README.md)

