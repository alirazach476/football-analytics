import pandas as pd
import streamlit as st

from fbplatform.dashboard import viz_ui as U
from fbplatform.dashboard.lib import require_db
from fbplatform.viz import matches as V
from fbplatform.viz.filters import apply_matches

require_db()
st.title("Match visualisations")
st.caption("Event-level charts are drawn only from data that exists: shot maps need shot coordinates (StatsBomb/Wyscout matches), passing networks need recorded pass recipients (StatsBomb), score progression must reproduce the final score. Otherwise the chart says why it is not shown.")

m_all, m_played = U.matches_all(), U.matches_played()
f = U.sidebar_filters(m_all, show_teams=True, show_stages=True)
mf, maf = apply_matches(m_played, f), apply_matches(m_all, f)
U.filtered_download(mf, "filtered_matches")
U.sample_banner(len(mf), len(m_played))

tabs = st.tabs(["Single match", "Shots (maps)", "Distributions", "Home / away", "Penalty shoot-outs"])

with tabs[0]:
    if maf.empty:
        st.info("No matches in the current filters.")
    else:
        opts = maf.sort_values("match_date", ascending=False).head(400)
        label = lambda r: f"{r.match_date:%Y-%m-%d} · {r.home_team_name} {'' if pd.isna(r.home_score) else int(r.home_score)}–{'' if pd.isna(r.away_score) else int(r.away_score)} {r.away_team_name} · {r.stage_name} ({r.season_id})" + ("  · COMING SOON" if not r.is_played else "")
        lab = {int(r.match_key): label(r) for r in opts.itertuples()}
        played_first = next((i for i, k in enumerate(lab) if bool(opts[opts.match_key == k].iloc[0].is_played)), 0)         # default = latest PLAYED match; fixtures stay selectable
        mk = st.selectbox("Match (most recent 400 in the filters; 'COMING SOON' = not played yet)", list(lab), index=played_first, format_func=lambda k: lab[k])
        row = opts[opts.match_key == mk].iloc[0]
        if not row.is_played:
            st.info(f"**Coming soon.** {row.fixture_detail}. No result and no events exist yet.")
        else:
            e = V.load_match_events(int(mk))
            st.markdown(f"**{row.home_team_name} {int(row.home_score)} – {int(row.away_score)} {row.away_team_name}** · {row.stage_name} · {pd.Timestamp(row.match_date):%Y-%m-%d}")
            U.render(V.goal_timeline(row, e), "m_goal_tl")
            U.render(V.score_progression(row, e), "m_prog")
            U.render(V.event_timeline(row, e), "m_events")
            sh = V.load_shots([int(mk)])
            U.render(V.shot_map(sh, f"Shots: {row.home_team_name} v {row.away_team_name}"), "m_shots_one")
            passes = V.load_passes(int(mk))
            team = st.radio("Passing network for", [row.home_team_name, row.away_team_name], horizontal=True)
            upto = st.slider("Use passes up to minute", 15, 120, 60, help="Before the first substitution the network shows the starting players only")
            U.render(V.passing_network(passes, team, upto), "m_net")

with tabs[1]:
    seasons_with = ["WC-2018", "WC-2022", "EURO-2016", "EURO-2020", "EURO-2024", "COPA-2024"]
    c1, c2 = st.columns(2)
    season = c1.selectbox("Edition (only these have shot coordinates)", seasons_with, index=1)
    teams = sorted(set(m_played[m_played.season_id == season].home_team_name) | set(m_played[m_played.season_id == season].away_team_name))
    team = c2.selectbox("Team", teams)
    U.render(V.shot_map(V.load_shots(season_id=season, team=team), f"{team}: all shots, {season}"), "m_shots_team")

with tabs[2]:
    U.render(V.scoreline_heatmap(mf), "m_scoreline")
    by = st.radio("Group outcomes by", ["competition_id", "season_id", "stage_name"], horizontal=True, format_func=lambda x: {"competition_id": "Competition", "season_id": "Edition", "stage_name": "Stage"}[x])
    U.render(V.outcome_distribution(mf, by), "m_outcome")

with tabs[3]:
    U.render(V.home_away(mf, U.team_country()), "m_homeaway")

with tabs[4]:
    a, b, c = V.shootouts(mf)
    U.render(a, "m_so_ed")
    U.render(b, "m_so_sc")
    U.render(c, "m_so_rec")
