"""Machine-learning visualisations built from the SAVED models and reports (nothing is retrained here):
confusion matrices, ROC and precision-recall curves, feature importance, SHAP, calibration / actual-vs-predicted, residuals, clustering views, model comparison.
Predictions come from `models/*.joblib` applied to the chronological TEST period (matches after the training and validation periods)."""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.metrics import auc, precision_recall_curve, roc_curve

from ..config import ROOT
from ..ml import features as F
from . import common as C
from .common import Chart, unavailable

MODELS = ROOT / "models"
REPORTS = ROOT / "reports" / "ml"
CLASSES = ["A win", "draw", "B win"]
MODEL_ORDER = ["baseline_prior", "baseline_elo_logreg", "logreg", "random_forest", "xgboost"]
MODEL_COLOR = {m: C.CAT[i] for i, m in enumerate(MODEL_ORDER)}          # a model keeps its colour in every chart
SRC = "models/*.joblib applied to the chronological test period; reports/ml/*"


# ------------------------------------------------------------------ loaders
def load_outcome_test() -> dict | None:
    """-> {'y': array, 'proba': {model: n x 3}, 'X': DataFrame, 'frame': test rows} or None when models are missing."""
    if not (MODELS / "match_outcome_xgboost.joblib").exists():
        return None
    df = F.build_match_features()
    _, _, te = F.chronological_split(df)
    X = F.feature_matrix(te)
    proba = {}
    for name in MODEL_ORDER:
        p, meta = MODELS / f"match_outcome_{name}.joblib", MODELS / f"match_outcome_{name}.json"
        if p.exists() and meta.exists():
            cols = json.loads(meta.read_text(encoding="utf-8"))["features"]
            proba[name] = joblib.load(p).predict_proba(X[cols])
    return dict(y=te.y.values, proba=proba, X=X, frame=te)


def load_goal_test() -> dict | None:
    sel = MODELS / "goals_selected.json"
    if not sel.exists():
        return None
    meta = json.loads(sel.read_text(encoding="utf-8"))
    df = F.build_match_features()
    _, _, te = F.chronological_split(df)
    rows = F.team_rows(te)
    rows = rows[rows.goals.notna()].reset_index(drop=True)
    model = joblib.load(MODELS / "goals_selected.joblib")
    mu = np.clip(model.predict(rows[meta["features"]]), 1e-3, None)
    return dict(rows=rows.assign(predicted=mu), model=meta["selected_model"])


def load_shap(class_idx: int = 0):
    """SHAP values of the saved XGBoost outcome model on the test period. Returns (values n x features, X) or None."""
    try:
        import shap
    except Exception:
        return None
    t = load_outcome_test()
    if t is None or "xgboost" not in t["proba"]:
        return None
    meta = json.loads((MODELS / "match_outcome_xgboost.json").read_text(encoding="utf-8"))
    model = joblib.load(MODELS / "match_outcome_xgboost.joblib")
    X = t["X"][meta["features"]]
    sv = shap.TreeExplainer(model).shap_values(X)
    sv = np.stack(sv, axis=-1) if isinstance(sv, list) else sv
    return sv, X


def _csv(*p) -> pd.DataFrame:
    f = REPORTS.joinpath(*p)
    return pd.read_csv(f) if f.exists() else pd.DataFrame()


