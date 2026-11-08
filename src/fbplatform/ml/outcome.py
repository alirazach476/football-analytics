"""ML project 1: match outcome (team A win / draw / team B win; 'A' = team listed first; result = recorded score incl. extra time, excl. shoot-out).

Protocol: chronological train / validation / test; hyper-parameters tuned ONLY on the training period with expanding-window time-series CV
(scoring = log loss); models compared on validation; the test period is looked at once for the final numbers. Baselines: class prior and a
single-feature Elo logistic regression. LightGBM is not installed in this environment (documented, skipped). Bootstrap CIs show how noisy a
test set of this size is. Scheduled fixtures are never used (no outcome)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from . import features as F
from . import tracking as T

warnings.filterwarnings("ignore")
CLASSES = ["A win", "draw", "B win"]
SEED = 42
GRIDS = {
    "logreg": {"clf__C": [0.01, 0.1, 1.0, 10.0]},
    "random_forest": {"clf__n_estimators": [300], "clf__max_depth": [3, 5, 8], "clf__min_samples_leaf": [10, 25]},
    "xgboost": {"max_depth": [2, 3], "learning_rate": [0.03, 0.1], "n_estimators": [100, 250], "min_child_weight": [5, 15]},
}


def _prep(scale: bool):
    steps = [("imp", SimpleImputer(strategy="median", add_indicator=True))]
    if scale:
        steps.append(("sc", StandardScaler()))
    return steps


def make_models(quick=False):
    G = {k: ({kk: vv[:1] for kk, vv in v.items()} if quick else v) for k, v in GRIDS.items()}
    return {
        "baseline_prior": (DummyClassifier(strategy="prior"), None),
        "baseline_elo_logreg": (Pipeline(_prep(True) + [("clf", LogisticRegression(max_iter=2000))]), None),
        "logreg": (Pipeline(_prep(True) + [("clf", LogisticRegression(max_iter=3000))]), G["logreg"]),
        "random_forest": (Pipeline(_prep(False) + [("clf", RandomForestClassifier(random_state=SEED, n_jobs=-1))]), G["random_forest"]),
        "xgboost": (XGBClassifier(objective="multi:softprob", num_class=3, eval_metric="mlogloss", tree_method="hist", subsample=0.8, colsample_bytree=0.8,
                                  random_state=SEED, n_jobs=4, verbosity=0), G["xgboost"]),
    }


def metrics(y, proba, pred=None) -> dict:
    pred = proba.argmax(axis=1) if pred is None else pred
    m = dict(accuracy=accuracy_score(y, pred), precision_macro=precision_score(y, pred, average="macro", zero_division=0),
             recall_macro=recall_score(y, pred, average="macro", zero_division=0), f1_macro=f1_score(y, pred, average="macro", zero_division=0),
             log_loss=log_loss(y, proba, labels=[0, 1, 2]))
    try:
        m["roc_auc_ovr"] = roc_auc_score(y, proba, multi_class="ovr", average="macro", labels=[0, 1, 2])
    except ValueError:
        m["roc_auc_ovr"] = np.nan
    return m


def boot(y, proba, b=1000, seed=1):
    rng = np.random.default_rng(seed)
    acc, ll = [], []
    for _ in range(b):
        i = rng.integers(0, len(y), len(y))
        acc.append(accuracy_score(y[i], proba[i].argmax(1)))
        ll.append(log_loss(y[i], proba[i], labels=[0, 1, 2]))
    return np.percentile(acc, [2.5, 97.5]), np.percentile(ll, [2.5, 97.5])


def fit_all(df: pd.DataFrame, quick: bool = False):
    tr, va, te = F.chronological_split(df)
    assert tr.match_date.max() < va.match_date.min() <= va.match_date.max() < te.match_date.min()          # no overlap in time
    Xtr, Xva, Xte = (F.feature_matrix(x) for x in (tr, va, te))
    ytr, yva, yte = tr.y.values, va.y.values, te.y.values
    cv = TimeSeriesSplit(n_splits=5)
    fitted, rows, cms = {}, [], {}
    for name, (est, grid) in make_models(quick).items():
        cols = ["elo_diff"] if name == "baseline_elo_logreg" else list(Xtr.columns)
        best = {}
        if grid:
            gs = GridSearchCV(est, grid, cv=cv, scoring="neg_log_loss", n_jobs=1, refit=True)
            gs.fit(Xtr[cols], ytr)
            model, best, cv_ll = gs.best_estimator_, gs.best_params_, -gs.best_score_
        else:
            model, cv_ll = est.fit(Xtr[cols], ytr), np.nan
        fitted[name] = (model, cols)
        for split, X, y in (("validation", Xva, yva), ("test", Xte, yte)):
            p = model.predict_proba(X[cols])
            row = dict(model=name, split=split, n=len(y), cv_log_loss_train=cv_ll, best_params=str(best), **metrics(y, p))
            if split == "test":
                (alo, ahi), (llo, lhi) = boot(y, p)
                row.update(accuracy_ci_low=alo, accuracy_ci_high=ahi, log_loss_ci_low=llo, log_loss_ci_high=lhi)
                cms[name] = confusion_matrix(y, p.argmax(1), labels=[0, 1, 2])
            rows.append(row)
    res = pd.DataFrame(rows)
    return dict(train=tr, val=va, test=te, Xtr=Xtr, Xva=Xva, Xte=Xte, ytr=ytr, yva=yva, yte=yte, fitted=fitted, results=res, confusion=cms)


def select_and_refit(art):
    """Pick the best non-baseline model on VALIDATION log loss; refit it on train+validation; report the test period once more."""
    v = art["results"][(art["results"].split == "validation") & ~art["results"].model.str.startswith("baseline")].sort_values("log_loss")
    name = v.iloc[0].model
    model, cols = art["fitted"][name]
    from sklearn.base import clone
    refit = clone(model)
    Xtv = pd.concat([art["Xtr"], art["Xva"]])[cols]
    ytv = np.concatenate([art["ytr"], art["yva"]])
    refit.fit(Xtv, ytv)
    p = refit.predict_proba(art["Xte"][cols])
    return name, refit, cols, metrics(art["yte"], p), p


def explain(art, name):
    """Permutation importance (test period, log-loss based), built-in importance, and SHAP for XGBoost."""
    out = {}
    model, cols = art["fitted"][name]
    pi = permutation_importance(model, art["Xte"][cols], art["yte"], scoring="neg_log_loss", n_repeats=30, random_state=SEED, n_jobs=1)
    out["permutation"] = pd.DataFrame({"feature": cols, "importance_mean": pi.importances_mean, "importance_std": pi.importances_std}).sort_values("importance_mean", ascending=False)
    xgb, xcols = art["fitted"]["xgboost"]
    out["xgb_gain"] = pd.DataFrame({"feature": xcols, "gain": xgb.feature_importances_}).sort_values("gain", ascending=False)
    try:
        import shap
        ex = shap.TreeExplainer(xgb)
        sv = ex.shap_values(art["Xte"][xcols])
        sv = np.stack(sv, axis=-1) if isinstance(sv, list) else sv                    # (n, features, classes)
        mean_abs = np.abs(sv).mean(axis=0)
        out["shap"] = pd.DataFrame(mean_abs, index=xcols, columns=CLASSES).assign(mean_abs_shap=mean_abs.mean(axis=1)).sort_values("mean_abs_shap", ascending=False).reset_index(names="feature")
        out["shap_values"], out["shap_X"] = sv, art["Xte"][xcols]
    except Exception as e:                                                             # SHAP is optional; failure is reported, not hidden
        out["shap_error"] = f"{type(e).__name__}: {e}"
    from sklearn.inspection import partial_dependence
    top = out["xgb_gain"].feature.head(4).tolist()
    pdp = []
    for f in top:
        r = partial_dependence(xgb, art["Xte"][xcols], [f], kind="average", grid_resolution=20)
        for k in range(3):
            pdp += [dict(feature=f, value=x, outcome=CLASSES[k], partial_dependence=y) for x, y in zip(r["grid_values"][0], r["average"][k])]
    out["pdp"] = pd.DataFrame(pdp)
    return out


def run(track: bool = True, quick: bool = False, save: bool = True) -> dict:
    df = F.build_match_features()
    art = fit_all(df, quick)
    name, refit, cols, final_metrics, final_p = select_and_refit(art)
    ex = explain(art, name)
    res = art["results"]
    if not save:
        return dict(results=res, selected=name, final_metrics=final_metrics, explain=ex, art=art, final_proba=final_p)
    T.save_table(res, "match_outcome_model_comparison", "outcome")
    T.save_table(ex["permutation"], "permutation_importance", "outcome")
    T.save_table(ex["xgb_gain"], "xgboost_gain_importance", "outcome")
    T.save_table(ex["pdp"], "partial_dependence", "outcome")
    if "shap" in ex:
        T.save_table(ex["shap"], "shap_mean_abs", "outcome")
    cm = pd.DataFrame([dict(model=k, **{f"true_{CLASSES[i]}__pred_{CLASSES[j]}": int(v[i, j]) for i in range(3) for j in range(3)}) for k, v in art["confusion"].items()])
    T.save_table(cm, "confusion_matrices_test", "outcome")
    preds = art["test"][["match_id", "match_date", "season_id", "team_a_key", "team_b_key", "result"]].copy()
    for i, c in enumerate(CLASSES):
        preds[f"p_{c.replace(' ', '_')}"] = final_p[:, i]
    preds["predicted"] = [CLASSES[i] for i in final_p.argmax(1)]
    preds["note"] = "MODEL PREDICTION (out-of-sample, made without the result); 'result' is the actual outcome"
    T.save_table(preds, "test_period_predictions", "outcome")
    meta = dict(task="match outcome", classes=CLASSES, features=cols, selected_model=name, selection_rule="lowest validation log loss, then refit on train+validation",
                split=dict(train=[str(art["train"].match_date.min().date()), str(art["train"].match_date.max().date()), len(art["train"])],
                           validation=[str(art["val"].match_date.min().date()), str(art["val"].match_date.max().date()), len(art["val"])],
                           test=[str(art["test"].match_date.min().date()), str(art["test"].match_date.max().date()), len(art["test"])]),
                final_test_metrics=final_metrics, lightgbm="not installed - not evaluated")
    T.save_model(refit, "match_outcome_selected", meta)
    for n, (m_, c_) in art["fitted"].items():
        T.save_model(m_, f"match_outcome_{n}", dict(task="match outcome", model=n, features=c_, trained_on="train period only"))
    if track:
        for n in res.model.unique():
            with T.run("match_outcome", n, params={"features": len(F.MATCH_FEATS), "split": "chronological 70/15/15"}):
                import mlflow
                if n in art["fitted"]:
                    mlflow.log_param("best_params", res[(res.model == n)].best_params.iloc[0])
                for sp in ("validation", "test"):
                    r = res[(res.model == n) & (res.split == sp)].iloc[0]
                    T.log_metrics({k: r[k] for k in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "log_loss", "roc_auc_ovr")}, prefix=f"{sp}_")
                mlflow.log_artifact(str(T.REPORTS / "outcome" / "match_outcome_model_comparison.csv"))
    return dict(results=res, selected=name, final_metrics=final_metrics, explain=ex, art=art, meta=meta)


# ------------------------------------------------------------------ prediction for any pairing
def predict_matchup(team_a: str, team_b: str, as_of: str, competition: str = "WC", stage_name: str = "Group stage", venue_country: str | None = None,
                    model_name: str = "match_outcome_selected") -> dict:
    """Probabilities for a HYPOTHETICAL meeting on `as_of`, built only from matches before that date. This is a model output, not a result."""
    import joblib
    from ..analysis import data as D
    meta_p = T.MODELS / f"{model_name}.json"
    import json
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    model = joblib.load(T.MODELS / f"{model_name}.joblib")
    names = D.q("select team_key, team_name from staging.stg_teams").set_index("team_name").team_key
    a, b = int(names[team_a]), int(names[team_b])
    date = pd.Timestamp(as_of)
    m = D.matches()
    fb = F.FeatureBuilder()
    fb.build(m[m.match_date < date])                       # state = every finished match strictly before the date
    f = fb.row_for(a, b, date, competition, stage_name, stage_name != "Group stage", venue_country)
    f["a_elo"], f["b_elo"] = fb.teams[a].elo, fb.teams[b].elo
    f["elo_diff"] = f["a_elo"] - f["b_elo"]
    X = pd.DataFrame([f])[meta["features"]].astype(float)
    p = model.predict_proba(X)[0]
    return dict(team_a=team_a, team_b=team_b, as_of=as_of, probabilities={CLASSES[i]: float(p[i]) for i in range(3)},
                label="MODEL PREDICTION - not an actual result", based_on_matches_before=str(date.date()))


if __name__ == "__main__":
    r = run()
    pd.set_option("display.width", 250)
    print(r["results"][r["results"].split.isin(["validation", "test"])][["model", "split", "n", "accuracy", "f1_macro", "log_loss", "roc_auc_ovr"]].round(3).to_string(index=False))
    print("selected:", r["selected"], "final test:", {k: round(v, 3) for k, v in r["final_metrics"].items()})
