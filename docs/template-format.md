# Templateformat

Templates werden als validiertes JSON in PostgreSQL gespeichert. Ein Template
gehört über die externe ID zu einem Paperless-Dokumenttyp.

Jedes Feld benötigt `target_field_id`, mindestens einen Provider und optional
Validatoren sowie `minimum_confidence`.

Provider:

- `regex`: `patterns`, optional `group` und `timeout_ms`
- `keyword`: `keywords`, `synonyms`, Kontextgrößen und `case_sensitive`

Validatoren:

- `not_empty`
- `required_pattern`
- `date`
- `monetary_amount`
- `iban`
- `allowed_values`
- `length`
- `numeric_range`

Unbekannte Provider und Validatoren werden beim Anlegen abgelehnt. Pro
Dokumenttyp darf über die API nur ein aktives Standardtemplate existieren.