# ------------------------------------------------------------------ classification
def confusion(t: dict, model: str, normalise: bool = True) -> Chart:
    if t is None or model not in t["proba"]:
        return unavailable("confusion", "saved model or test predictions not found (run python -m fbplatform.ml.outcome)")
    pred = t["proba"][model].argmax(1)
    cm = pd.crosstab(pd.Series(t["y"], name="actual"), pd.Series(pred, name="pred")).reindex(index=range(3), columns=range(3), fill_value=0)
    rate = cm.div(cm.sum(axis=1).replace(0, np.nan), axis=0) * 100
    z = rate if normalise else cm
    txt = [[f"{cm.iloc[i, j]}<br>({rate.iloc[i, j]:.0f}%)" if not np.isnan(rate.iloc[i, j]) else "0" for j in range(3)] for i in range(3)]
    fig = go.Figure(go.Heatmap(z=z.values, x=[f"predicted {c}" for c in CLASSES], y=[f"actual {c}" for c in CLASSES], colorscale=C.SEQ, text=txt, texttemplate="%{text}", xgap=3, ygap=3, zmin=0,
                               colorbar=dict(title="% of actual" if normalise else "matches"), hovertemplate="%{y} → %{x}<br>%{text}<extra></extra>"))
    C.style(fig, f"Confusion matrix: {model} (test period, n = {len(t['y'])})", None, None, legend=False, height=420)
    fig.update_yaxes(autorange="reversed")
    return Chart(fig, cm.rename(index=dict(enumerate(CLASSES)), columns=dict(enumerate(CLASSES))).reset_index(), len(t["y"]), SRC,
                 "Rows = what happened, columns = what the model predicted; colour = share of each actual outcome. Draws are almost never predicted (draw recall 0–4% for every model).", name=f"confusion_{model}")


def roc_curves(t: dict, cls: int = 0) -> Chart:
    if t is None or not t["proba"]:
        return unavailable("roc_curves", "saved models / test predictions not found")
    y = (t["y"] == cls).astype(int)
    if y.sum() < 10 or (1 - y).sum() < 10:
        return unavailable("roc_curves", f"fewer than 10 test matches in one of the two groups for '{CLASSES[cls]}'")
    fig = go.Figure()
    rows = []
    for name in MODEL_ORDER:
        if name not in t["proba"]:
            continue
        fpr, tpr, _ = roc_curve(y, t["proba"][name][:, cls])
        a = auc(fpr, tpr)
        fig.add_scatter(x=fpr, y=tpr, mode="lines", name=f"{name} (AUC {a:.2f})", line=dict(color=MODEL_COLOR[name], width=2), hovertemplate="FPR %{x:.2f} · TPR %{y:.2f}<extra>" + name + "</extra>")
        rows.append(dict(model=name, auc=round(a, 4), positives=int(y.sum()), negatives=int((1 - y).sum())))
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="chance", line=dict(color=C.AXIS, width=1), hoverinfo="skip")
    C.style(fig, f"ROC curves: '{CLASSES[cls]}' vs the rest (test period, n = {len(y)})", "False-positive rate", "True-positive rate", height=480)
    fig.update_xaxes(range=[0, 1]); fig.update_yaxes(range=[0, 1.02], scaleanchor="x")
    return Chart(fig, pd.DataFrame(rows), len(y), SRC, f"One-vs-rest curve for '{CLASSES[cls]}'. A model on the diagonal is no better than chance (the class-prior baseline is a point on it). With {int(y.sum())} positives the curves are noisy: differences of 0.03–0.05 AUC are not reliable.", name=f"roc_{cls}")


def pr_curves(t: dict, cls: int = 0) -> Chart:
    if t is None or not t["proba"]:
        return unavailable("pr_curves", "saved models / test predictions not found")
    y = (t["y"] == cls).astype(int)
    if y.sum() < 10:
        return unavailable("pr_curves", f"fewer than 10 test matches with outcome '{CLASSES[cls]}'")
    fig = go.Figure()
    rows = []
    for name in MODEL_ORDER:
        if name not in t["proba"]:
            continue
        p, r, _ = precision_recall_curve(y, t["proba"][name][:, cls])
        a = auc(r, p)
        fig.add_scatter(x=r, y=p, mode="lines", name=f"{name} (AP≈{a:.2f})", line=dict(color=MODEL_COLOR[name], width=2), hovertemplate="recall %{x:.2f} · precision %{y:.2f}<extra>" + name + "</extra>")
        rows.append(dict(model=name, area_under_pr=round(a, 4), prevalence=round(float(y.mean()), 4)))
    fig.add_hline(y=float(y.mean()), line=dict(color=C.AXIS, width=1))
    C.style(fig, f"Precision–recall curves: '{CLASSES[cls]}' (test period, n = {len(y)})", "Recall", "Precision", height=480)
    fig.update_xaxes(range=[0, 1]); fig.update_yaxes(range=[0, 1.02])
    return Chart(fig, pd.DataFrame(rows), len(y), SRC, f"Grey line = prevalence of '{CLASSES[cls]}' ({100 * y.mean():.0f}%): precision below it is worse than guessing. Area under the curve is trapezoidal (approximates average precision).", name=f"pr_{cls}")


