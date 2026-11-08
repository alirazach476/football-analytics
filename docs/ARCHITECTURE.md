# Architecture

## Layers (medallion)

| Layer | Location | Contents | Rules |
|---|---|---|---|
| **Bronze** | `data/raw/**`, `data/bronze/` | every downloaded source file; `ingestion_history.csv` (path, source, URL, SHA-256, size, version, time); frozen snapshots of the collected tables in `data/bronze/collected/v<n>/` (read-only) | immutable: a changed file becomes version n+1, an unchanged file adds nothing; UEFA Champions League files are registered but flagged `excluded_ucl` and never reach Silver |
| **Silver** | `data/silver/*.parquet` | matches, teams, players (canonical), player_xref, events, lineups, squads, awards, venues, team/player match stats | built **only** from the Bronze snapshot; raw values kept in `*_raw` columns; nothing dropped; scheduled fixtures kept |
| **Warehouse** | PostgreSQL schema `wh` | 10 dimensions + 8 facts (+ name history, player xref, load log) | surrogate keys, PK/FK/CHECK constraints, indexes; rebuilt idempotently from Silver |
| **Gold** | PostgreSQL schemas `staging`, `intermediate`, `gold` (dbt) | 11 marts: match, team, player performance; tournament summary; goal analysis; competition comparison; head-to-head; player career; knockout; group stage; upcoming fixtures | dbt tests (unique, not_null, relationships, accepted_values, arithmetic and reconciliation tests) |
| **Monitoring** | PostgreSQL schema `monitoring` | `pipeline_execution_logs`, `data_quality_results`, `ingestion_history`, `source_coverage_report`, `pipeline_state` | survives warehouse rebuilds |

## Silver standardisation (what changes, what never does)

* Entity resolution of **teams** (R0–R4 rules in `docs/entity_resolution.md`) and **players**: D1 same normalised name + date of birth; D2 name containment (≥2 tokens) + shared national team + non-conflicting DOB + never in one line-up. Canonical id priority StatsBomb > Wyscout > Fjelstul > squad. Every original id stays in `player_xref` with its rule.
* Wyscout names double-escaped (`\uXXXX`) are decoded; the raw value is kept.
* Enrichments, each with provenance and never overwriting a source value: martj42 assist names (461 goals), shoot-out winners (martj42, 68 matches, 0 conflicts with known penalty scores), goal scorers and Wikipedia line-up rows linked to players by squad-name match (`player_id_source = squad_name_match`; unique matches only), minutes derived for Wikipedia line-ups from substitution/card times (`minutes_basis`).
* `match_status` ∈ {completed, scheduled}; scheduled rows get `status_label = 'Coming soon'` and a `fixture_detail` sentence.

## Data flow of one pipeline run

```text
bronze (register files, snapshot)  →  silver (skipped if snapshot + Silver code unchanged)  →  validate (Pandera: critical failures stop here)
   →  warehouse load (skipped if Silver unchanged)  →  dbt build (staging, intermediate, marts, 115 tests)  →  coverage report
every step: retries (not for bad data), logged to monitoring.pipeline_execution_logs; checks logged to monitoring.data_quality_results
```
Orchestration: `fbplatform.orchestration.steps.run_pipeline()` (plain) and the same steps as Dagster assets (`dagster_defs.py`, daily schedule defined but stopped by default). Configuration only via environment variables (`WH_HOST/PORT/USER/PASSWORD/DB`, `FB_FORCE`).

## Key design decisions and why

| Decision | Reason |
|---|---|
| PostgreSQL in Docker (port 5442) | spec requires PostgreSQL; the machine had no native install; 5432/5433 are used by other projects |
| Dagster, not Prefect | already installed; asset lineage fits the layered design |
| One event provider per match and event class | prevents double counting (priority: full events > Fjelstul > OpenFootball > martj42 > Wikipedia) |
| Result = recorded score (extra time in, shoot-out out) | consistent across sources; shoot-out winners stored separately |
| Wikipedia only fills nulls | secondary source; conflicts are reported, never silently resolved |
| Derived standings labelled with their rules | no official tables were collected |
| Scheduled fixtures kept, never modelled | user requirement; they have no outcome |
| No scraping of FIFA/UEFA/CONMEBOL/Forza/Google | their terms/robots prohibit it; licensed/open datasets and the official Wikipedia API are used instead |

## Testing strategy

Unit (parsers, Elo, statistics helpers), integration (warehouse reconciliation vs Silver, dbt build, Pandera negative tests, retries), end-to-end (second pipeline run skips unchanged work, Dagster materialises assets in lineage order), ML (leakage test, chronological split, quick end-to-end training, saved-model metadata), dashboard (every query, every page rendered headless with Streamlit AppTest) and original-data integrity (raw files re-hashed against the Bronze register).
