# API image for a free 512 MB host (Render). The warehouse is a separate hosted Postgres (DATABASE_URL); heavy ML caches ship as pickles in deploy/cache.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg MLFLOW_DISABLE_AGENT_HINT=1 MALLOC_ARENA_MAX=2 PYTHONPATH=/app/src FB_CACHE_DIR=/app/deploy/cache
WORKDIR /app
COPY deploy/requirements-api.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY models ./models
COPY reports ./reports
COPY sql ./sql
COPY data/registry ./data/registry
COPY data/silver ./data/silver
COPY data/layer_counts_snapshot.json ./data/layer_counts_snapshot.json
COPY deploy/cache ./deploy/cache
CMD ["sh", "-c", "uvicorn fbplatform.api.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
