"""Monitoring tables (PostgreSQL schema `monitoring`): pipeline_execution_logs, data_quality_results, ingestion_history, source_coverage_report,
pipeline_state. The schema is never dropped by the warehouse rebuild, so run history survives reloads."""
from __future__ import annotations

import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd
import psycopg

from ..config import DATA
from ..warehouse.load import _copy, dsn

DDL = """
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE TABLE IF NOT EXISTS monitoring.pipeline_execution_logs (
  log_id bigserial PRIMARY KEY, run_id text NOT NULL, step text NOT NULL, attempt int NOT NULL, status text NOT NULL CHECK (status IN ('success','failed','skipped')),
  started_at timestamptz NOT NULL, finished_at timestamptz NOT NULL, duration_seconds numeric, rows_processed bigint, detail text, error text);
CREATE TABLE IF NOT EXISTS monitoring.data_quality_results (
  result_id bigserial PRIMARY KEY, run_id text NOT NULL, checked_at timestamptz NOT NULL, layer text NOT NULL, table_name text NOT NULL, check_name text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('critical','warning')), status text NOT NULL CHECK (status IN ('pass','fail')), failed_rows bigint, total_rows bigint, detail text);
CREATE TABLE IF NOT EXISTS monitoring.ingestion_history (
  path text NOT NULL, original_name text, source text, sha256 text NOT NULL, size_bytes bigint, version int NOT NULL, ingested_at timestamptz, excluded_ucl boolean,
  origin text, PRIMARY KEY (path, version));
CREATE TABLE IF NOT EXISTS monitoring.source_coverage_report (
  run_id text NOT NULL, generated_at timestamptz NOT NULL, season_id text NOT NULL, competition_id text NOT NULL, expected_matches int, matches_in_dataset int,
  matches_played int, matches_coming_soon int, pct_referee numeric, pct_venue numeric, pct_attendance numeric, pct_lineups numeric, pct_events numeric,
  pct_team_stats numeric, pct_man_of_match numeric, pct_events_with_coordinates numeric, goal_events int, goal_events_with_player int, awards int,
  coverage_flag text NOT NULL, PRIMARY KEY (run_id, season_id));
ALTER TABLE monitoring.source_coverage_report ADD COLUMN IF NOT EXISTS goals_recorded int;
ALTER TABLE monitoring.source_coverage_report ADD COLUMN IF NOT EXISTS pct_goals_with_event numeric;
CREATE TABLE IF NOT EXISTS monitoring.pipeline_state (key text PRIMARY KEY, value text, updated_at timestamptz DEFAULT now());
"""


def connect():
    return psycopg.connect(dsn())


def ensure_schema():
    with connect() as c:
        c.execute(DDL)


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:6]


def get_state(key: str):
    with connect() as c:
        r = c.execute("SELECT value FROM monitoring.pipeline_state WHERE key=%s", (key,)).fetchone()
    return r[0] if r else None


def set_state(key: str, value: str):
    with connect() as c:
        c.execute("INSERT INTO monitoring.pipeline_state(key,value,updated_at) VALUES (%s,%s,now()) "
                  "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()", (key, value))


def _log(run_id, step, attempt, status, t0, rows=None, detail=None, error=None):
    t1 = datetime.now(timezone.utc)
    with connect() as c:
        c.execute("INSERT INTO monitoring.pipeline_execution_logs(run_id,step,attempt,status,started_at,finished_at,duration_seconds,rows_processed,detail,error) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (run_id, step, attempt, status, t0, t1, round((t1 - t0).total_seconds(), 2), rows, detail, error))


def run_step(run_id: str, step: str, fn, retries: int = 2, backoff: float = 2.0):
    """Run fn() with retries; every attempt is logged. fn returns a dict that may contain rows / detail / skipped. Raises after the last failure."""
    for attempt in range(1, retries + 2):
        t0 = datetime.now(timezone.utc)
        try:
            out = fn() or {}
            _log(run_id, step, attempt, "skipped" if out.get("skipped") else "success", t0, out.get("rows"), out.get("detail"))
            return out
        except Exception as e:
            _log(run_id, step, attempt, "failed", t0, error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}")
            if attempt > retries or getattr(e, "no_retry", False):
                raise
            time.sleep(backoff * attempt)


def record_quality(run_id: str, rows: list[dict]):
    if not rows:
        return
    now = datetime.now(timezone.utc)
    with connect() as c, c.cursor() as cur:
        cur.executemany("INSERT INTO monitoring.data_quality_results(run_id,checked_at,layer,table_name,check_name,severity,status,failed_rows,total_rows,detail) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      [(run_id, now, r["layer"], r["table"], r["check"], r["severity"], r["status"], r.get("failed_rows"), r.get("total_rows"), r.get("detail")) for r in rows])


def load_ingestion_history() -> int:
    """Replace monitoring.ingestion_history with the Bronze register (idempotent)."""
    h = pd.read_csv(DATA / "bronze" / "ingestion_history.csv")
    with connect() as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE monitoring.ingestion_history")
            cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='monitoring' AND table_name='ingestion_history'")
            h = h[["path", "original_name", "source", "sha256", "size_bytes", "version", "ingested_at", "excluded_ucl", "origin"]]
            buf_rows = _copy_monitoring(cur, "ingestion_history", h)
    return buf_rows


def _copy_monitoring(cur, table, df):
    import io
    df = df.copy()
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    with cur.copy(f"COPY monitoring.{table} ({','.join(df.columns)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
        cp.write(buf.read())
    return len(df)