# ------------------------------------------------------------------ importance and SHAP
def feature_importance(kind: str = "permutation", top: int = 15) -> Chart:
    f = _csv("outcome", "permutation_importance.csv" if kind == "permutation" else "xgboost_gain_importance.csv")
    if f.empty:
        return unavailable("feature_importance", "importance report not found (run python -m fbplatform.ml.outcome)")
    col, err = ("importance_mean", "importance_std") if kind == "permutation" else ("gain", None)
    d = f.sort_values(col, ascending=False).head(top).iloc[::-1]
    fig = go.Figure(go.Bar(y=d.feature, x=d[col], orientation="h", marker_color=C.CAT[0], error_x=dict(type="data", array=d[err], color=C.INK2, thickness=1.2, width=3) if err else None,
                           hovertemplate="<b>%{y}</b><br>%{x:.4f}<extra></extra>"))
    C.style(fig, "Permutation importance (test period)" if kind == "permutation" else "XGBoost gain importance (training)", "Drop in log-loss score when the feature is shuffled (± SD of 30 repeats)" if kind == "permutation" else "Share of total gain", None, legend=False, height=max(360, 24 * len(d) + 140))
    C.bar_gap(fig)
    return Chart(fig, f.sort_values(col, ascending=False), len(f), "reports/ml/outcome", "Importance describes the MODEL, not football causality; correlated features (e.g. Elo difference and goal-difference average) share credit. 'editions' = earlier tournament editions a team has played.", name=f"importance_{kind}")


def shap_bar(sv_x, top: int = 12) -> Chart:
    if sv_x is None:
        return unavailable("shap_bar", "SHAP or the saved XGBoost model is not available")
    sv, X = sv_x
    mean_abs = pd.DataFrame(np.abs(sv).mean(axis=0), index=X.columns, columns=CLASSES)
    mean_abs["total"] = mean_abs.sum(axis=1)
    d = mean_abs.sort_values("total", ascending=False).head(top).iloc[::-1]
    fig = go.Figure()
    for i, c in enumerate(CLASSES):
        fig.add_bar(y=d.index, x=d[c], name=c, orientation="h", marker_color=[C.CAT[0], C.OUTCOME_COLOR["draw"], C.CAT[1]][i], hovertemplate="%{y}<br>" + c + ": %{x:.3f}<extra></extra>")
    fig.update_layout(barmode="stack")
    C.style(fig, f"SHAP: mean |impact| on each outcome (XGBoost, n = {len(X)} test matches)", "Mean |SHAP value| (log-odds units)", None, height=max(380, 26 * len(d) + 150))
    C.bar_gap(fig)
    return Chart(fig, mean_abs.round(4).reset_index(names="feature"), len(X), SRC, "Larger = the feature moves the predicted probability more (on average) for that outcome. Magnitude only: direction is in the beeswarm.", name="shap_bar")


