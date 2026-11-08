import pandas as pd
import plotly.express as px
import streamlit as st

from fbplatform.dashboard.lib import cached, fig, require_db

require_db()
st.title("Match analytics")
seasons = cached("season_ids")
teams = cached("team_names")
season = st.sidebar.selectbox("Edition", ["(all)"] + seasons, index=seasons.index("WC-2022") + 1 if "WC-2022" in seasons else 0)
team = st.sidebar.selectbox("Team", ["(any)"] + teams)
upcoming = st.sidebar.checkbox("Include 'Coming soon' fixtures", value=True)

res = cached("match_search", None if season == "(all)" else season, None if team == "(any)" else team, upcoming)
st.caption(f"{len(res)} matches shown (most recent first, max 200).")
if res.empty:
    st.info("No matches for this filter.")
    st.stop()
label = lambda r: f"{r.match_date:%Y-%m-%d} · {r.home_team_name} {'' if pd.isna(r.home_score) else int(r.home_score)}–{'' if pd.isna(r.away_score) else int(r.away_score)} {r.away_team_name} · {r.stage_name} ({r.season_id})" + (" · COMING SOON" if r.status_label == "Coming soon" else "")
rows = {int(r.match_key): label(r) for r in res.itertuples()}
mk = st.selectbox("Match", list(rows), format_func=lambda k: rows[k])
m = cached("match_row", mk).iloc[0]

st.markdown(f"### {m.home_team_name}  {'–' if not m.is_played else int(m.home_score)}  :  {'–' if not m.is_played else int(m.away_score)}  {m.away_team_name}")
bits = [str(m.match_date), m.stage_name, f"Group {m.group_name}" if isinstance(m.group_name, str) else None, m.venue_name if isinstance(m.venue_name, str) else "venue to be confirmed",
        m.venue_city if isinstance(m.venue_city, str) else None, f"attendance {int(m.attendance):,}" if pd.notna(m.attendance) else None, f"referee {m.referee_name}" if isinstance(m.referee_name, str) else None]
st.caption(" · ".join(b for b in bits if b))
if not m.is_played:
    st.info(f"**Coming soon.** {m.fixture_detail}. No result exists yet.")
    st.stop()
if m.had_shootout:
    side = m.shootout_winner_side
    pens = f" ({int(m.home_pen)}–{int(m.away_pen)} on penalties)" if pd.notna(m.home_pen) else ""
    st.write(f"Level after extra time; **{m.home_team_name if side == 'home' else m.away_team_name}** won the shoot-out{pens}.")
elif m.went_beyond_90:
    st.write("Went to extra time.")
if isinstance(m.man_of_the_match_raw, str):
    st.write(f"Man of the match: **{m.man_of_the_match_raw}**")

t1, t2, t3, t4 = st.tabs(["Timeline", "Match statistics", "Line-ups", "Head-to-head & goal timing"])
with t1:
    tl = cached("match_timeline", mk)
    if tl.empty:
        st.info("No event timeline available for this match (the sources have no minute-level events for it).")
    else:
        st.dataframe(tl[["minute", "minute_added", "kind", "team_name", "player", "other_player", "provider"]], hide_index=True, use_container_width=True)
        goals = tl[tl.kind.isin(["Goal", "Own goal"])]
        if len(goals):
            fig(px.scatter(goals, x="minute", y="team_name", color="kind", hover_data=["player"], title="Goal timeline", size_max=12).update_traces(marker_size=14))
with t2:
    st_ = cached("match_team_stats", mk)
    if st_.empty:
        st.info("No team statistics for this match: they exist only for event-level (StatsBomb) coverage.")
    else:
        st.dataframe(st_, hide_index=True, use_container_width=True)
with t3:
    lu = cached("match_lineups", mk)
    st.dataframe(lu, hide_index=True, use_container_width=True) if len(lu) else st.info("No line-up recorded for this match.")
with t4:
    h = cached("head_to_head_table", m.home_team_name, m.away_team_name)
    st.markdown(f"**Meetings between {m.home_team_name} and {m.away_team_name} in these competitions: {len(h)}**")
    st.dataframe(h, hide_index=True, use_container_width=True)
    g = cached("goals_by_minute", m.competition_id, m.season_id)
    fig(px.bar(g, x="minute_band", y="goals", title=f"Goals by minute band in {m.season_id} (whole edition)"))
