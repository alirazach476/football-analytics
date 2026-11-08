import streamlit as st

from fbplatform.dashboard import viz_ui as U
from fbplatform.dashboard.lib import require_db
from fbplatform.viz import competition as V
from fbplatform.viz.filters import apply_matches, apply_seasons

require_db()
st.title("Competition visualisations")
st.caption("Played matches only; upcoming fixtures appear in brackets as 'Coming soon'. Edition-level charts use whole editions (competition/edition filters apply; date, stage and team filters apply to match-level charts).")

m_all, m_played = U.matches_all(), U.matches_played()
f = U.sidebar_filters(m_all, show_teams=True, show_stages=True)
mf, maf = apply_matches(m_played, f), apply_matches(m_all, f)
tr = apply_seasons(U.tournaments(), f)
U.filtered_download(mf, "filtered_matches")
U.sample_banner(len(mf), len(m_played))

tabs = st.tabs(["History", "Champions", "Edition comparison", "Progression & groups", "Knockout bracket", "Goal distributions"])
seasons_avail = list(tr.season_id) if len(tr) else []

with tabs[0]:
    measure = st.radio("Measure", ["total_goals", "matches_played", "goals_per_match"], index=2, horizontal=True, format_func=lambda x: {"total_goals": "Goals", "matches_played": "Matches", "goals_per_match": "Goals per match"}[x])
    st.caption("Click a bar or point to select that edition: the detail tabs (progression, standings, bracket) follow your selection.")
    ev = U.render(V.edition_history(tr, measure), "v_hist", select=True)
    picks = [c[0] for c in U.selected(ev, "customdata")] if measure == "goals_per_match" else U.selected(ev, "x")
    if picks:
        st.session_state["xf_season"] = picks[-1]
    sel = st.session_state.get("xf_season")
    if sel:
        c1, c2 = st.columns([4, 1])
        c1.success(f"Selected edition: **{sel}** (used in the detail tabs)")
        if c2.button("Clear selection"):
            st.session_state.pop("xf_season", None)
            st.rerun()

with tabs[1]:
    U.render(V.champions_timeline(tr), "v_champ")
    U.render(V.title_counts(tr), "v_titles")

with tabs[2]:
    metric = st.selectbox("Measure", list(V.METRICS), format_func=lambda k: V.METRICS[k])
    U.render(V.edition_comparison(tr, metric), "v_cmp")
    U.render(V.edition_heatmap(tr), "v_cmp_heat")

detail_default = st.session_state.get("xf_season")
with tabs[3]:
    if not seasons_avail:
        st.info("No edition matches the current filters.")
    else:
        season = st.selectbox("Edition", seasons_avail, index=seasons_avail.index(detail_default) if detail_default in seasons_avail else len(seasons_avail) - 1, key="v_prog_season")
        U.render(V.progression_funnel(maf[maf.season_id == season], season), "v_funnel")
        U.render(V.group_standings(U.standings(), season), "v_groups")

with tabs[4]:
    if not seasons_avail:
        st.info("No edition matches the current filters.")
    else:
        season = st.selectbox("Edition", seasons_avail, index=seasons_avail.index(detail_default) if detail_default in seasons_avail else len(seasons_avail) - 1, key="v_bracket_season")
        ms = m_all[m_all.season_id == season]                                    # a bracket is shown whole (upcoming matches as 'Coming soon')
        U.render(V.knockout_bracket(ms, season), "v_bracket")

with tabs[5]:
    reg = st.toggle("Regulation time only (exclude extra-time goals)", value=True)
    U.render(V.goal_distribution(mf, regulation=reg), "v_gdist")
    g = U.goals()
    gf = g[g.match_key.isin(mf.match_key)] if len(mf) else g.iloc[0:0]
    U.render(V.goal_minutes(gf), "v_gmin")