def shap_beeswarm(sv_x, cls: int = 0, top: int = 10) -> Chart:
    if sv_x is None:
        return unavailable("shap_beeswarm", "SHAP or the saved XGBoost model is not available")
    sv, X = sv_x
    v = sv[:, :, cls]
    order = np.argsort(np.abs(v).mean(axis=0))[::-1][:top][::-1]
    fig = go.Figure()
    rng = np.random.default_rng(3)
    rows = []
    for yi, j in enumerate(order):
        f = X.columns[j]
        col = X.iloc[:, j]
        rank = col.rank(pct=True).fillna(0.5)                                    # colour = rank of the feature value (missing -> middle)
        fig.add_scatter(x=v[:, j], y=yi + rng.uniform(-0.28, 0.28, len(v)), mode="markers", showlegend=False,
                        marker=dict(size=6, color=rank, colorscale=[[0, "#cde2fb"], [1, "#0d366b"]], cmin=0, cmax=1, opacity=0.8, showscale=(yi == len(order) - 1), colorbar=dict(title="feature value<br>(low → high)", thickness=12, tickvals=[0, 1], ticktext=["low", "high"])),
                        customdata=np.c_[[f] * len(v), col.values], hovertemplate="%{customdata[0]} = %{customdata[1]:.2f}<br>SHAP %{x:.3f}<extra></extra>")
        rows += [dict(feature=f, feature_value=a, shap_value=b) for a, b in zip(col.values, v[:, j])]
    fig.add_vline(x=0, line=dict(color=C.AXIS, width=1))
    C.style(fig, f"SHAP beeswarm for '{CLASSES[cls]}' (each dot = one test match)", f"SHAP value: pushes the probability of '{CLASSES[cls]}' up (right) or down (left)", None, legend=False, height=max(420, 44 * len(order) + 120))
    fig.update_yaxes(tickvals=list(range(len(order))), ticktext=[X.columns[j] for j in order], gridcolor=C.GRID)
    return Chart(fig, pd.DataFrame(rows).round(4), len(X), SRC, "Dark dot = high value of the feature, light = low (rank within the test matches; missing values sit in the middle). Explains the MODEL's behaviour, not causes. Log-odds scale.", name="shap_beeswarm")


