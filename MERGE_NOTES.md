# Merge GitHub → GitLab, 21.09.2026

GitHub (`floridafischet-hash/eZEUS-AI-2`) ist ab sofort Single Source of Truth.
GitLab (`wizard/e-zeus-ai-2`) enthält sieben Commits, die nie auf GitHub
angekommen sind. Dieses Dokument hält fest, was der Merge überschreibt und was
danach wieder eingebaut werden muss.

Bei Konflikten gewinnt GitHub. Unsere Arbeit wird nicht im Merge untergemischt,
sondern danach bewusst neu aufgesetzt.

| | |
|---|---|
| Merge-Basis | `6e7fd3c` |
| nur auf GitHub | 8 Commits, bis `e31529b` |
| nur auf GitLab | 7 Commits, bis `fc6a4c8` |
| echte Konflikte | `apps/api/dashboard.py`, `infrastructure/migrations/versions/0014_add_field_extraction_profile.py` |

## Blocker: `github/main` ist nicht lauffähig

`core/field_config/service.py` lässt sich auf GitHub nicht parsen:

```
core/field_config/service.py:434  expected an indented block after 'if' statement on line 433
```

Von 151 Python-Dateien auf `github/main` ist genau diese eine betroffen. Die drei
jüngsten GitHub-Commits (`5b67704`, `0fb7354`, `e31529b`) haben die Einrückung in
`_providers`/`by_name` zerschossen und dabei ein `providers.append(...)` doppelt
eingefügt.

Konsequenz: Direkt nach dem Merge scheitert `quality` an `ruff`/`mypy`/`pytest`,
es entsteht kein Image. Käme der Stand doch in den Cluster, stürbe jeder Pod beim
Import. **Das muss repariert werden, bevor irgendetwas gepusht wird** – am besten
auf GitHub, weil dort die Wahrheit liegt.

Die inhaltliche Absicht der drei Commits bleibt erhaltenswert: Über
`standard_field_key_for_label()` sollen importierte Paperless-Felder anhand ihres
Namens auf bekannte eZEUS-Standardfelder gemappt werden. Nur die Umsetzung ist
kaputt.

## Was der Merge überschreibt

### 1. Migration 0014 – Guard gegen `DuplicateColumn` (`125a12d`)

**Konflikt. Nichts nachzubauen – GitHub hat denselben Fix unabhängig gebaut.**

Beide Seiten lösen exakt dasselbe Problem: `0002_repair_initial_schema` ruft
`Base.metadata.create_all()` auf, dadurch existiert `extraction_profile` auf einer
frischen Datenbank schon, wenn 0014 die Spalte anlegen will. Der einzige
Unterschied ist die Faktorisierung – wir hatten einen Helper
`_has_extraction_profile()`, GitHub schreibt die Spaltenabfrage in `upgrade()` und
`downgrade()` je einmal aus.

Verloren geht damit nur der erklärende Kommentar und die Deduplizierung. Beides
verschmerzbar. **GitHub übernehmen.**

### 2. `dashboard.py` – mypy-Fehler (`abb8e62`)

**Konflikt. Nichts nachzubauen – GitHub hat denselben Fix unabhängig gebaut.**

`derive_step_warnings()` ist auf beiden Seiten **zeichengleich**, inklusive der
`isinstance(fields_written, int)`-Korrektur und der ruff-Umbrüche.

Unterschied nur beim Einsammeln von `job_warnings`:

* unsere Fassung sammelt an der Entstehungsstelle (`job_warnings.extend(step_warnings)` in der Schleife) und entfernt das Nachlesen aus dem fertigen `steps`-dict
* GitHub behält das Nachlesen und sichert es mit `isinstance` + `str()` ab

Beide sind typkorrekt und liefern dasselbe Ergebnis. **GitHub übernehmen.**

### 3. `core/field_config/profiles.py` – `ExtractionProfile` als TypedDict (`abb8e62`)

**Kein Konflikt – GitHub hat die Datei nicht angefasst, unsere Fassung überlebt den Merge automatisch.**

Trotzdem prüfen: Das TypedDict war die Voraussetzung dafür, dass
`field_type not in profile["field_types"]` in `schemas.py` typisiert ist. Wenn
GitHubs `service.py` daneben steht, muss mypy das noch zusammen abnehmen.

`validators` bleibt bewusst `list[dict[str, object]]` – `dict` ist in seinem
Value-Typ invariant, `list[dict[str, str]]` ließe sich sonst nicht extenden.

### 4. `core/field_config/service.py` – Signatur von `_validators` (`abb8e62`)

**Wieder einbauen.** Beide Seiten haben die Datei geändert, git merged sie
automatisch (verschiedene Regionen) – aber genau diese Datei ist die kaputte.
Sobald sie repariert ist, muss unsere Änderung erneut hinein:

```python
from core.field_config.profiles import ExtractionProfile, extraction_profile
...
    @staticmethod
    def _validators(
        field: InstanceFieldConfig,
        profile: ExtractionProfile | None = None,
    ) -> list[dict[str, object]]:
```

