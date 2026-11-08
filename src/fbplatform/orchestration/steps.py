"""Pipeline steps shared by the plain runner and the Dagster assets. Configuration: environment variables only (WH_* for the warehouse,
FB_FORCE=1 to ignore the 'unchanged input' shortcuts). Every step is idempotent and logged to monitoring.pipeline_execution_logs.

Network ingestion (Wikipedia etc.) is NOT part of the scheduled run on purpose: it is rate-limited by the sources' terms and lives in
fbplatform.pipeline / rebuild; this pipeline starts from the data already collected.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pandas as pd

from ..config import DATA, ROOT
from ..medallion import bronze, silver
from ..monitoring import db
from ..validation import schemas
from ..warehouse import load as wh_load

DBT_DIR = ROOT / "dbt" / "football_dbt"


class CriticalDataQualityError(RuntimeError):
    no_retry = True                                     # retrying will not fix bad data


def force() -> bool:
    return os.environ.get("FB_FORCE", "0") == "1"


def _hash_dir(d: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(d.glob("*.parquet")):
        h.update(p.name.encode())
        with open(p, "rb") as f:
            while b := f.read(1 << 22):
                h.update(b)
    return h.hexdigest()


def step_bronze() -> dict:
    reg = bronze.register()
    snap = bronze.snapshot_collected()
    hist_rows = db.load_ingestion_history()
    return dict(rows=reg["registered"], detail=f"registered={reg['registered']} unchanged={reg['unchanged']} snapshot={snap} history_rows={hist_rows}")


def step_silver(force_run: bool = False) -> dict:
    snap = bronze.latest_snapshot().name + "|code=" + hashlib.sha256(Path(silver.__file__).read_bytes()).hexdigest()[:12]   # Silver code change => rebuild
    if not (force_run or force()) and db.get_state("silver_input_snapshot") == snap and (silver.SILVER / "matches.parquet").exists():
        return dict(skipped=True, detail=f"Bronze snapshot + Silver code ({snap}) unchanged since last Silver build")
    rep = silver.build()
    db.set_state("silver_input_snapshot", snap)
    return dict(rows=rep["matches"], detail=json.dumps({k: rep[k] for k in ("matches", "scheduled_kept", "players_silver", "events")}))


def step_validate(run_id: str) -> dict:
    results = schemas.validate()
    db.record_quality(run_id, results)
    bad = schemas.critical_failures(results)
    warn = [r for r in results if r["severity"] == "warning" and r["status"] == "fail"]
    if bad:
        raise CriticalDataQualityError("critical data-quality failures: " + "; ".join(f"{r['table']}:{r['check']} ({r['failed_rows']} rows)" for r in bad))
    return dict(rows=len(results), detail=f"{len(results)} checks, 0 critical failures, {len(warn)} warnings")


def step_warehouse(force_run: bool = False) -> dict:
    h = _hash_dir(silver.SILVER)
    if not (force_run or force()) and db.get_state("warehouse_input_hash") == h:
        return dict(skipped=True, detail="Silver unchanged since last warehouse load")
    out = wh_load.load()
    db.set_state("warehouse_input_hash", h)
    return dict(rows=sum(out.values()), detail=f"loaded {len(out)} tables")


def step_dbt(run_id: str) -> dict:
    r = subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=DBT_DIR, capture_output=True, text=True)
    m = re.search(r"PASS=(\d+) WARN=(\d+) ERROR=(\d+) SKIP=(\d+) TOTAL=(\d+)", r.stdout)
    if not m:
        raise RuntimeError("dbt build produced no summary: " + (r.stdout + r.stderr)[-800:])
    p, w, e, s, t = map(int, m.groups())
    db.record_quality(run_id, [dict(layer="gold", table="dbt_project", check="dbt build (models + tests)", severity="critical", status="fail" if e else "pass",
                                    failed_rows=e, total_rows=t, detail=f"pass={p} warn={w} error={e} skip={s}")])
    if e:
        raise CriticalDataQualityError(f"dbt build: {e} errors")
    return dict(rows=t, detail=f"pass={p} warn={w} error={e} skip={s}")


COVERAGE_SQL = """
WITH m AS (SELECT * FROM staging.stg_matches),
ev AS (SELECT match_key, count(*) n, count(*) FILTER (WHERE location_x IS NOT NULL) n_xy FROM wh.fact_match_events GROUP BY 1),
ap AS (SELECT DISTINCT match_key FROM wh.fact_player_appearances),
ts AS (SELECT DISTINCT match_key FROM wh.fact_team_match_stats),
gl AS (SELECT match_key, count(*) n, count(*) FILTER (WHERE player_key IS NOT NULL) n_pl FROM staging.stg_goal_events GROUP BY 1),
aw AS (SELECT season_id, count(*) n FROM (SELECT s.season_id FROM wh.fact_player_awards a JOIN wh.dim_season s USING (season_key)
                                         UNION ALL SELECT s.season_id FROM wh.fact_team_awards a JOIN wh.dim_season s USING (season_key)) x GROUP BY 1)