def shap_dependence(sv_x, feature: str, cls: int = 0) -> Chart:
    if sv_x is None:
        return unavailable("shap_dependence", "SHAP or the saved XGBoost model is not available")
    sv, X = sv_x
    if feature not in X.columns:
        return unavailable("shap_dependence", f"feature '{feature}' is not in the model")
    j = list(X.columns).index(feature)
    fig = go.Figure(go.Scatter(x=X[feature], y=sv[:, j, cls], mode="markers", marker=dict(size=7, color=C.CAT[0], opacity=0.65, line=dict(color=C.SURFACE, width=1)), hovertemplate=feature + " = %{x:.2f}<br>SHAP %{y:.3f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=C.AXIS, width=1))
    C.style(fig, f"SHAP dependence: {feature} → '{CLASSES[cls]}'", feature, f"SHAP value for '{CLASSES[cls]}'", legend=False, height=420)
    return Chart(fig, pd.DataFrame({feature: X[feature], "shap": sv[:, j, cls]}).round(4), len(X), SRC, "Matches with a missing feature value (e.g. no earlier history) are drawn at their (imputed/native-NaN) position only if the value exists; NaN rows are not plotted.", name=f"shap_dependence_{feature}")


# ------------------------------------------------------------------ actual vs predicted, residuals
def calibration(t: dict, model: str, cls: int = 0, bins: int = 8) -> Chart:
    if t is None or model not in t["proba"]:
        return unavailable("calibration", "saved model / test predictions not found")
    p = t["proba"][model][:, cls]
    y = (t["y"] == cls).astype(int)
    q = pd.qcut(p, bins, duplicates="drop")
    d = pd.DataFrame({"p": p, "y": y, "bin": q}).groupby("bin", observed=True).agg(predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size")).reset_index(drop=True)
    d["lo"], d["hi"] = zip(*[C.wilson(int(round(o * n)), int(n)) for o, n in zip(d.observed, d.n)])
    if len(d) < 3:
        return unavailable("calibration", "too few distinct predicted probabilities for a reliability plot")
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=C.AXIS, width=1), name="perfect calibration", hoverinfo="skip")
    fig.add_scatter(x=d.predicted, y=d.observed, mode="markers+lines", name=f"{model}", line=dict(color=C.CAT[0], width=2), marker=dict(size=np.clip(d.n / 2, 8, 20), color=C.CAT[0], line=dict(color=C.SURFACE, width=2)),
                    error_y=dict(type="data", symmetric=False, array=d.hi - d.observed, arrayminus=d.observed - d.lo, color=C.INK2, thickness=1.1, width=3), customdata=d.n, hovertemplate="predicted %{x:.2f} → observed %{y:.2f} (n=%{customdata})<extra></extra>")
    C.style(fig, f"Predicted vs actual frequency: '{CLASSES[cls]}' ({model})", "Predicted probability", "Observed frequency (95% Wilson interval)", height=470)
    fig.update_xaxes(range=[0, 1]); fig.update_yaxes(range=[0, 1])
    return Chart(fig, d.round(4), len(y), SRC, f"Test matches grouped into {len(d)} bins of predicted probability. On the diagonal = calibrated. Intervals are wide (~{int(d.n.mean())} matches per bin).", name=f"calibration_{model}_{cls}")


def goals_actual_vs_predicted(g: dict | None) -> Chart:
    if g is None:
        return unavailable("goals_actual_vs_predicted", "saved goal model not found (run python -m fbplatform.ml.goals)")
    r = g["rows"]
    r = r.assign(bin=pd.qcut(r.predicted, 8, duplicates="drop"))
    b = r.groupby("bin", observed=True).agg(pred=("predicted", "mean"), obs=("goals", "mean"), n=("goals", "size"), se=("goals", lambda s: s.std() / np.sqrt(len(s)))).reset_index(drop=True)
    jit = np.random.default_rng(2).uniform(-0.06, 0.06, len(r))
    fig = go.Figure()
    fig.add_scatter(x=r.predicted, y=r.goals + jit, mode="markers", name="single team-match", marker=dict(size=5, color=C.CAT[0], opacity=0.25), hoverinfo="skip")
    fig.add_scatter(x=b.pred, y=b.obs, mode="markers+lines", name="mean per prediction bin", line=dict(color=C.CAT[1], width=2), marker=dict(size=10, color=C.CAT[1], line=dict(color=C.SURFACE, width=2)),
                    error_y=dict(type="data", array=1.96 * b.se, color=C.INK2, thickness=1.1, width=3), customdata=b.n, hovertemplate="predicted %{x:.2f} → actual mean %{y:.2f} (n=%{customdata})<extra></extra>")
    mx = float(max(r.predicted.max(), b.obs.max())) + 0.3
    fig.add_scatter(x=[0, mx], y=[0, mx], mode="lines", name="perfect", line=dict(color=C.AXIS, width=1), hoverinfo="skip")
    C.style(fig, f"Expected vs actual goals per team ({g['model']}, test period, n = {len(r)})", "Predicted expected goals", "Actual goals (jittered; counts are whole numbers)", height=480)
    return Chart(fig, r[["match_key", "side", "predicted", "goals"]].round(3), len(r), SRC, "Individual matches scatter widely (goals are rare and random); the model is judged by whether the bin means follow the diagonal. Regulation-time goals only.", name="goals_actual_vs_predicted")


def residual_plots(g: dict | None) -> Chart:
    if g is None:
        return unavailable("residual_plots", "saved goal model not found (run python -m fbplatform.ml.goals)")
    r = g["rows"].copy()
    r["pearson"] = (r.goals - r.predicted) / np.sqrt(r.predicted)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Pearson residual vs predicted goals", "Distribution of Pearson residuals"), horizontal_spacing=0.12)
    jit = np.random.default_rng(5).uniform(-0.01, 0.01, len(r))
    fig.add_scatter(x=r.predicted + jit, y=r.pearson, mode="markers", marker=dict(size=5, color=C.CAT[0], opacity=0.4), showlegend=False, hovertemplate="predicted %{x:.2f}<br>residual %{y:.2f}<extra></extra>", row=1, col=1)
    lo = __import__("statsmodels.api", fromlist=["x"]).nonparametric.lowess(r.pearson, r.predicted, frac=0.6)
    fig.add_scatter(x=lo[:, 0], y=lo[:, 1], mode="lines", line=dict(color=C.CAT[1], width=2), showlegend=False, hoverinfo="skip", row=1, col=1)
    fig.add_histogram(x=r.pearson, nbinsx=30, marker_color=C.CAT[0], showlegend=False, hovertemplate="%{x:.1f}: %{y} team-matches<extra></extra>", row=1, col=2)
    fig.update_xaxes(title_text="Predicted goals", row=1, col=1, linecolor=C.AXIS); fig.update_yaxes(title_text="Pearson residual", row=1, col=1, gridcolor=C.GRID)
    fig.update_xaxes(title_text="Pearson residual", row=1, col=2, linecolor=C.AXIS); fig.update_yaxes(title_text="Team-matches (count)", row=1, col=2, gridcolor=C.GRID)
    C.style(fig, f"Residuals of the goal model ({g['model']}, n = {len(r)})", None, None, legend=False, height=420)
    disp = float((r.pearson ** 2).sum() / (len(r) - 1))
    return Chart(fig, r[["match_key", "side", "predicted", "goals", "pearson"]].round(4), len(r), SRC, f"Pearson residual = (actual − predicted)/√predicted. A flat smooth line near 0 means no systematic bias; the variance of the residuals (dispersion {disp:.2f}) near 1 means the Poisson assumption fits. Residuals of discrete goal counts form bands.", name="residual_plots")


# ------------------------------------------------------------------ clustering
def team_cluster_scatter() -> Chart:
    t = _csv("clustering", "team_clusters.csv")
    if t.empty:
        return unavailable("team_cluster_scatter", "team clustering report not found (run python -m fbplatform.ml.clustering)")
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from ..ml.clustering import TEAM_FEATURES
    Z = StandardScaler().fit_transform(t[TEAM_FEATURES])
    pca = PCA(2, random_state=0).fit(Z)
    P = pca.transform(Z)
    t = t.assign(pc1=P[:, 0], pc2=P[:, 1])
    fig = go.Figure()
    for i, (lab, g) in enumerate(t.groupby("cluster_description")):
        fig.add_scatter(x=g.pc1, y=g.pc2, mode="markers+text", text=g.team_name.where(g.matches >= 40, ""), textposition="top center", textfont=dict(size=9, color=C.INK2), name=f"{lab} (n={len(g)})",
                        marker=dict(size=np.clip(g.matches / 4, 8, 28), color=C.CAT[i], symbol="circle" if i == 0 else "square", opacity=0.85, line=dict(color=C.SURFACE, width=2)), customdata=np.c_[g.team_name, g.matches, g.gf_pm, g.ga_pm, g.win_pct],
                        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]} matches<br>scored %{customdata[2]:.2f} · conceded %{customdata[3]:.2f} per match<br>win rate %{customdata[4]:.0f}%<extra></extra>")
    ev = pca.explained_variance_ratio_
    C.style(fig, "Team clusters on the first two principal components", f"PC1 ({100 * ev[0]:.0f}% of variance)", f"PC2 ({100 * ev[1]:.0f}% of variance)", height=520)
    return Chart(fig, t[["team_name", "matches", "kmeans", "hierarchical", "dbscan", "cluster_description", "pc1", "pc2"]].round(3), len(t), "reports/ml/clustering/team_clusters.csv",
                 "K-Means clusters (k chosen by silhouette); teams with 40+ matches are labelled. The two groups overlap: the data show a continuum, not distinct team types. Cluster names are rule-based descriptions of the centroids.", name="team_clusters")


