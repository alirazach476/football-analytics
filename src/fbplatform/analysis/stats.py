"""Statistical investigation: the 10 required questions.
Every analysis: assumptions are checked first and drive the test choice; results carry n, estimate, 95% CI, p-value (Holm-adjusted inside each
question's family), an effect size and the limitations. Played matches only; shoot-outs excluded from goals; extra-time matches whose 90-minute
score is unknown are excluded from 'goals in regulation' (never guessed). Correlation is never read as causation.
Outputs: reports/statistics/results.csv, descriptives.csv, correlations.csv, STATISTICAL_REPORT.md (also copied to docs/)."""
from __future__ import annotations

import warnings
from itertools import combinations

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats as ss
from sklearn.metrics import roc_auc_score
from statsmodels.stats.multitest import multipletests

from ..config import ROOT
from . import data as D

warnings.filterwarnings("ignore")
OUT = ROOT / "reports" / "statistics"
RNG = np.random.default_rng(20261106)
ALPHA = 0.05
B = 4000                                                    # bootstrap / permutation draws
ROWS: list[dict] = []


# ------------------------------------------------------------------ helpers
def cliffs_delta(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = ss.mannwhitneyu(a, b, alternative="two-sided").statistic
    return 2 * u / (len(a) * len(b)) - 1


def cohens_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return (a.mean() - b.mean()) / sp if sp > 0 else np.nan


def boot_ci(fn, *arrays, b=B):
    arrays = [np.asarray(x, float) for x in arrays]
    vals = [fn(*[x[RNG.integers(0, len(x), len(x))] for x in arrays]) for _ in range(b)]
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def shapiro(x):
    x = np.asarray(x, float)
    x = x if len(x) <= 5000 else RNG.choice(x, 5000, replace=False)
    return ss.shapiro(x).pvalue


def cramers_v(table):
    t = np.asarray(table)
    chi2 = ss.chi2_contingency(t, correction=False)[0]
    return float(np.sqrt(chi2 / (t.sum() * (min(t.shape) - 1))))


def add(q, question, analysis, method, assumptions, n, estimate_name, estimate, lo, hi, stat, p, eff_name, eff, limits, family=None):
    ROWS.append(dict(q=q, question=question, analysis=analysis, method=method, assumption_checks=assumptions, n=n, estimate_name=estimate_name,
                     estimate=estimate, ci_low=lo, ci_high=hi, statistic=stat, p_value=p, p_adj_holm=np.nan, effect_size_name=eff_name,
                     effect_size=eff, limitations=limits, family=family or f"{q}"))


def holm_within_family():
    df = pd.DataFrame(ROWS)
    for fam, g in df.groupby("family"):
        ok = g.p_value.notna()
        if ok.sum():
            df.loc[g.index[ok], "p_adj_holm"] = multipletests(g.p_value[ok], method="holm")[1]
    return df


def poisson_trend(df, ycol, xcol, extra=""):
    f = f"{ycol} ~ {xcol}{extra}"
    r = smf.glm(f, data=df, family=sm.families.Poisson()).fit()
    disp = r.pearson_chi2 / r.df_resid
    r2 = smf.glm(f, data=df, family=sm.families.Poisson()).fit(scale="X2") if disp > 1.2 else r      # quasi-Poisson when over-dispersed
    return r2, disp


# ------------------------------------------------------------------ descriptives
def descriptives(m, tm):
    rows = []
    for comp, g in [("ALL", m)] + list(m.groupby("competition_id")):
        for col in ("goals_total", "goals90", "margin"):
            x = g[col].dropna().astype(float)
            rows.append(dict(competition=comp, variable=col, n=len(x), mean=x.mean(), median=x.median(), mode=x.mode().iloc[0], variance=x.var(), sd=x.std(),
                             p05=x.quantile(.05), p25=x.quantile(.25), p75=x.quantile(.75), p95=x.quantile(.95), iqr=x.quantile(.75) - x.quantile(.25),
                             skew=ss.skew(x), excess_kurtosis=ss.kurtosis(x), dispersion_index_var_over_mean=x.var() / x.mean() if x.mean() else np.nan))
    team = tm.groupby(["season_id", "team_key"]).agg(gf_pm=("goals_for", "mean"), ga_pm=("goals_against", "mean"), ppm=("points", "mean"),
                                                     cs=("clean_sheet", "mean"), matches=("match_key", "size")).reset_index()
    corr = team[["gf_pm", "ga_pm", "ppm", "cs", "matches"]]
    return pd.DataFrame(rows), corr.corr(method="spearman"), corr.corr(method="pearson"), corr.cov()


# ------------------------------------------------------------------ Q1
def q1(m):
    Q = "Q1 Has the average number of goals per match changed over time?"
    d = m[m.goals90.notna()].copy()
    d["decade"] = (d.season_year - 2000) / 10.0
    fam = "Q1_by_competition"
    for comp in D.COMP_ORDER:
        g = d[d.competition_id == comp]
        if g.season_id.nunique() < 4:
            continue
        r, disp = poisson_trend(g, "goals90", "decade")
        rr, lo, hi = np.exp(r.params["decade"]), *np.exp(r.conf_int().loc["decade"])
        rho, prho = ss.spearmanr(g.season_year, g.goals90)
        kw = ss.kruskal(*[x.goals90.values for _, x in g.groupby("season_id")])
        add("Q1", Q, f"{comp}: goals per match (regulation) vs edition year", "quasi-Poisson GLM (log link), rate ratio per decade" if disp > 1.2 else "Poisson GLM, rate ratio per decade",
            f"count outcome; Pearson dispersion={disp:.2f} ({'over-dispersed -> quasi-Poisson robust SE' if disp > 1.2 else 'ok'}); matches treated as independent; "
            f"Spearman rho={rho:.3f} (p={prho:.3f}); Kruskal-Wallis across {g.season_id.nunique()} editions H={kw.statistic:.1f}, p={kw.pvalue:.3f}",
            len(g), "rate ratio per +10 years", rr, lo, hi, r.tvalues["decade"], r.pvalues["decade"], "RR-1 (relative change per decade)", rr - 1,
            "few editions (confounded with format/host changes); matches within an edition are not independent; 90-minute goals only", fam)
    r, disp = poisson_trend(d, "goals90", "decade", " + C(competition_id)")
    rr, lo, hi = np.exp(r.params["decade"]), *np.exp(r.conf_int().loc["decade"])
    add("Q1", Q, "All competitions pooled (competition fixed effects)", "quasi-Poisson GLM + competition fixed effects", f"Pearson dispersion={disp:.2f}", len(d),
        "rate ratio per +10 years", rr, lo, hi, r.tvalues["decade"], r.pvalues["decade"], "RR-1", rr - 1,
        "pools different formats/eras; trend is an association, not a cause", "Q1_pooled")


# ------------------------------------------------------------------ Q2
def q2(m):
    Q = "Q2 Are knockout matches lower-scoring than group matches?"
    d = m[m.goals90.notna()].copy()
    fam = "Q2"
    for comp in D.COMP_ORDER + ["ALL"]:
        g = d if comp == "ALL" else d[d.competition_id == comp]
        a, b = g[g.phase == "knockout"].goals90, g[g.phase != "knockout"].goals90
        if len(a) < 10:
            continue
        sh = (shapiro(a), shapiro(b))
        mw = ss.mannwhitneyu(a, b, alternative="two-sided")
        wt = ss.ttest_ind(a, b, equal_var=False)
        diff = a.mean() - b.mean()
        lo, hi = boot_ci(lambda x, y: x.mean() - y.mean(), a, b)
        add("Q2", Q, f"{comp}: knockout vs group/league, goals in regulation", "Mann-Whitney U (two-sided); Welch t shown as sensitivity",
            f"Shapiro-Wilk p={sh[0]:.1e}/{sh[1]:.1e} (counts, non-normal -> rank test primary); Welch t p={wt.pvalue:.3f}; Levene var-equal p={ss.levene(a, b).pvalue:.3f}",
            len(a) + len(b), "mean difference knockout - group (goals/match), bootstrap CI", diff, lo, hi, mw.statistic, mw.pvalue,
            f"Cliff's delta (Cohen's d={cohens_d(a, b):.2f})", cliffs_delta(a, b),
            "extra-time matches without a known 90-min score are excluded (knockout n smaller); knockout teams are a selected subset", fam)
    r, disp = poisson_trend(d.assign(ko=(d.phase == "knockout").astype(int)), "goals90", "ko", " + C(competition_id)")
    rr, lo, hi = np.exp(r.params["ko"]), *np.exp(r.conf_int().loc["ko"])
    add("Q2", Q, "Pooled, competition fixed effects: knockout rate ratio", "quasi-Poisson GLM", f"dispersion={disp:.2f}", len(d), "rate ratio knockout/group", rr, lo, hi,
        r.tvalues["ko"], r.pvalues["ko"], "RR-1", rr - 1, "association only; competition effects absorbed by fixed effects", "Q2_pooled")


# ------------------------------------------------------------------ Q3
def first_scorer(m, g):
    g = g[~g.is_own_goal & g.minute.notna()].copy()
    full = m.set_index("match_key")
    counts = D.q("select match_key, count(*) n, bool_or(is_own_goal) any_og from staging.stg_goal_events group by 1").set_index("match_key")
    ok = counts.join(full[["goals_total"]], how="inner")
    complete = set(ok[(ok.n == ok.goals_total) & (ok.goals_total > 0)].index)
    gl = D.q("select match_key, team_key, minute, minute_added, period, is_own_goal, event_key from staging.stg_goal_events")
    gl = gl[gl.match_key.isin(complete)].sort_values(["match_key", "period", "minute", "minute_added", "event_key"], na_position="last")
    first = gl.groupby("match_key").first()
    firsts = gl.merge(first[["period", "minute"]], on="match_key", suffixes=("", "_f"))
    tied = firsts[(firsts.period == firsts.period_f) & (firsts.minute == firsts.minute_f)].groupby("match_key").team_key.nunique()
    first = first[(~first.is_own_goal.astype(bool)) & ~first.index.isin(tied[tied > 1].index)]
    f = first.join(full[["home_team_key", "away_team_key", "home_score", "away_score", "competition_id", "phase"]], how="inner")
    f["first_scorer_result"] = np.where(f.home_score == f.away_score, "draw", np.where((f.team_key == f.home_team_key) == (f.home_score > f.away_score), "win", "loss"))
    return f, len(complete), int((~first.index.isin(first.index)).sum())


def q3(m, g):
    Q = "Q3 Do teams that score first win more frequently?"
    f, n_complete, _ = first_scorer(m, g)
    fam = "Q3"
    for comp in D.COMP_ORDER + ["ALL"]:
        x = f if comp == "ALL" else f[f.competition_id == comp]
        if len(x) < 30:
            continue
        w, d_, l = [(x.first_scorer_result == k).sum() for k in ("win", "draw", "loss")]
        n = len(x)
        bt = ss.binomtest(int(w), int(w + l), 0.5)
        ci = ss.binomtest(int(w), n).proportion_ci(method="exact")
        add("Q3", Q, f"{comp}: result of the team that scored first (W {w} / D {d_} / L {l})", "exact binomial sign test: win vs loss among decisive results (H0: scoring first gives no edge)",
            "no distributional assumption; first goal determined from goal events (matches with complete goal events only; own-goal-first and same-minute ties excluded); draws shown separately",
            n, "P(win | scored first), exact 95% CI", w / n, ci.low, ci.high, w, bt.pvalue, "win/(win+loss) share (0.5 = no edge)", w / (w + l),
            "reverse causation possible (strong teams score first and win); 0-0 matches excluded by definition; extra-time goals count", fam)
    tab = pd.crosstab(f.competition_id, f.first_scorer_result)
    chi = ss.chi2_contingency(tab)
    add("Q3", Q, "Homogeneity: first-scorer result distribution across competitions", "chi-square test of independence", f"min expected count={chi[3].min():.1f} (>=5 required)", int(tab.values.sum()),
        "chi-square", chi[0], np.nan, np.nan, chi[0], chi[1], "Cramer's V", cramers_v(tab), "descriptive consistency check", "Q3_homog")


# ------------------------------------------------------------------ team-edition table (Q4, Q5, Q7)
def team_edition(tm):
    t = tm[tm.comp.isin(["WC", "EURO", "COPA"])]
    grp = t[~t.is_knockout.astype(bool)].groupby(["season_id", "comp", "team_key"]).agg(
        gf_pm=("goals_for", "mean"), ga_pm=("goals_against", "mean"), ppm_group=("points", "mean"), cs_group=("clean_sheet", "mean"), g_matches=("match_key", "size")).reset_index()
    ko = t[t.is_knockout.astype(bool)].groupby(["season_id", "team_key"]).size().rename("ko_matches").reset_index()
    te = grp.merge(ko, how="left", on=["season_id", "team_key"]).fillna({"ko_matches": 0})
    te["progressed"] = (te.ko_matches > 0).astype(int)
    return te[te.g_matches >= 2]


def q4(te):
    Q = "Q4 Is there a meaningful relationship between goals scored and tournament success?"
    fam = "Q4"
    for lab, y in (("number of knockout matches played", "ko_matches"), ("points per match in the group stage", "ppm_group")):
        rho, p = ss.spearmanr(te.gf_pm, te[y])
        r, pp = ss.pearsonr(te.gf_pm, te[y])
        ci = ss.bootstrap((te.gf_pm.values, te[y].values), lambda a, b: ss.spearmanr(a, b)[0], paired=True, vectorized=False, n_resamples=1500, random_state=1).confidence_interval
        add("Q4", Q, f"Group-stage goals scored/match vs {lab}", "Spearman rank correlation (Pearson shown)", f"Shapiro p(gf)={shapiro(te.gf_pm):.1e}; monotone relation assumed; Pearson r={r:.3f} (p={pp:.1e})",
            len(te), "Spearman rho (bootstrap 95% CI)", rho, ci.low, ci.high, rho, p, "Spearman rho^2", rho ** 2,
            "group goals only (avoids counting knockout goals that follow from success); points are mechanically linked to goals; format differences across competitions; association not causation" if y == "ppm_group" else
            "group goals only; Euro 24-team format lets third-placed teams advance; association not causation", fam)
    lr = smf.logit("progressed ~ gf_pm + C(comp)", data=te).fit(disp=0)
    orr, lo, hi = np.exp(lr.params["gf_pm"]), *np.exp(lr.conf_int().loc["gf_pm"])
    auc = roc_auc_score(te.progressed, te.gf_pm)
    add("Q4", Q, "Reaching the knockout stage ~ group-stage goals scored/match (+ competition)", "logistic regression (odds ratio per +1 goal/match)",
        f"events per variable ok (progressed={int(te.progressed.sum())}, not={int((1 - te.progressed).sum())}); AUC of goals alone={auc:.3f}", len(te), "odds ratio per +1 goal/match", orr, lo, hi, lr.tvalues["gf_pm"], lr.pvalues["gf_pm"],
        "AUC (goals scored alone)", auc, "team-editions from the same tournament are not independent; goals and conceded goals are correlated (see Q5 for the joint model)", "Q4_logit")


def q5(te):
    Q = "Q5 Are stronger defensive teams more likely to progress?"
    fam = "Q5"
    a, b = te[te.progressed == 1].ga_pm, te[te.progressed == 0].ga_pm
    mw = ss.mannwhitneyu(a, b)
    lo, hi = boot_ci(lambda x, y: x.mean() - y.mean(), a, b)
    add("Q5", Q, "Group-stage goals conceded/match: progressed vs eliminated", "Mann-Whitney U", f"Shapiro p={shapiro(te.ga_pm):.1e} (non-normal -> rank test)", len(te), "mean difference (progressed - eliminated), bootstrap CI",
        a.mean() - b.mean(), lo, hi, mw.statistic, mw.pvalue, "Cliff's delta", cliffs_delta(a, b), "descriptive; group goals only; Euro/Copa formats differ in how many teams advance", fam)
    lr = smf.logit("progressed ~ ga_pm + gf_pm + C(comp)", data=te).fit(disp=0)
    for var, lab in (("ga_pm", "goals conceded/match"), ("gf_pm", "goals scored/match")):
        orr, lo, hi = np.exp(lr.params[var]), *np.exp(lr.conf_int().loc[var])
        add("Q5", Q, f"Joint logistic model: effect of {lab}, adjusting for the other", "logistic regression (odds ratio per +1 goal/match)",
            f"collinearity gf/ga: Spearman={ss.spearmanr(te.gf_pm, te.ga_pm)[0]:.2f}; pseudo-R2={lr.prsquared:.3f}", len(te), "odds ratio", orr, lo, hi, lr.tvalues[var], lr.pvalues[var],
            "standardised OR", float(np.exp(lr.params[var] * te[var].std())), "association only", "Q5_joint")
    aucs = {v: roc_auc_score(te.progressed, -te[v] if v == "ga_pm" else te[v]) for v in ("ga_pm", "gf_pm")}
    diff = aucs["ga_pm"] - aucs["gf_pm"]
    bs = [(roc_auc_score(s.progressed, -s.ga_pm) - roc_auc_score(s.progressed, s.gf_pm)) for s in (te.iloc[RNG.integers(0, len(te), len(te))] for _ in range(1500)) if s.progressed.nunique() == 2]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    add("Q5", Q, f"Which predicts progress better? AUC defence ({aucs['ga_pm']:.3f}) vs attack ({aucs['gf_pm']:.3f})", "AUC difference with bootstrap CI", "in-sample AUC, no model fitting", len(te), "AUC(defence) - AUC(attack)", diff, lo, hi,
        diff, np.nan, "AUC difference", diff, "in-sample; differences in AUC of this size need the CI, not a p-value", "Q5_auc")


# ------------------------------------------------------------------ strength helper (season-to-date points per match, past only)
def add_strength(m, tm):
    t = tm.sort_values(["season_id", "team_key", "match_date", "match_key"]).copy()
    t["ppm_before"] = t.groupby(["season_id", "team_key"]).points.transform(lambda s: s.shift().expanding().mean())
    t["n_before"] = t.groupby(["season_id", "team_key"]).cumcount()
    h = t.set_index(["match_key", "team_key"])
    mm = m.copy()
    mm["ppm_home"] = [h.ppm_before.get((k, tk), np.nan) for k, tk in zip(mm.match_key, mm.home_team_key)]
    mm["ppm_away"] = [h.ppm_before.get((k, tk), np.nan) for k, tk in zip(mm.match_key, mm.away_team_key)]
    mm["n_home"] = [h.n_before.get((k, tk), 0) for k, tk in zip(mm.match_key, mm.home_team_key)]
    mm["n_away"] = [h.n_before.get((k, tk), 0) for k, tk in zip(mm.match_key, mm.away_team_key)]
    return mm


# ------------------------------------------------------------------ Q6
def q6(m):
    Q = "Q6 Do penalty shootouts favour particular teams?"
    fam = "Q6"
    s = m[m.had_shootout & m.shootout_winner_side.notna()].copy()
    s["winner_key"] = np.where(s.shootout_winner_side == "home", s.home_team_key, s.away_team_key)
    s["loser_key"] = np.where(s.shootout_winner_side == "home", s.away_team_key, s.home_team_key)
    n = len(s)
    bt = ss.binomtest(int((s.shootout_winner_side == "home").sum()), n, .5)
    ci = bt.proportion_ci(method="exact")
    add("Q6", Q, f"Does the team listed first win more often? ({n} shoot-outs)", "exact binomial test vs 0.5", "listing order is arbitrary in the sources, so a deviation would indicate a data artefact rather than a real advantage", n,
        "P(first-listed team wins), exact 95% CI", (s.shootout_winner_side == "home").mean(), ci.low, ci.high, bt.statistic, bt.pvalue, "deviation from 0.5", (s.shootout_winner_side == "home").mean() - .5,
        "kick-by-kick data and the first shooter are not in the dataset, so 'first shooter advantage' cannot be tested", fam)
    st = s[(s.n_home >= 2) & (s.n_away >= 2)].copy()
    st = st[st.ppm_home != st.ppm_away]
    st["stronger_won"] = ((st.ppm_home > st.ppm_away) == (st.shootout_winner_side == "home")).astype(int)
    if len(st) >= 10:
        bt = ss.binomtest(int(st.stronger_won.sum()), len(st), .5)
        ci = bt.proportion_ci(method="exact")
        add("Q6", Q, "Does the team with the better record so far in that tournament win the shoot-out?", "exact binomial test vs 0.5", "strength = points per match in earlier matches of the same edition (past only), needs >=2 prior matches each; ties dropped", len(st),
            "P(stronger-so-far team wins)", st.stronger_won.mean(), ci.low, ci.high, bt.statistic, bt.pvalue, "deviation from 0.5", st.stronger_won.mean() - .5, "small n -> low power; a null result does not prove shoot-outs are a lottery", fam)
    teams = pd.concat([s.winner_key.rename("team").to_frame().assign(w=1), s.loser_key.rename("team").to_frame().assign(w=0)])
    tt = teams.groupby("team").w.agg(["sum", "count"])
    tt = tt[tt["count"] >= 4]
    names = D.q("select team_key, team_name from staging.stg_teams").set_index("team_key").team_name
    for k, r in tt.iterrows():
        bt = ss.binomtest(int(r["sum"]), int(r["count"]), .5)
        ci = bt.proportion_ci(method="exact")
        add("Q6", Q, f"{names[k]}: shoot-out record ({int(r['sum'])}/{int(r['count'])})", "exact binomial test vs 0.5 (Holm across teams)", "teams with >=4 shoot-outs only", int(r["count"]), "win rate, exact 95% CI", r["sum"] / r["count"], ci.low, ci.high,
            bt.statistic, bt.pvalue, "deviation from 0.5", r["sum"] / r["count"] - .5, "very small samples; multiple teams tested -> Holm adjustment", "Q6_teams")


# ------------------------------------------------------------------ Q7
def icc1(df, group, val):
    g = df.groupby(group)[val]
    k = g.size()
    n, N = len(k), len(df)
    n0 = (N - (k ** 2).sum() / N) / (n - 1)
    msb = (k * (g.mean() - df[val].mean()) ** 2).sum() / (n - 1)
    msw = ((df[val] - g.transform("mean")) ** 2).sum() / (N - n)
    return (msb - msw) / (msb + (n0 - 1) * msw), msb / msw, n - 1, N - n


def q7(tm):
    Q = "Q7 Is performance consistent across tournament editions?"
    fam = "Q7"
    te = tm.groupby(["comp", "season_id", "season_year", "team_key"]).agg(ppm=("points", "mean"), n=("match_key", "size")).reset_index()
    for comp in D.COMP_ORDER:
        x = te[te.comp == comp]
        eds = x.groupby("team_key").season_id.nunique()
        x = x[x.team_key.isin(eds[eds >= 3].index)]
        if x.team_key.nunique() < 8:
            continue
        icc, F, d1, d2 = icc1(x, "team_key", "ppm")
        pF = ss.f.sf(F, d1, d2)
        perm = []
        for _ in range(1500):                                         # null: team identity carries no information (shuffle within edition)
            y = x.copy()
            y["ppm"] = y.groupby("season_id").ppm.transform(lambda s: RNG.permutation(s.values))
            perm.append(icc1(y, "team_key", "ppm")[0])
        pperm = (np.sum(np.array(perm) >= icc) + 1) / (len(perm) + 1)
        teams = x.team_key.unique()
        bs = []
        for _ in range(600):
            pick = RNG.choice(teams, len(teams))
            bs.append(icc1(pd.concat([x[x.team_key == t].assign(team_key=f"{t}_{i}") for i, t in enumerate(pick)]), "team_key", "ppm")[0])
        lo, hi = np.percentile(bs, [2.5, 97.5])
        ed = sorted(x.season_year.unique())
        cons = []
        for a, b in zip(ed[:-1], ed[1:]):
            j = x[x.season_year == a].merge(x[x.season_year == b], on="team_key")
            if len(j) >= 6:
                cons.append(ss.spearmanr(j.ppm_x, j.ppm_y)[0])
        add("Q7", Q, f"{comp}: share of variance in edition performance explained by team identity (teams with >=3 editions: {x.team_key.nunique()})",
            "intraclass correlation ICC(1) from one-way random-effects ANOVA; F-test and permutation test", f"unbalanced design; ppm is bounded/discrete -> permutation p ({pperm:.4f}) preferred over F-test p ({pF:.4f}); mean consecutive-edition Spearman={np.mean(cons):.2f}",
            len(x), "ICC(1), team-bootstrap 95% CI", icc, lo, hi, F, pperm, "ICC (0 = no consistency, 1 = fully consistent)", icc,
            "ppm from few matches per edition is noisy (attenuates ICC); squads change between editions; only repeat participants", fam)


# ------------------------------------------------------------------ Q8
def q8b(m, tm):
    Q = "Q8 Does extra time significantly affect match outcomes?"
    mm = add_strength(m[m.is_knockout.astype(bool)], tm)
    mm = mm[(mm.n_home >= 2) & (mm.n_away >= 2) & (mm.ppm_home != mm.ppm_away)].copy()
    winner_home = np.where(mm.home_score != mm.away_score, mm.home_score > mm.away_score, mm.shootout_winner_side == "home")
    decided = (mm.home_score != mm.away_score) | mm.shootout_winner_side.notna()
    mm = mm[decided].copy()
    winner_home = np.where(mm.home_score != mm.away_score, mm.home_score > mm.away_score, mm.shootout_winner_side == "home")
    mm["stronger_won"] = ((mm.ppm_home > mm.ppm_away) == winner_home).astype(int)
    mm["beyond"] = mm.went_beyond_90.astype(int)
    tab = pd.crosstab(mm.beyond, mm.stronger_won).reindex(index=[0, 1], columns=[0, 1], fill_value=0)
    if tab.values.min() >= 0 and tab.values.sum() > 20:
        orr, p = ss.fisher_exact(tab.values)
        a, b, c, d = tab.loc[1, 1], tab.loc[1, 0], tab.loc[0, 1], tab.loc[0, 0]
        se = np.sqrt(1 / max(a, .5) + 1 / max(b, .5) + 1 / max(c, .5) + 1 / max(d, .5))
        lo, hi = np.exp(np.log(orr) + np.array([-1.96, 1.96]) * se)
        add("Q8", Q, f"Is the team with the better record so far less likely to win when the match goes beyond 90 minutes? (n={int(tab.values.sum())})", "Fisher exact test (2x2), Woolf CI for the odds ratio",
            f"expected counts small in the extra-time row ({int(tab.loc[1].sum())} matches) -> Fisher exact instead of chi-square; stronger = higher points/match so far in the edition (past only)", int(tab.values.sum()),
            "odds ratio stronger-team-wins (beyond 90 vs decided in 90)", orr, lo, hi, orr, p, "phi coefficient", float(np.sqrt(ss.chi2_contingency(tab.values, correction=False)[0] / tab.values.sum())),
            "extra-time matches are by construction the closer ones; strength proxy is noisy early in a tournament", "Q8_strength")
        pct = (tab[1] / tab.sum(axis=1)).round(3).to_dict()
        ROWS[-1]["assumption_checks"] += f"; stronger-team win share: decided in 90 = {pct[0]}, beyond 90 = {pct[1]}"


# ------------------------------------------------------------------ Q9
def q9(m):
    Q = "Q9 Are some competitions statistically more competitive than others?"
    fam = "Q9"
    for lab, d in (("all matches", m), ("group/league phase only", m[~m.is_knockout.astype(bool)])):
        x = d[d.home_goals90.notna()].copy()
        x["margin90"] = (x.home_goals90 - x.away_goals90).abs()
        groups = [x[x.competition_id == c].margin90.values for c in D.COMP_ORDER]
        kw = ss.kruskal(*groups)
        eps = max((kw.statistic - len(D.COMP_ORDER) + 1) / (len(x) - len(D.COMP_ORDER)), 0.0)
        lev = ss.levene(*groups)
        add("Q9", Q, f"Absolute goal margin (regulation) differs between competitions ({lab})", "Kruskal-Wallis H test", f"margin is discrete/skewed (Shapiro p={shapiro(x.margin90):.1e}); Levene p={lev.pvalue:.3f}; matches independent assumed", len(x),
            "epsilon-squared", eps, np.nan, np.nan, kw.statistic, kw.pvalue, "epsilon-squared (0.01 small, 0.06 medium, 0.14 large)", eps,
            "margin depends on goal level; different formats/opposition pools (Nations League has four leagues of unequal strength)", f"Q9_{lab}")
        pairs = []
        for a, b in combinations(D.COMP_ORDER, 2):
            u = ss.mannwhitneyu(x[x.competition_id == a].margin90, x[x.competition_id == b].margin90)
            pairs.append((a, b, u.pvalue, cliffs_delta(x[x.competition_id == a].margin90, x[x.competition_id == b].margin90),
                          x[x.competition_id == a].margin90.mean() - x[x.competition_id == b].margin90.mean()))
        for a, b, p, dl, md in pairs:
            lo, hi = boot_ci(lambda u, v: u.mean() - v.mean(), x[x.competition_id == a].margin90.values, x[x.competition_id == b].margin90.values, b=1500)
            add("Q9", Q, f"Pairwise ({lab}): {a} vs {b} mean margin", "Mann-Whitney U, Holm across the 6 pairs", "post-hoc after Kruskal-Wallis", int((x.competition_id.isin([a, b])).sum()), "mean margin difference, bootstrap CI",
                md, lo, hi, np.nan, p, "Cliff's delta", dl, "multiple comparisons -> Holm", f"Q9_pairs_{lab}")
        tab = pd.crosstab(x.competition_id, x.margin90 == 0)
        chi = ss.chi2_contingency(tab)
        add("Q9", Q, f"Draw share differs between competitions ({lab})", "chi-square test of independence", f"min expected count={chi[3].min():.1f}", int(tab.values.sum()), "chi-square", chi[0], np.nan, np.nan, chi[0], chi[1], "Cramer's V", cramers_v(tab),
            "draw share in regulation; knockout matches drawn after 90 are included in 'all matches'", f"Q9_draw_{lab}")


# ------------------------------------------------------------------ Q10
def q10(m):
    Q = "Q10 Are goal-scoring patterns significantly different between tournament formats?"
    fam = "Q10"
    ts = D.tournaments().set_index("season_id").teams
    x = m[m.goals90.notna()].copy()
    x["teams"] = x.season_id.map(ts)
    x["format"] = x.competition_id + "-" + x.teams.astype(int).astype(str)
    for comp in ("WC", "EURO", "COPA"):
        c = x[x.competition_id == comp]
        fm = sorted(c.format.unique())
        if len(fm) < 2:
            continue
        gs = [c[c.format == f].goals90.values for f in fm]
        if len(fm) == 2:
            st = ss.mannwhitneyu(*gs)
            meth, stat, p, eff, ename = "Mann-Whitney U", st.statistic, st.pvalue, cliffs_delta(*gs), "Cliff's delta"
            lo, hi = boot_ci(lambda a, b: a.mean() - b.mean(), *gs, b=2000)
            diff = gs[0].mean() - gs[1].mean()
            en = f"mean goals {fm[0]} - {fm[1]}, bootstrap CI"
        else:
            st = ss.kruskal(*gs)
            n = sum(len(g) for g in gs)
            meth, stat, p, eff, ename = "Kruskal-Wallis H", st.statistic, st.pvalue, max((st.statistic - len(gs) + 1) / (n - len(gs)), 0.0), "epsilon-squared"
            diff, lo, hi, en = np.nan, np.nan, np.nan, "see descriptives"
        disp = {f: round(g.var() / g.mean(), 2) for f, g in zip(fm, gs)}
        add("Q10", Q, f"{comp}: goals per match by format ({', '.join(f'{f}: {len(g)} matches, mean {g.mean():.2f}' for f, g in zip(fm, gs))})", meth,
            f"goal counts non-normal; variance/mean per format = {disp}", sum(len(g) for g in gs), en, diff, lo, hi, stat, p, ename, eff,
            "format is confounded with era, hosts and (for the 48-team World Cup) a much larger share of mismatches; cannot isolate a format effect", "Q10_means")
        cat = pd.crosstab(c.format, c.goals90.clip(upper=4))
        chi = ss.chi2_contingency(cat)
        add("Q10", Q, f"{comp}: distribution of goals per match (0,1,2,3,4+) differs between formats", "chi-square test of independence", f"min expected count={chi[3].min():.1f}{' (<5: interpret with caution)' if chi[3].min() < 5 else ''}",
            int(cat.values.sum()), "chi-square", chi[0], np.nan, np.nan, chi[0], chi[1], "Cramer's V", cramers_v(cat), "same confounding as above", "Q10_dist")
    g = x[~x.is_knockout.astype(bool)]
    comp_fm = {f: v.goals90.values for f, v in g.groupby("format") if len(v) >= 30}
    st = ss.kruskal(*comp_fm.values())
    n = sum(len(v) for v in comp_fm.values())
    add("Q10", Q, f"All formats compared on group/league matches ({len(comp_fm)} formats)", "Kruskal-Wallis H test", "formats with >= 30 matches only", n, "epsilon-squared", max((st.statistic - len(comp_fm) + 1) / (n - len(comp_fm)), 0.0), np.nan, np.nan,
        st.statistic, st.pvalue, "epsilon-squared", max((st.statistic - len(comp_fm) + 1) / (n - len(comp_fm)), 0.0), "mixes competitions and eras", "Q10_all")


# ------------------------------------------------------------------ report
def write_report(df: pd.DataFrame):
    def verdict(r):
        if pd.isna(r.p_value):
            return "descriptive / interval estimate"
        p = r.p_adj_holm if pd.notna(r.p_adj_holm) else r.p_value
        return ("significant at 5%" if p < ALPHA else "no significant evidence at 5%") + f" (adj. p={p:.3g})"
    L = ["# Statistical report", "", "Generated by `fbplatform.analysis.stats` from the warehouse. Played matches only; scheduled fixtures are excluded from every test. "
         "Multiple-testing: Holm adjustment inside each family. All numbers below are computed, not typed. Significance is not importance: read the effect size and the CI. "
         "No causal claims are made.", ""]
    for q, g in df.groupby("q", sort=False):
        L += [f"## {g.question.iloc[0]}", ""]
        for r in g.itertuples():
            ci = "" if pd.isna(r.ci_low) else f" [{r.ci_low:.3g}, {r.ci_high:.3g}]"
            L += [f"**{r.analysis}**  ", f"- method: {r.method}  ", f"- assumptions/diagnostics: {r.assumption_checks}  ",
                  f"- n = {r.n}; {r.estimate_name}: {r.estimate:.4g}{ci}; test statistic {r.statistic:.4g}; p = {r.p_value:.3g}" if pd.notna(r.p_value) else
                  f"- n = {r.n}; {r.estimate_name}: {r.estimate:.4g}{ci}", f"- effect size ({r.effect_size_name}): {r.effect_size:.3g}  ", f"- result: {verdict(r)}  ", f"- limitations: {r.limitations}", ""]
    return "\n".join(L)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    m, tm, g = D.matches(), D.team_matches(), D.goals()
    desc, sp, pe, cov = descriptives(m, tm)
    desc.round(4).to_csv(OUT / "descriptives.csv", index=False)
    pd.concat({"spearman": sp, "pearson": pe, "covariance": cov}).round(4).to_csv(OUT / "correlations.csv")
    te = team_edition(tm)
    q1(m); q2(m); q3(m, g); q4(te); q5(te)
    mm = add_strength(m, tm)
    q6(mm)
    q7(tm)
    q8(m)
    q8b(m, tm)
    q9(m); q10(m)
    df = holm_within_family()
    df.to_csv(OUT / "results.csv", index=False)
    md = write_report(df)
    (OUT / "STATISTICAL_REPORT.md").write_text(md, encoding="utf-8")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "STATISTICAL_REPORT.md").write_text(md, encoding="utf-8")
    return df


