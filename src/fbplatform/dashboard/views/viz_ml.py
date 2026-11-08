import streamlit as st

from fbplatform.dashboard import viz_ui as U
from fbplatform.dashboard.lib import prediction_banner, require_db
from fbplatform.viz import mlplots as V

require_db()
st.title("Machine-learning visualisations")
prediction_banner()
st.caption("All curves and matrices come from the SAVED models applied to the chronological test period (nothing is retrained here). The test period was never used for training or tuning.")

t, g = U.outcome_test(), U.goal_test()
if t is None:
    st.error("No saved models found. Run `python -m fbplatform.ml.outcome` and `python -m fbplatform.ml.goals` first.")
    st.stop()
models = [m for m in V.MODEL_ORDER if m in t["proba"]]
cls_names = V.CLASSES

tabs = st.tabs(["Classification", "Importance & SHAP", "Calibration & residuals", "Clustering", "Model comparison"])
with tabs[0]:
    c1, c2 = st.columns(2)
    model = c1.selectbox("Model", models, index=len(models) - 1)
    norm = c2.toggle("Show row percentages", value=True)
    U.render(V.confusion(t, model, norm), "ml_cm")
    cls = st.radio("Outcome for the curves (one-vs-rest)", [0, 1, 2], format_func=lambda i: cls_names[i], horizontal=True)
    U.render(V.roc_curves(t, cls), "ml_roc")
    U.render(V.pr_curves(t, cls), "ml_pr")

with tabs[1]:
    U.render(V.feature_importance("permutation"), "ml_perm")
    U.render(V.feature_importance("gain"), "ml_gain")
    sv = U.shap_values()
    U.render(V.shap_bar(sv), "ml_shap_bar")
    cls2 = st.radio("Outcome for the beeswarm", [0, 1, 2], format_func=lambda i: cls_names[i], horizontal=True, key="shap_cls")
    U.render(V.shap_beeswarm(sv, cls2), "ml_shap_swarm")
    if sv is not None:
        feats = list(sv[1].columns)
        feat = st.selectbox("Dependence plot feature", feats, index=feats.index("elo_diff") if "elo_diff" in feats else 0)
        U.render(V.shap_dependence(sv, feat, cls2), "ml_shap_dep")

with tabs[2]:
    c1, c2 = st.columns(2)
    m2 = c1.selectbox("Model", models, index=len(models) - 1, key="cal_model")
    k2 = c2.selectbox("Outcome", [0, 1, 2], format_func=lambda i: cls_names[i], key="cal_cls")
    U.render(V.calibration(t, m2, k2), "ml_cal")
    U.render(V.goals_actual_vs_predicted(g), "ml_goals_avp")
    U.render(V.residual_plots(g), "ml_resid")

with tabs[3]:
    U.render(V.team_cluster_scatter(), "ml_team_cl")
    U.render(V.silhouette_by_k(), "ml_sil")
    U.render(V.team_dendrogram(), "ml_dendro")
    pos = st.radio("Players: position group", ["Forward", "Midfielder", "Defender"], horizontal=True)
    U.render(V.player_cluster_scatter(pos), "ml_player_cl")

with tabs[4]:
    metric = st.radio("Outcome-model metric", ["log_loss", "accuracy", "f1_macro", "roc_auc_ovr"], horizontal=True)
    U.render(V.model_comparison(metric), "ml_cmp")
    gm = st.radio("Goal-model metric", ["poisson_deviance", "mae_team_goals", "rmse_team_goals", "mae_total_goals"], horizontal=True)
    U.render(V.goal_model_comparison(gm), "ml_gcmp")
