import pandas as pd
import streamlit as st

from fbplatform.dashboard import viz_ui as U
from fbplatform.dashboard.lib import require_db
from fbplatform.viz import players as V
from fbplatform.viz.filters import apply_matches

require_db()
st.title("Player visualisations")
st.warning("Collected competitions only (not careers). Goals are goals linked to a player id (Nations League scorers are not linked). Assists exist only in editions with event-level data. Per-90 rates use only matches with known minutes. Position and age are known for a subset of players: others are omitted, never guessed.", icon="ℹ️")

m_all = U.matches_all()
f = U.sidebar_filters(m_all, show_teams=False, show_stages=False)
ps_all = U.player_seasons()
mask = pd.Series(True, index=ps_all.index)
if f.seasons:
    mask &= ps_all.season_id.isin(f.seasons)
if f.competitions:
    mask &= ps_all.season_id.str.split("-").str[0].isin(f.competitions)
ps = ps_all[mask]
if f.teams:
    ps = ps[ps.team_name.isin(f.teams)]
rel = U.reliable_seasons()
st.sidebar.markdown("**Player filter**")
term = st.sidebar.text_input("Find players (name contains)", "", key="p_term")
pool = sorted(ps[ps.full_name.str.contains(term, case=False, na=False)].groupby("full_name").goals.sum().sort_values(ascending=False).head(300).index) if len(term) >= 2 else \
    list(ps.groupby("full_name").goals.sum().sort_values(ascending=False).head(60).index)
picked = st.sidebar.multiselect("Players", pool, default=[p for p in pool[:2]] if not term else [], key="p_sel")
st.caption(f"{len(ps):,} player-tournament rows in the current selection · {ps.player_key.nunique():,} players · editions with assist data: {len(rel)}")
U.filtered_download(ps[["full_name", "nationality", "team_name", "season_id", "appearances", "starts", "minutes_played", "goals", "assists", "goals_per_90", "primary_position", "age"]], "filtered_player_seasons", "Download the filtered player rows (CSV)")

tabs = st.tabs(["Top scorers & assists", "Per 90 minutes", "Profile radar", "Trends", "Age & position", "Contribution index"])
with tabs[0]:
    n = st.slider("How many players", 10, 40, 20)
    U.render(V.top_players(ps, "goals", n, rel), "p_goals")
    U.render(V.top_players(ps, "assists", n, rel), "p_assists")
with tabs[1]:
    mm = st.slider("Minimum known minutes", 90, 1500, 270, step=90)
    U.render(V.per90(ps, "goals", mm, rel), "p_p90g")
    U.render(V.per90(ps, "assists", mm, rel), "p_p90a")
with tabs[2]:
    stats = U.player_stats()
    names = sorted(stats.full_name.unique())
    default = [n for n in picked if n in names] or [n for n in ("Harry Kane", "Luka Modrić") if n in names]
    sel = st.multiselect("Players with event-level data (max 4)", names, default=default[:4], max_selections=4, key="p_radar")
    U.render(V.radar(stats, sel), "p_radar_chart")
with tabs[3]:
    measure = st.radio("Measure", ["goals", "assists"], horizontal=True)
    U.render(V.trends(ps, picked or list(pool[:2]), measure), "p_trend")
with tabs[4]:
    U.render(V.age_vs_performance(ps), "p_age")
    U.render(V.position_comparison(ps), "p_pos")
with tabs[5]:
    pci = U.contribution_index()
    mm2 = st.slider("Minimum known minutes", 270, 3000, 900, step=90, key="pci_min")
    U.render(V.contribution(pci, mm2), "p_pci")
