"""Pandera validation of the Silver tables. Two severities:
  critical - violations stop the pipeline before the warehouse is touched (keys, enums, score/status consistency, UCL scope);
  warning  - recorded in monitoring.data_quality_results but do not stop the run (plausibility ranges, known source limits).
Every check reports failed rows / total rows; nothing is silently dropped.
"""
from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from ..config import DATA

SILVER = DATA / "silver"
COMPS = ["WC", "EURO", "COPA", "UNL"]


def _col(dtype=None, **kw):
    return pa.Column(dtype, **kw)


def critical_schemas() -> dict[str, pa.DataFrameSchema]:
    return {
        "matches": pa.DataFrameSchema({
            "match_id": _col(str, unique=True, nullable=False),
            "competition_id": _col(str, checks=pa.Check.isin(COMPS), nullable=False),
            "season_id": _col(str, checks=pa.Check.str_matches(r"^(WC|EURO|COPA)-\d{4}$|^UNL-\d{4}-\d{2}$"), nullable=False),
            "match_status": _col(str, checks=pa.Check.isin(["completed", "scheduled"]), nullable=False),
            "stage": _col(str, nullable=False),
            "home_team_raw": _col(str, nullable=False), "away_team_raw": _col(str, nullable=False),
            "home_score": _col(nullable=True, checks=pa.Check(lambda s: s.dropna() >= 0)),
            "away_score": _col(nullable=True, checks=pa.Check(lambda s: s.dropna() >= 0)),
        }, checks=[
            pa.Check(lambda d: ~((d.match_status == "scheduled") & (d.home_score.notna() | d.away_score.notna())),
                     error="scheduled fixtures must have null scores"),
            pa.Check(lambda d: ~((d.match_status == "completed") & (d.home_score.isna() | d.away_score.isna())),
                     error="completed matches must have both scores"),
            pa.Check(lambda d: ~((d.match_status == "scheduled") & d.fixture_detail.isna()),
                     error="scheduled fixtures must carry a fixture_detail ('Coming soon' summary)"),
        ]),
        "players": pa.DataFrameSchema({"player_id": _col(str, unique=True, nullable=False), "full_name": _col(str, nullable=False)}),
        "player_xref": pa.DataFrameSchema({"player_id_original": _col(str, unique=True, nullable=False),
                                           "canonical_player_id": _col(str, nullable=False)}),
        "events": pa.DataFrameSchema({"event_id": _col(str, unique=True, nullable=False), "match_id": _col(str, nullable=False),
                                      "period": _col(nullable=True, checks=pa.Check(lambda s: s.dropna().between(1, 5)))}),
        "lineups": pa.DataFrameSchema({"match_id": _col(str, nullable=False), "team_id": _col(str, nullable=False)}),
        "awards": pa.DataFrameSchema({"season_id": _col(str, nullable=False), "winner_type": _col(str, checks=pa.Check.isin(["player", "team"])),
                                      "entity_name_raw": _col(str, nullable=False)}),
        "venues": pa.DataFrameSchema({"venue_id": _col(str, unique=True, nullable=False)}),
        "teams": pa.DataFrameSchema({"team_id": _col(str, unique=True, nullable=False)}),
    }


def warning_schemas() -> dict[str, pa.DataFrameSchema]:
    return {
        "matches": pa.DataFrameSchema({
            "attendance": _col(nullable=True, checks=pa.Check.in_range(0, 150000)),
        }, checks=[pa.Check(lambda d: pd.to_datetime(d.match_date).between("2000-01-01", "2028-12-31"), error="match_date outside 2000-2028")]),
        "players": pa.DataFrameSchema({"date_of_birth": _col(nullable=True, checks=pa.Check(
            lambda s: pd.to_datetime(s.dropna(), errors="coerce").between("1940-01-01", "2012-12-31"), error="implausible date of birth"))}),
        "events": pa.DataFrameSchema({
            "minute": _col(nullable=True, checks=pa.Check(lambda s: s.dropna().between(0, 135))),
            "location_x": _col(nullable=True, checks=pa.Check(lambda s: s.dropna().between(0, 121))),
            "location_y": _col(nullable=True, checks=pa.Check(lambda s: s.dropna().between(0, 101))),
        }),
        "lineups": pa.DataFrameSchema({"minutes_played_derived": _col(nullable=True, checks=pa.Check(lambda s: s.dropna().between(0, 130)))}),
        "awards": pa.DataFrameSchema({"rank": _col(nullable=True, checks=pa.Check(lambda s: s.dropna().between(1, 3)))}),
    }


def validate(tables: dict[str, pd.DataFrame] | None = None) -> list[dict]:
    """Run both schema sets; returns one result row per (table, check)."""
    out = []
    for severity, schemas in (("critical", critical_schemas()), ("warning", warning_schemas())):
        for name, schema in schemas.items():
            df = tables[name] if tables and name in tables else pd.read_parquet(SILVER / f"{name}.parquet")
            try:
                schema.validate(df, lazy=True)
                out.append(dict(layer="silver", table=name, check=f"pandera_{severity}_schema", severity=severity, status="pass",
                                failed_rows=0, total_rows=len(df), detail=f"{len(schema.columns)} column rules, {len(schema.checks)} table rules"))
            except pa.errors.SchemaErrors as e:
                fc = e.failure_cases
                for (check, col), g in fc.groupby(["check", "column"], dropna=False):
                    out.append(dict(layer="silver", table=name, check=f"{col}: {check}", severity=severity, status="fail",
                                    failed_rows=int(g["index"].nunique()) if g["index"].notna().any() else len(g), total_rows=len(df),
                                    detail="e.g. " + "; ".join(map(str, g.failure_case.head(3).tolist()))[:200]))
    return out


def critical_failures(results: list[dict]) -> list[dict]:
    return [r for r in results if r["severity"] == "critical" and r["status"] == "fail"]