def team_dendrogram() -> Chart:
    t = _csv("clustering", "team_clusters.csv")
    if t.empty:
        return unavailable("team_dendrogram", "team clustering report not found")
    from scipy.cluster.hierarchy import dendrogram, linkage
    from sklearn.preprocessing import StandardScaler
    from ..ml.clustering import TEAM_FEATURES
    Z = StandardScaler().fit_transform(t[TEAM_FEATURES])
    d = dendrogram(linkage(Z, "ward"), labels=t.team_name.tolist(), no_plot=True)
    fig = go.Figure()
    for xs, ys in zip(d["icoord"], d["dcoord"]):
        fig.add_scatter(x=ys, y=xs, mode="lines", line=dict(color=C.CAT[0], width=1.2), hoverinfo="skip", showlegend=False)
    n = len(d["ivl"])
    fig.update_yaxes(tickvals=[5 + 10 * i for i in range(n)], ticktext=d["ivl"], autorange="reversed", tickfont=dict(size=8))
    C.style(fig, "Hierarchical clustering (Ward linkage) of teams", "Ward distance (merge height)", None, legend=False, height=max(520, 13 * n + 120))
    return Chart(fig, pd.DataFrame({"team_in_dendrogram_order": d["ivl"]}), n, "reports/ml/clustering/team_clusters.csv", "Long vertical gaps before a merge suggest natural groups; here the heights grow smoothly, consistent with a continuum.", name="team_dendrogram")


