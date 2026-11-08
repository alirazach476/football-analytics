"""Data-engineering visualisations: record counts per layer, completeness, missing-value heatmaps, duplicates, pipeline durations/failures,
freshness, source coverage and data-quality trends. Everything is read from the warehouse, the monitoring schema and the layer files.
Missing is never shown as zero: a 'missing' share and a genuine zero (e.g. attendance 0 = closed doors) are reported separately."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pyarrow.parquet as pq
from plotly.subplots import make_subplots

from ..analysis import data as D
from ..config import DATA
from . import common as C
from .common import Chart, unavailable

STEP_ORDER = ["bronze", "silver", "validate_silver", "warehouse", "dbt_gold", "coverage_report"]
STEP_COLOR = {s: C.CAT[i] for i, s in enumerate(STEP_ORDER)}
STATUS_COLOR = {"success": "#0ca30c", "failed": "#d03b3b", "skipped": "#b4b2a9"}      # reserved status palette: always paired with a text label


# ------------------------------------------------------------------ loaders
SNAPSHOT = DATA / "layer_counts_snapshot.json"


def layer_counts() -> pd.DataFrame:
    """Row counts per layer. Bronze files and the large silver event table are not shipped to the hosted API, so their counts come from a snapshot written by
    tools/prepare_render.py (when the files exist locally they are counted live)."""
    rows = []
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else []
    snaps = sorted((DATA / "bronze" / "collected").glob("v*"))
    if snaps:
        for f in sorted(snaps[-1].iterdir()):
            if f.suffix == ".parquet":
                rows.append(dict(layer="Bronze (frozen snapshot)", table=f.stem, rows=pq.ParquetFile(f).metadata.num_rows))
            elif f.suffix == ".csv":
                rows.append(dict(layer="Bronze (frozen snapshot)", table=f.stem, rows=sum(1 for _ in open(f, encoding="utf-8", errors="ignore")) - 1))
    else:
        rows += [r for r in snap if r["layer"].startswith("Bronze")]
    for f in sorted((DATA / "silver").glob("*.parquet")):
        rows.append(dict(layer="Silver", table=f.stem, rows=pq.ParquetFile(f).metadata.num_rows))
    have = {r["table"] for r in rows if r["layer"] == "Silver"}
    rows += [r for r in snap if r["layer"] == "Silver" and r["table"] not in have]
    rows.sort(key=lambda r: (["Bronze (frozen snapshot)", "Silver"].index(r["layer"]), r["table"]))
    gold = D.q("select table_name from information_schema.tables where table_schema='gold' order by 1").table_name.tolist()
    for t in gold:
        rows.append(dict(layer="Gold (dbt marts)", table=t, rows=int(D.q(f"select count(*) c from gold.{t}").c.iloc[0])))
    return pd.DataFrame(rows)


def raw_files() -> pd.DataFrame:
    return D.q("select source, count(*) files, sum(size_bytes) bytes, count(*) filter (where excluded_ucl) excluded_ucl from monitoring.ingestion_history group by 1 order by 2 desc")


def pipeline_log() -> pd.DataFrame:
    d = D.q("select run_id, step, attempt, status, started_at, finished_at, duration_seconds, rows_processed, left(coalesce(error, detail), 200) as detail from monitoring.pipeline_execution_logs order by log_id")
    d["duration_seconds"] = pd.to_numeric(d.duration_seconds, errors="coerce")
    return d


def dq_log() -> pd.DataFrame:
    return D.q("select run_id, checked_at, layer, table_name, check_name, severity, status, failed_rows, total_rows from monitoring.data_quality_results order by result_id")


def freshness_rows() -> pd.DataFrame:
    return D.q("""select 'last pipeline run' item, max(finished_at) ts from monitoring.pipeline_execution_logs
                  union all select 'last successful dbt build', max(finished_at) from monitoring.pipeline_execution_logs where step='dbt_gold' and status='success'
                  union all select 'warehouse last loaded', max(loaded_at) from wh.etl_load_log
                  union all select 'last data-quality check', max(checked_at) from monitoring.data_quality_results""")


def coverage() -> pd.DataFrame:
    return D.q("select * from monitoring.source_coverage_report where run_id = (select run_id from monitoring.source_coverage_report order by generated_at desc limit 1) order by season_id")


def silver_table(name: str, columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(DATA / "silver" / f"{name}.parquet", columns=columns)


# ------------------------------------------------------------------ 1. record counts per layer
def layer_record_counts(lc: pd.DataFrame) -> Chart:
    if lc.empty:
        return unavailable("layer_counts", "no layer data found (run the pipeline: python -m fbplatform.orchestration.steps)")
    layers = list(dict.fromkeys(lc.layer))
    fig = make_subplots(rows=1, cols=len(layers), subplot_titles=layers, horizontal_spacing=0.2, shared_yaxes=False)
    for i, ly in enumerate(layers):
        d = lc[lc.layer == ly].sort_values("rows")
        # dots, not bars: on a log axis a bar's length depends on an arbitrary baseline
        fig.add_scatter(y=d.table, x=d.rows, mode="markers", marker=dict(size=10, color=C.CAT[0], line=dict(color=C.SURFACE, width=2)), showlegend=False, hovertemplate="<b>%{y}</b><br>%{x:,} records<extra></extra>", row=1, col=i + 1)
        fig.update_xaxes(type="log", title_text="Records (log scale)", row=1, col=i + 1, showgrid=True, gridcolor=C.GRID, linecolor=C.AXIS)
        fig.update_yaxes(automargin=True, tickfont=dict(size=10), showgrid=True, gridcolor=C.GRID, row=1, col=i + 1)
    C.style(fig, "Records per table in the Bronze, Silver and Gold layers", None, None, legend=False, height=max(440, 24 * lc.groupby("layer").size().max() + 170))
    return Chart(fig, lc, int(lc.rows.sum()), "layer files + warehouse", "Dot plot on a log scale (tables range from ~100 to 1,000,000 records; a bar's length would depend on an arbitrary baseline). Each layer has its own tables (Bronze = collected tables frozen as parquet/CSV; Silver = cleaned tables; Gold = dbt marts), so rows are not comparable across panels.", name="layer_counts")


# ------------------------------------------------------------------ 2. completeness / missing values
def missing_heatmap(df: pd.DataFrame, columns: list[str], group: str, title: str, zero_columns: list[str] | None = None) -> Chart:
    cols = [c for c in columns if c in df.columns]
    if df.empty or not cols or group not in df.columns:
        return unavailable("missing_heatmap", "the table or its columns are not available")
    miss = df.groupby(group)[cols].agg(lambda s: 100 * s.isna().mean()).T
    n = df.groupby(group).size()
    zeros = {}
    for c in (zero_columns or []):
        if c in df.columns:
            zeros[c] = df.groupby(group)[c].agg(lambda s: int((s == 0).sum()))
    custom = np.array([[("" if c not in zeros else f"genuine zeros: {zeros[c][g]}") for g in miss.columns] for c in miss.index])
    fig = go.Figure(go.Heatmap(z=miss.values, x=[f"{g}<br>n={n[g]}" for g in miss.columns], y=miss.index, colorscale=C.SEQ, zmin=0, zmax=100, xgap=2, ygap=2, customdata=custom, text=np.round(miss.values).astype(int), texttemplate="%{text}",
                               colorbar=dict(title="% missing"), hovertemplate="<b>%{y}</b> · %{x}<br>%{z:.1f}% missing<br>%{customdata}<extra></extra>"))
    C.style(fig, title, None, None, legend=False, height=max(340, 26 * len(cols) + 190))
    fig.update_xaxes(tickangle=60)
    fig.update_yaxes(autorange="reversed")
    out = miss.round(2).reset_index(names="column")
    return Chart(fig, out, len(df), "Silver layer", "Darker = more of the values are missing (NULL). A genuine zero (e.g. attendance 0 = closed doors) is NOT missing: it is counted separately in the hover text.", name="missing_heatmap")


def completeness_bars(tables: dict[str, pd.DataFrame], key_columns: dict[str, list[str]]) -> Chart:
    rows = []
    for t, df in tables.items():
        for c in key_columns.get(t, []):
            if c in df.columns:
                rows.append(dict(table=t, column=c, complete_pct=100 * df[c].notna().mean(), rows=len(df)))
    d = pd.DataFrame(rows)
    if d.empty:
        return unavailable("completeness_bars", "no Silver tables available")
    d["label"] = d.table + " · " + d.column
    d = d.sort_values("complete_pct")
    fig = go.Figure(go.Bar(y=d.label, x=d.complete_pct, orientation="h", marker_color=C.CAT[0], customdata=d.rows, hovertemplate="<b>%{y}</b><br>%{x:.1f}% complete (%{customdata:,} rows)<extra></extra>"))
    C.style(fig, "Completeness of key columns (Silver)", "Rows with a value (%)", None, legend=False, height=max(380, 22 * len(d) + 140))
    C.bar_gap(fig)
    fig.update_xaxes(range=[0, 100])
    return Chart(fig, d.drop(columns="label").round(2), int(d.rows.max()), "Silver layer", "Complete = not NULL. Low completeness is usually a real source limit (e.g. line-ups for Nations League group matches), documented in DATA_QUALITY.md.", name="completeness_bars")


# ------------------------------------------------------------------ 3. duplicates
def duplicates(dup: pd.DataFrame) -> Chart:
    if dup.empty:
        return unavailable("duplicates", "duplicate checks are not available")
    d = dup.copy()
    d["kind"] = np.where(d.check.str.contains("merged|still separate"), "entity resolution", "integrity check (must be 0)")
    d = d.sort_values(["kind", "found"])
    fig = go.Figure()
    for kind, color in (("integrity check (must be 0)", C.CAT[0]), ("entity resolution", C.CAT[1])):
        s = d[d.kind == kind]
        if len(s):
            fig.add_bar(y=s.check, x=s.found, orientation="h", name=kind, marker_color=color, text=s.found.astype(int), textposition="outside", hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>")
    C.style(fig, "Duplicate and identity checks", "Records found", None, height=max(340, 50 * len(d) + 130))
    C.bar_gap(fig)
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(range=[0, max(d.found.max() * 1.15, 1)])
    return Chart(fig, d[["check", "found", "kind"]], len(d), "warehouse", "Integrity checks must read 0 (the label shows the real count, so 0 is visible). 'Merged' counts are identities unified by the documented entity-resolution rules; 'still separate' are same name + birth date pairs that remain (should be 0).", name="duplicates")


# ------------------------------------------------------------------ 4. pipeline times and failures
def pipeline_durations(log: pd.DataFrame, last_n: int = 15) -> Chart:
    d = log[log.status.isin(["success", "skipped"])]
    runs = d.groupby("run_id").started_at.min().sort_values().tail(last_n).index
    d = d[d.run_id.isin(runs)]
    if d.empty:
        return unavailable("pipeline_durations", "no pipeline runs have been logged yet")
    order = list(runs)
    fig = go.Figure()
    for s in STEP_ORDER:
        x = d[d.step == s].groupby("run_id").duration_seconds.sum().reindex(order)
        if x.notna().any():
            fig.add_bar(x=[r.replace("run-", "") for r in order], y=x.fillna(0), name=s, marker_color=STEP_COLOR[s], hovertemplate="%{x}<br>" + s + ": %{y:.1f} s<extra></extra>")
    fig.update_layout(barmode="stack")
    C.style(fig, f"Pipeline duration per run (last {len(order)} runs)", "Run (UTC start)", "Seconds (successful or skipped attempts)", height=420)
    C.bar_gap(fig)
    fig.update_xaxes(tickangle=45)
    return Chart(fig, d[["run_id", "step", "status", "duration_seconds", "rows_processed"]], len(order), "monitoring.pipeline_execution_logs", "A skipped step (unchanged input) takes ~0 s: short runs are the idempotent re-runs. Failed attempts are shown on the failures chart, not here.", name="pipeline_durations")


def pipeline_failures(log: pd.DataFrame) -> Chart:
    if log.empty:
        return unavailable("pipeline_failures", "no pipeline runs have been logged yet")
    t = log.groupby(["step", "status"]).size().unstack(fill_value=0).reindex([s for s in STEP_ORDER if s in set(log.step)] + sorted(set(log.step) - set(STEP_ORDER)))
    fig = go.Figure()
    for st in ("success", "skipped", "failed"):
        if st in t:
            fig.add_bar(x=t.index, y=t[st], name=st.capitalize(), marker_color=STATUS_COLOR[st], text=[f"{v} {st}" if v else "" for v in t[st]], textposition="inside", textfont=dict(color="#ffffff" if st != "skipped" else C.INK, size=11),
                        hovertemplate="%{x}: %{y} " + st + " attempt(s)<extra></extra>")
    fig.update_layout(barmode="stack")
    C.style(fig, "Pipeline step attempts by outcome", "Pipeline step", "Attempts (count)", height=400)
    C.bar_gap(fig)
    nfail = int(t["failed"].sum()) if "failed" in t else 0
    return Chart(fig, t.reset_index(), len(log), "monitoring.pipeline_execution_logs", f"{nfail} failed attempt(s) in the whole history (each logged with its error; most come from development runs before fixes). Retries appear as extra attempts. Colour carries the status AND each bar is labelled.", name="pipeline_failures")


# ------------------------------------------------------------------ 5. freshness
def freshness(fr: pd.DataFrame, latest_match: str | None = None) -> Chart:
    d = fr.dropna(subset=["ts"]).copy()
    if d.empty:
        return unavailable("freshness", "no timestamps recorded yet")
    now = pd.Timestamp.now(tz="UTC")
    d["age_hours"] = [(now - pd.Timestamp(t).tz_convert("UTC")).total_seconds() / 3600 if pd.Timestamp(t).tzinfo else (now - pd.Timestamp(t, tz="UTC")).total_seconds() / 3600 for t in d.ts]
    d = d.sort_values("age_hours")
    fig = go.Figure(go.Bar(y=d.item, x=d.age_hours, orientation="h", marker_color=C.CAT[0], text=[f"{h:.1f} h" if h < 48 else f"{h / 24:.1f} d" for h in d.age_hours], textposition="outside", customdata=d.ts.astype(str), hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>"))
    C.style(fig, "Data freshness: time since each step last ran", "Hours since (now, UTC)", None, legend=False, height=320)
    C.bar_gap(fig)
    fig.update_xaxes(range=[0, d.age_hours.max() * 1.25 + 1])
    return Chart(fig, d[["item", "ts", "age_hours"]].round(2), len(d), "monitoring.* / wh.etl_load_log", "Freshness of the PIPELINE, not of the sources: the collection of new source data is a separate, rate-limited step. " + (f"Latest played match in the data: {latest_match}." if latest_match else ""), name="freshness")


# ------------------------------------------------------------------ 6. source coverage
def source_coverage(cov: pd.DataFrame) -> Chart:
    cols = [("Referee", "pct_referee"), ("Venue", "pct_venue"), ("Attendance", "pct_attendance"), ("Line-ups", "pct_lineups"), ("Events", "pct_events"), ("Team stats", "pct_team_stats"),
            ("Man of match", "pct_man_of_match"), ("Goals with an event", "pct_goals_with_event"), ("Events with coordinates", "pct_events_with_coordinates")]
    if cov.empty:
        return unavailable("source_coverage", "no coverage report yet (run the pipeline)")
    z = cov.set_index("season_id")[[c for _, c in cols]].astype(float)
    fig = go.Figure(go.Heatmap(z=z.T.values, x=z.index, y=[l for l, _ in cols], colorscale=C.SEQ, zmin=0, zmax=100, xgap=2, ygap=2, text=z.T.round(0).fillna(-1).astype(int).astype(str).replace("-1", "").values, texttemplate="%{text}",
                               colorbar=dict(title="% of played<br>matches"), hovertemplate="<b>%{x}</b> · %{y}<br>%{z:.1f}% of played matches<extra></extra>"))
    C.style(fig, "Source coverage by edition (% of played matches with the field)", None, None, legend=False, height=430)
    fig.update_xaxes(tickangle=60)
    fig.update_yaxes(autorange="reversed")
    return Chart(fig, cov[["season_id", "competition_id", "expected_matches", "matches_in_dataset", "matches_played", "matches_coming_soon"] + [c for _, c in cols] + ["coverage_flag"]], int(cov.matches_played.sum()), "monitoring.source_coverage_report",
                 "Blank cell = nothing to measure (an upcoming edition has no played matches), not 0%. Low values are real source limits, e.g. Nations League line-ups, Copa man of the match 2001–2007.", name="source_coverage")


# ------------------------------------------------------------------ 7. data-quality trends
def dq_trends(dq: pd.DataFrame) -> Chart:
    if dq.empty:
        return unavailable("dq_trends", "no data-quality results recorded yet")
    g = dq.groupby(["run_id", "layer"]).agg(checked_at=("checked_at", "min"), checks=("status", "size"), passed=("status", lambda s: int((s == "pass").sum()))).reset_index()
    g["pass_rate"] = 100 * g.passed / g.checks
    g = g.sort_values("checked_at")
    fig = go.Figure()
    for i, ly in enumerate(sorted(g.layer.unique())):
        s = g[g.layer == ly]
        fig.add_scatter(x=s.checked_at, y=s.pass_rate, mode="lines+markers", name=f"{ly} layer", line=dict(color=C.CAT[i], width=2), marker=dict(size=8, color=C.CAT[i], symbol=["circle", "square", "diamond"][i % 3], line=dict(color=C.SURFACE, width=2)),
                        customdata=np.c_[s.checks, s.passed, s.run_id], hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y:.0f}% passed (%{customdata[1]} of %{customdata[0]} checks)<br>%{customdata[2]}<extra>" + ly + "</extra>")
    C.style(fig, "Data-quality check pass rate per pipeline run", "Run time (UTC)", "Checks passed (%)", height=400)
    fig.update_yaxes(range=[0, 105])
    return Chart(fig, g.round(2), len(g), "monitoring.data_quality_results", f"{int(g.checks.sum())} check results over {g.run_id.nunique()} runs. The pass rate measures compliance with the rules, not completeness. Gold = dbt build (one summary check per run); Silver = Pandera schemas.", name="dq_trends")
