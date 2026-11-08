import pandas as pd
import plotly.express as px
import streamlit as st

from fbplatform.dashboard.lib import cached, coming_soon_note, fig, require_db

require_db()
st.title("Football analytics: World Cup, Euro, Copa América, Nations League")
st.caption("Men's national-team competitions only. Data from licensed/open datasets and Wikipedia (see Data Engineering page). Results are never invented; missing data stays empty.")

k = cached("kpis")
c = st.columns(5)
c[0].metric("Competitions", k["competitions"])
c[1].metric("Editions with matches", k["editions_played"], help=f"plus {k['editions_upcoming']} upcoming edition(s) not played yet")
c[2].metric("Matches played", f"{k['matches_played']:,}")
c[3].metric("Teams", k["teams"])
c[4].metric("Players", f"{k['players']:,}", help="after merging duplicate identities across sources")
c = st.columns(5)
c[0].metric("Goals (recorded scores)", f"{k['goals']:,}")
c[1].metric("Match events", f"{k['events']:,}")
c[2].metric("Venues", k["venues"])
c[3].metric("Coming soon", k["matches_coming_soon"], help="scheduled fixtures kept in the data")
dq = cached("data_quality_score")
c[4].metric("Data quality score", "n/a" if dq["score"] is None else f"{dq['score']:.0f}%", help=f"{dq['passed']} of {dq['total']} automated checks passed in the latest run (Pandera on Silver + dbt on Gold). It measures rule compliance, not completeness.")

st.subheader("Dataset coverage by edition")
cov = cached("coverage_report")
metric = st.selectbox("Coverage measure", ["pct_lineups", "pct_events", "pct_man_of_match", "pct_attendance", "pct_referee", "pct_venue", "pct_goals_with_event", "pct_events_with_coordinates"],
                      format_func=lambda x: x.replace("pct_", "% ").replace("_", " "))
h = cov.assign(competition=cov.competition_id).pivot_table(index="competition", columns="season_id", values=metric)
f = px.imshow(h.reindex(["WC", "EURO", "COPA", "UNL"]), aspect="auto", color_continuous_scale="Blues", zmin=0, zmax=100, labels=dict(color="%"), text_auto=".0f")
fig(f.update_xaxes(tickangle=60))
st.caption("Blank = nothing to measure yet (upcoming edition). Low values are real source limits, e.g. Nations League group matches have no lineups on the public pages we may use.")
st.dataframe(cov[["season_id", "expected_matches", "matches_in_dataset", "matches_played", "matches_coming_soon", "pct_lineups", "pct_events", "goal_events", "goal_events_with_player", "awards", "coverage_flag"]],
             hide_index=True, use_container_width=True)

st.subheader("Coming soon")
up = cached("upcoming_fixtures")
coming_soon_note(len(up))
st.dataframe(up[["match_date", "season_id", "stage_name", "group_name", "home_team_name", "away_team_name", "venue_name", "venue_city", "status_label", "fixture_detail"]], hide_index=True, use_container_width=True)
