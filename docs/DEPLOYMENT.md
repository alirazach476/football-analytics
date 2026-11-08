# Deployment (free)

| Part | Where | Notes |
|---|---|---|
| React front end | **Vercel** — https://football-analytics-xi.vercel.app | project `football-analytics`, built from `frontend/`; `/api/*` is proxied to the API (see `frontend/vercel.template.json`) |
| API (FastAPI) | **this PC**, exposed by a Cloudflare quick tunnel | `python tools/serve_public.py` starts the API + tunnel and redeploys Vercel with the new tunnel address |
| Warehouse | local Docker Postgres (default) or **Neon** (free, 0.5 GB; a copy of the warehouse is loaded) | `--neon` with `FOOTBALL_DATABASE_URL` |
| Code | GitHub `alirazach476/football-analytics` | code, docs, tests, small runtime data; no raw/bronze data, no secrets |

The site works only while `serve_public.py` is running (a quick tunnel gets a new address every run, hence the redeploy). For an always-on API use `Dockerfile` + `render.yaml` (Render needs a card on file even for the free plan) or any host that runs the Docker image with `DATABASE_URL` set.

## Run
```
docker compose up -d                       # local warehouse (or use --neon)
python tools/serve_public.py               # API + tunnel + Vercel redeploy; keep it running
```
## Rebuild the shipped caches (after retraining or reloading data)
`PYTHONPATH=src python tools/prepare_render.py` writes `deploy/cache/*.pkl` (heavy ML caches) and `data/layer_counts_snapshot.json`.
## Reload Neon
`pg_dump -Fc` the local warehouse and `pg_restore --no-owner --no-privileges` it into the Neon database.

## Free-tier limits
Neon 0.5 GB (the warehouse is ~300 MB); Vercel hobby; the tunnel needs this PC on. Memory use of the API is about 190 MB at start-up and ~500 MB after the ML charts are opened (scikit-learn/statsmodels load lazily).
