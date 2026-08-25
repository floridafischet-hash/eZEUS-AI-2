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

## Paperless-Webhook einrichten

Der Webhook informiert eZEUS darüber, dass Paperless ein Dokument verarbeiten soll. Für die normale Einrichtung ist kein technisches Wissen erforderlich.

### Empfohlene automatische Einrichtung

1. In eZEUS **Instanzen** öffnen.
2. Bei der gewünschten Paperless-Instanz **Workflow einrichten** auswählen.
3. Warten, bis die Erfolgsmeldung erscheint.
4. **Verbindung testen** auswählen.
5. Wird die Verbindung und der Workflow als erfolgreich angezeigt, ist die Einrichtung abgeschlossen.

Diese Methode erstellt den Auslöser und die Webhook-Aktion automatisch mit den richtigen Einstellungen.

### Manuelle Einrichtung in Paperless

Die manuelle Einrichtung wird nur benötigt, wenn ein eigener Auslöser verwendet werden soll, zum Beispiel in einer Testinstanz.

#### 1. Benötigte Angaben bereithalten

- Die **Webhook-URL** steht in eZEUS unter **Instanzen** bei der gewünschten Instanz. Sie endet mit `/webhooks/paperless/...`.
- Das **Webhook-Secret** wurde beim Anlegen oder Bearbeiten der Instanz festgelegt. Es muss in Paperless exakt gleich eingetragen werden.

Webhook-Secret und API-Token sind Passwörter. Nicht in Nachrichten, E-Mails oder Screenshots zeigen.

#### 2. Workflow in Paperless öffnen

1. In Paperless den Bereich **Workflows** öffnen.
2. Einen neuen Workflow anlegen oder den gewünschten Test-Workflow bearbeiten.
3. Einen verständlichen Namen vergeben, zum Beispiel `eZEUS – Fahrzeugdokumente`.
4. Den Workflow **aktivieren**.

#### 3. Auslöser wählen

1. Unter **Auslöser** einen Auslöser hinzufügen.
2. Für den späteren Regelbetrieb **Dokument hinzugefügt** wählen.
3. Für einen vorübergehenden Test darf **Dokument aktualisiert** verwendet werden. Dabei kann eZEUS mehrfach ausgelöst werden, weil eZEUS das Dokument nach der Verarbeitung selbst aktualisiert.
4. Falls gewünscht, Filter setzen, zum Beispiel auf den Dokumenttyp `Zulassungsbescheinigung Teil I`.

#### 4. Webhook-Aktion ausfüllen

Unter **Aktionen** eine neue Aktion hinzufügen und diese Felder ausfüllen:

- **Aktionstyp:** `Webhook`
- **Webhook-URL:** die vollständige Webhook-URL aus eZEUS einfügen
- **HTTP-Methode:** `POST`, falls Paperless dieses Feld anzeigt
- **Parameter für Webhook-Inhalt verwenden:** einschalten
- **Webhook-Payload als JSON senden:** einschalten
- **Dokument einbeziehen:** ausschalten
- **Body/Inhalt:** leer lassen

Unter **Webhook-Parameter** einmal **Hinzufügen** auswählen:

- **Name:** `document_id`
- **Wert:** `{{ doc_url.split("/")[-2] }}`

Unter **Webhook-Kopfzeilen** zweimal **Hinzufügen** auswählen:

Erste Kopfzeile:

- **Name:** `X-EZEUS-Webhook-Secret`
- **Wert:** das Webhook-Secret der Instanz

Zweite Kopfzeile:

- **Name:** `Content-Type`
- **Wert:** `application/json`

Anschließend den gesamten Workflow in Paperless **speichern**.

#### 5. Einrichtung testen

1. In eZEUS bei der Instanz **Verbindung testen** auswählen.
2. Für einen echten Test ein neues passendes Dokument in Paperless hochladen oder in der Testinstanz den gewählten Auslöser auslösen.
3. In eZEUS die **Übersicht** öffnen.
4. Prüfen, ob das Dokument im Verarbeitungsprotokoll erscheint.
5. Nach Abschluss in Paperless kontrollieren, ob die erwarteten Felder, zum Beispiel die Fahrzeug-ID, gefüllt wurden.

Bereits vorhandene Dokumente lösen **Dokument hinzugefügt** nicht nachträglich aus.

### Typische Fehler beim Webhook

- **Das Dokument erscheint nicht in eZEUS:** Workflow aktivieren, Auslöser prüfen und die Webhook-URL Zeichen für Zeichen vergleichen.
- **Nicht autorisiert/401:** Das Webhook-Secret in Paperless stimmt nicht exakt mit dem Secret der eZEUS-Instanz überein.
- **Dokument-ID fehlt:** Prüfen, ob der Parameter `document_id` mit dem oben angegebenen Wert eingetragen ist und die JSON-Übertragung eingeschaltet ist.
- **Dokument wird immer wieder verarbeitet:** Den Auslöser **Dokument aktualisiert** deaktivieren und im Regelbetrieb **Dokument hinzugefügt** verwenden.
- **Workflow-Test in eZEUS schlägt fehl:** In eZEUS **Workflow einrichten** auswählen und anschließend erneut **Verbindung testen**.

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