SELECT m.season_id, m.competition_id, s.expected_matches, count(*)::int AS matches_in_dataset,
  count(*) FILTER (WHERE m.is_played)::int AS matches_played, count(*) FILTER (WHERE NOT m.is_played)::int AS matches_coming_soon,
  round(100.0 * count(*) FILTER (WHERE m.is_played AND m.referee_name IS NOT NULL) / nullif(count(*) FILTER (WHERE m.is_played), 0), 1) AS pct_referee,
  round(100.0 * count(*) FILTER (WHERE m.is_played AND m.venue_name IS NOT NULL) / nullif(count(*) FILTER (WHERE m.is_played), 0), 1) AS pct_venue,
  round(100.0 * count(*) FILTER (WHERE m.is_played AND m.attendance IS NOT NULL) / nullif(count(*) FILTER (WHERE m.is_played), 0), 1) AS pct_attendance,
  round(100.0 * count(*) FILTER (WHERE m.is_played AND ap.match_key IS NOT NULL) / nullif(count(*) FILTER (WHERE m.is_played), 0), 1) AS pct_lineups,
  round(100.0 * count(*) FILTER (WHERE m.is_played AND ev.match_key IS NOT NULL) / nullif(count(*) FILTER (WHERE m.is_played), 0), 1) AS pct_events,
  round(100.0 * count(*) FILTER (WHERE m.is_played AND ts.match_key IS NOT NULL) / nullif(count(*) FILTER (WHERE m.is_played), 0), 1) AS pct_team_stats,
  round(100.0 * count(*) FILTER (WHERE m.is_played AND m.man_of_the_match_raw IS NOT NULL) / nullif(count(*) FILTER (WHERE m.is_played), 0), 1) AS pct_man_of_match,
  round(100.0 * sum(coalesce(ev.n_xy, 0)) / nullif(sum(coalesce(ev.n, 0)), 0), 1) AS pct_events_with_coordinates,
  coalesce(sum(gl.n), 0)::int AS goal_events, coalesce(sum(gl.n_pl), 0)::int AS goal_events_with_player, coalesce(max(aw.n), 0)::int AS awards,
  sum(m.home_score + m.away_score)::int AS goals_recorded,
  round(100.0 * coalesce(sum(gl.n), 0) / nullif(sum(m.home_score + m.away_score), 0), 1) AS pct_goals_with_event
FROM m JOIN wh.dim_season s ON s.season_id = m.season_id
LEFT JOIN ev USING (match_key) LEFT JOIN ap USING (match_key) LEFT JOIN ts USING (match_key) LEFT JOIN gl USING (match_key) LEFT JOIN aw ON aw.season_id = m.season_id
GROUP BY m.season_id, m.competition_id, s.expected_matches ORDER BY 1
"""


def step_coverage(run_id: str) -> dict:
    with db.connect() as c:
        df = pd.DataFrame(c.execute(COVERAGE_SQL).fetchall(), columns=[d.name for d in c.execute(COVERAGE_SQL).description])
        flags = []
        for r in df.itertuples():
            if r.matches_coming_soon > 0 and r.matches_played == 0:
                flags.append("upcoming - not played yet")
            elif pd.notna(r.expected_matches) and r.matches_in_dataset < r.expected_matches:
                flags.append(f"missing {int(r.expected_matches - r.matches_in_dataset)} vs format-based expectation")
            elif r.matches_coming_soon > 0:
                flags.append("in progress")
            elif pd.notna(r.pct_goals_with_event) and r.pct_goals_with_event < 99:
                flags.append(f"goal events cover {r.pct_goals_with_event}% of recorded goals")
            else:
                flags.append("complete vs expectation" if pd.notna(r.expected_matches) else "no expectation defined")
        df.insert(0, "run_id", run_id)
        df.insert(1, "generated_at", pd.Timestamp.now(tz="UTC"))
        df["coverage_flag"] = flags
        with c.cursor() as cur:
            cur.execute("DELETE FROM monitoring.source_coverage_report WHERE run_id = %s", (run_id,))
            for col in ("expected_matches", "matches_in_dataset", "matches_played", "matches_coming_soon", "goal_events", "goal_events_with_player", "awards", "goals_recorded"):
                df[col] = pd.to_numeric(df[col]).round().astype("Int64").astype("object")
            db._copy_monitoring(cur, "source_coverage_report", df)
    return dict(rows=len(df), detail=f"{len(df)} seasons")


def run_pipeline(force_run: bool = False) -> str:
    """Plain sequential runner (same steps the Dagster assets call)."""
    db.ensure_schema()
    rid = db.new_run_id()
    db.run_step(rid, "bronze", step_bronze)
    db.run_step(rid, "silver", lambda: step_silver(force_run))
    db.run_step(rid, "validate_silver", lambda: step_validate(rid), retries=0)
    db.run_step(rid, "warehouse", lambda: step_warehouse(force_run))
    db.run_step(rid, "dbt_gold", lambda: step_dbt(rid), retries=1)
    db.run_step(rid, "coverage_report", lambda: step_coverage(rid))
    return rid


if __name__ == "__main__":
    import sys
    print(run_pipeline("--force" in sys.argv))
