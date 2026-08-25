# eZEUS-AI-2 – Benutzerhandbuch

Dieses Handbuch erklärt die tägliche Bedienung ohne technische Vorkenntnisse. Die Anleitung ist auch direkt in der Anwendung über **Hilfe** erreichbar.

## Schnellstart

1. Mit dem persönlichen Benutzernamen und Passwort anmelden.
2. In Paperless einen API-Token für ein berechtigtes Konto erzeugen.
3. In eZEUS unter **Instanzen** die Paperless-Adresse und den API-Token eintragen.
4. Nach dem Speichern **Verbindung testen** auswählen.
5. Über **Felder** festlegen, welche Dokumentdaten ausgelesen werden.

Wenn der Verbindungstest erfolgreich ist und der Workflow als korrekt eingerichtet gemeldet wird, ist die Instanz einsatzbereit.

## Navigation

- **Übersicht:** Systemzustand und letzte Verarbeitungsschritte
- **Instanzen:** Paperless-Verbindungen, Workflows und Dokumentfelder
- **Benutzer:** persönliche Zugänge und Berechtigungen
- **Hilfe:** dieses Benutzerhandbuch

Die auf manchen Seiten angezeigte **Alternative API-Anmeldung** wird im normalen Betrieb nicht benötigt.

## Paperless-Instanz anlegen

1. In Paperless einen API-Token erstellen. Je nach Paperless-Version befindet sich diese Funktion im Benutzerprofil oder in der Administration unter API-Token.
2. In eZEUS **Instanzen** öffnen.
3. Als **Bezeichnung** einen verständlichen Namen, zum Beispiel den Kundennamen, eintragen.
4. Die vollständige **Paperless-URL** mit `https://` eintragen. Keine Unterseite wie `/documents` anhängen.
5. Den Paperless-API-Token einfügen.
6. **Instanz speichern** auswählen.

eZEUS prüft die Verbindung und richtet den benötigten Paperless-Workflow automatisch ein. Der API-Token ist wie ein Passwort zu schützen und darf nicht in Chats, E-Mails oder Screenshots erscheinen.

## Verbindung und Workflow prüfen

- **Verbindung testen** prüft Paperless, den API-Token und den Workflow.
- **Workflow einrichten** repariert oder ergänzt den von eZEUS verwalteten Workflow.
- **Bearbeiten** ändert Bezeichnung, Adresse oder Zugangsdaten. Leere Passwortfelder behalten die gespeicherten Werte bei.

Der Workflow darf nur auf **Dokument hinzugefügt** reagieren. **Dokument geändert** kann eine Verarbeitungsschleife verursachen.

## Dokumentfelder festlegen

Bei der gewünschten Instanz **Felder** auswählen.

- **In eZEUS:** Feld ein- oder ausschalten
- **Pflichtfeld:** Angabe soll vorhanden sein
- **OCR:** erkannten Dokumenttext verwenden
- **KI:** Angabe durch die KI bestimmen
- **Feldtyp:** Text, Zahl, Geldbetrag, Datum, Ja/Nein oder Auswahl
- **Extraktionshinweise:** in einfachen Worten beschreiben, wie die Angabe erkannt werden soll

Die Reihenfolge lässt sich mit den Pfeilen ändern. Die Vorschau zeigt das erwartete Formular. Änderungen werden erst mit **Konfiguration speichern** übernommen.

## Verarbeitung kontrollieren

Auf der **Übersicht** zeigt das Verarbeitungsprotokoll den Zustand der Dokumente. Instanzfilter und Suche helfen beim Auffinden eines Dokuments.

- **Erfolgreich:** Schritt abgeschlossen
- **In Bearbeitung:** Verarbeitung läuft
- **Fehlgeschlagen:** Eintrag öffnen und Dateiname, Phase, Zeitpunkt sowie Fehlerklasse notieren

Für Supportanfragen niemals API-Token, Passwörter, Webhook-Secrets oder vertrauliche Dokumentinhalte mitsenden.

## Benutzer verwalten

Jede Person sollte ein eigenes Konto erhalten.

- **Administrator:** darf Einstellungen und Benutzer verändern
- **Nur lesen:** darf Informationen ansehen, aber keine administrativen Änderungen vornehmen

Ein Konto muss vor dem endgültigen Löschen deaktiviert werden. Der letzte aktive Administrator kann nicht entfernt werden.

## Häufige Probleme

### Der Anmeldedialog erscheint immer wieder

Benutzername und Passwort erneut sorgfältig eingeben. Bleibt der Dialog bestehen, muss ein Administrator beide Zugangsebenen prüfen.

### Paperless-Verbindung fehlgeschlagen

Paperless-Adresse, Erreichbarkeit und API-Token prüfen. Die Adresse muss mit `https://` beginnen.

### Workflow fehlt oder ist fehlerhaft

Bei der Instanz **Workflow einrichten** und danach **Verbindung testen** auswählen.

### Ein Paperless-Feld fehlt

Das Feld zuerst in Paperless anlegen und anschließend die Feldseite in eZEUS neu laden.

### Ein Dokument wird nicht verarbeitet

Prüfen, ob die Instanz aktiv ist und der Workflow auf **Dokument hinzugefügt** reagiert. Danach das Verarbeitungsprotokoll öffnen.
