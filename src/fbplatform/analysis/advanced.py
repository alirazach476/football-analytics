"""Advanced projects A-E. Every index is transparent (formula in the docstring and in the output tables) and every limitation is stated.

A  Tournament competitiveness index      B  Team dominance          C  Player contribution index
D  Trend forecasting (exploratory)       E  Head-to-head tool (reusable)
Played matches only. Outputs: reports/advanced/*.csv"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats as ss

from ..config import ROOT
from . import data as D

warnings.filterwarnings("ignore")
OUT = ROOT / "reports" / "advanced"
RNG = np.random.default_rng(7)


def _save(df, name):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"{name}.csv", index=False)


# =============================================================== A. competitiveness index
def _components(m: pd.DataFrame, tm: pd.DataFrame, elo_fav: pd.Series) -> dict:
    margin = m.margin90.dropna() if "margin90" in m else (m.home_goals90 - m.away_goals90).abs().dropna()
    pts = tm.groupby("team_key").points.mean()
    o = m.outcome.value_counts(normalize=True).reindex(["home win", "draw", "away win"]).fillna(0)
    ent = -(o[o > 0] * np.log(o[o > 0])).sum() / np.log(3)
    sub = m[m.match_key.isin(elo_fav.index)]
    fav_pts = elo_fav.reindex(sub.match_key).mean() if len(sub) else np.nan                      # points share of the pre-match Elo favourite (0.5 = coin flip)
    gap = (pts.sort_values(ascending=False).head(max(2, len(pts) // 4)).mean() - pts.sort_values().head(max(2, len(pts) // 4)).mean())
    return dict(mean_abs_margin=margin.mean(), draw_share=(m.outcome == "draw").mean(), outcome_entropy=ent, favourite_points_share=fav_pts, top_bottom_quartile_ppm_gap=gap)


def competitiveness():
    """Index = equal-weight mean of four percentile-rank components (each 0 = least competitive edition, 1 = most competitive):
         1  closeness       = rank of  -mean |goal margin| (regulation)
         2  outcome balance = rank of  normalised Shannon entropy of {home win, draw, away win}
         3  upset rate      = rank of  -(Elo favourite's share of available points)   [Elo from earlier matches only, matches with both teams >= 3 prior]
         4  strength spread = rank of  -(top-quarter minus bottom-quarter team points per match)
       Percentile ranks across editions remove units; sensitivity (drop-one, margin-only) and a bootstrap CI (resampling matches) are reported.
       LIMITS: only ~29 editions, formats differ (a 4-team group vs a 48-team league), Elo uses these four competitions only."""
    from ..ml import features as F
    m, tm = D.matches(), D.team_matches()
    m["margin90"] = (m.home_goals90 - m.away_goals90).abs()
    ft = F.build_match_features()
    ok = ft[(ft.a_n_prior >= 3) & (ft.b_n_prior >= 3) & (ft.elo_diff != 0)]
    fav_pts = pd.Series(np.where(ok.elo_diff > 0, np.where(ok.result == "A", 1, np.where(ok.result == "D", .5, 0)), np.where(ok.result == "B", 1, np.where(ok.result == "D", .5, 0))), index=ok.match_key)
    rows = []
    for sid, g in m.groupby("season_id"):
        if len(g) < 20:
            continue
        c = _components(g, tm[tm.season_id == sid], fav_pts)
        rows.append(dict(season_id=sid, competition_id=g.competition_id.iloc[0], matches=len(g), **c))
    df = pd.DataFrame(rows)
    rk = lambda s, sign: (sign * s).rank(pct=True, na_option="keep")
    comp = pd.DataFrame({"closeness": rk(df.mean_abs_margin, -1), "outcome_balance": rk(df.outcome_entropy, 1), "upset_rate": rk(df.favourite_points_share, -1), "strength_spread": rk(df.top_bottom_quartile_ppm_gap, -1)})
    df["competitiveness_index"] = comp.mean(axis=1, skipna=True)
    for c in comp.columns:
        df[f"c_{c}"] = comp[c]
    df["index_without_upset_rate"] = comp.drop(columns="upset_rate").mean(axis=1)
    df["index_margin_only"] = comp.closeness
    # bootstrap CI of the index (match resampling; team-strength component recomputed from resampled team-matches is skipped -> margin/entropy/upset only)
    ci = []
    for sid, g in m.groupby("season_id"):
        if len(g) < 20:
            continue
        vals = []
        for _ in range(300):
            s = g.iloc[RNG.integers(0, len(g), len(g))]
            c = _components(s, tm[tm.season_id == sid], fav_pts)
            vals.append((c["mean_abs_margin"], c["outcome_entropy"]))
        ci.append(dict(season_id=sid, margin_ci_low=np.percentile([v[0] for v in vals], 2.5), margin_ci_high=np.percentile([v[0] for v in vals], 97.5)))
    df = df.merge(pd.DataFrame(ci), on="season_id")
    df["rank_note"] = "index is a within-sample percentile construct: differences of a few hundredths are within noise (see margin CI)"
    df = df.sort_values("competitiveness_index", ascending=False).reset_index(drop=True)
    _save(df.round(4), "A_competitiveness_index")
    sens = pd.DataFrame([dict(spearman_full_vs_without_upset=ss.spearmanr(df.competitiveness_index, df.index_without_upset_rate)[0],
                              spearman_full_vs_margin_only=ss.spearmanr(df.competitiveness_index, df.index_margin_only)[0])])
    _save(sens.round(3), "A_competitiveness_sensitivity")
    return df, sens


# =============================================================== B. team dominance
def dominance(min_editions=3):
    """Dominance score = mean percentile rank (among teams with >= 3 editions) of: shrunk win %, goal difference per match, knockout win %,
    average progression (knockout matches played per edition, WC/Euro/Copa), titles per edition.  Win % is shrunk toward the global mean with
    a prior of 10 matches so tiny samples cannot top the list."""
    tm = D.team_matches()
    tr = D.tournaments()
    g = tm.groupby("team_name").agg(matches=("match_key", "size"), editions=("season_id", "nunique"), wins=("result", lambda s: (s == "W").sum()), gd_pm=("goal_diff", "mean"),
                                    ppm=("points", "mean")).reset_index()
    gm = (tm.result == "W").mean()
    g["win_pct_shrunk"] = 100 * (g.wins + 10 * gm) / (g.matches + 10)
    ko = tm[tm.is_knockout.astype(bool)].groupby("team_name").agg(ko_matches=("match_key", "size"), ko_wins=("result", lambda s: (s == "W").sum()))
    ko["ko_win_pct"] = 100 * ko.ko_wins / ko.ko_matches
    prog = tm[tm.comp.isin(["WC", "EURO", "COPA"]) & tm.is_knockout.astype(bool)].groupby(["team_name", "season_id"]).size().groupby("team_name").mean().rename("knockout_matches_per_edition")
    ed = tm[tm.comp.isin(["WC", "EURO", "COPA"])].groupby("team_name").season_id.nunique().rename("major_editions")
    titles = tr.champion.value_counts().rename("titles")
    sd = tm.groupby(["team_name", "season_id"]).points.mean().groupby("team_name").std().rename("ppm_sd_editions")
    g = g.merge(ko[["ko_matches", "ko_win_pct"]], on="team_name", how="left").merge(prog, on="team_name", how="left").merge(ed, on="team_name", how="left").merge(titles, left_on="team_name", right_index=True, how="left").merge(sd, on="team_name", how="left")
    g["titles"] = g.titles.fillna(0)
    g["titles_per_major_edition"] = g.titles / g.major_editions.replace(0, np.nan)
    g = g[g.editions >= min_editions].copy()
    g["ko_win_pct_shrunk"] = 100 * (g.ko_matches.fillna(0) * g.ko_win_pct.fillna(0) / 100 + 5 * 0.5) / (g.ko_matches.fillna(0) + 5)
    comp = pd.DataFrame({"win": g.win_pct_shrunk.rank(pct=True), "gd": g.gd_pm.rank(pct=True), "ko": g.ko_win_pct_shrunk.rank(pct=True),
                         "prog": g.knockout_matches_per_edition.fillna(0).rank(pct=True), "titles": g.titles_per_major_edition.fillna(0).rank(pct=True)})
    g["dominance_score"] = comp.mean(axis=1)
    g["consistency_note"] = np.where(g.ppm_sd_editions.notna() & (g.ppm_sd_editions < g.ppm_sd_editions.median()), "more consistent than median", "less consistent than median")
    g = g.sort_values("dominance_score", ascending=False).reset_index(drop=True)
    _save(g.round(4), "B_team_dominance")
    return g


# =============================================================== C. player contribution index
def player_contribution(m0=900, min_minutes=270):
    """Contribution per 90 = goals_p90 (+ 0.5 * assists_p90 only where assists are reliably recorded), shrunk toward the POSITION mean:
         rate_shrunk = (events + prior_rate * m0/90) / (minutes/90 + m0/90),  m0 = 900 minutes of prior weight.
       PCI = z-score of rate_shrunk within position group (so forwards are compared with forwards). Goalkeepers excluded.
       Assist weight 0.5 is a documented judgement, not a fitted value. Goals/assists are counted ONLY in matches with known minutes."""
    ps = D.player_seasons()
    from ..ml.clustering import pos_group
    ps["position"] = ps.primary_position.map(pos_group)
    rel = D.q("select distinct s.season_id from wh.fact_match_events e join wh.fact_matches m using (match_key) join wh.dim_season s using (season_key) where e.provider='statsbomb'")
    reliable = set(rel.season_id)
    ps["assists_reliable"] = ps.season_id.isin(reliable)
    ps["events"] = ps.goals_in_minute_matches + 0.5 * np.where(ps.assists_reliable, ps.assists_in_minute_matches, 0)
    career = ps.groupby("player_key").agg(full_name=("full_name", "first"), position=("position", "first"), nationality=("nationality", "first"), minutes=("minutes_played", "sum"),
                                         goals=("goals_in_minute_matches", "sum"), events=("events", "sum"), editions=("season_id", "nunique"), assist_seasons=("assists_reliable", "sum")).reset_index()
    career = career[(career.minutes >= min_minutes) & career.position.isin(["Defender", "Midfielder", "Forward"])].copy()
    out = []
    for pos, g in career.groupby("position"):
        prior = g.events.sum() * 90 / g.minutes.sum()
        g = g.copy()
        g["rate_raw_p90"] = g.events * 90 / g.minutes
        g["rate_shrunk_p90"] = (g.events + prior * m0 / 90) / (g.minutes / 90 + m0 / 90)
        g["pci_z_within_position"] = (g.rate_shrunk_p90 - g.rate_shrunk_p90.mean()) / g.rate_shrunk_p90.std()
        g["position_prior_p90"] = prior
        out.append(g)
    c = pd.concat(out)
    c["sample_size_flag"] = np.where(c.minutes < 900, "low (<900 min): treat with caution", "ok")
    c["rank_reliable"] = c.pci_z_within_position.where(c.minutes >= 900).rank(ascending=False, method="min")     # ranking only among players with >= 900 min
    c = c.sort_values(["rank_reliable", "pci_z_within_position"], ascending=[True, False], na_position="last").reset_index(drop=True)
    c["note"] = "goals + 0.5*assists (assists only in StatsBomb-covered editions); linked goals only; not a measure of overall quality"
    _save(c.round(4), "C_player_contribution_index")
    return c


# =============================================================== D. trend forecasting (exploratory)
def forecast():
    """Per competition: goals per match by edition. With 5-9 editions per series ARIMA is not identifiable, so three transparent methods are compared by
    leave-last-out error: naive mean, linear trend (Poisson GLM on matches), Holt linear smoothing. The forecast for the next edition carries a
    prediction interval that includes edition-to-edition noise. EXPLORATORY ONLY - not a reliable prediction."""
    from statsmodels.tsa.holtwinters import Holt
    m = D.matches()
    m = m[m.goals90.notna()]
    rows, fc = [], []
    nxt = {"WC": 2030, "EURO": 2028, "COPA": 2028, "UNL": 2028}
    for comp in D.COMP_ORDER:
        g = m[m.competition_id == comp]
        ed = g.groupby("season_year").goals90.agg(["mean", "size", "var"]).reset_index()
        if len(ed) < 5:
            continue
        y = ed["mean"].values
        errs = {"naive_mean": [], "linear_trend": [], "holt": []}
        for i in range(3, len(ed)):
            tr = ed.iloc[:i]
            errs["naive_mean"].append(abs(y[i] - tr["mean"].mean()))
            b = np.polyfit(tr.season_year, tr["mean"], 1)
            errs["linear_trend"].append(abs(y[i] - np.polyval(b, ed.season_year[i])))
            try:
                errs["holt"].append(abs(y[i] - Holt(tr["mean"].values, initialization_method="estimated").fit().forecast(1)[0]))
            except Exception:
                errs["holt"].append(np.nan)
        for k, v in errs.items():
            rows.append(dict(competition=comp, method=k, editions=len(ed), backtest_origins=len(v), mae_goals_per_match=np.nanmean(v)))
        best = min(errs, key=lambda k: np.nanmean(errs[k]) if not np.all(np.isnan(errs[k])) else 9e9)
        n_ed = ed["size"].values
        X = sm.add_constant((g.season_year - 2000) / 10.0)
        res = sm.GLM(g.goals90, X, family=sm.families.Poisson()).fit(scale="X2")
        pred = res.get_prediction(sm.add_constant(pd.Series([(nxt[comp] - 2000) / 10.0]), has_constant="add")).summary_frame(alpha=.05)
        trend_fit = np.polyval(np.polyfit(ed.season_year, y, 1), ed.season_year)
        if best == "naive_mean":
            mu = float(np.average(y, weights=n_ed))
            sd = float(np.std(y, ddof=1)) * np.sqrt(1 + 1 / len(y))
            lo_ci, hi_ci = mu - 1.96 * np.std(y, ddof=1) / np.sqrt(len(y)), mu + 1.96 * np.std(y, ddof=1) / np.sqrt(len(y))
        elif best == "holt":
            fit = Holt(y, initialization_method="estimated").fit()
            mu = float(fit.forecast(1)[0])
            sd = float(np.std(y - fit.fittedvalues, ddof=2))
            lo_ci, hi_ci = np.nan, np.nan
        else:
            mu = float(pred["mean"].iloc[0])
            lo_ci, hi_ci = float(pred["mean_ci_lower"].iloc[0]), float(pred["mean_ci_upper"].iloc[0])
            sd = float(np.sqrt(max(np.var(y - trend_fit, ddof=2), 1e-6)))
        fc.append(dict(competition=comp, next_edition=nxt[comp], method_selected_by_backtest=best, forecast_goals_per_match=mu, ci_low=lo_ci, ci_high=hi_ci,
                       pi_low=mu - 1.96 * sd, pi_high=mu + 1.96 * sd, editions_used=len(ed), last_observed=float(y[-1]), status="EXPLORATORY - not a reliable prediction",
                       note="method = lowest leave-last-out error on only a few origins; CI = parameter uncertainty, PI adds edition-to-edition noise; format changes (e.g. 48-team World Cup) are not modelled"))
    bt, f = pd.DataFrame(rows), pd.DataFrame(fc)
    _save(bt.round(4), "D_forecast_backtest")
    _save(f.round(4), "D_forecast_next_edition")
    return bt, f


# =============================================================== E. head-to-head
@dataclass
class H2H:
    team_a: str
    team_b: str
    meetings: int
    wins_a: int
    draws: int
    wins_b: int
    goals_a: int
    goals_b: int
    shootouts_won_a: int
    shootouts_won_b: int
    by_competition: pd.DataFrame
    by_stage_type: pd.DataFrame
    recent: pd.DataFrame
    caveats: list


def head_to_head(team_a: str, team_b: str, competition: str | None = None, since: int | None = None, recent: int = 5) -> H2H:
    """All meetings of two teams inside the four competitions. Results use the recorded score (extra time included, shoot-outs shown separately).
    Meetings are NOT equivalent (different competitions, stages, eras, squads): the caveats list says so and the breakdowns let you filter."""
    names = D.q("select team_key, team_name from staging.stg_teams").set_index("team_name").team_key
    if team_a not in names.index or team_b not in names.index:
        raise KeyError(f"unknown team: {team_a if team_a not in names.index else team_b}")
    a, b = int(names[team_a]), int(names[team_b])
    m = D.matches()
    x = m[((m.home_team_key == a) & (m.away_team_key == b)) | ((m.home_team_key == b) & (m.away_team_key == a))].copy()
    if competition:
        x = x[x.competition_id == competition]
    if since:
        x = x[x.season_year >= since]
    x = x.sort_values("match_date")
    isa = x.home_team_key == a
    x["goals_a"] = np.where(isa, x.home_score, x.away_score)
    x["goals_b"] = np.where(isa, x.away_score, x.home_score)
    x["result_a"] = np.where(x.goals_a > x.goals_b, "W", np.where(x.goals_a == x.goals_b, "D", "L"))
    sh = x.shootout_winner_side.notna()
    x["shootout_winner"] = np.where(sh, np.where((x.shootout_winner_side == "home") == isa, team_a, team_b), None)
    byc = x.groupby("competition_id").agg(meetings=("match_key", "size"), wins_a=("result_a", lambda s: (s == "W").sum()), draws=("result_a", lambda s: (s == "D").sum()),
                                          wins_b=("result_a", lambda s: (s == "L").sum()), goals_a=("goals_a", "sum"), goals_b=("goals_b", "sum")).reset_index()
    bys = x.assign(stage_type=np.where(x.is_knockout.astype(bool), "knockout", "group/league")).groupby("stage_type").agg(
        meetings=("match_key", "size"), wins_a=("result_a", lambda s: (s == "W").sum()), draws=("result_a", lambda s: (s == "D").sum()), wins_b=("result_a", lambda s: (s == "L").sum())).reset_index()
    rec = x.tail(recent)[["match_date", "season_id", "stage_name", "home_team_name", "home_score", "away_score", "away_team_name", "shootout_winner"]]
    cav = ["Meetings span different competitions, stages, venues and squads - treat them as context, not as a prediction.",
           "Only matches inside the four collected competitions are included (no friendlies or qualifiers), so the record is partial.",
           "Result = recorded score (extra time included, shoot-out excluded); shoot-out winners are listed separately."]
    if len(x) < 3:
        cav.append(f"Only {len(x)} meeting(s): percentages would be meaningless.")
    return H2H(team_a, team_b, len(x), int((x.result_a == "W").sum()), int((x.result_a == "D").sum()), int((x.result_a == "L").sum()), int(x.goals_a.sum()), int(x.goals_b.sum()),
               int((x.shootout_winner == team_a).sum()), int((x.shootout_winner == team_b).sum()), byc, bys, rec, cav)


def run_all():
    ci, sens = competitiveness()
    dom = dominance()
    pci = player_contribution()
    bt, fc = forecast()
    h = head_to_head("Argentina", "Brazil")
    _save(h.by_competition, "E_example_head_to_head_Argentina_Brazil_by_competition")
    return dict(competitiveness=ci, sensitivity=sens, dominance=dom, pci=pci, backtest=bt, forecast=fc, h2h=h)


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 40)
    r = run_all()
    print(r["competitiveness"][["season_id", "competitiveness_index", "mean_abs_margin", "margin_ci_low", "margin_ci_high"]].head(6).round(3).to_string(index=False)); print(r["sensitivity"])
    print(r["dominance"][["team_name", "editions", "matches", "win_pct_shrunk", "gd_pm", "titles", "dominance_score"]].head(10).round(3).to_string(index=False))
    print(r["pci"][["full_name", "position", "minutes", "goals", "rate_shrunk_p90", "pci_z_within_position", "sample_size_flag"]].head(10).round(3).to_string(index=False))
    print(r["backtest"].round(3).to_string(index=False)); print(r["forecast"][["competition", "next_edition", "method_selected_by_backtest", "forecast_goals_per_match", "pi_low", "pi_high"]].round(2))
    h = r["h2h"]; print(h.team_a, h.team_b, h.meetings, h.wins_a, h.draws, h.wins_b, h.goals_a, h.goals_b)
