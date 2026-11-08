import pandas as pd
import psycopg
import pytest
from fbplatform.config import DATA
from fbplatform.validation import schemas
from fbplatform.warehouse.load import dsn

try:
    psycopg.connect(dsn(), connect_timeout=3).close()
    UP = True
except Exception:
    UP = False
needs_db = pytest.mark.skipif(not UP, reason="warehouse not running")
M = lambda: pd.read_parquet(DATA / "silver" / "matches.parquet")


def _fails(tables):
    return {(r["table"], r["check"]) for r in schemas.critical_failures(schemas.validate(tables))}


def test_validation_passes_on_real_silver():
    assert schemas.critical_failures(schemas.validate()) == []


def test_validation_catches_scheduled_fixture_with_a_score():
    m = M()
    i = m.index[m.match_status == "scheduled"][0]
    m.loc[i, "home_score"] = 1
    assert any("scheduled fixtures must have null scores" in c for _, c in _fails({"matches": m}))


def test_validation_catches_duplicates_and_out_of_scope_competition():
    m = M()
    m2 = pd.concat([m, m.iloc[[0]]], ignore_index=True)
    assert any("match_id" in c for _, c in _fails({"matches": m2}))
    m3 = M()
    m3.loc[0, "competition_id"] = "UCL"
    assert any("competition_id" in c for _, c in _fails({"matches": m3}))


def test_validation_catches_completed_match_without_score():
    m = M()
    i = m.index[m.match_status == "completed"][0]
    m.loc[i, "away_score"] = pd.NA
    assert any("completed matches must have both scores" in c for _, c in _fails({"matches": m}))


def test_warning_checks_are_recorded_not_fatal():
    m = M()
    m.loc[0, "attendance"] = 999999
    res = schemas.validate({"matches": m})
    assert schemas.critical_failures(res) == []
    assert any(r["severity"] == "warning" and r["status"] == "fail" for r in res)


@needs_db
def test_run_step_retries_and_logs_every_attempt():
    from fbplatform.monitoring import db
    db.ensure_schema()
    rid, calls = db.new_run_id(), []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("temporary")
        return {"rows": 7}
    assert db.run_step(rid, "retry_demo", flaky, retries=2, backoff=0)["rows"] == 7
    with db.connect() as c:
        got = c.execute("select attempt, status from monitoring.pipeline_execution_logs where run_id=%s order by attempt", (rid,)).fetchall()
    assert got == [(1, "failed"), (2, "failed"), (3, "success")]


@needs_db
def test_critical_failure_is_not_retried():
    from fbplatform.monitoring import db
    from fbplatform.orchestration.steps import CriticalDataQualityError
    rid = db.new_run_id()

    def bad():
        raise CriticalDataQualityError("x")
    with pytest.raises(CriticalDataQualityError):
        db.run_step(rid, "bad", bad, retries=3, backoff=0)
    with db.connect() as c:
        assert c.execute("select count(*) from monitoring.pipeline_execution_logs where run_id=%s", (rid,)).fetchone()[0] == 1


@needs_db
def test_pipeline_is_idempotent_second_run_skips_unchanged_work():
    from fbplatform.monitoring import db
    from fbplatform.orchestration import steps
    steps.run_pipeline()
    rid = steps.run_pipeline()
    with db.connect() as c:
        st = dict(c.execute("select step, status from monitoring.pipeline_execution_logs where run_id=%s", (rid,)).fetchall())
        n = c.execute("select count(*) from wh.fact_matches").fetchone()[0]
    assert st["silver"] == "skipped" and st["warehouse"] == "skipped" and st["dbt_gold"] == "success" and n == 1830


@needs_db
def test_coverage_report_flags_upcoming_and_in_progress_seasons():
    from fbplatform.monitoring import db
    with db.connect() as c:
        rid = c.execute("select run_id from monitoring.source_coverage_report order by generated_at desc limit 1").fetchone()[0]
        flags = dict(c.execute("select season_id, coverage_flag from monitoring.source_coverage_report where run_id=%s", (rid,)).fetchall())
    assert flags["EURO-2028"] == "upcoming - not played yet" and len(flags) == 29


@needs_db
def test_dagster_assets_materialize_in_lineage_order():
    from dagster import materialize
    from fbplatform.orchestration import dagster_defs as d
    r = materialize([d.bronze_snapshot, d.silver_tables, d.silver_validation, d.warehouse_tables, d.dbt_gold, d.coverage_report])
    assert r.success
    order = [e.asset_key.to_user_string() for e in r.get_asset_materialization_events()]
    assert order == ["bronze_snapshot", "silver_tables", "silver_validation", "warehouse_tables", "dbt_gold", "coverage_report"]
