"""Dagster definitions: one asset per pipeline step, wired in lineage order. Run with:
    dagster dev -m fbplatform.orchestration.dagster_defs
The daily schedule is defined but STOPPED by default (start it in the UI). Retries live in monitoring.run_step; Dagster adds run history/UI.
"""

from dagster import (AssetExecutionContext, Definitions, DefaultScheduleStatus, MaterializeResult, ScheduleDefinition, asset, define_asset_job)

from ..monitoring import db
from . import steps


def _meta(out: dict) -> dict:
    return {"rows": out.get("rows"), "detail": out.get("detail"), "skipped": bool(out.get("skipped"))}


@asset(group_name="bronze", description="Register raw files (sha256, versions) and snapshot the collected dataset; reload ingestion_history.")
def bronze_snapshot(context: AssetExecutionContext) -> MaterializeResult:
    db.ensure_schema()
    return MaterializeResult(metadata=_meta(db.run_step(context.run_id, "bronze", steps.step_bronze)))


@asset(deps=[bronze_snapshot], group_name="silver", description="Cleaned, entity-resolved Silver tables built only from the Bronze snapshot.")
def silver_tables(context: AssetExecutionContext) -> MaterializeResult:
    return MaterializeResult(metadata=_meta(db.run_step(context.run_id, "silver", steps.step_silver)))


@asset(deps=[silver_tables], group_name="silver", description="Pandera validation (critical failures stop the pipeline).")
def silver_validation(context: AssetExecutionContext) -> MaterializeResult:
    return MaterializeResult(metadata=_meta(db.run_step(context.run_id, "validate_silver", lambda: steps.step_validate(context.run_id), retries=0)))


@asset(deps=[silver_validation], group_name="warehouse", description="PostgreSQL star schema (schema wh), rebuilt only when Silver changed.")
def warehouse_tables(context: AssetExecutionContext) -> MaterializeResult:
    return MaterializeResult(metadata=_meta(db.run_step(context.run_id, "warehouse", steps.step_warehouse)))


@asset(deps=[warehouse_tables], group_name="gold", description="dbt build: staging, intermediate, Gold marts and all dbt tests.")
def dbt_gold(context: AssetExecutionContext) -> MaterializeResult:
    return MaterializeResult(metadata=_meta(db.run_step(context.run_id, "dbt_gold", lambda: steps.step_dbt(context.run_id), retries=1)))


@asset(deps=[dbt_gold], group_name="monitoring", description="monitoring.source_coverage_report per season.")
def coverage_report(context: AssetExecutionContext) -> MaterializeResult:
    return MaterializeResult(metadata=_meta(db.run_step(context.run_id, "coverage_report", lambda: steps.step_coverage(context.run_id))))


football_job = define_asset_job("football_full_refresh", selection="*")
daily = ScheduleDefinition(job=football_job, cron_schedule="0 6 * * *", default_status=DefaultScheduleStatus.STOPPED)

defs = Definitions(assets=[bronze_snapshot, silver_tables, silver_validation, warehouse_tables, dbt_gold, coverage_report],
                   jobs=[football_job], schedules=[daily])
