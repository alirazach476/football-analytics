"""ML project 5: player performance analysis. Two honest, separate questions.

(a) ASSOCIATION  - which recorded features go with a player's goals per 90 in a tournament? (age, position, minutes, appearances, starts, team
    strength, assists...). A regularised model + permutation importance + partial dependence. NOT predictive and NOT causal.
(b) PREDICTION   - can a player's goals per 90 in his NEXT tournament be predicted from what is known BEFORE it (previous tournaments only)?
    Chronological split (train editions up to 2016, test later), compared with a naive baseline. Reported as it comes out.
Nothing here ranks 'player quality': minutes and position coverage are incomplete, and goal totals are linked goals only."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import partial_dependence, permutation_importance
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..analysis import data as D
from . import tracking as T
from .clustering import pos_group

warnings.filterwarnings("ignore")
SEED = 42
POS = ["Goalkeeper", "Defender", "Midfielder", "Forward"]


def player_season_table(min_minutes=180) -> pd.DataFrame:
    ps = D.player_seasons()
    ps["position"] = ps.primary_position.map(pos_group)
    tpm = D.q("select team_name, season_id, points::float / nullif(played,0) as team_ppm, goals_for::float / played as team_gf_pm from gold.mart_team_performance")
    ps = ps.merge(tpm, on=["team_name", "season_id"], how="left")
    ps["start_share"] = ps.starts / ps.appearances.replace(0, np.nan)
    ps = ps[(ps.minutes_played >= min_minutes) & ps.goals_per_90.notna()].copy()
    for p in POS:
        ps[f"pos_{p}"] = (ps.position == p).astype(int)
    ps["assists_p90"] = ps.assists_per_90
    return ps.sort_values(["season_year", "season_id"]).reset_index(drop=True)


ASSOC_FEATS = ["age", "minutes_played", "appearances", "start_share", "team_ppm", "team_gf_pm", "assists_p90"] + [f"pos_{p}" for p in POS]


def association(ps: pd.DataFrame):
    d = ps.dropna(subset=["goals_per_90"]).copy()
    X, y = d[ASSOC_FEATS], d.goals_per_90.clip(upper=d.goals_per_90.quantile(.99))
    ridge = Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler()), ("m", RidgeCV(alphas=np.logspace(-2, 3, 20)))]).fit(X, y)
    gbr = Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("m", GradientBoostingRegressor(n_estimators=200, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=SEED))]).fit(X, y)
    from sklearn.model_selection import GroupKFold, cross_val_predict
    groups = d.player_key
    out = {}
    for n, m in (("ridge", ridge), ("gradient_boosting", gbr)):
        pr = cross_val_predict(m, X, y, cv=GroupKFold(5), groups=groups)
        out[n] = dict(model=n, n=len(d), cv_r2_grouped_by_player=r2_score(y, pr), cv_mae=mean_absolute_error(y, pr), baseline_mae_mean=mean_absolute_error(y, np.full(len(y), y.mean())))
    pi = permutation_importance(gbr, X, y, n_repeats=20, random_state=SEED, scoring="r2", n_jobs=1)
    imp = pd.DataFrame({"feature": ASSOC_FEATS, "r2_drop_mean": pi.importances_mean, "r2_drop_std": pi.importances_std}).sort_values("r2_drop_mean", ascending=False)
    coef = pd.DataFrame({"feature": ridge.named_steps["imp"].get_feature_names_out(ASSOC_FEATS), "standardised_coef": ridge.named_steps["m"].coef_})
    pdp = []
    for f in imp.feature.head(4):
        if f.startswith("pos_"):
            continue
        r = partial_dependence(gbr, X, [f], kind="average", grid_resolution=15)
        pdp += [dict(feature=f, value=a, partial_dependence=b) for a, b in zip(r["grid_values"][0], r["average"][0])]
    corr = d[["goals_per_90", "age", "minutes_played", "appearances", "team_ppm", "assists_p90"]].corr(method="spearman").round(3)
    return pd.DataFrame(out.values()), imp, coef, pd.DataFrame(pdp), corr, gbr


def next_tournament_table(ps: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, edition t) with features from editions BEFORE t only, target = goals per 90 in t. Same competition family = any."""
    ps = ps.sort_values(["player_key", "season_year", "season_id"])
    rows = []
    for pk, g in ps.groupby("player_key"):
        g = g.reset_index(drop=True)
        for i in range(1, len(g)):
            prev, cur = g.iloc[:i], g.iloc[i]
            mins = prev.minutes_played.sum()
            rows.append(dict(player_key=pk, season_id=cur.season_id, season_year=cur.season_year, target_goals_p90=cur.goals_per_90,
                             prior_goals_p90=(prev.goals_in_minute_matches.sum() * 90 / mins) if mins > 0 else np.nan, prior_minutes=mins,
                             prior_editions=len(prev), prior_goals=prev.goals.sum(), prior_assists_p90=(prev.assists_in_minute_matches.sum() * 90 / mins) if mins > 0 else np.nan,
                             age=cur.age, position=cur.position, last_goals_p90=prev.goals_per_90.iloc[-1], prior_team_ppm=prev.team_ppm.mean(),
                             **{f"pos_{p}": int(cur.position == p) for p in POS}))
    return pd.DataFrame(rows)


