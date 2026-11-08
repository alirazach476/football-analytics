# Pipeline guide

## Prerequisites

* Python 3.12 and `pip install -r requirements.txt && pip install -e .`
* Docker Desktop running; `docker compose up -d` starts PostgreSQL 16 as container `football_warehouse` on **host port 5442** (change via `WH_PORT` in `.env`).
* Environment variables (all optional, defaults match `docker-compose.yml`): `WH_HOST`, `WH_PORT`, `WH_USER`, `WH_PASSWORD`, `WH_DB`; `FB_FORCE=1` ignores "unchanged input" shortcuts; `PYTHONPATH=src` when running modules.

## Running

| Goal | Command |
|---|---|
| Full pipeline (plain runner) | `python -m fbplatform.orchestration.steps` (`--force` to rebuild all) |
| Same steps in the Dagster UI | `dagster dev -m fbplatform.orchestration.dagster_defs` → materialise `football_full_refresh`; schedule `daily` (06:00) is defined but stopped |
| Only Bronze | `python -m fbplatform.medallion.bronze` |
| Only Silver | `python -m fbplatform.medallion.silver` |
| Only warehouse | `python -m fbplatform.warehouse.load` (drops and recreates schema `wh`; then run dbt, because the dbt views depend on it) |
| Only dbt | `cd dbt/football_dbt && dbt build --profiles-dir .` |
| Docs for dbt (lineage) | `dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .` |

## Steps, in order

1. **bronze:** register every file under `data/raw` and the collected tables (SHA-256, version), snapshot the collected tables to `data/bronze/collected/v<n>/` when anything changed, reload `monitoring.ingestion_history`.
2. **silver:** rebuild from the latest snapshot — *skipped* when the snapshot **and the Silver code** are unchanged.
3. **validate_silver:** Pandera. Critical failures raise `CriticalDataQualityError` (no retry) and stop the run before the warehouse is touched; warning-level failures are recorded.
4. **warehouse:** load all `wh` tables — *skipped* when Silver is unchanged.
5. **dbt_gold:** `dbt build` (models + tests). Any error fails the run.
6. **coverage_report:** per-edition coverage written to `monitoring.source_coverage_report` with a flag per season.

Every attempt is logged in `monitoring.pipeline_execution_logs` (status success/failed/skipped, duration, rows, error). Transient failures are retried (default 2); bad data is never retried.

## Idempotence and incremental behaviour

Re-running changes nothing when inputs are unchanged (Bronze registers 0 files; Silver and the warehouse are skipped; dbt re-runs in ~10 s). A changed source file becomes a new Bronze version; a new Bronze snapshot triggers Silver → warehouse → dbt. The warehouse load is a full rebuild by design (the dataset is small); surrogate keys are deterministic so rebuilds produce identical keys.

## Adding or refreshing source data

The scheduled pipeline starts from the data **already collected**. Network collection (Wikipedia API, open datasets) is separate and rate-limited: `python -m fbplatform.pipeline` (fetch + build, resumable, cached under `data/raw`) or `python -m fbplatform.rebuild` (rebuild all derived tables from the downloaded cache, ~15 minutes, lock-file protected). After collecting, run the pipeline above.

## Monitoring

Dashboard page **Data engineering** shows run history, ingestion status, check results, coverage/missing data, duplicates, table sizes and freshness. Direct SQL: `select * from monitoring.pipeline_execution_logs order by log_id desc;`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `relation "staging.stg_matches" does not exist` | the warehouse was reloaded without dbt: `cd dbt/football_dbt && dbt build --profiles-dir .` |
| `port is already allocated` | another container uses the port: set `WH_PORT` in `.env` |
| Silver did not pick up a code change | the pipeline hashes `silver.py`; for other modules use `--force` |
| Critical data-quality error | read `monitoring.data_quality_results` (`status='fail'`) — fix the data, do not relax the check |
| Tests skipped | the warehouse is not running (`docker compose up -d`) |
