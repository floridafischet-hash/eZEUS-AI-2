# eZEUS-AI-2 – Benutzerhandbuch

Dieses Handbuch erklärt die tägliche Bedienung ohne technische Vorkenntnisse. Die Anleitung ist auch direkt in der Anwendung über **Hilfe** erreichbar.

## Schnellstart

1. Mit dem persönlichen Benutzernamen und Passwort anmelden.
2. In Paperless einen API-Token für ein berechtigtes Konto erzeugen.
3. In eZEUS unter **Instanzen** die Paperless-Adresse und den API-Token eintragen.
4. **Workflow einrichten** und danach **Verbindung testen** auswählen.
5. Über **Felder** festlegen, welche Dokumentdaten ausgelesen werden.
6. Mehrere typische Kundendokumente hochladen und die Ergebnisse kontrollieren.

**Wichtig:** Ein erfolgreicher Verbindungstest bedeutet noch nicht, dass die
Dokumente richtig ausgelesen werden. Er bestätigt nur die technische
Verbindung. Die Instanz ist erst einsatzbereit, wenn auch der Dokumenttest
erfolgreich war.

## So funktioniert eZEUS

Der Ablauf besteht aus drei getrennten Teilen:

1. **Paperless liest das Dokument.** Paperless erzeugt den OCR-Text.
2. **Der Workflow meldet das Dokument.** Paperless sendet die Dokument-ID an
   eZEUS.
3. **eZEUS liest die Werte aus.** eZEUS sucht beispielsweise
   Rechnungsnummer, Rechnungsbetrag und Baustellennummer und schreibt sichere
   Treffer zurück nach Paperless.

Dadurch kann der Workflow korrekt funktionieren, obwohl ein Feld leer bleibt.
In diesem Fall ist nicht die Verbindung kaputt, sondern das konkrete
Dokumentlayout wurde nicht erkannt oder das Zielfeld ist nicht richtig
zugeordnet.

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

Nach dem Speichern ist die Einrichtung noch nicht beendet. Führe anschließend
immer die Abschnitte **Dokumentfelder festlegen** und **Kundeninstanz abnehmen**
aus.

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
5. Wird die Verbindung und der Workflow als erfolgreich angezeigt, ist die
   technische Einrichtung abgeschlossen. Danach müssen Felder und reale
   Dokumente geprüft werden.

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

- **In eZEUS:** Dieses Feld wird für den Kunden verarbeitet. Aus Paperless neu
  geladene Felder sind zunächst ausgeschaltet.
- **Pflichtfeld:** Fehlt ein gültiger Wert, zeigt der Job eine Warnung. Das
  erzwingt keinen Treffer und sollte nur für wirklich notwendige Angaben
  eingeschaltet werden.
- **OCR:** eZEUS verwendet feste Erkennungsregeln auf dem Paperless-OCR-Text.
  Dieser Schalter sollte für Rechnungsnummer, Betrag und Baustellennummer
  normalerweise aktiv sein.
- **KI:** Zusätzlich wird die lokale KI verwendet, wenn Ollama systemweit
  aktiviert ist. Der Schalter allein garantiert nicht, dass Ollama verfügbar
  ist.
- **Feldtyp:** Text, Zahl, Geldbetrag, Datum, Ja/Nein oder Auswahl
- **Paperless-ID:** Ziel des Wertes in Paperless. Bei einem aktiven
  benutzerdefinierten Feld darf diese Zuordnung nicht fehlen.
- **Extraktionshinweise:** Anweisung ausschließlich für die KI-Auslesung. Sie
  verändert keine feste Regex-Regel.

Die Reihenfolge lässt sich mit den Pfeilen ändern. Die Vorschau zeigt das erwartete Formular. Änderungen werden erst mit **Konfiguration speichern** übernommen.

### Empfohlene Einstellungen für Rechnungen

- **Rechnungsnummer:** In eZEUS an, Pflichtfeld an, OCR an
- **Rechnungsbetrag:** In eZEUS an, Pflichtfeld an, OCR an, Typ Geldbetrag
- **Rechnungsdatum:** In eZEUS an, Pflichtfeld meistens aus, OCR an
- **Baustellennummer:** In eZEUS an, Pflichtfeld nur bei sicherer Verwendung,
  OCR an
- **KI:** zunächst aus; nur bei nachgewiesenen Regex-Lücken gezielt verwenden

Wenn eine Instanz Rechnungen, Lieferscheine und andere Dokumente verarbeitet,
sollten rechnungsspezifische Felder nicht pauschal für alle Dokumente als
Pflichtfelder behandelt werden.

## Kundeninstanz abnehmen

Eine neue Kundeninstanz sollte niemals direkt nach dem Verbindungstest für den
Produktivbetrieb freigegeben werden.

### Geeignete Testdokumente

Verwende mindestens:

1. eine normale einseitige Rechnung;
2. eine mehrseitige Rechnung;
3. eine Gutschrift, falls der Kunde Gutschriften verarbeitet;
4. eine Rechnung mit Baustellennummer;
5. Dokumente von mehreren häufigen Lieferanten.

### Durchführung

