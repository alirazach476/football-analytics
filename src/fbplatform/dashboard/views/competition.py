import plotly.express as px
import streamlit as st

from fbplatform.analysis.data import COMP_COLOR
from fbplatform.dashboard.lib import OUTCOME_COLORS, cached, coming_soon_note, comp_selector, fig, require_db

require_db()
comp, name = comp_selector()
st.title(f"Competition analysis: {name}")
ed = cached("edition_table", comp)
played = ed[ed.matches_played > 0]
coming_soon_note(int(ed.matches_coming_soon.sum()))

c = st.columns(4)
c[0].metric("Editions played", len(played))
c[1].metric("Matches played", int(played.matches_played.sum()))
c[2].metric("Goals per match", f"{played.total_goals.sum() / played.matches_played.sum():.2f}")
c[3].metric("Draw share", f"{(played.draw_pct * played.matches_played).sum() / played.matches_played.sum():.1f}%")

st.subheader("Edition comparison")
metric = st.radio("Measure (per match, so editions of different size are comparable)", ["goals_per_match", "draw_pct", "avg_attendance", "matches_beyond_90"], horizontal=True,
                  format_func=lambda x: {"goals_per_match": "Goals per match", "draw_pct": "Draw %", "avg_attendance": "Average attendance", "matches_beyond_90": "Matches beyond 90 min (count)"}[x])
f = px.bar(played, x="season_id", y=metric, color_discrete_sequence=[COMP_COLOR[comp]], hover_data=["matches_played", "teams", "champion"])
fig(f)
if comp == "UNL" and metric == "matches_beyond_90":
    st.caption("Nations League extra time is not recorded by the sources, so this undercounts it.")

st.subheader("Match outcomes by edition")
o = cached("outcome_table", comp).melt("season_id", var_name="outcome", value_name="matches")
o["outcome"] = o.outcome.map({"team_listed_first_wins": "team listed first wins", "draws": "draws", "team_listed_second_wins": "team listed second wins"})
fig(px.bar(o, x="season_id", y="matches", color="outcome", barmode="relative", color_discrete_map=OUTCOME_COLORS))
st.caption("'Listed first' is not 'home': most tournament matches are on neutral ground (the Nations League is the exception).")

st.subheader("Tournament records")
st.dataframe(ed[["season_id", "teams", "matches_played", "total_goals", "goals_per_match", "champion", "runner_up", "tournament_status"]], hide_index=True, use_container_width=True)
r = cached("records", comp)
a, b = st.columns(2)
a.markdown("**Highest-scoring matches**")
a.dataframe(r["highest_scoring"], hide_index=True, use_container_width=True)
b.markdown("**Biggest winning margins**")
b.dataframe(r["biggest_margin"], hide_index=True, use_container_width=True)
st.markdown("**Top scorers in this competition** (goals linked to a player; Nations League scorers are not linked)")
st.dataframe(r["top_scorers"], hide_index=True, use_container_width=True)

st.subheader("Goals by minute band")
g = cached("goals_by_minute", comp, None)
fig(px.bar(g, x="minute_band", y="goals", color_discrete_sequence=[COMP_COLOR[comp]]))
