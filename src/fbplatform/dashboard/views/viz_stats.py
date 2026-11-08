import streamlit as st

from fbplatform.dashboard import viz_ui as U
from fbplatform.dashboard.lib import require_db
from fbplatform.viz import statplots as V
from fbplatform.viz.filters import apply_matches, apply_team_matches

require_db()
st.title("Statistical visualisations")
st.caption("Association is not causation. Goal counts are discrete and over-dispersed, so rank-based and count-model tools are used; every chart shows its sample size.")

m_all, m_played = U.matches_all(), U.matches_played()
f = U.sidebar_filters(m_all, show_teams=False, show_stages=True)
mf = apply_matches(m_played, f)
tm = apply_team_matches(U.team_matches(), f, "team_name")
te = V.team_edition_table(tm)
U.filtered_download(mf, "filtered_matches")
U.sample_banner(len(mf), len(m_played))
res = V.load_results()

tabs = st.tabs(["Correlations", "Distributions", "Box & violin", "Scatter & regression", "Confidence intervals", "Hypothesis tests", "Regression diagnostics"])
cols = {"gf_pm": "Goals for / match", "ga_pm": "Goals against / match", "ppm": "Points / match", "win_pct": "Win %", "cs_pct": "Clean sheets %"}
with tabs[0]:
    method = st.radio("Method", ["spearman", "pearson"], horizontal=True)
    U.render(V.correlation_matrix(te, cols, method), "s_corr")
with tabs[1]:
    var = st.radio("Variable", ["goals90", "goals_total", "margin"], horizontal=True, format_func=lambda x: V.VAR_LABEL[x])
    U.render(V.distribution(mf, var), "s_dist")
with tabs[2]:
    var = st.radio("Variable", ["goals90", "margin"], horizontal=True, format_func=lambda x: V.VAR_LABEL[x], key="bv_var")
    by = st.radio("Group by", ["stage_name", "competition_id"], horizontal=True, format_func=lambda x: {"stage_name": "Stage", "competition_id": "Competition"}[x])
    U.render(V.box_plot(mf, var, by), "s_box")
    U.render(V.violin_plot(mf, "margin", "competition_id"), "s_violin")
with tabs[3]:
    c1, c2 = st.columns(2)
    x = c1.selectbox("X", list(cols), format_func=lambda k: cols[k], index=0)
    y = c2.selectbox("Y", [k for k in cols if k != x], format_func=lambda k: cols[k], index=1)
    U.render(V.scatter_regression(te, x, y, cols[x], cols[y]), "s_scatter")
with tabs[4]:
    if res.empty:
        st.info("Run `python -m fbplatform.analysis.stats` to create reports/statistics/results.csv.")
    else:
        kind = st.radio("Kind of estimate (each kind has its own scale)", ["ratio", "difference", "proportion"], horizontal=True)
        U.render(V.ci_forest(res, kind), "s_forest")
with tabs[5]:
    if res.empty:
        st.info("Run `python -m fbplatform.analysis.stats` to create reports/statistics/results.csv.")
    else:
        U.render(V.hypothesis_summary(res), "s_hyp")
with tabs[6]:
    c = V.regression_diagnostics(mf)
    U.render(c, "s_diag")
    if c.available and st.toggle("Show the Matplotlib/Seaborn version"):
        st.pyplot(c.static())