PRED_FEATS = ["prior_goals_p90", "prior_minutes", "prior_editions", "prior_goals", "prior_assists_p90", "age", "last_goals_p90", "prior_team_ppm"] + [f"pos_{p}" for p in POS]


def prediction(nt: pd.DataFrame, split_year=2016):
    tr, te = nt[nt.season_year <= split_year], nt[nt.season_year > split_year]
    assert tr.season_year.max() < te.season_year.min()
    X, Xt = tr[PRED_FEATS], te[PRED_FEATS]
    cap = tr.target_goals_p90.quantile(.99)
    y, yt = tr.target_goals_p90.clip(upper=cap), te.target_goals_p90
    models = {"baseline_train_mean": None,
              "baseline_last_edition_rate": "last",
              "ridge": Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler()), ("m", RidgeCV(alphas=np.logspace(-2, 3, 20)))]),
              "random_forest": Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("m", RandomForestRegressor(300, min_samples_leaf=10, max_depth=4, random_state=SEED, n_jobs=-1))])}
    rows, fitted = [], {}
    for n, m in models.items():
        if m is None:
            p = np.full(len(te), y.mean())
        elif m == "last":
            p = te.last_goals_p90.fillna(y.mean()).values
        else:
            m.fit(X, y)
            fitted[n] = m
            p = m.predict(Xt)
        rows.append(dict(model=n, n_train=len(tr), n_test=len(te), mae=mean_absolute_error(yt, p), r2=r2_score(yt, p), spearman=pd.Series(p).corr(pd.Series(yt.values), method="spearman")))
    return pd.DataFrame(rows), fitted, tr, te


def run(track=True):
    ps = player_season_table()
    assoc, imp, coef, pdp, corr, gbr = association(ps)
    nt = next_tournament_table(ps)
    pred, fitted, tr, te = prediction(nt)
    T.save_table(assoc.assign(note="association models; grouped CV by player; goals/90 capped at the 99th percentile; team_gf_pm is partly MECHANICAL (the player's own goals are part of his team's goals), so its importance is not evidence of influence"), "association_model_scores", "players")
    T.save_table(imp, "association_permutation_importance", "players")
    T.save_table(coef, "association_ridge_coefficients", "players")
    T.save_table(pdp, "association_partial_dependence", "players")
    T.save_table(corr.reset_index(names="variable"), "spearman_correlations", "players")
    T.save_table(pred.assign(note="chronological split: train editions <= 2016, test later; target = goals per 90 in the next tournament"), "next_tournament_prediction", "players")
    T.save_model(gbr, "player_goals_p90_association", dict(task="association (not predictive)", features=ASSOC_FEATS, n=len(ps)))
    if "random_forest" in fitted:
        T.save_model(fitted["random_forest"], "player_next_tournament_goals_p90", dict(task="predict next-tournament goals per 90", features=PRED_FEATS, train_years="<=2016"))
    if track:
        import mlflow
        with T.run("player_performance", "association+next_tournament", params=dict(player_seasons=len(ps), min_minutes=180)):
            for r in assoc.itertuples():
                T.log_metrics({f"assoc_{r.model}_cv_r2": r.cv_r2_grouped_by_player})
            for r in pred.itertuples():
                T.log_metrics({f"next_{r.model}_mae": r.mae})
    return dict(player_seasons=ps, assoc=assoc, importance=imp, coef=coef, corr=corr, prediction=pred, next_table=nt)


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    r = run()
    print(len(r["player_seasons"]), "player-seasons;", len(r["next_table"]), "next-tournament rows")
    print(r["assoc"].round(3).to_string(index=False)); print(r["importance"].round(4).to_string(index=False)); print(r["prediction"].round(3).to_string(index=False))
