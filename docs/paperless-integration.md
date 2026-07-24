# Paperless-Integration

eZEUS verwendet ausschließlich die offizielle HTTP-API von Paperless-ngx.
Unterstützt sind Dokumentabruf, Originaldownload, OCR-Inhalt und Custom Fields.

Paperless muss einen Webhook mit Dokument-ID und stabiler Event-ID senden. Das
Secret wird im Header `X-EZEUS-Webhook-Secret` übermittelt.

Vor dem Schreiben lädt der Connector das Dokument erneut. Bereits gefüllter
Inhalt und bereits gefüllte Custom Fields bleiben unverändert. HTTP-Fehler werden
in einheitliche Connectorfehler übersetzt; nur temporäre Verbindungs-, Timeout-
und Rate-Limit-Fehler werden automatisch wiederholt.
