# Football Data Platform

A data-engineering, data-science and analytics platform for **men's international tournament football**: FIFA World Cup (2002–2026), UEFA Euro (2000–2028), Copa América (2001–2028) and UEFA Nations League (2018-19 to 2026-27). The UEFA Champions League was removed from scope on 2026-11-05 and is excluded everywhere (its cached source files are kept on disk, flagged, never processed).

**Golden rules of this project:** nothing is invented (missing data stays NULL and is reported); every record keeps its provenance; the original collected data is never modified; upcoming fixtures are kept and shown as **"Coming soon"** with whatever is known; model output is always labelled as a prediction.

## At a glance (see `docs/DATA_QUALITY.md` for the live numbers)

| | |
|---|---|
| Matches | 1,830 = 1,779 played + 51 **Coming soon** (Euro 2028) |
| Teams / players | 103 national teams / 8,410 canonical players (after entity resolution) |
| Goals / events | 4,494 recorded goals / 1,033,220 event rows |
| Warehouse | PostgreSQL star schema `wh` (8 dimensions, 8 facts) + dbt Gold marts (11) + monitoring schema |
| Quality | 13 Pandera checks (Silver) + 115 dbt tests/models (Gold) + PostgreSQL constraints |
| Tests | automated unit, integration, end-to-end, ML, dashboard, visualization and data-integrity tests (see `python -m pytest -q`) |

## Architecture

```text
 sources (open datasets, Wikipedia API)            Bronze                  Silver                    Warehouse (PostgreSQL)         Gold (dbt)            Consumers
 OpenFootball · martj42 · Fjelstul · StatsBomb ─►  immutable register ─►   cleaned, standardised, ─► star schema wh.*, surrogate ─► staging → intermediate ─► Streamlit dashboard (7 pages)
 Wyscout · Wikipedia en/es                         (SHA-256, versions,     entity-resolved           keys, constraints              → 11 marts + tests      EDA notebooks, statistics
                                                    frozen snapshots)      (raw values kept)                                                                ML (features → models → MLflow)
                                       Dagster assets / plain runner  ·  Pandera validation  ·  monitoring.* tables  ·  retries, idempotent, env-var config
```
Details: `docs/ARCHITECTURE.md`.

## Quick start

```bash
# 1. environment (Python 3.12)
pip install -r requirements.txt && pip install -e .
# 2. warehouse (Docker): host port 5442, credentials from .env / defaults in docker-compose.yml
docker compose up -d
# 3. build everything from the data already collected: Bronze -> Silver -> validate -> warehouse -> dbt -> coverage report
set PYTHONPATH=src            # PowerShell: $env:PYTHONPATH="src"
python -m fbplatform.orchestration.steps          # add --force to rebuild regardless of "unchanged input"
# 4. analysis and models (each writes into reports/ and models/)
python -m fbplatform.analysis.eda
python -m fbplatform.analysis.stats
python -m fbplatform.ml.outcome && python -m fbplatform.ml.goals && python -m fbplatform.ml.clustering && python -m fbplatform.ml.players
python -m fbplatform.analysis.advanced
# 5. dashboard
streamlit run src/fbplatform/dashboard/app.py
# or the React dashboard (themed per tournament): python -m uvicorn fbplatform.api.main:app --port 8000  -> see docs/REACT_DASHBOARD_GUIDE.md
# 6. orchestration UI / experiment UI / docs
dagster dev -m fbplatform.orchestration.dagster_defs
mlflow ui --backend-store-uri sqlite:///mlflow.db
cd dbt/football_dbt && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .
# 7. tests (the warehouse must be running for the integration/dashboard tests; they skip otherwise)
python -m pytest -q
```
Refresh the generated documents (data dictionary, schema, quality, science and model reports) with `python -m fbplatform.docs_gen`.

## Repository map

| Path | What |
|---|---|
| `src/fbplatform/ingest/`, `sources/`, `registry.py`, `pipeline.py`, `rebuild.py` | collection and normalisation of the source data (network stages are rate-limited and respect each source's terms) |
| `src/fbplatform/medallion/` | Bronze register + snapshots, Silver builder (entity resolution, assists, shoot-out winners, scorer/line-up linking, derived minutes) |
| `src/fbplatform/warehouse/`, `sql/warehouse_schema.sql`, `docker-compose.yml` | PostgreSQL warehouse |
| `dbt/football_dbt/` | staging, intermediate, Gold marts, tests, docs |
| `src/fbplatform/validation/`, `monitoring/`, `orchestration/` | Pandera, monitoring tables, pipeline steps, Dagster assets |
| `src/fbplatform/analysis/` | EDA, statistics (10 required questions), advanced projects A–E |
| `src/fbplatform/ml/` | leakage-free features, 5 ML projects, explainability, MLflow tracking |
| `src/fbplatform/dashboard/` | Streamlit app (queries, lib, 7 analytics views + 7 visualization-lab views) |
| `src/fbplatform/api/` + `frontend/` | FastAPI backend and the React dashboard (tournament pages themed from the logos, WC 2030 coming-soon page) |
| `src/fbplatform/viz/` | reusable chart modules (competition, teams, players, matches, statplots, mlplots, engineering), filters, export |
| `notebooks/` | 5 executed notebooks (EDA, statistics, features/models, advanced) |
| `reports/`, `models/`, `data/` | generated reports, saved models, Bronze/Silver/processed data (git-ignored artefacts) |
| `docs/` | the documentation set below |

## Documentation

`docs/ARCHITECTURE.md` · `VISUALIZATION_GUIDE.md` · `DATA_DICTIONARY.md` · `DATA_SOURCES.md` · `DATA_QUALITY.md` · `DATABASE_SCHEMA.md` · `PIPELINE_GUIDE.md` · `DATA_SCIENCE_REPORT.md` · `STATISTICAL_REPORT.md` · `MODEL_DOCUMENTATION.md` · `DASHBOARD_GUIDE.md` · plus collection-phase notes `entity_resolution.md`, `event_coverage.md`, `data_dictionary_matches.md`.

## What the data can and cannot do (honest summary)

* **Strong:** match results, stages, referees, venues, attendance for all four competitions; goals for every match; squads, line-ups, cards and substitutions for most World Cup/Euro/Copa matches; full event data with coordinates for 313 matches (StatsBomb/Wyscout).
* **Weak or absent:** Nations League group matches have goals only (no line-ups/cards/substitutions; scorers are names without player ids); possession, VAR and (outside StatsBomb) xG are not available; half-time scores exist only for WC and Euro; extra time is not recorded for the Nations League; man of the match is missing for Copa 2001–2007.
* **Modelling reality:** tournament football gives few matches per team. Match-outcome models reach ~55–57% accuracy on three outcomes and **do not clearly beat a one-feature Elo baseline**; goal totals are barely predictable beyond the base rate. These are findings, not failures to hide.
* **Not collected on purpose:** FIFA, UEFA and CONMEBOL websites (their terms prohibit scraping), Forza Football (blocks bots), Google results (robots/ToS). See `docs/DATA_SOURCES.md`.

## History

The collection phase (OpenFootball, martj42, Fjelstul, StatsBomb, Wyscout, Wikipedia match boxes/details/squads/venues) and its validation are described in `docs/entity_resolution.md`, `docs/event_coverage.md` and `docs/DATA_QUALITY.md`. Platform phases: inventory and quality investigation → Bronze/Silver → PostgreSQL → dbt → pipeline/monitoring → EDA and statistics → features and ML → dashboard and documentation.
