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
instanzbezogenen Tag zusammen mit einem frei benennbaren Wartemarker. Sobald
Paperless-gpt das Eingangstag entfernt, setzt der Abschlussworkflow das
konfigurierte OCR-Abschluss-Tag. Tag-Namen wie `3` sind damit keine festen
Programmwerte.

Erst das Abschluss-Tag startet den eZEUS-Webhook. Danach setzt der Workflow
zusätzlich ein frei benennbares Bereits-verarbeitet-Tag und entfernt einen
eventuell verbliebenen Wartemarker. Dadurch lösen spätere Metadatenänderungen
dasselbe Dokument nicht unbeabsichtigt erneut aus.

Auch die manuelle Neuverarbeitung ist optional und pro Instanz konfigurierbar.
Im ff-Pilot wird dafür der Tag-Name `9` verwendet. Wird er einem bestehenden
Dokument hinzugefügt, sendet Paperless dessen ID erneut an eZEUS und entfernt
das Tag danach automatisch. Andere Instanzen können die Funktion deaktiviert
lassen oder einen beliebigen anderen Tag-Namen wie `Günther` verwenden. Alle
Workflow-Tags werden pro Instanz in der eZEUS-Instanzverwaltung eingestellt;
ihre installationsabhängigen internen Paperless-IDs werden automatisch
ermittelt. Aktive Tags derselben Instanz müssen unterschiedliche Namen haben.

| Einstellung | Aufgabe | Nur aktiv, wenn |
|---|---|---|
| Paperless-gpt-Eingangstag | fordert die vorgelagerte OCR an | OCR-Handoff aktiv und Feld nicht leer |
| OCR-Wartemarker | kennzeichnet den wartenden OCR-Auftrag | ein Eingangstag verwendet wird |
| OCR-Abschluss-Tag | startet den automatischen eZEUS-Lauf | OCR-Handoff aktiv |
| Bereits-verarbeitet-Tag | verhindert automatische Wiederholungen | OCR-Handoff aktiv |
| Manuelles Trigger-Tag | startet eine einmalige Neuverarbeitung | manueller Trigger aktiv |

Änderungen werden unter **Instanzen → Bearbeiten** gespeichert. Danach muss
für genau diese Instanz **Workflow einrichten** ausgeführt werden. Der
Connector legt fehlende Tags an und aktualisiert ausschließlich die von eZEUS
verwalteten Workflows. Fremde Workflows und nicht mehr verwendete Tags werden
nicht gelöscht.

Eine Umbenennung verändert nur zukünftige Auslösungen. Das bisherige Tag bleibt
in Paperless erhalten und kann nach einer manuellen Prüfung dort entfernt
werden. Das manuelle Trigger-Tag wird dagegen nach jeder erfolgreichen
Webhook-Annahme automatisch vom Dokument entfernt, damit dasselbe Kommando
später erneut gesetzt werden kann.

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
