# Paperless-Integration

eZEUS verwendet ausschließlich die offizielle HTTP-API von Paperless-ngx.
Unterstützt sind Dokumentmetadaten, der bereits von Paperless erzeugte
OCR-Inhalt, Custom Fields, Korrespondenten und die verwaltete Webhook-Workflow-
Konfiguration. Originaldateien werden bewusst weder heruntergeladen noch
geparst; Binärdatei-, Malware- und PDF-Bomb-Schutz verbleiben bei Paperless.

Standardmäßig bleibt der bisherige Ablauf erhalten: Ein neu hinzugefügtes
Dokument startet eZEUS direkt. Die Paperless-gpt-Übergabe ist eine optionale
Erweiterung pro Paperless-Instanz und niemals eine globale Voraussetzung.

Ist die Erweiterung aktiviert, startet das frei konfigurierbare
OCR-Abschluss-Tag den eZEUS-Webhook. Setzt Paperless-gpt dieses Tag selbst, kann
das optionale OCR-Eingangstag leer bleiben. Benötigt eine Instanz wie der
ff-Pilot ein Eingangstag, setzt der verwaltete Eingangsworkflow diesen
instanzbezogenen Tag zusammen mit `ezeus-ai-2-ocr-pending`. Sobald
Paperless-gpt das Eingangstag entfernt, setzt der Abschlussworkflow das
konfigurierte OCR-Abschluss-Tag. Tag-Namen wie `3` sind damit keine festen
Programmwerte.

Erst das Abschluss-Tag startet den eZEUS-Webhook. Danach setzt der Workflow
zusätzlich `ezeus-ai-2-ocr-triggered` und entfernt einen eventuell verbliebenen
Pending-Marker. Dadurch lösen spätere Metadatenänderungen dasselbe Dokument
nicht unbeabsichtigt erneut aus.

Auch die manuelle Neuverarbeitung ist optional und pro Instanz konfigurierbar.
Im ff-Pilot wird dafür der Tag-Name `9` verwendet. Wird er einem bestehenden
Dokument hinzugefügt, sendet Paperless dessen ID erneut an eZEUS und entfernt
das Tag danach automatisch. Andere Instanzen können die Funktion deaktiviert
lassen oder einen anderen Tag-Namen verwenden. Die installationsabhängige
interne Paperless-ID wird automatisch ermittelt.

Paperless muss einen Webhook mit Dokument-ID und stabiler Event-ID senden. Das
Secret wird im Header `X-EZEUS-Webhook-Secret` übermittelt.

Vor dem Schreiben lädt der Connector das Dokument erneut. Bereits gefüllter
Inhalt und bereits gefüllte Custom Fields bleiben unverändert. Der Dokumenttitel
wird nur geschrieben, wenn er leer ist oder dem ursprünglichen Dateinamen
entspricht; ein manuell gesetzter Titel wird nicht überschrieben. Dieses
Verhalten kann pro Instanz mit der Option `allow_title_overwrite` aufgehoben
werden. HTTP-Fehler werden in einheitliche Connectorfehler übersetzt; nur
temporäre Verbindungs-, Timeout- und Rate-Limit-Fehler werden automatisch
wiederholt.
