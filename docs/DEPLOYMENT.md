# Deployment (free, always on)

| Part | Where | Notes |
|---|---|---|
| React front end | **Vercel**, https://football-analytics-xi.vercel.app | project `football-analytics`, built from `frontend/`; `/api/*` is proxied to the API project (`frontend/vercel.template.json`) |
| API (FastAPI) | **Vercel serverless Python function**, https://football-analytics-api.vercel.app | project `football-analytics-api`, bundle built by `tools/build_vercel_api.py`; reads `DATABASE_URL` (Neon, pooled endpoint) |
| Warehouse | **Neon** free Postgres (~300 MB of 0.5 GB) | a `pg_dump -Fc` of the local warehouse restored with `pg_restore --no-owner --no-privileges` |
| Code | GitHub `alirazach476/football-analytics` | code, docs, tests, models, reports and small runtime data; no raw/bronze data and no secrets |

Nothing depends on a personal machine. The free function sleeps when idle, so the first request after a quiet period can take about 10 s (cold start); later requests take about a second.

## Why the API fits a serverless function
* `fbplatform/db.py` holds the connection settings (no heavy imports); scikit-learn, statsmodels and the mlflow tracking import are loaded lazily; the build uses `xgboost-cpu` and has no pyarrow, shap, mlflow, dbt or dagster (`deploy/vercel/requirements.txt`).
* Heavy ML objects (scoring the test period, SHAP, event-level player stats) are pre-computed into `deploy/cache/*.pkl`; the silver tables the engineering charts read ship as small pickles (`data/silver_pkl`) and the layer row counts as `data/layer_counts_snapshot.json`.
* Queries reuse one connection per thread (`prepare_threshold=None`, safe behind Neon's PgBouncer pooler).

## Update the deployment
```
docker compose up -d                                   # local warehouse (source of truth)
PYTHONPATH=src python tools/prepare_render.py          # refresh pickles + snapshot after retraining / reloading data
python tools/build_vercel_api.py                       # builds build/vercel_api
cd build/vercel_api && vercel deploy --prod --yes      # first time: vercel link --yes --project football-analytics-api
                                                       #             vercel env add DATABASE_URL production   (Neon pooled connection string)
python tools/deploy_vercel.py https://football-analytics-api.vercel.app --prod    # front end, proxied to the API
```
Reload Neon after a data refresh: `pg_dump -Fc --no-owner --no-privileges` the local warehouse, then `pg_restore --clean --if-exists --no-owner --no-privileges -d <neon direct url>`.

## Alternatives
* `Dockerfile` + `render.yaml`: the same API as a container on Render or any Docker host (`DATABASE_URL` set; Render needs a card on file even for its free plan).
* `tools/serve_public.py`: serve the API from a PC through a Cloudflare quick tunnel (no longer needed).

## Limits
Vercel hobby function: 1 GB memory, 60 s maximum duration. Neon free: 0.5 GB storage. The API needs about 190 MB at start-up and about 500 MB after the ML charts are opened.
