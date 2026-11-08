"""Statistical visualisations: correlation matrix, distributions, box/violin, scatter with regression CI, confidence-interval forest plots,
hypothesis-test summary and regression diagnostics. Each has a Matplotlib/Seaborn twin (`Chart.static`) for PNG export."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import statsmodels.api as sm
import statsmodels.formula.api as smf
from plotly.subplots import make_subplots
from scipy import stats as ss

from ..config import ROOT
from . import common as C
from .common import Chart, unavailable

SRC = "staging.stg_matches / intermediate.int_team_matches (warehouse)"
RESULTS = ROOT / "reports" / "statistics" / "results.csv"
VAR_LABEL = {"goals90": "Goals in regulation time", "goals_total": "Goals incl. extra time", "margin": "Goal margin (|home − away|)", "attendance": "Attendance"}


def team_edition_table(tm: pd.DataFrame, min_matches: int = 3) -> pd.DataFrame:
    g = tm.groupby(["season_id", "comp", "team_name"]).agg(matches=("match_key", "size"), gf_pm=("goals_for", "mean"), ga_pm=("goals_against", "mean"), ppm=("points", "mean"),
                                                         win_pct=("result", lambda s: 100 * (s == "W").mean()), cs_pct=("clean_sheet", lambda s: 100 * s.mean())).reset_index()
    return g[g.matches >= min_matches]


# ------------------------------------------------------------------ correlation matrix
def correlation_matrix(df: pd.DataFrame, cols: dict[str, str], method: str = "spearman") -> Chart:
    d = df[list(cols)].dropna()
    if len(d) < 20 or len(cols) < 3:
        return unavailable("correlation_matrix", "needs at least 20 complete rows and 3 variables")
    r = d.corr(method=method)
    r.index = r.columns = [cols[c] for c in r.columns]
    n = len(d)
    mask = np.triu(np.ones_like(r, dtype=bool), k=1)
    z = r.where(~mask)
    fig = go.Figure(go.Heatmap(z=z.values, x=r.columns, y=r.index, zmin=-1, zmax=1, colorscale=[[0, "#2a78d6"], [0.5, "#f0efec"], [1, "#e34948"]], text=np.where(mask, "", r.round(2).astype(str)), texttemplate="%{text}", xgap=2, ygap=2,
                               colorbar=dict(title=f"{method.capitalize()}<br>correlation"), hovertemplate="%{y} × %{x}<br>" + method + " ρ = %{z:.2f}<extra></extra>"))
    C.style(fig, f"{method.capitalize()} correlation matrix (n = {n:,} team-editions)", None, None, legend=False, height=470)
    fig.update_yaxes(autorange="reversed")

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(figsize=(7, 5.5))
        sns.heatmap(r, mask=mask, vmin=-1, vmax=1, cmap=sns.diverging_palette(250, 15, s=80, l=55, as_cmap=True), annot=True, fmt=".2f", linewidths=2, linecolor="white", ax=ax)
        ax.set_title(f"{method.capitalize()} correlation (n={n})"); return f
    return Chart(fig, r.round(3).reset_index(names="variable"), n, SRC, "Blue = negative, red = positive, grey = none. Correlation is association, not causation; points/goals are partly linked by construction (points come from goals).", static=static, name="correlation_matrix")


# ------------------------------------------------------------------ distributions
def distribution(m: pd.DataFrame, var: str = "goals90", by: str = "competition_id") -> Chart:
    d = m[m[var].notna()]
    if len(d) < 30:
        return unavailable("distribution", f"fewer than 30 matches with a known {VAR_LABEL.get(var, var)}")
    fig = go.Figure()
    rows = []
    bins = np.arange(-0.5, d[var].max() + 1.5, 1) if d[var].max() <= 12 else None
    for k in (C.COMPS if by == "competition_id" else sorted(d[by].unique())):
        g = d[d[by] == k][var]
        if len(g) < 10:
            continue
        col = C.COMP_COLOR.get(k, C.CAT[0])
        counts = g.value_counts(normalize=True).sort_index() * 100
        fig.add_bar(x=counts.index, y=counts.values, name=f"{C.COMP_LABEL.get(k, k)} (n={len(g)})", marker_color=col, opacity=0.9, hovertemplate="%{x}: %{y:.1f}% of matches<extra>" + C.COMP_LABEL.get(k, k) + "</extra>")
        rows += [dict(group=k, value=v, share_pct=round(p, 2)) for v, p in counts.items()]
    if not rows:
        return unavailable("distribution", "no group has 10+ matches in the selection")
    fig.update_layout(barmode="group")
    C.style(fig, f"Distribution of {VAR_LABEL.get(var, var).lower()}", VAR_LABEL.get(var, var), "Share of matches (%)")
    C.bar_gap(fig)

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(figsize=(8, 4.2))
        sns.histplot(data=d, x=var, hue=by, discrete=True, stat="percent", common_norm=False, multiple="dodge", palette=C.COMP_COLOR if by == "competition_id" else None, shrink=0.85, ax=ax)
        ax.set_xlabel(VAR_LABEL.get(var, var)); ax.set_ylabel("Share of matches (%)"); return f
    return Chart(fig, pd.DataFrame(rows), len(d), SRC, "Each group sums to 100% (shares, not counts). Matches with an unknown value (e.g. extra-time matches without a 90-minute score for 'regulation goals') are excluded, not zero.", static=static, name="distribution")


def box_plot(m: pd.DataFrame, var: str = "goals90", by: str = "stage_name") -> Chart:
    d = m[m[var].notna()]
    if len(d) < 30:
        return unavailable("box_plot", f"fewer than 30 matches with a known {VAR_LABEL.get(var, var)}")
    order = list(d.groupby(by)[var].size().loc[lambda s: s >= 5].index)
    if by == "stage_name":
        pref = ["Group stage", "Play-off", "Promotion/relegation play-off", "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Third place", "Final"]
        order = [s for s in pref if s in order]
    elif by == "competition_id":
        order = [c for c in C.COMPS if c in order]
    fig = go.Figure()
    for k in order:
        g = d[d[by] == k][var]
        fig.add_box(y=g, x=[f"{C.COMP_LABEL.get(k, k)}<br>n={len(g)}"] * len(g), name=str(k), marker_color=C.CAT[0], line=dict(color=C.CAT[0], width=1.5), fillcolor="#cde2fb", boxmean=True, showlegend=False,
                    hovertemplate=f"{k}<br>%{{y}}<extra></extra>")
    C.style(fig, f"{VAR_LABEL.get(var, var)} by {by.replace('_', ' ')}", by.replace("_name", "").replace("_id", "").capitalize() + " (n = matches)", VAR_LABEL.get(var, var), legend=False, height=450)
    fig.update_xaxes(tickangle=30)

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(figsize=(9, 4.5))
        sns.boxplot(data=d[d[by].isin(order)], x=by, y=var, order=order, color="#cde2fb", linecolor="#2a78d6", showmeans=True, ax=ax)
        ax.set_ylabel(VAR_LABEL.get(var, var)); ax.tick_params(axis="x", rotation=30); return f
    return Chart(fig, d[[by, var]], len(d), SRC, "Box = interquartile range, line = median, diamond = mean, whiskers = 1.5×IQR; groups with fewer than 5 matches omitted. Goal counts are discrete, so boxes sit on whole numbers.", static=static, name="box_plot")


def violin_plot(m: pd.DataFrame, var: str = "margin", by: str = "competition_id") -> Chart:
    d = m[m[var].notna()]
    if len(d) < 30:
        return unavailable("violin_plot", f"fewer than 30 matches with a known {VAR_LABEL.get(var, var)}")
    fig = go.Figure()
    keys = [c for c in (C.COMPS if by == "competition_id" else sorted(d[by].unique())) if (d[by] == c).sum() >= 10]
    for k in keys:
        g = d[d[by] == k][var]
        col = C.COMP_COLOR.get(k, C.CAT[0])
        fig.add_violin(y=g, x=[f"{C.COMP_LABEL.get(k, k)}<br>n={len(g)}"] * len(g), line_color=col, fillcolor=col + "55", meanline_visible=True, box_visible=True, points=False, spanmode="hard", showlegend=False, name=str(k),
                       hovertemplate=f"{k}<br>%{{y}}<extra></extra>")
    C.style(fig, f"{VAR_LABEL.get(var, var)}: density by {by.replace('_', ' ')}", "Group (n = matches)", VAR_LABEL.get(var, var), legend=False, height=450)

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(figsize=(8, 4.5))
        sns.violinplot(data=d[d[by].isin(keys)], x=by, y=var, hue=by, order=keys, palette=C.COMP_COLOR if by == "competition_id" else None, legend=False, cut=0, inner="quartile", ax=ax)
        ax.set_ylabel(VAR_LABEL.get(var, var)); return f
    return Chart(fig, d[[by, var]], len(d), SRC, "Width = density of matches at that value (cut at the observed range; discrete counts make flat steps). White box = quartiles, line = mean.", static=static, name="violin_plot")


# ------------------------------------------------------------------ scatter with regression
def scatter_regression(df: pd.DataFrame, x: str, y: str, xlabel: str, ylabel: str) -> Chart:
    d = df[[x, y, "comp", "team_name", "season_id", "matches"]].dropna()
    if len(d) < 30:
        return unavailable("scatter_regression", "needs at least 30 team-editions")
    X = sm.add_constant(d[x])
    fit = sm.OLS(d[y], X).fit()
    grid = np.linspace(d[x].min(), d[x].max(), 60)
    pr = fit.get_prediction(sm.add_constant(pd.Series(grid, name=x))).summary_frame(alpha=0.05)
    rho = ss.spearmanr(d[x], d[y])[0]
    fig = go.Figure()
    fig.add_scatter(x=np.r_[grid, grid[::-1]], y=np.r_[pr.mean_ci_upper, pr.mean_ci_lower[::-1]], fill="toself", fillcolor="rgba(42,120,214,0.15)", line=dict(width=0), hoverinfo="skip", showlegend=False, name="95% CI of the fit")
    for c in C.COMPS:
        s = d[d.comp == c]
        if len(s):
            fig.add_scatter(x=s[x], y=s[y], mode="markers", name=f"{C.COMP_LABEL[c]} (n={len(s)})", marker=dict(size=8, color=C.COMP_COLOR[c], symbol=C.COMP_SYMBOL[c], opacity=0.75, line=dict(color=C.SURFACE, width=1.2)),
                            customdata=np.c_[s.team_name, s.season_id, s.matches], hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>" + xlabel + ": %{x:.2f}<br>" + ylabel + ": %{y:.2f}<br>%{customdata[2]} matches<extra></extra>")
    fig.add_scatter(x=grid, y=pr["mean"], mode="lines", line=dict(color=C.INK, width=2), name=f"OLS fit: slope {fit.params[x]:.2f} (R² {fit.rsquared:.2f})")
    C.style(fig, f"{ylabel} vs {xlabel}", xlabel, ylabel, height=500)
    out = d.assign(fitted=fit.predict(X), residual=fit.resid)

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(figsize=(7.5, 5))
        sns.regplot(data=d, x=x, y=y, scatter_kws=dict(s=18, alpha=0.6, color="#2a78d6"), line_kws=dict(color="black"), ax=ax)
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(f"slope {fit.params[x]:.2f}, R² {fit.rsquared:.2f}"); return f
    return Chart(fig, out.round(4), len(d), SRC, f"One point per team-edition (3+ matches). OLS slope {fit.params[x]:.2f} (95% CI {fit.conf_int().loc[x, 0]:.2f} to {fit.conf_int().loc[x, 1]:.2f}), Spearman ρ = {rho:.2f}. Band = 95% CI of the mean fit. Points from one tournament are not independent; association only.", static=static, name="scatter_regression")


# ------------------------------------------------------------------ confidence intervals and hypothesis tests (from reports/statistics/results.csv)
def load_results() -> pd.DataFrame:
    return pd.read_csv(RESULTS) if RESULTS.exists() else pd.DataFrame()


def _kind(name: str) -> str:
    n = name.lower()
    if "ratio" in n:
        return "ratio"
    if n.startswith("p(") or "share" in n or "rate" in n and "ratio" not in n:
        return "proportion"
    return "difference"


def ci_forest(res: pd.DataFrame, kind: str = "ratio") -> Chart:
    d = res[res.ci_low.notna() & res.ci_high.notna()].copy()
    d["kind"] = d.estimate_name.map(_kind)
    d = d[d.kind == kind]
    if d.empty:
        return unavailable("ci_forest", f"no '{kind}' estimates with a confidence interval in reports/statistics/results.csv (run python -m fbplatform.analysis.stats)")
    d = d.sort_values(["q", "estimate"]).iloc[::-1]
    d["label"] = d.q + " · " + d.analysis.str.slice(0, 62) + " (n=" + d.n.astype(int).astype(str) + ")"
    ref = {"ratio": 1.0, "proportion": 0.5, "difference": 0.0}[kind]
    p = d.p_adj_holm.fillna(d.p_value)
    sig = p < 0.05
    fig = go.Figure()
    for flag, col, lab in ((True, C.CAT[0], "adjusted p < 0.05"), (False, "#898781", "not significant at 5%")):
        s = d[sig == flag]
        if len(s):
            fig.add_scatter(x=s.estimate, y=s.label, mode="markers", name=lab, marker=dict(size=9, color=col, line=dict(color=C.SURFACE, width=2)),
                            error_x=dict(type="data", symmetric=False, array=s.ci_high - s.estimate, arrayminus=s.estimate - s.ci_low, color=col, thickness=1.6, width=4),
                            customdata=np.c_[s.ci_low, s.ci_high, p[sig == flag], s.effect_size_name, s.effect_size], hovertemplate="<b>%{y}</b><br>estimate %{x:.3g} (95% CI %{customdata[0]:.3g} to %{customdata[1]:.3g})<br>adj. p = %{customdata[2]:.3g}<br>%{customdata[3]}: %{customdata[4]:.3g}<extra></extra>")
    fig.add_vline(x=ref, line=dict(color=C.INK2, width=1))
    C.style(fig, f"Estimates with 95% confidence intervals ({kind}s)", {"ratio": "Ratio (1 = no effect; log scale)", "proportion": "Proportion (0.5 = no edge)", "difference": "Difference / correlation (0 = none)"}[kind], None, height=max(360, 30 * len(d) + 150))
    if kind == "ratio":
        fig.update_xaxes(type="log")
    return Chart(fig, d[["q", "analysis", "n", "estimate_name", "estimate", "ci_low", "ci_high", "p_value", "p_adj_holm", "effect_size_name", "effect_size"]].round(4), len(d), "reports/statistics/results.csv", "Only estimates of the same kind share a scale. A CI crossing the vertical line means no reliable difference from 'no effect' - not proof of equality.", name=f"ci_forest_{kind}")


def hypothesis_summary(res: pd.DataFrame, top: int = 30) -> Chart:
    d = res[res.p_value.notna()].copy()
    if d.empty:
        return unavailable("hypothesis_summary", "no tests with a p-value in reports/statistics/results.csv")
    d["p_used"] = d.p_adj_holm.fillna(d.p_value).clip(lower=1e-300)
    d["score"] = -np.log10(d.p_used)
    d = d.sort_values("score", ascending=False).head(top).iloc[::-1]
    d["label"] = d.q + " · " + d.analysis.str.slice(0, 58)
    sig = d.p_used < 0.05
    fig = go.Figure()
    for flag, col, lab in ((True, C.CAT[0], "adjusted p < 0.05"), (False, "#b4b2a9", "not significant at 5%")):
        s = d[sig == flag]
        if len(s):
            fig.add_bar(y=s.label, x=s.score, orientation="h", name=lab, marker_color=col, customdata=np.c_[s.p_used, s.n, s.effect_size_name, s.effect_size, s.method],
                        hovertemplate="<b>%{y}</b><br>adjusted p = %{customdata[0]:.3g} (n = %{customdata[1]:.0f})<br>%{customdata[2]}: %{customdata[3]:.3g}<br>%{customdata[4]}<extra></extra>")
    fig.add_vline(x=-np.log10(0.05), line=dict(color=C.INK2, width=1)); fig.add_vline(x=-np.log10(0.001), line=dict(color=C.AXIS, width=1))
    C.style(fig, "Hypothesis tests: strength of evidence", "−log10(adjusted p)   (right of the first line: p < 0.05; second line: p < 0.001)", None, height=max(380, 24 * len(d) + 150))
    C.bar_gap(fig)
    fig.update_layout(barmode="overlay")
    return Chart(fig, d.sort_values("score", ascending=False)[["q", "analysis", "method", "n", "p_value", "p_adj_holm", "effect_size_name", "effect_size"]].round(5), len(d), "reports/statistics/results.csv",
                 "Evidence strength only: p-values say nothing about size - read effect sizes in the table/hover. Effect sizes use different scales per test. p-values are Holm-adjusted inside each question's family.", name="hypothesis_summary")


# ------------------------------------------------------------------ regression diagnostics
def regression_diagnostics(m: pd.DataFrame) -> Chart:
    d = m[m.goals90.notna()].copy()
    if len(d) < 100:
        return unavailable("regression_diagnostics", "needs at least 100 matches with a known regulation score")
    d["decade"] = (d.season_year - 2000) / 10.0
    d["competition_id"] = d.competition_id.astype("category")
    fit = smf.glm("goals90 ~ decade + competition_id", data=d, family=sm.families.Poisson()).fit()
    mu, dev, pear = fit.fittedvalues, fit.resid_deviance, fit.resid_pearson
    infl = fit.get_influence()
    cook, lev = infl.cooks_distance[0], infl.hat_matrix_diag
    disp = float(fit.pearson_chi2 / fit.df_resid)
    fig = make_subplots(rows=2, cols=2, subplot_titles=("Deviance residuals vs fitted", "Normal Q–Q of deviance residuals", "Scale–location", "Leverage vs residual (size = Cook's distance)"), vertical_spacing=0.17, horizontal_spacing=0.1)
    rng = np.random.default_rng(1)
    jit = rng.normal(0, 0.012, len(d))
    fig.add_scatter(x=mu + jit, y=dev, mode="markers", marker=dict(size=5, color=C.CAT[0], opacity=0.45), showlegend=False, hovertemplate="fitted %{x:.2f}<br>residual %{y:.2f}<extra></extra>", row=1, col=1)
    lo = sm.nonparametric.lowess(dev, mu, frac=0.5)
    fig.add_scatter(x=lo[:, 0], y=lo[:, 1], mode="lines", line=dict(color=C.CAT[1], width=2), showlegend=False, hoverinfo="skip", row=1, col=1)
    qq = ss.probplot(dev, dist="norm")
    fig.add_scatter(x=qq[0][0], y=qq[0][1], mode="markers", marker=dict(size=5, color=C.CAT[0], opacity=0.5), showlegend=False, hovertemplate="theoretical %{x:.2f}<br>observed %{y:.2f}<extra></extra>", row=1, col=2)
    fig.add_scatter(x=[qq[0][0].min(), qq[0][0].max()], y=[qq[1][1] + qq[1][0] * qq[0][0].min(), qq[1][1] + qq[1][0] * qq[0][0].max()], mode="lines", line=dict(color=C.INK2, width=1), showlegend=False, hoverinfo="skip", row=1, col=2)
    fig.add_scatter(x=mu + jit, y=np.sqrt(np.abs(dev)), mode="markers", marker=dict(size=5, color=C.CAT[0], opacity=0.45), showlegend=False, hovertemplate="fitted %{x:.2f}<br>√|residual| %{y:.2f}<extra></extra>", row=2, col=1)
    lo2 = sm.nonparametric.lowess(np.sqrt(np.abs(dev)), mu, frac=0.5)
    fig.add_scatter(x=lo2[:, 0], y=lo2[:, 1], mode="lines", line=dict(color=C.CAT[1], width=2), showlegend=False, hoverinfo="skip", row=2, col=1)
    fig.add_scatter(x=lev, y=pear, mode="markers", marker=dict(size=np.clip(cook / max(cook.max(), 1e-9) * 22 + 4, 4, 26), color=C.CAT[0], opacity=0.5), showlegend=False,
                    customdata=np.c_[cook], hovertemplate="leverage %{x:.4f}<br>Pearson residual %{y:.2f}<br>Cook's D %{customdata[0]:.4f}<extra></extra>", row=2, col=2)
    for r, c, xt, yt in ((1, 1, "Fitted goals", "Deviance residual"), (1, 2, "Theoretical quantile", "Observed quantile"), (2, 1, "Fitted goals", "√|deviance residual|"), (2, 2, "Leverage", "Pearson residual")):
        fig.update_xaxes(title_text=xt, row=r, col=c, showgrid=False, linecolor=C.AXIS)
        fig.update_yaxes(title_text=yt, row=r, col=c, gridcolor=C.GRID, linecolor=C.AXIS)
    C.style(fig, f"Regression diagnostics: Poisson GLM goals ~ decade + competition (n = {len(d):,}; dispersion = {disp:.2f})", None, None, legend=False, height=720)

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(2, 2, figsize=(10, 8))
        sns.scatterplot(x=mu, y=dev, s=12, alpha=0.4, ax=ax[0, 0]); ax[0, 0].set(title="Deviance residuals vs fitted", xlabel="Fitted goals", ylabel="Deviance residual")
        ss.probplot(dev, dist="norm", plot=ax[0, 1]); ax[0, 1].set_title("Normal Q–Q")
        sns.scatterplot(x=mu, y=np.sqrt(np.abs(dev)), s=12, alpha=0.4, ax=ax[1, 0]); ax[1, 0].set(title="Scale–location", xlabel="Fitted goals", ylabel="√|deviance residual|")
        sns.scatterplot(x=lev, y=pear, s=12, alpha=0.4, ax=ax[1, 1]); ax[1, 1].set(title="Leverage vs Pearson residual", xlabel="Leverage", ylabel="Pearson residual")
        f.tight_layout(); return f
    out = pd.DataFrame({"fitted": mu, "deviance_residual": dev, "pearson_residual": pear, "leverage": lev, "cooks_distance": cook}).round(5)
    return Chart(fig, out, len(d), SRC, f"Counts are discrete, so residuals form bands (jittered slightly for display). Dispersion {disp:.2f}: close to 1 means the Poisson variance assumption is reasonable; the Q–Q shows the usual departure for count data. No observation has a large Cook's distance (max {cook.max():.3f}).", static=static, name="regression_diagnostics")