def silhouette_by_k() -> Chart:
    s = _csv("clustering", "team_clustering_summary.csv")
    if s.empty:
        return unavailable("silhouette_by_k", "team clustering summary not found")
    import ast
    sil = ast.literal_eval(s.silhouette_by_k.iloc[0])
    d = pd.DataFrame({"k": list(sil), "silhouette": list(sil.values())})
    fig = go.Figure(go.Scatter(x=d.k, y=d.silhouette, mode="lines+markers", line=dict(color=C.CAT[0], width=2), marker=dict(size=9, color=C.CAT[0], line=dict(color=C.SURFACE, width=2)), hovertemplate="k = %{x}: silhouette %{y:.3f}<extra></extra>"))
    C.style(fig, "Choosing k: silhouette score by number of clusters", "Number of clusters k", "Silhouette (higher = better separated)", legend=False, height=340)
    fig.update_xaxes(dtick=1); fig.update_yaxes(range=[0, max(0.5, d.silhouette.max() * 1.2)])
    return Chart(fig, d.round(4), len(d), "reports/ml/clustering/team_clustering_summary.csv", "Scores under ~0.5 indicate weak structure: the best k is only the least bad option.", name="silhouette_by_k")


def player_cluster_scatter(position: str = "Forward") -> Chart:
    prof = _csv("clustering", "player_clusters_by_position.csv")
    if prof.empty:
        return unavailable("player_cluster_scatter", "player clustering report not found")
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from ..ml.clustering import PLAYER_FEATS, player_stat_table
    s = player_stat_table()
    d = s.merge(prof[["player_key", "cluster", "cluster_description"]], on="player_key")
    d = d[d.position == position].dropna(subset=PLAYER_FEATS)
    if len(d) < 30:
        return unavailable("player_cluster_scatter", f"fewer than 30 {position}s with event-level data")
    P = PCA(2, random_state=0).fit(StandardScaler().fit_transform(d[PLAYER_FEATS]))
    xy = P.transform(StandardScaler().fit_transform(d[PLAYER_FEATS]))
    d = d.assign(pc1=xy[:, 0], pc2=xy[:, 1])
    fig = go.Figure()
    for i, (lab, g) in enumerate(d.groupby("cluster_description")):
        fig.add_scatter(x=g.pc1, y=g.pc2, mode="markers", name=f"{lab} (n={len(g)})", marker=dict(size=9, color=C.CAT[i], opacity=0.8, symbol=["circle", "square", "diamond"][i % 3], line=dict(color=C.SURFACE, width=1.5)),
                        customdata=np.c_[g.full_name, g.mins], hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]:,.0f} min<extra></extra>")
    ev = P.explained_variance_ratio_
    C.style(fig, f"{position} clusters (per-90 event features, PCA view)", f"PC1 ({100 * ev[0]:.0f}%)", f"PC2 ({100 * ev[1]:.0f}%)", height=500)
    return Chart(fig, d[["full_name", "position", "mins", "cluster", "cluster_description", "pc1", "pc2"]].round(3), len(d), "wh.fact_player_match_stats (StatsBomb) → reports/ml/clustering",
                 f"Clustered within {position}s only (roles differ); {len(d)} players with 270+ minutes of event data. Silhouettes are low, so the groups are descriptive tendencies.", name=f"player_clusters_{position}")


