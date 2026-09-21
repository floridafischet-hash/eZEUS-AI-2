# ruff: noqa: E501

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from apps.api.ui import page_shell

router = APIRouter(tags=["help"])


@router.get("/help", response_class=HTMLResponse, include_in_schema=False)
def help_page() -> str:
    content = """
<div class="content-stack help-content">
  <section class="panel">
    <div class="section-heading"><div>
      <h2>Schnellstart</h2>
      <p class="section-copy">In sechs Schritten von der Anmeldung zur geprüften Dokumentverarbeitung.</p>
    </div></div>
    <ol>
      <li>Mit dem persönlichen Benutzernamen und Passwort anmelden.</li>
      <li>In Paperless einen API-Token für ein berechtigtes Konto erzeugen.</li>
      <li>Unter <a href="/admin/instances">Instanzen</a> die Paperless-Adresse und den API-Token eintragen.</li>
      <li><strong>Workflow einrichten</strong> und danach <strong>Verbindung testen</strong>.</li>
      <li>Über <strong>Felder</strong> festlegen, welche Dokumentdaten ausgelesen werden.</li>
      <li>Mehrere typische Kundendokumente hochladen und die Ergebnisse kontrollieren.</li>
    </ol>
    <div class="notice warning"><strong>Wichtig:</strong> Ein erfolgreicher Verbindungstest prüft nur die technische Verbindung. Die Instanz ist erst einsatzbereit, wenn Rechnungsnummer, Betrag und weitere benötigte Felder bei echten Testdokumenten richtig erkannt wurden.</div>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>So funktioniert eZEUS</h2></div></div>
    <ol>
      <li><strong>Paperless liest:</strong> Paperless erzeugt den OCR-Text des Dokuments.</li>
      <li><strong>Der Workflow meldet:</strong> Paperless sendet die Dokument-ID an eZEUS.</li>
      <li><strong>eZEUS extrahiert:</strong> eZEUS sucht die aktivierten Werte, prüft sie und schreibt sichere Treffer in noch leere Paperless-Felder.</li>
    </ol>
    <p>Ein Dokument kann deshalb in eZEUS erscheinen, obwohl einzelne Felder leer bleiben. Dann funktioniert der Workflow bereits; meistens passt das Dokumentlayout zu keiner aktiven Regel, das Zielfeld ist nicht zugeordnet oder es ist bereits gefüllt.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>1. Anmeldung und Navigation</h2></div></div>
    <p>Beim Öffnen der Anwendung fragt der Browser nach den persönlichen Zugangsdaten. Diese Daten dürfen nicht an andere Personen weitergegeben werden.</p>
    <ul>
      <li><strong>Übersicht:</strong> zeigt den Systemzustand und die letzten Verarbeitungsschritte.</li>
      <li><strong>Instanzen:</strong> verbindet eZEUS mit Paperless und verwaltet Dokumentfelder.</li>
      <li><strong>Benutzer:</strong> verwaltet persönliche Zugänge und Berechtigungen.</li>
      <li><strong>Hilfe:</strong> öffnet diese Anleitung.</li>
    </ul>
    <p><strong>Wichtig:</strong> Die Bereiche „Alternative API-Anmeldung“ werden im normalen Betrieb nicht benötigt und können geschlossen bleiben.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>2. Paperless-Instanz anlegen</h2></div></div>
    <ol>
      <li>In Paperless einen API-Token erstellen. Je nach Paperless-Version befindet sich diese Funktion im Benutzerprofil oder in der Administration unter API-Token.</li>
      <li>In eZEUS links auf <a href="/admin/instances">Instanzen</a> klicken.</li>
      <li>Bei <strong>Bezeichnung</strong> einen verständlichen Namen eintragen, zum Beispiel den Kundennamen.</li>
      <li>Bei <strong>Paperless-URL</strong> die vollständige Adresse mit <code>https://</code> eintragen. Keine Unterseite wie <code>/documents</code> anhängen.</li>
      <li>Den Paperless-API-Token in das dafür vorgesehene Feld einfügen.</li>
      <li>Auf <strong>Instanz speichern</strong> klicken.</li>
    </ol>
    <p>eZEUS prüft die Verbindung und richtet den benötigten Paperless-Workflow automatisch ein. Das kann einige Sekunden dauern.</p>
    <p><strong>API-Token schützen:</strong> Er ist wie ein Passwort zu behandeln. Nicht per Chat oder E-Mail versenden und nicht in Screenshots zeigen.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>3. Verbindung und Workflow prüfen</h2></div></div>
    <ul>
      <li><strong>Verbindung testen:</strong> prüft Paperless, den API-Token und den eingerichteten Workflow.</li>
      <li><strong>Workflow einrichten:</strong> repariert oder ergänzt den von eZEUS verwalteten Workflow.</li>
      <li><strong>Bearbeiten:</strong> ändert Name, Adresse oder Zugangsdaten. Leere Passwortfelder behalten die gespeicherten Werte bei.</li>
    </ul>
    <p>Der automatisch erzeugte Workflow reagiert auf <strong>„Dokument hinzugefügt“</strong>. „Dokument geändert“ darf nicht zusätzlich aktiviert werden, weil sonst eine Verarbeitungsschleife entstehen kann.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div>
      <h2>4. Paperless-Webhook einrichten</h2>
      <p class="section-copy">Der Webhook informiert eZEUS darüber, dass Paperless ein Dokument verarbeiten soll.</p>
    </div></div>
    <h3>Empfohlen: automatisch einrichten</h3>
    <ol>
      <li>In eZEUS <a href="/admin/instances">Instanzen</a> öffnen.</li>
      <li>Bei der gewünschten Instanz auf <strong>Workflow einrichten</strong> klicken.</li>
      <li>Die Erfolgsmeldung abwarten und danach <strong>Verbindung testen</strong> auswählen.</li>
      <li>Werden Verbindung und Workflow als erfolgreich angezeigt, ist die technische Einrichtung abgeschlossen. Danach Felder und echte Dokumente prüfen.</li>
    </ol>
    <div class="notice success">Diese Methode erstellt Auslöser und Webhook-Aktion automatisch mit den richtigen Einstellungen.</div>

    <h3>Manuell in Paperless einrichten</h3>
    <p>Diese Schritte werden nur benötigt, wenn ein eigener Auslöser verwendet werden soll, zum Beispiel in einer Testinstanz.</p>
    <h4>1. Angaben bereithalten</h4>
    <ul>
      <li>Die <strong>Webhook-URL</strong> steht in eZEUS unter <strong>Instanzen</strong>. Sie endet mit <code>/webhooks/paperless/...</code>.</li>
      <li>Das <strong>Webhook-Secret</strong> wurde beim Anlegen oder Bearbeiten der Instanz festgelegt. Es muss in Paperless exakt gleich eingetragen werden.</li>
    </ul>
    <p><strong>Geheimnisse schützen:</strong> Webhook-Secret und API-Token nicht in Nachrichten, E-Mails oder Screenshots zeigen.</p>

    <h4>2. Workflow und Auslöser anlegen</h4>
    <ol>
      <li>In Paperless <strong>Workflows</strong> öffnen und einen Workflow anlegen oder bearbeiten.</li>
      <li>Einen verständlichen Namen vergeben und den Workflow aktivieren.</li>
      <li>Unter <strong>Auslöser</strong> für den Regelbetrieb <strong>Dokument hinzugefügt</strong> wählen.</li>
      <li>Nur für Tests darf <strong>Dokument aktualisiert</strong> gewählt werden. Das kann zu Mehrfachauslösungen führen.</li>
      <li>Bei Bedarf einen Filter setzen, zum Beispiel auf den Dokumenttyp „Zulassungsbescheinigung Teil I“.</li>
    </ol>

    <h4>3. Webhook-Aktion ausfüllen</h4>
    <p>Unter <strong>Aktionen</strong> eine Aktion hinzufügen und genau diese Einstellungen verwenden:</p>
    <ul>
      <li><strong>Aktionstyp:</strong> <code>Webhook</code></li>
      <li><strong>Webhook-URL:</strong> vollständige URL aus eZEUS</li>
      <li><strong>HTTP-Methode:</strong> <code>POST</code>, falls das Feld angezeigt wird</li>
      <li><strong>Parameter für Webhook-Inhalt verwenden:</strong> einschalten</li>
      <li><strong>Webhook-Payload als JSON senden:</strong> einschalten</li>
      <li><strong>Dokument einbeziehen:</strong> ausschalten</li>
      <li><strong>Body/Inhalt:</strong> leer lassen</li>
    </ul>
    <p>Unter <strong>Webhook-Parameter</strong> einmal <strong>Hinzufügen</strong>:</p>
    <ul>
      <li><strong>Name:</strong> <code>document_id</code></li>
      <li><strong>Wert:</strong> <code>{{ doc_url.split("/")[-2] }}</code></li>
    </ul>
    <p>Unter <strong>Webhook-Kopfzeilen</strong> zweimal <strong>Hinzufügen</strong>:</p>
    <ul>
      <li><code>X-EZEUS-Webhook-Secret</code> → als Wert das Webhook-Secret der Instanz</li>
      <li><code>Content-Type</code> → als Wert <code>application/json</code></li>
    </ul>
    <p>Danach den gesamten Workflow in Paperless <strong>speichern</strong>.</p>

    <h4>4. Einrichtung testen</h4>
    <ol>
      <li>In eZEUS <strong>Verbindung testen</strong> auswählen.</li>
      <li>Ein neues passendes Dokument in Paperless hochladen oder in der Testinstanz den gewählten Auslöser auslösen.</li>
      <li>In der <a href="/">Übersicht</a> prüfen, ob das Dokument im Verarbeitungsprotokoll erscheint.</li>
      <li>Nach Abschluss in Paperless kontrollieren, ob die erwarteten Felder gefüllt wurden.</li>
    </ol>
    <p>Bereits vorhandene Dokumente lösen <strong>Dokument hinzugefügt</strong> nicht nachträglich aus.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>5. Dokumentfelder festlegen</h2></div></div>
    <p>Bei der gewünschten Instanz auf <strong>Felder</strong> klicken. Dort wird festgelegt, welche Informationen eZEUS aus Dokumenten übernimmt.</p>
    <ul>
      <li><strong>In eZEUS:</strong> schaltet ein Feld für diesen Kunden ein oder aus. Neu importierte Paperless-Felder sind zunächst aus.</li>
      <li><strong>Pflichtfeld:</strong> erzeugt eine Warnung, wenn kein sicherer Wert gefunden wird. Der Schalter erzwingt keinen Treffer.</li>
      <li><strong>OCR:</strong> wendet feste Erkennungsregeln auf den Paperless-OCR-Text an.</li>
      <li><strong>KI:</strong> verwendet zusätzlich Ollama, sofern die KI systemweit aktiviert und erreichbar ist.</li>
      <li><strong>Feldtyp:</strong> bestimmt, ob Text, Zahl, Geldbetrag, Datum, Ja/Nein oder eine Auswahl erwartet wird.</li>
      <li><strong>Paperless-ID:</strong> bestimmt das Zielfeld in Paperless und darf bei aktiven benutzerdefinierten Feldern nicht fehlen.</li>
      <li><strong>Extraktionshinweise:</strong> gelten nur für die KI und verändern keine feste Regex-Regel.</li>
    </ul>
    <p>Mit den Pfeilen lässt sich die Reihenfolge ändern. Die Vorschau zeigt das spätere Ergebnis. Erst <strong>Konfiguration speichern</strong> übernimmt die Änderungen.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>6. Kundeninstanz abnehmen</h2></div></div>
    <p>Vor der Freigabe mindestens eine normale Rechnung, eine mehrseitige Rechnung, eine Gutschrift und – falls verwendet – ein Dokument mit Baustellennummer testen. Zusätzlich Dokumente der wichtigsten Lieferanten verwenden.</p>
    <ol>
      <li>Ein neues Testdokument in Paperless hochladen und die OCR abwarten.</li>
      <li>Den neuesten Job in der <a href="/">Übersicht</a> öffnen.</li>
      <li>In Paperless Rechnungsnummer, Betrag und weitere Felder inhaltlich kontrollieren.</li>
      <li>Erst freigeben, wenn mehrere typische Dokumente richtig erkannt werden und keine falschen Werte entstehen.</li>
    </ol>
    <div class="notice warning">Bereits gefüllte Paperless-Felder werden nicht überschrieben. Vorhandene Dokumente lösen „Dokument hinzugefügt“ nicht nachträglich aus.</div>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>7. Verarbeitung kontrollieren</h2></div></div>
    <p>Die <a href="/">Übersicht</a> zeigt das Verarbeitungsprotokoll. Über den Instanzfilter und die Suche lässt sich ein bestimmtes Dokument finden.</p>
    <ul>
      <li><strong>Erfolgreich:</strong> der Schritt wurde abgeschlossen.</li>
      <li><strong>Mit Warnungen abgeschlossen:</strong> das Dokument wurde verarbeitet, aber ein Pflichtfeld fehlt oder war nicht sicher.</li>
      <li><strong>In Bearbeitung:</strong> die Verarbeitung läuft noch.</li>
      <li><strong>Fehlgeschlagen:</strong> der Eintrag öffnen und Dateiname, Phase, Zeitpunkt und Fehlerklasse notieren.</li>
    </ul>
    <p>Bei einer Supportanfrage niemals API-Token, Passwörter, Webhook-Secrets oder vertrauliche Dokumentinhalte mitsenden.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>8. Benutzer verwalten</h2></div></div>
    <p>Jede Person sollte ein eigenes Konto erhalten. Unter <a href="/api/admin-users/page">Benutzer</a> kann ein Administrator Konten anlegen und Rollen vergeben.</p>
    <ul>
      <li><strong>Administrator:</strong> darf Einstellungen und Benutzer verändern.</li>
      <li><strong>Nur lesen:</strong> darf Informationen ansehen, aber keine administrativen Änderungen vornehmen.</li>
    </ul>
    <p>Ein Konto muss zuerst deaktiviert werden, bevor es endgültig gelöscht werden kann. Der letzte aktive Administrator kann nicht entfernt werden.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>Häufige Probleme</h2></div></div>
    <dl>
      <dt><strong>Der Anmeldedialog erscheint immer wieder</strong></dt>
      <dd>Benutzername und Passwort erneut sorgfältig eingeben. Bleibt der Dialog bestehen, muss ein Administrator beide Zugangsebenen prüfen.</dd>
      <dt><strong>Paperless-Verbindung fehlgeschlagen</strong></dt>
      <dd>Paperless-Adresse, Erreichbarkeit und API-Token prüfen. Die Adresse muss mit <code>https://</code> beginnen.</dd>
      <dt><strong>Workflow fehlt oder ist fehlerhaft</strong></dt>
      <dd>Bei der Instanz auf <strong>Workflow einrichten</strong> und anschließend auf <strong>Verbindung testen</strong> klicken.</dd>
      <dt><strong>Der Webhook meldet „Nicht autorisiert“ oder 401</strong></dt>
      <dd>Das Webhook-Secret in Paperless stimmt nicht exakt mit dem Secret der eZEUS-Instanz überein.</dd>
      <dt><strong>Die Dokument-ID fehlt</strong></dt>
      <dd>Prüfen, ob der Parameter <code>document_id</code> eingetragen und die Übertragung als JSON aktiviert ist.</dd>
      <dt><strong>Ein Dokument wird immer wieder verarbeitet</strong></dt>
      <dd>Den Auslöser „Dokument aktualisiert“ deaktivieren und im Regelbetrieb „Dokument hinzugefügt“ verwenden.</dd>
      <dt><strong>Ein Paperless-Feld fehlt</strong></dt>
      <dd>Das Feld zuerst in Paperless anlegen und danach die Feldseite in eZEUS neu laden.</dd>
      <dt><strong>Ein Dokument wird nicht verarbeitet</strong></dt>
      <dd>Prüfen, ob die Instanz aktiv ist und der Workflow auf „Dokument hinzugefügt“ reagiert. Danach das Verarbeitungsprotokoll öffnen.</dd>
      <dt><strong>Das Dokument erscheint, aber Felder bleiben leer</strong></dt>
      <dd>Dann funktioniert der Workflow. OCR-Text, Feldaktivierung, OCR-Schalter, Paperless-ID und ein bereits gefülltes Zielfeld prüfen. Bei <code>candidates_found: 0</code> wurde das konkrete Layout nicht erkannt.</dd>
      <dt><strong>Der Rechnungsbetrag fehlt</strong></dt>
      <dd>Im OCR-Text nach eindeutigen Bezeichnungen wie Gesamtbetrag, Rechnungssumme, Zahlbetrag, Brutto-Rechnungsbetrag oder Erstattungsbetrag suchen.</dd>
      <dt><strong>Die Baustellennummer fehlt</strong></dt>
      <dd>Numerische Formen wie <code># 26051</code>, <code>BV- 25095</code> oder <code>Baustellennummer: 26070</code> werden unterstützt. Reine Namen wie „BV Buck“ werden bewusst nicht als Nummer übernommen.</dd>
    </dl>
  </section>
</div>
"""
    return page_shell(
        title="Benutzerhandbuch",
        description="Schritt-für-Schritt-Anleitung für die tägliche Bedienung – ohne technische Vorkenntnisse.",
        active="help",
        content=content,
        eyebrow="Hilfe & Anleitung",
    )
