import pandas as pd
import plotly.express as px
import streamlit as st

from fbplatform.dashboard.lib import cached, fig, prediction_banner, require_db

require_db()
st.title("Machine learning")
prediction_banner()
meta = cached("ml_meta")
if not meta:
    st.error("No trained models found. Run `python -m fbplatform.ml.outcome` first.")
    st.stop()

tabs = st.tabs(["Match outcome", "Goals", "Explainability", "Clustering", "Try a matchup"])

with tabs[0]:
    comp = cached("ml_outcome_comparison")
    sp = meta["split"]
    st.markdown(f"Chronological split: train {sp['train'][0]} → {sp['train'][1]} ({sp['train'][2]} matches), validation → {sp['validation'][1]} ({sp['validation'][2]}), test {sp['test'][0]} → {sp['test'][1]} ({sp['test'][2]}). "
                f"Selected on validation log loss: **{meta['selected_model']}**. LightGBM was not available.")
    test = comp[comp.split == "test"][["model", "accuracy", "accuracy_ci_low", "accuracy_ci_high", "f1_macro", "log_loss", "log_loss_ci_low", "log_loss_ci_high", "roc_auc_ovr"]]
    st.dataframe(test.round(3), hide_index=True, use_container_width=True)
    fig(px.bar(test, x="model", y="log_loss", error_y=test.log_loss_ci_high - test.log_loss, error_y_minus=test.log_loss - test.log_loss_ci_low, title="Test log loss with 95% bootstrap interval (lower is better)"))
    st.info("The intervals overlap: no complex model is clearly better than the one-feature Elo baseline on this test set. Accuracy of ~55% on three outcomes is realistic for tournament football.")
    cm = cached("ml_importance")["confusion"]
    pick = st.selectbox("Confusion matrix (test period)", cm.model)
    r = cm[cm.model == pick].iloc[0]
    labels = ["A win", "draw", "B win"]
    z = [[r[f"true_{a}__pred_{b}"] for b in labels] for a in labels]
    fig(px.imshow(z, x=[f"predicted {l}" for l in labels], y=[f"actual {l}" for l in labels], text_auto=True, color_continuous_scale="Blues"))
    st.subheader("Out-of-sample predictions vs what happened")
    pr = cached("ml_outcome_predictions")
    show = pr[["match_date", "season_id", "team_a", "team_b", "p_A_win", "p_draw", "p_B_win", "predicted", "result"]].rename(columns={"predicted": "PREDICTION", "result": "actual result (A/D/B)"})
    st.dataframe(show.round(3), hide_index=True, use_container_width=True)
    st.caption("'A' = team listed first. Every row was predicted from matches played before it. The 51 Euro 2028 fixtures cannot be predicted: their teams are not decided yet.")

with tabs[1]:
    g = cached("ml_goals")
    st.dataframe(g["comparison"].round(3), hide_index=True, use_container_width=True)
    st.markdown("**Count-model diagnostics (selected model, test period)**")
    st.dataframe(g["diagnostics"].round(3), hide_index=True, use_container_width=True)
    fig(px.scatter(g["calibration"], x="mean_predicted", y="mean_observed", size="n", title="Calibration: predicted vs observed goals per team (deciles)").add_shape(type="line", x0=0, y0=0, x1=2.5, y1=2.5, line=dict(dash="dash")))
    st.markdown("**Over/under 2.5 goals: an analytical experiment**")
    st.dataframe(g["over_under"].round(3), hide_index=True, use_container_width=True)
    st.caption("Model accuracy for over/under is essentially the base rate: goal totals are very hard to predict.")
    ex = g["expected"].head(40).rename(columns={"predicted_expected_goals": "PREDICTED expected goals", "goals": "actual goals"})
    st.dataframe(ex.drop(columns=["note"]).round(2), hide_index=True, use_container_width=True)

with tabs[2]:
    imp = cached("ml_importance")
    st.markdown("**Permutation importance** (drop in test log-loss score when a feature is shuffled)")
    fig(px.bar(imp["permutation"].head(15).iloc[::-1], x="importance_mean", y="feature", error_x="importance_std", orientation="h"))
    if len(imp["shap"]):
        st.markdown("**SHAP: mean |impact| per outcome (XGBoost)**")
        s = imp["shap"].head(12).melt("feature", ["A win", "draw", "B win"], var_name="outcome", value_name="impact")
        fig(px.bar(s, x="impact", y="feature", color="outcome", orientation="h", barmode="stack", labels={"impact": "mean |SHAP|"}))
    st.markdown("**Partial dependence**")
    feats = imp["pdp"].feature.unique().tolist()
    f = st.selectbox("Feature", feats)
    fig(px.line(imp["pdp"][imp["pdp"].feature == f], x="value", y="partial_dependence", color="outcome", markers=True))
    st.caption("Importance describes the model, not football causality. 'editions' = number of earlier tournament editions the team played, a proxy for tournament experience.")

with tabs[3]:
    cl = cached("ml_clusters")
    st.markdown("**Teams (K-Means)**")
    s = cl["team_summary"].iloc[0]
    st.write(f"Selected k = {int(s.k_selected)} (silhouette {s.silhouette_kmeans:.2f}); bootstrap stability ARI {s.bootstrap_stability_mean_ari:.2f}. The structure is weak: teams form a continuum, not distinct types.")
    st.dataframe(cl["team_profiles"][["kmeans", "n_teams", "gf_pm", "ga_pm", "win_pct", "suggested_description", "members"]], hide_index=True, use_container_width=True)
    fig(px.scatter(cl["teams"], x="gf_pm", y="ga_pm", color="cluster_description", hover_name="team_name", size="matches", labels={"gf_pm": "Goals scored per match", "ga_pm": "Goals conceded per match"}).update_yaxes(autorange="reversed"))
    with st.expander("Exploratory finer split (k=4, lower silhouette)"):
        st.dataframe(cl["team_k4"][["k4", "n_teams", "gf_pm", "ga_pm", "win_pct", "suggested_description", "members"]], hide_index=True, use_container_width=True)
    st.markdown("**Players (K-Means within position, StatsBomb-covered matches only)**")
    st.dataframe(cl["player_profiles"][["position", "cluster", "n_players", "goals_p90", "assists_p90", "tackles_p90", "description", "examples"]], hide_index=True, use_container_width=True)

with tabs[4]:
    st.markdown("Probabilities for a **hypothetical** meeting, built only from matches before the chosen date. This is a model prediction, not a result.")
    teams = cached("team_names")
    c = st.columns(4)
    a = c[0].selectbox("Team A", teams, index=teams.index("Argentina") if "Argentina" in teams else 0)
    b = c[1].selectbox("Team B", teams, index=teams.index("France") if "France" in teams else 1)
    date = c[2].date_input("As of date", pd.Timestamp("2026-07-01"))
    stage = c[3].selectbox("Stage", ["Group stage", "Round of 16", "Quarter-finals", "Semi-finals", "Final"])
    if st.button("Predict") and a != b:
        from fbplatform.ml import outcome
        p = outcome.predict_matchup(a, b, str(date), competition="WC", stage_name=stage)
        fig(px.bar(pd.DataFrame({"outcome": list(p["probabilities"]), "probability": list(p["probabilities"].values())}), x="outcome", y="probability", range_y=[0, 1], text_auto=".0%"))
        st.caption(f"{p['label']} · uses only matches before {p['based_on_matches_before']}")
