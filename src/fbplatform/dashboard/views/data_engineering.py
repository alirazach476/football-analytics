import pandas as pd
import plotly.express as px
import streamlit as st

from fbplatform.dashboard.lib import cached, fig, require_db

require_db()
st.title("Data engineering: pipeline health and data quality")

fr = cached("freshness")
c = st.columns(len(fr))
for col, r in zip(c, fr.itertuples()):
    col.metric(r.item, (r.value or "n/a")[:19])

dq = cached("data_quality_score")
st.metric("Data quality score", "n/a" if dq["score"] is None else f"{dq['score']:.0f}%", help="share of automated checks that passed in the latest runs; it is about rule compliance, not completeness (see coverage below)")

tab = st.tabs(["Pipeline runs", "Ingestion", "Data quality checks", "Coverage & missing data", "Duplicates", "Database"])
with tab[0]:
    ps = cached("pipeline_summary")
    st.markdown("**Recent runs** (one run = bronze → silver → validation → warehouse → dbt → coverage)")
    st.dataframe(ps, hide_index=True, use_container_width=True)
    if len(ps):
        fig(px.bar(ps.sort_values("started_at"), x="started_at", y="total_seconds", hover_data=["failed_attempts", "skipped_steps"], title="Run duration (seconds)"))
    st.markdown("**Step history**")
    runs = cached("pipeline_runs")
    st.dataframe(runs, hide_index=True, use_container_width=True)
    st.caption("'skipped' = the step's input had not changed (idempotent re-run). Failed attempts are retried and every attempt is logged.")
with tab[1]:
    ing = cached("ingestion_status")
    st.dataframe(ing, hide_index=True, use_container_width=True)
    fig(px.bar(ing, x="source", y="files", hover_data=["mb", "last_ingested"], title="Registered source files (Bronze) by source"))
    st.caption("Every raw file is registered with SHA-256 and a version; originals are never modified. UEFA Champions League files are flagged and excluded from all processing (kept on disk, not deleted).")
with tab[2]:
    only = st.checkbox("Only failed checks", value=False)
    d = cached("dq_results", only)
    st.dataframe(d, hide_index=True, use_container_width=True)
    if only and d.empty:
        st.success("No failed checks in the stored history.")
    summ = d.groupby(["layer", "status"]).size().reset_index(name="checks")
    fig(px.bar(summ, x="layer", y="checks", color="status", color_discrete_map={"pass": "#009E73", "fail": "#D55E00"}))
with tab[3]:
    cov = cached("coverage_report")
    cols = ["pct_referee", "pct_venue", "pct_attendance", "pct_lineups", "pct_events", "pct_team_stats", "pct_man_of_match", "pct_goals_with_event", "pct_events_with_coordinates"]
    h = cov.set_index("season_id")[cols]
    fig(px.imshow(h.T, aspect="auto", color_continuous_scale="Blues", zmin=0, zmax=100, text_auto=".0f", labels=dict(color="%")).update_xaxes(tickangle=60), key="cov")
    st.dataframe(cov[["season_id", "expected_matches", "matches_in_dataset", "matches_played", "matches_coming_soon", "coverage_flag"]], hide_index=True, use_container_width=True)
    st.caption("Expected matches come from format arithmetic and are unverified. Gaps are source limits: no minute-level events/lineups for Nations League group matches, no man-of-the-match for Copa 2001–2007, coordinates only for StatsBomb/Wyscout matches.")
with tab[4]:
    st.dataframe(cached("duplicate_checks"), hide_index=True, use_container_width=True)
    st.caption("'Merged' counts are identities unified by the documented entity-resolution rules (same name and birth date, or name containment + same national team + never in one line-up).")
with tab[5]:
    db = cached("db_stats")
    st.dataframe(db, hide_index=True, use_container_width=True)
    fig(px.bar(db.sort_values("rows"), x="rows", y="table", orientation="h", log_x=True, title="Rows per warehouse table (log scale)"))