# ------------------------------------------------------------------ model comparison
def model_comparison(metric: str = "log_loss") -> Chart:
    c = _csv("outcome", "match_outcome_model_comparison.csv")
    c = c[c.split == "test"] if len(c) else c
    if c.empty:
        return unavailable("model_comparison", "model comparison report not found (run python -m fbplatform.ml.outcome)")
    lab = {"log_loss": "Log loss (lower is better)", "accuracy": "Accuracy (higher is better)", "f1_macro": "Macro F1", "roc_auc_ovr": "ROC-AUC one-vs-rest"}
    ci = {"log_loss": ("log_loss_ci_low", "log_loss_ci_high"), "accuracy": ("accuracy_ci_low", "accuracy_ci_high")}.get(metric)
    d = c.set_index("model").reindex([m for m in MODEL_ORDER if m in set(c.model)]).reset_index()
    fig = go.Figure(go.Bar(x=d.model, y=d[metric], marker_color=[MODEL_COLOR[m] for m in d.model], error_y=dict(type="data", symmetric=False, array=d[ci[1]] - d[metric], arrayminus=d[metric] - d[ci[0]], color=C.INK2, thickness=1.3, width=4) if ci else None,
                           hovertemplate="%{x}<br>" + metric + " %{y:.3f}<extra></extra>"))
    C.style(fig, f"Match-outcome models: {lab[metric]} on the test period (n = {int(d.n.iloc[0])})", None, lab[metric], legend=False, height=420)
    C.bar_gap(fig)
    if metric in ("accuracy", "roc_auc_ovr", "f1_macro"):
        fig.update_yaxes(range=[0, 1])
    return Chart(fig, d[["model", "n", "accuracy", "f1_macro", "log_loss", "roc_auc_ovr"] + (list(ci) if ci else [])].round(4), int(d.n.iloc[0]), "reports/ml/outcome/match_outcome_model_comparison.csv",
                 "Whiskers = 95% bootstrap interval over test matches. Overlapping whiskers = the models cannot be separated on this test set; the one-feature Elo baseline is the bar to beat.", name=f"model_comparison_{metric}")


def goal_model_comparison(metric: str = "poisson_deviance") -> Chart:
    c = _csv("goals", "goal_model_comparison.csv")
    c = c[c.split == "test"] if len(c) else c
    if c.empty:
        return unavailable("goal_model_comparison", "goal model report not found (run python -m fbplatform.ml.goals)")
    lab = {"poisson_deviance": "Mean Poisson deviance (lower is better)", "mae_team_goals": "MAE of team goals", "rmse_team_goals": "RMSE of team goals", "mae_total_goals": "MAE of total match goals"}
    d = c.sort_values(metric)
    fig = go.Figure(go.Bar(x=d.model, y=d[metric], marker_color=[C.CAT[i] for i in range(len(d))] if False else C.CAT[0], hovertemplate="%{x}<br>%{y:.3f}<extra></extra>"))
    C.style(fig, f"Goal models: {lab[metric]} (test period, n = {int(d.n_rows.iloc[0])} team-matches)", None, lab[metric], legend=False, height=400)
    C.bar_gap(fig)
    return Chart(fig, d[["model", "n_rows", "mae_team_goals", "rmse_team_goals", "poisson_deviance", "mae_total_goals"]].round(4), int(d.n_rows.iloc[0]), "reports/ml/goals/goal_model_comparison.csv", "Bars start at zero. The baseline is the training-period mean number of goals.", name=f"goal_models_{metric}")