def q8(m):
    Q = "Q8 Does extra time significantly affect match outcomes?"
    fam = "Q8"
    ko = m[m.is_knockout.astype(bool)]
    et = ko[ko.went_beyond_90]
    n_et, n_sh = len(et), int(et.had_shootout.sum())
    ci = ss.binomtest(n_sh, n_et).proportion_ci(method="exact")
    add("Q8", Q, f"Of {n_et} knockout matches that went beyond 90 minutes, how many were still level after extra time?", "exact binomial CI (descriptive)",
        "extra-time status inferred from sources (score basis, penalties, shoot-out winner); Nations League extra time is not recorded", n_et, "share ending in a shoot-out",
        n_sh / n_et, ci.low, ci.high, n_sh, np.nan, "share", n_sh / n_et, "undercounts extra-time matches in competitions that do not record it", fam)
    e = et[et.home_score_ft90.notna() & et.away_score_ft90.notna()].copy()
    e["reg_goals"] = e.home_score_ft90 + e.away_score_ft90
    e["et_goals"] = e.goals_total - e.reg_goals
    g_et, g_reg, k = float(e.et_goals.sum()), float(e.reg_goals.sum()), len(e)
    share_null = (30 * k) / (30 * k + 90 * k)
    bt = ss.binomtest(int(g_et), int(g_et + g_reg), share_null)
    ci = bt.proportion_ci(method="exact")
    ratio = lambda q: (q / (1 - q)) * 3.0
    add("Q8", Q, f"Goals per minute in extra time vs regulation, same {k} matches", "exact conditional (binomial) test of equal Poisson rates",
        "goals are rare events; same matches contribute to both periods; matches level at 90 minutes are the tighter ones, so the regulation rate here is below average",
        k, "rate ratio ET / regulation per minute", ratio(g_et / (g_et + g_reg)), ratio(ci.low), ratio(ci.high), g_et, bt.pvalue, "rate ratio", ratio(g_et / (g_et + g_reg)),
        f"ET goals={int(g_et)}, regulation goals={int(g_reg)} in {k} matches; only matches with a known 90-minute score; fatigue vs caution cannot be separated", fam)


if __name__ == "__main__":
    r = run()
    print(len(r), "result rows;", r.q.value_counts().sort_index().to_dict())