### 5. `.gitlab-ci.yml` – die komplette Pipeline (`9af26c3`, `e20083b`, `484cad0`, `fc6a4c8`)

**Kein Konflikt, aber Handlungsbedarf.** GitHub kennt nur die alte, 72-zeilige
Fassung mit ausschließlich dem `sync`-Stage. Geändert hat die Datei seit der
Merge-Basis nur GitLab, deshalb überlebt unsere Fassung den Merge unangetastet.

Inhalt, der dranhängt und nirgends sonst dokumentiert ist:

* `quality` (ruff, mypy, pytest, bandit, pip-audit `--strict`) und `migrations` gegen echtes PostgreSQL
* `build` mit **Kaniko statt dind**, weil die `docker`-Runner unprivilegiert sind – dind scheitert dort, bevor es startet
* `scan` mit Trivy **nach** dem Push, weil Kaniko direkt aus dem Build pusht
* Tag-Schema bewusst ohne `latest`: nur `:<short-sha>`, plus `:<tag>` bei Releases
* `build`/`scan` laufen nur bei Änderungen an Pfaden, die tatsächlich ins Image wandern
* keiner der CI-Jobs läuft auf dem Schedule – sonst würde der Sync-Takt die gesamte Pipeline mitziehen
* `sync_from_github` selbst

Weil GitHub Source of Truth ist, muss diese Datei **nach GitHub gespiegelt**
werden. Sonst überschreibt der nächste Sync sie wieder mit der alten Fassung und
die Historien divergieren erneut.

### 6. ruff-format-Korrekturen in `tests/unit/test_automatic_template.py` (`125a12d`)

Beide Seiten haben die Datei angefasst, kein Konflikt. Reine Umbrüche, keine
Logik. Nach dem Merge `ruff format --check` entscheiden lassen.

## Was tatsächlich passiert ist

Der Merge lief mit `-X theirs`. Das war gröber als gedacht: Die Option ersetzt nur
die *konfliktierenden* Hunks zugunsten von GitHub, unsere konfliktfreien Hunks aus
denselben Commits kamen trotzdem mit. Dadurch entstanden zwei Doppelungen, die in
der Reparatur wieder rausgeräumt wurden:

* `dashboard.py` hatte `job_warnings` zweimal annotiert – einmal unsere Sammlung
  in der Schleife, einmal GitHubs Nachlesen danach. GitHubs Variante bleibt.
* Migration 0014 hatte unseren Helper `_has_extraction_profile()` mitgenommen,
  benutzt wird aber GitHubs Inline-Abfrage. Helper entfernt.

Unsere `service.py`-Änderung (`ExtractionProfile`-Import und die `_validators`-
Signatur) hat der Merge dagegen von selbst wieder eingesetzt.

- [x] `core/field_config/service.py` repariert – Einrückung in drei Bereichen, doppeltes `providers.append(...)` entfernt, fehlende Leerzeilen ergänzt
- [x] `_validators(profile: ExtractionProfile | None)` – kam automatisch durch
- [x] `profiles.py` gegen GitHubs Code typgeprüft
- [x] `ruff format --check`, `ruff check`, `mypy` (93 Dateien), `pytest`, `bandit`, `pip-audit --strict` – alle grün
- [ ] Migrations-Roundtrip gegen PostgreSQL – lokal übersprungen, läuft nur in CI
- [ ] nach **beiden** Remotes pushen – erst wenn GitHub denselben Commit hat, greift der Fast-Forward-Guard im Sync-Job wieder
- [ ] `.gitlab-ci.yml` nach GitHub spiegeln
- [ ] neue Image-SHA in `flux/apps/prod/eZEUS-AI-2/deployment.yaml` eintragen

### Offene Unsicherheit

Die Rekonstruktion der Verzweigung in `_providers` stützt sich auf GitHubs
Einrückungsniveau und Kommentarposition, nicht auf einen Test – die mitgelieferte
`tests/unit/test_construction_site_patterns.py` prüft nur die Regex-Muster, nicht
den Fallback über `standard_field_key_for_label()`. Semantisch ist die Platzierung
unkritisch: Existiert ein Profil, ist `profile["patterns"]` nie `None`, der
Fallback greift also ohnehin nur im `else`-Zweig.

Zusätzlich musste `patterns: list[str] | None` explizit annotiert werden. GitHub
hatte den ursprünglichen Ternär-Ausdruck in ein `if`/`else` aufgetrennt; dabei
leitet mypy den Typ aus dem ersten Zweig ab und der `.get()`-Aufruf im zweiten
passt nicht mehr.

## Warum das überhaupt passiert ist

Der Sync-Job kann nur fast-forwarden und bricht bei divergenten Historien bewusst
ab, statt zu überschreiben. Jeder Commit, der direkt in GitLab landet, blockiert
ihn deshalb, bis er nach GitHub gespiegelt ist. Solange GitHub Source of Truth
ist, gilt: **erst GitHub, dann GitLab** – oder die Gegenrichtung automatisieren
(GitLab Push-Mirroring), statt sie von Hand nachzuziehen.
