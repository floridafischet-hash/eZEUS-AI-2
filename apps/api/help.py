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
      <p class="section-copy">In fünf Schritten von der Anmeldung zur automatischen Dokumentverarbeitung.</p>
    </div></div>
    <ol>
      <li>Mit dem persönlichen Benutzernamen und Passwort anmelden.</li>
      <li>In Paperless einen API-Token für ein berechtigtes Konto erzeugen.</li>
      <li>Unter <a href="/admin/instances">Instanzen</a> die Paperless-Adresse und den API-Token eintragen.</li>
      <li>Nach dem Speichern auf <strong>Verbindung testen</strong> klicken.</li>
      <li>Über <strong>Felder</strong> festlegen, welche Dokumentdaten ausgelesen werden.</li>
    </ol>
    <div class="notice success">Wenn der Verbindungstest erfolgreich ist und der Workflow als korrekt eingerichtet gemeldet wird, ist die Instanz einsatzbereit.</div>
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
    <div class="section-heading"><div><h2>4. Dokumentfelder festlegen</h2></div></div>
    <p>Bei der gewünschten Instanz auf <strong>Felder</strong> klicken. Dort wird festgelegt, welche Informationen eZEUS aus Dokumenten übernimmt.</p>
    <ul>
      <li><strong>In eZEUS:</strong> schaltet ein Feld für die Verarbeitung ein oder aus.</li>
      <li><strong>Pflichtfeld:</strong> kennzeichnet Angaben, die vorhanden sein sollen.</li>
      <li><strong>OCR:</strong> nutzt den erkannten Dokumenttext.</li>
      <li><strong>KI:</strong> lässt die Angabe durch die KI bestimmen.</li>
      <li><strong>Feldtyp:</strong> bestimmt, ob Text, Zahl, Geldbetrag, Datum, Ja/Nein oder eine Auswahl erwartet wird.</li>
      <li><strong>Extraktionshinweise:</strong> beschreibt in einfachen Worten, wo oder wie die Angabe erkannt werden soll.</li>
    </ul>
    <p>Mit den Pfeilen lässt sich die Reihenfolge ändern. Die Vorschau zeigt das spätere Ergebnis. Erst <strong>Konfiguration speichern</strong> übernimmt die Änderungen.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>5. Verarbeitung kontrollieren</h2></div></div>
    <p>Die <a href="/">Übersicht</a> zeigt das Verarbeitungsprotokoll. Über den Instanzfilter und die Suche lässt sich ein bestimmtes Dokument finden.</p>
    <ul>
      <li><strong>Erfolgreich:</strong> der Schritt wurde abgeschlossen.</li>
      <li><strong>In Bearbeitung:</strong> die Verarbeitung läuft noch.</li>
      <li><strong>Fehlgeschlagen:</strong> der Eintrag öffnen und Dateiname, Phase, Zeitpunkt und Fehlerklasse notieren.</li>
    </ul>
    <p>Bei einer Supportanfrage niemals API-Token, Passwörter, Webhook-Secrets oder vertrauliche Dokumentinhalte mitsenden.</p>
  </section>

  <section class="panel">
    <div class="section-heading"><div><h2>6. Benutzer verwalten</h2></div></div>
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
      <dt><strong>Ein Paperless-Feld fehlt</strong></dt>
      <dd>Das Feld zuerst in Paperless anlegen und danach die Feldseite in eZEUS neu laden.</dd>
      <dt><strong>Ein Dokument wird nicht verarbeitet</strong></dt>
      <dd>Prüfen, ob die Instanz aktiv ist und der Workflow auf „Dokument hinzugefügt“ reagiert. Danach das Verarbeitungsprotokoll öffnen.</dd>
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
