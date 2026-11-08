"""ML project 2: expected goals per team and total match goals (regulation time), plus an over/under 2.5 ANALYTICAL experiment.

Rows are team-centric (own attack vs opponent defence, past-only). Models: Poisson regression, Random Forest, XGBoost (count:poisson); baseline =
training-period mean. Metrics: MAE, RMSE (team goals and total goals), mean Poisson deviance, plus count-model diagnostics (over-dispersion,
zero share vs Poisson expectation, calibration by predicted-rate decile). Over/under: P(total>2.5) assuming independent Poisson goals, scored with
Brier/log-loss against the base rate - an experiment, not a betting tool. Matches whose 90-minute score is unknown (extra time) are skipped."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats as ss
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, mean_squared_error
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from . import features as F
from . import tracking as T

warnings.filterwarnings("ignore")
SEED = 42


def make_models(quick=False):
    g = (lambda full, one: one) if quick else (lambda full, one: full)
    return {
        "poisson_regression": (Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler()), ("m", PoissonRegressor(max_iter=2000))]),
                               {"m__alpha": g([0.1, 1.0, 10.0, 50.0], [1.0])}),
        "random_forest": (Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                                    ("m", RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1))]),
                          {"m__max_depth": g([3, 5, 8], [5]), "m__min_samples_leaf": g([15, 40], [15])}),
        "xgboost": (XGBRegressor(objective="count:poisson", tree_method="hist", subsample=0.8, colsample_bytree=0.8, random_state=SEED, n_jobs=4, verbosity=0),
                    {"max_depth": g([2, 3], [2]), "learning_rate": g([0.03, 0.1], [0.05]), "n_estimators": g([100, 250], [100]), "min_child_weight": g([10, 30], [10])}),
    }


def evaluate(y_team, mu_team, mu_total, y_total, tag):
    return dict(model=tag, mae_team_goals=mean_absolute_error(y_team, mu_team), rmse_team_goals=np.sqrt(mean_squared_error(y_team, mu_team)),
                poisson_deviance=mean_poisson_deviance(y_team, np.clip(mu_team, 1e-6, None)), mae_total_goals=mean_absolute_error(y_total, mu_total),
                rmse_total_goals=np.sqrt(mean_squared_error(y_total, mu_total)))


def pair_totals(rows: pd.DataFrame, mu: np.ndarray):
    r = rows.assign(mu=mu)
    wide = r.pivot(index="match_key", columns="side", values=["goals", "mu"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide["y_total"] = wide.goals_a + wide.goals_b
    wide["mu_total"] = wide.mu_a + wide.mu_b
    return wide.dropna()


def over_under(wide, base_rate):
    """P(total > 2.5) from independent Poisson team means; compare with the training base rate."""
    lam = wide.mu_total.values                              # sum of independent Poissons is Poisson(mu_a+mu_b)
    p_over = 1 - ss.poisson.cdf(2, lam)
    y = (wide.y_total.values > 2.5).astype(int)
    eps = 1e-9
    return dict(brier=float(np.mean((p_over - y) ** 2)), brier_base_rate=float(np.mean((base_rate - y) ** 2)),
                log_loss=float(-np.mean(y * np.log(p_over + eps) + (1 - y) * np.log(1 - p_over + eps))),
                log_loss_base_rate=float(-np.mean(y * np.log(base_rate) + (1 - y) * np.log(1 - base_rate))),
                accuracy=float(np.mean((p_over > .5) == y)), accuracy_base_rate=float(max(y.mean(), 1 - y.mean())), observed_over_share=float(y.mean()), n=len(y))


def diagnostics(y, mu):
    pear = float(np.sum((y - mu) ** 2 / mu) / (len(y) - 1))
    zeros_obs, zeros_exp = float((y == 0).mean()), float(np.exp(-mu).mean())
    d = pd.DataFrame({"mu": mu, "y": y})
    d["decile"] = pd.qcut(d.mu, 10, duplicates="drop")
    cal = d.groupby("decile", observed=True).agg(n=("y", "size"), mean_predicted=("mu", "mean"), mean_observed=("y", "mean")).reset_index(drop=True)
    return dict(pearson_dispersion=pear, zero_share_observed=zeros_obs, zero_share_poisson_expected=zeros_exp), cal


def run(track=True, quick=False, save=True):
    df = F.build_match_features()
    rows = F.team_rows(df)
    tr_m, va_m, te_m = F.chronological_split(df)
    key = lambda x: set(x.match_key)
    sp = {"train": key(tr_m), "validation": key(va_m), "test": key(te_m)}
    data = {k: rows[rows.match_key.isin(v) & rows.goals.notna()].reset_index(drop=True) for k, v in sp.items()}
    Xtr, ytr = data["train"][F.GOAL_FEATS], data["train"].goals.values
    cv = TimeSeriesSplit(n_splits=5)
    results, fitted, tuned = [], {}, {}
    base_mu = ytr.mean()
    for split in ("validation", "test"):
        d = data[split]
        mu = np.full(len(d), base_mu)
        w = pair_totals(d, mu)
        results.append(dict(split=split, n_rows=len(d), best_params="", **evaluate(d.goals.values, mu, w.mu_total.values, w.y_total.values, "baseline_train_mean")))
    for name, (est, grid) in make_models(quick).items():
        gs = GridSearchCV(est, grid, cv=cv, scoring="neg_mean_poisson_deviance", n_jobs=1).fit(Xtr, ytr)
        model = gs.best_estimator_
        fitted[name], tuned[name] = model, gs.best_params_
        for split in ("validation", "test"):
            d = data[split]
            mu = np.clip(model.predict(d[F.GOAL_FEATS]), 1e-3, None)
            w = pair_totals(d, mu)
            results.append(dict(split=split, n_rows=len(d), best_params=str(gs.best_params_), cv_poisson_deviance_train=-gs.best_score_,
                                **evaluate(d.goals.values, mu, w.mu_total.values, w.y_total.values, name)))
    res = pd.DataFrame(results)
    best = res[(res.split == "validation") & (res.model != "baseline_train_mean")].sort_values("poisson_deviance").iloc[0].model
    d = data["test"]
    mu = np.clip(fitted[best].predict(d[F.GOAL_FEATS]), 1e-3, None)
    diag, cal = diagnostics(d.goals.values, mu)
    wide = pair_totals(d, mu)
    ou = over_under(wide, float((pair_totals(data["train"], np.zeros(len(data["train"]))).y_total > 2.5).mean()))
    if not save:
        return dict(results=res, selected=best, diagnostics=diag, calibration=cal, over_under=ou, fitted=fitted, data=data)
    T.save_table(res, "goal_model_comparison", "goals")
    T.save_table(cal, "calibration_by_predicted_rate_decile", "goals")
    T.save_table(pd.DataFrame([diag | {"model": best}]), "count_model_diagnostics", "goals")
    T.save_table(pd.DataFrame([ou | {"model": best, "note": "analytical experiment: independent-Poisson P(total>2.5)"}]), "over_under_2_5_experiment", "goals")
    out = d[["match_key", "match_date", "side", "goals"]].assign(predicted_expected_goals=mu)
    out["note"] = "MODEL PREDICTION of expected goals (regulation); 'goals' is the actual"
    T.save_table(out, "test_period_expected_goals", "goals")
    meta = dict(task="expected goals per team (regulation)", features=F.GOAL_FEATS, selected_model=best, selection_rule="lowest validation Poisson deviance",
                best_params={k: str(v) for k, v in tuned.items()}, diagnostics=diag, over_under=ou)
    T.save_model(fitted[best], "goals_selected", meta)
    for n, mdl in fitted.items():
        T.save_model(mdl, f"goals_{n}", dict(task="expected goals", model=n, features=F.GOAL_FEATS, trained_on="train period only"))
    if track:
        import mlflow
        for n in res.model.unique():
            with T.run("goal_prediction", n, params={"features": len(F.GOAL_FEATS)}):
                for sp_ in ("validation", "test"):
                    r = res[(res.model == n) & (res.split == sp_)].iloc[0]
                    T.log_metrics({k: r[k] for k in ("mae_team_goals", "rmse_team_goals", "poisson_deviance", "mae_total_goals", "rmse_total_goals")}, prefix=f"{sp_}_")
                mlflow.log_artifact(str(T.REPORTS / "goals" / "goal_model_comparison.csv"))
    return dict(results=res, selected=best, diagnostics=diag, calibration=cal, over_under=ou, fitted=fitted, data=data)


if __name__ == "__main__":
    r = run()
    pd.set_option("display.width", 250)
    print(r["results"][["model", "split", "n_rows", "mae_team_goals", "rmse_team_goals", "poisson_deviance", "mae_total_goals", "rmse_total_goals"]].round(3).to_string(index=False))
    print("selected:", r["selected"], r["diagnostics"], r["over_under"])