1. Neues Testdokument in Paperless hochladen.
2. Warten, bis Paperless die OCR abgeschlossen hat.
3. In eZEUS die **Übersicht** öffnen.
4. Den neuesten Job der richtigen Instanz aufklappen.
5. In Paperless kontrollieren, ob die Werte wirklich richtig angekommen sind.
6. Ergebnisse nicht nur auf Vorhandensein, sondern inhaltlich prüfen: Eine
   Kundennummer darf beispielsweise nicht als Rechnungsnummer erscheinen.

Die Kundeninstanz ist abgenommen, wenn alle notwendigen Felder bei mehreren
typischen Dokumenten richtig erkannt wurden und keine falschen Werte
geschrieben werden.

### Bereits vorhandene Dokumente

Der Workflow **Dokument hinzugefügt** verarbeitet nur neue Ereignisse.
Vorhandene Dokumente werden nicht automatisch nachträglich geprüft. Außerdem
überschreibt eZEUS bereits gefüllte Paperless-Felder grundsätzlich nicht. Für
einen erneuten Test muss das Zielfeld leer sein und der Job kontrolliert neu
ausgelöst werden.

## Verarbeitung kontrollieren

Auf der **Übersicht** zeigt das Verarbeitungsprotokoll den Zustand der Dokumente. Instanzfilter und Suche helfen beim Auffinden eines Dokuments.

- **Erfolgreich:** Schritt abgeschlossen
- **Mit Warnungen abgeschlossen:** Dokument wurde verarbeitet, aber mindestens
  ein Pflichtfeld fehlte oder konnte nicht sicher übernommen werden
- **In Bearbeitung:** Verarbeitung läuft
- **Fehlgeschlagen:** Eintrag öffnen und Dateiname, Phase, Zeitpunkt sowie Fehlerklasse notieren

### Die wichtigsten Zahlen im Jobprotokoll

- `fields_configured`: Anzahl der für den Kunden geprüften Felder
- `candidates_found`: Anzahl der von Regex oder KI gefundenen Kandidaten
- `fields_accepted`: Anzahl der validierten Werte
- `missing_fields`: fehlende Pflichtfelder
- `fields_written`: tatsächlich neu nach Paperless geschriebene Felder
- `text_characters`: Länge des von Paperless gelieferten OCR-Textes

Typische Interpretation:

- `candidates_found: 0`: Das Dokumentlayout passt zu keiner aktiven Regel.
- Kandidat vorhanden, aber nicht akzeptiert: Der Wert war ungültig oder
  widersprüchlich.
- Wert akzeptiert, aber nichts geschrieben: Das Paperless-Feld war bereits
  gefüllt oder die Paperless-ID fehlt.

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

### Das Dokument erscheint in eZEUS, aber die Felder bleiben leer

Dann funktioniert der Workflow bereits. Prüfe in dieser Reihenfolge:

1. Liefert Paperless einen OCR-Text mit Inhalt?
2. Ist das Feld unter **Felder** in eZEUS aktiviert?
3. Ist **OCR** für das Feld aktiviert?
4. Ist die richtige Paperless-ID eingetragen?
5. Ist das Paperless-Zielfeld wirklich leer?
6. Stehen Feldname und Wert im OCR-Text in einer unterstützten Form?
7. Zeigt das Jobprotokoll `candidates_found: 0` oder einen abgelehnten Wert?

### Rechnungsbetrag fehlt

Suche im Paperless-OCR-Text nach eindeutigen Begriffen wie `Gesamtbetrag`,
`Rechnungssumme`, `Zahlbetrag`, `Brutto-Rechnungsbetrag` oder
`Erstattungsbetrag`. Steht der Betrag nur unbeschriftet in einer Tabelle, kann
eZEUS ihn absichtlich nicht sicher zuordnen.

### Baustellennummer fehlt

Gut erkennbare Beispiele sind `# 26051`, `BV- 25095`, `BV-Nr. 25180` oder
`Baustellennummer: 26070`. Bezeichnungen wie `BV Buck` enthalten keine
numerische Baustellennummer und werden bewusst nicht übernommen.

### Ein Dokument wird mehrfach verarbeitet

Prüfe in Paperless, ob mehrere aktive Workflows oder Webhook-Aktionen dasselbe
Dokument senden. Der produktive Workflow soll nur auf **Dokument hinzugefügt**
reagieren. **Dokument aktualisiert** kann nach den eZEUS-Schreiboperationen
erneut auslösen.

## Checkliste vor der Freigabe

- Verbindungstest erfolgreich
- Workflow automatisch eingerichtet
- nur der gewünschte Workflow-Auslöser aktiv
- benötigte Felder in eZEUS aktiviert
- Paperless-IDs kontrolliert
- Feldtypen stimmen überein
- mehrere Lieferanten getestet
- normale Rechnung getestet
- mehrseitige Rechnung getestet
- Gutschrift getestet, falls verwendet
- Baustellennummer getestet, falls verwendet
- keine Kundennummer als Rechnungsnummer übernommen
- keine Wörter als Baustellennummer übernommen
- Warnungen im Jobprotokoll verstanden
