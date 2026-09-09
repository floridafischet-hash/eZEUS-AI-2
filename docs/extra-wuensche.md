# Extra Wünsche

Sammlung offener Verbesserungswünsche und Analyse-Notizen, die (noch) nicht
Teil des offiziellen Roadmap-/Backlog-Prozesses sind. Reihenfolge = Zeitpunkt
der Erfassung, neueste oben.

---

## 2026-09-07 · Rechnungsbetrag-Extraktion („Rechnungsbetrag wird nicht ausgelesen / geschrieben")

### Auslöser

Produktive Instanz `https://212.227.20.171:18794/` (eZEUS-AI-2) zeigt viele
Jobs mit Status `COMPLETED_WITH_WARNINGS`. Bei ~19 % der Läufe (196 von
1043 Jobs) wird `invoice_amount` – und häufig zusätzlich `invoice_number` /
`construction_site_number` – nicht in Paperless geschrieben, weil der
Regex-Extractor keinen Kandidaten findet und kein KI-Fallback greift.

Beispiel-Layout, das reihenweise fehlschlägt:
`2026-09-04 team baucenter raisa GmbH & Co. KG Rechnung RG3301234656 …pdf`
→ `missing_fields: [construction_site_number, invoice_number, invoice_amount]`.

### Bestehende Regex-Konfiguration (alle Instanzen)

Zentral definiert in `core/templates/automatic.py`, `FIELD_DEFINITIONS`
→ `rechnungsbetrag` → `patterns`. Wird via `config_from_custom_fields()` für
**jede** Paperless-Instanz identisch verwendet (kein Per-Instance-Override in
`instance_field_configs.options` / `extraction_instructions` /
`extraction_profile` – geprüft für `tj-ezeus-dms-de`, `ff-ezeus-dms-de`,
`ff-ezeus-dms-de-2`, `rr-ezeus-dms-de`).

Auswahlstrategie: `highest` · Validators: `not_empty`, `monetary_amount`
· `minimum_confidence: 0.55`.

Aktive Muster:

1. Zeilenpaar „Gesamt …"

   ```regex
   (?im)^\s*Gesamt\s+(?:[\d.,]+\d{2}\s*(?:EUR|€)?\s+)?([\d.,]+\d{2})\s*(?:EUR|€)?\s*$
   ```

2. „Übertrag: …"

   ```regex
   (?im)^\s*Übertrag\s*:\s*(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€|Euro)?\s*$
   ```

3. „Fälligkeitsdatum … Summe: …"

   ```regex
   (?im)^\s*Fälligkeitsdatum\s*:\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s+Summe\s*:\s*(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€)?\s*$
   ```

4. „Artikel: N Total: …"

   ```regex
   (?im)^\s*Artikel\s*:\s*\d+\s+Total\s*:\s*(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€)?\s*$
   ```

5. Isoliertes „Brutto …" (mit negativem Lookbehind für „Endsumme brutto" und
   „Gesamtbetrag brutto", damit dort Muster 6 greift):

   ```regex
   (?i)(?<!Endsumme )(?<!Gesamtbetrag )\bBrutto\s*[:.]?\s*(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€)?
   ```

6. Gesamt-/Zahlbetrags-Alternativen:

   ```regex
   (?i)(?:
     Brutto[\s.-]*Rechnungsbetrag|
     Bruttobetrag|
     Endsumme\s+brutto|
     Gesamtbetrag|
     Gesamtbetrag\s+brutto|
     Gesamtsumme|
     Gesamtrechnungsbetrag|
     Rechnungswert\s*\(\s*brutto\s*\)|
     Zahlbetrag|
     Endbetrag|
     Zu\s+zahlen|
     (?<!Netto[ -])(?<![\w-])Rechnungsbetrag
   )\s*[:.]?\s*(?:EUR|€)?\s*([\d.,]+\d{2})\s*(?:EUR|€)?
   ```

### Beobachtete Lücken

* Layouts mit reinem Zeilentotal ohne Anker („1.493,39 €" allein am
  Zeilenende, Gesamt-Zeile in Tabellenform ohne Schlüsselwort).
* US-formatierte Beträge ohne Anker (`1304.48`).
* „Rechnungssumme", „Summe brutto", „Netto/Brutto"-Tabellen mit „Brutto"
  als reine Spaltenüberschrift (dort trifft nichts, weil Muster 5/6 einen
  Wert in derselben Zeile erwartet).
* Handschriftliche/OCR-schwache Belege ohne konsistente Whitespace-Struktur.
* Provider-Nutzung laut DB: `regex` 2149× vs. `ollama` nur 7× – das heißt
  der geplante KI-Fallback ist praktisch nicht aktiv, weil in allen
  `instance_field_configs` `ai_enabled = false` steht.

### Wünsche / Vorschläge

1. **KI-Fallback aktivieren:** Für `invoice_amount`, `invoice_number`,
   `construction_site_number` `ai_enabled = true` als Default bzw. per
   Migration setzen. Regex-first, Ollama nur wenn kein Kandidat.
2. **Muster erweitern** (in `automatic.py`), u. a.:
   * „Rechnungssumme", „Summe brutto", „Rechnungs-Endbetrag"
   * Anker „inkl. MwSt", „inkl. USt", „inklusive Mehrwertsteuer"
   * US-Notation mit Punkt und ohne Tausendertrenner
3. **Per-Instance-Overrides** wirklich nutzen: Zusätzliche Muster/Beispiele
   in `instance_field_configs.extraction_instructions` erlauben, damit
   Sonderlayouts (`team baucenter raisa`, `custom_6ef0f2502a22` etc.)
   ohne globalen Code-Change fixbar sind.
4. **Eval-Set aufbauen:** Die 196 aktuellen `COMPLETED_WITH_WARNINGS`
   samt Ground-Truth-Beträgen als Fixture ablegen, damit jede Regex-/
   Prompt-Änderung gegen historische Fälle getestet werden kann, bevor
   sie live geht.
5. **Metrics/Alerting:** Prometheus-Counter
   `extraction_missed_total{field=..., instance=...}` und Alert, wenn
   Warn-Quote > 10 %/h.
6. **Backfill:** Nach jedem Fix die betroffenen alten Jobs automatisch
   erneut verarbeiten, damit Beträge nachträglich in Paperless landen.

### Referenzen

* Quelle Regexe: `core/templates/automatic.py`, `FIELD_DEFINITIONS`
* DB-Sichten: `extraction_results`, `job_phases.metadata` (`missing_fields`)
* Betroffene Instanzen: `tj-ezeus-dms-de`, `ff-ezeus-dms-de`,
  `ff-ezeus-dms-de-2`, `rr-ezeus-dms-de`
