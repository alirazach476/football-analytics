import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from fbplatform.dashboard.lib import cached, coming_soon_note, fig, require_db

require_db()
st.title("Team analytics")
teams = cached("team_names")
default = teams.index("Argentina") if "Argentina" in teams else 0
team = st.sidebar.selectbox("Team", teams, index=default)
st.caption("Records cover only matches in the four collected competitions (no friendlies or qualifiers). Result = recorded score (extra time included, shoot-outs excluded).")

s = cached("team_summary", team).iloc[0]
if int(s.matches) == 0:
    st.info("No played matches for this team yet.")
else:
    c = st.columns(6)
    c[0].metric("Matches", int(s.matches))
    c[1].metric("W-D-L", f"{int(s.wins)}-{int(s.draws)}-{int(s.losses)}")
    c[2].metric("Win %", f"{s.win_pct}%")
    c[3].metric("Goals for/against", f"{int(s.goals_for)}/{int(s.goals_against)}")
    c[4].metric("Goal difference", f"{int(s.goal_diff):+d}")
    c[5].metric("Clean sheets", int(s.clean_sheets))

    ed = cached("team_by_edition", team)
    st.subheader("Performance by edition")
    c1, c2 = st.columns(2)                                   # two measures on different scales -> two charts, never a shared/dual axis
    with c1:
        fig(px.bar(ed, x="season_id", y="goals_for_per_match", color_discrete_sequence=["#2a78d6"], labels={"goals_for_per_match": "Goals scored per match", "season_id": "Edition"}, title="Goals scored per match"))
    with c2:
        fig(px.bar(ed, x="season_id", y="win_pct", color_discrete_sequence=["#2a78d6"], labels={"win_pct": "Win rate (%)", "season_id": "Edition"}, title="Win rate (%)"), key="team_win_pct")
    st.dataframe(ed, hide_index=True, use_container_width=True)

    st.subheader("Historical results")
    res = cached("team_results", team)
    st.dataframe(res, hide_index=True, use_container_width=True)

    st.subheader("Scoring trend")
    ed2 = ed.assign(year=ed.season_id.str.extract(r"(\d{4})")[0].astype(int))
    fig(px.line(ed2, x="year", y="goals_for_per_match", color="competition_id", markers=True, labels={"goals_for_per_match": "Goals scored per match"}))

up = cached("team_upcoming", team)
if len(up):
    st.subheader("Coming soon")
    coming_soon_note(len(up))
    st.dataframe(up, hide_index=True, use_container_width=True)

st.subheader("Compare with another team")
other = st.selectbox("Compare with", [t for t in teams if t != team], index=0)
a, b = cached("team_summary", team).iloc[0], cached("team_summary", other).iloc[0]
cmp = pd.DataFrame({"measure": ["matches", "win_pct", "points_per_match", "goals_for", "goals_against", "goal_diff", "clean_sheets"],
                    team: [a[m] for m in ["matches", "win_pct", "points_per_match", "goals_for", "goals_against", "goal_diff", "clean_sheets"]],
                    other: [b[m] for m in ["matches", "win_pct", "points_per_match", "goals_for", "goals_against", "goal_diff", "clean_sheets"]]})
st.dataframe(cmp, hide_index=True, use_container_width=True)
h2h = cached("head_to_head_table", team, other)
st.markdown(f"**Head-to-head meetings: {len(h2h)}**")
if len(h2h):
    st.dataframe(h2h, hide_index=True, use_container_width=True)
st.caption("Meetings span different competitions, stages and eras: they are context, not a prediction.")
