# Paperless-Integration

eZEUS verwendet ausschließlich die offizielle HTTP-API von Paperless-ngx.
Unterstützt sind Dokumentmetadaten, der bereits von Paperless erzeugte
OCR-Inhalt, Custom Fields, Korrespondenten und die verwaltete Webhook-Workflow-
Konfiguration. Originaldateien werden bewusst weder heruntergeladen noch
geparst; Binärdatei-, Malware- und PDF-Bomb-Schutz verbleiben bei Paperless.

Paperless muss einen Webhook mit Dokument-ID und stabiler Event-ID senden. Das
Secret wird im Header `X-EZEUS-Webhook-Secret` übermittelt.

Vor dem Schreiben lädt der Connector das Dokument erneut. Bereits gefüllter
Inhalt und bereits gefüllte Custom Fields bleiben unverändert. HTTP-Fehler werden
in einheitliche Connectorfehler übersetzt; nur temporäre Verbindungs-, Timeout-
und Rate-Limit-Fehler werden automatisch wiederholt.
