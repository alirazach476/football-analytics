import streamlit as st

from fbplatform.dashboard import viz_ui as U
from fbplatform.dashboard.lib import require_db
from fbplatform.viz import teams as V
from fbplatform.viz.filters import apply_matches, apply_team_matches

require_db()
st.title("Team visualisations")
st.caption("Result = recorded score (extra time included, shoot-outs excluded). Only matches in the four collected competitions: these are not full national-team records.")

m_all, m_played = U.matches_all(), U.matches_played()
f = U.sidebar_filters(m_all, show_teams=False, show_stages=True)         # the team choice is made on this page (several charts need their own selection)
tm_all = U.team_matches()
tm = apply_team_matches(tm_all, f, "team_name")
mf = apply_matches(m_played, f)
U.filtered_download(mf, "filtered_matches")
U.sample_banner(len(mf), len(m_played))

names = sorted(tm.team_name.unique())
if not names:
    st.info("No team has matches in the current filters.")
    st.stop()
default = [t for t in ("Argentina", "France", "Spain") if t in names] or names[:3]
st.session_state.setdefault("v_team_sel", default)
st.session_state["v_team_sel"] = [t for t in st.session_state["v_team_sel"] if t in names]
sel = st.multiselect("Teams to highlight / compare (also set by clicking a bubble on the scatter below)", names, key="v_team_sel")

tabs = st.tabs(["Results", "Profile", "History", "Head-to-head", "Rankings & consistency"])
with tabs[0]:
    U.render(V.wdl_distribution(tm, sel or None, top_n=20, min_matches=10), "t_wdl")
    c = V.goals_scored_conceded(tm, None, min_matches=15)
    st.caption("Click bubbles to add teams to the selection used by the profile, heat-map and timeline tabs.")
    ev = U.render(c, "t_gfga", select=True)
    idx = U.selected(ev, "point_index")
    if idx and c.available:
        picked = list(c.data.team_name.iloc[[i for i in idx if i < len(c.data)]])
        if picked and set(picked) - set(sel):
            st.session_state["v_team_sel"] = list(dict.fromkeys(sel + picked))[:6]
            st.rerun()

with tabs[1]:
    U.render(V.radar(tm, sel), "t_radar")
    U.render(V.comparison_heatmap(tm, sel or None), "t_heat")

with tabs[2]:
    U.render(V.timeline(tm, sel), "t_timeline")
    U.render(V.edition_heatmap(tm, sel or None), "t_edheat")

with tabs[3]:
    c1, c2 = st.columns(2)
    a = c1.selectbox("Team A", names, index=names.index(sel[0]) if sel and sel[0] in names else 0, key="h2h_a")
    b = c2.selectbox("Team B", names, index=names.index(sel[1]) if len(sel) > 1 and sel[1] in names else min(1, len(names) - 1), key="h2h_b")
    s, t = V.head_to_head(mf, a, b)
    U.render(s, "t_h2h_s")
    U.render(t, "t_h2h_t")

with tabs[4]:
    mn = st.slider("Minimum matches for a team to be ranked", 5, 40, 15)
    U.render(V.rankings(tm, mn), "t_rank")
    U.render(V.consistency(tm, 4), "t_cons")
