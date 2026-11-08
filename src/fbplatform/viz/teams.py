"""Team analytics charts. Input: `team_matches` (analysis.data.team_matches: one row per team per PLAYED match) and `matches` where noted."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import common as C
from .common import Chart, unavailable

SRC = "intermediate.int_team_matches (warehouse); result = recorded score (extra time in, shoot-out out)"
RADAR_METRICS = [("Attack", "gf_pm", 1, "goals scored / match"), ("Defence", "ga_pm", -1, "goals conceded / match (fewer = better)"), ("Win rate", "win_pct", 1, "% of matches won"),
                 ("Points", "ppm", 1, "points / match (3-1-0)"), ("Clean sheets", "cs_pct", 1, "% of matches without conceding"), ("Knockout record", "ko_win_pct", 1, "% of knockout matches won"),
                 ("Consistency", "ppm_sd", -1, "SD of points/match across editions (lower = steadier)")]


def team_table(tm: pd.DataFrame, min_matches: int = 1) -> pd.DataFrame:
    """One row per team with the summary measures used by several charts."""
    if tm.empty:
        return pd.DataFrame()
    g = tm.groupby("team_name").agg(matches=("match_key", "size"), wins=("result", lambda s: (s == "W").sum()), draws=("result", lambda s: (s == "D").sum()), losses=("result", lambda s: (s == "L").sum()),
                                    gf=("goals_for", "sum"), ga=("goals_against", "sum"), points=("points", "sum"), clean=("clean_sheet", "sum"), editions=("season_id", "nunique")).reset_index()
    g["win_pct"], g["draw_pct"], g["loss_pct"] = 100 * g.wins / g.matches, 100 * g.draws / g.matches, 100 * g.losses / g.matches
    g["gf_pm"], g["ga_pm"], g["ppm"], g["cs_pct"] = g.gf / g.matches, g.ga / g.matches, g.points / g.matches, 100 * g.clean / g.matches
    ko = tm[tm.is_knockout.astype(bool)].groupby("team_name").agg(ko_n=("match_key", "size"), ko_w=("result", lambda s: (s == "W").sum()))
    g = g.merge(ko, how="left", left_on="team_name", right_index=True)
    g["ko_win_pct"] = np.where(g.ko_n >= 3, 100 * g.ko_w / g.ko_n, np.nan)               # fewer than 3 knockout matches: not shown (missing, not zero)
    sd = tm.groupby(["team_name", "season_id"]).points.mean().groupby("team_name").std().rename("ppm_sd")
    g = g.merge(sd, how="left", left_on="team_name", right_index=True)
    return g[g.matches >= min_matches].reset_index(drop=True)


def _pick(tbl: pd.DataFrame, teams: list[str] | None, top_n: int, min_matches: int) -> pd.DataFrame:
    d = tbl[tbl.team_name.isin(teams)] if teams else tbl[tbl.matches >= min_matches].sort_values("matches", ascending=False).head(top_n)
    return d


def wdl_distribution(tm: pd.DataFrame, teams: list[str] | None = None, top_n: int = 20, min_matches: int = 10) -> Chart:
    d = _pick(team_table(tm), teams, top_n, min_matches)
    if d.empty:
        return unavailable("wdl_distribution", f"no team with at least {min_matches} played matches in the current selection")
    d = d.sort_values("win_pct")
    fig = go.Figure()
    for k, lab, col in (("win_pct", "Win", C.OUTCOME_COLOR["win"]), ("draw_pct", "Draw", C.OUTCOME_COLOR["draw"]), ("loss_pct", "Loss", C.OUTCOME_COLOR["loss"])):
        fig.add_bar(y=d.team_name, x=d[k], name=lab, orientation="h", marker_color=col, customdata=np.c_[d.matches, d.wins, d.draws, d.losses],
                    hovertemplate="<b>%{y}</b> · %{customdata[0]} matches<br>W %{customdata[1]} · D %{customdata[2]} · L %{customdata[3]}<br>" + lab + ": %{x:.1f}%<extra></extra>")
    fig.update_layout(barmode="stack", yaxis=dict(categoryorder="array", categoryarray=list(d.team_name)))
    fig.update_yaxes(ticktext=[f"{t} (n={n})" for t, n in zip(d.team_name, d.matches)], tickvals=list(d.team_name))
    C.style(fig, "Win / draw / loss distribution", "Share of matches (%)", None, height=max(320, 26 * len(d) + 140))
    C.bar_gap(fig)
    return Chart(fig, d[["team_name", "matches", "wins", "draws", "losses", "win_pct", "draw_pct", "loss_pct"]].round(2), int(d.matches.sum()), SRC,
                 "Sorted by win share; n = matches played in the dataset (not careers). Team-matches inside the current filters only.", name="wdl_distribution")


def goals_scored_conceded(tm: pd.DataFrame, teams: list[str] | None = None, min_matches: int = 15) -> Chart:
    t = team_table(tm)
    d = t[t.team_name.isin(teams)] if teams else t[t.matches >= min_matches]
    if len(d) < 2:
        return unavailable("goals_scored_conceded", f"needs at least 2 teams with {min_matches}+ matches (or an explicit team selection)")
    ref_x, ref_y = tm.goals_for.mean(), tm.goals_against.mean()
    fig = go.Figure(go.Scatter(x=d.gf_pm, y=d.ga_pm, mode="markers+text", text=d.team_name, textposition="top center", textfont=dict(size=10, color=C.INK2),
                               marker=dict(size=np.clip(d.matches / 4, 8, 34), color=C.CAT[0], opacity=0.85, line=dict(color=C.SURFACE, width=2)), customdata=np.c_[d.matches, d.gf, d.ga],
                               hovertemplate="<b>%{text}</b><br>%{customdata[0]} matches<br>scored %{x:.2f} / match (%{customdata[1]} total)<br>conceded %{y:.2f} / match (%{customdata[2]} total)<extra></extra>"))
    fig.add_hline(y=ref_y, line=dict(color=C.AXIS, width=1)); fig.add_vline(x=ref_x, line=dict(color=C.AXIS, width=1))
    C.style(fig, "Goals scored vs conceded per match", "Goals scored per match", "Goals conceded per match (lower is better)", legend=False, height=520)
    return Chart(fig, d[["team_name", "matches", "gf", "ga", "gf_pm", "ga_pm"]].round(3), int(d.matches.sum()), SRC,
                 "Bubble size = matches played. Grey lines = average of all team-matches in the selection (bottom-right = strong attack and strong defence).", name="goals_scored_conceded")


def radar(tm: pd.DataFrame, teams: list[str], reference_min_matches: int = 15) -> Chart:
    t = team_table(tm)
    ref = t[t.matches >= reference_min_matches]
    teams = [x for x in teams if x in set(t.team_name)][:4]
    if not teams or len(ref) < 8:
        return unavailable("radar", "select 1–4 teams that have played matches in the current filters (at least 8 reference teams with 15+ matches are needed for percentiles)")
    pr = {}
    for lab, col, sign, _ in RADAR_METRICS:
        s = ref[col].dropna()
        pr[col] = lambda v, s=s, sign=sign: np.nan if pd.isna(v) or len(s) == 0 else 100 * (float((s < v).mean() + 0.5 * (s == v).mean()) if sign > 0 else float((s > v).mean() + 0.5 * (s == v).mean()))
    fig = go.Figure()
    rows = []
    for i, name in enumerate(teams):
        r = t[t.team_name == name].iloc[0]
        vals = [pr[col](r[col]) for _, col, _, _ in RADAR_METRICS]
        raw = [r[col] for _, col, _, _ in RADAR_METRICS]
        labs = [m[0] for m in RADAR_METRICS]
        fig.add_scatterpolar(r=vals + vals[:1], theta=labs + labs[:1], name=f"{name} (n={int(r.matches)})", line=dict(color=C.CAT[i], width=2), fill="toself", opacity=0.9, fillcolor=C.CAT[i].replace("#", "#") + "22",
                             customdata=[[x] for x in raw + raw[:1]], hovertemplate="%{theta}: percentile %{r:.0f}<br>raw value %{customdata[0]:.2f}<extra>" + name + "</extra>")
        rows += [dict(team=name, metric=m[0], unit=m[3], raw=None if pd.isna(rw) else round(float(rw), 3), percentile=None if pd.isna(v) else round(v, 1)) for m, rw, v in zip(RADAR_METRICS, raw, vals)]
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickvals=[25, 50, 75, 100], gridcolor=C.GRID, linecolor=C.GRID, tickfont=dict(size=10)), angularaxis=dict(gridcolor=C.GRID)))
    C.style(fig, "Team profile: percentile among teams with 15+ matches", None, None, height=520, legend=True)
    miss = [r for r in rows if r["percentile"] is None]
    note = ("Knockout record needs 3+ knockout matches; teams without it show a gap (missing, not zero). " if miss else "") + "Axes are percentiles (50 = median team); defence and consistency are inverted so outward is always better. Hover for the raw value."
    return Chart(fig, pd.DataFrame(rows), int(t[t.team_name.isin(teams)].matches.sum()), SRC, note, name="team_radar")


def comparison_heatmap(tm: pd.DataFrame, teams: list[str] | None = None, top_n: int = 16, min_matches: int = 15) -> Chart:
    t = team_table(tm)
    d = t[t.team_name.isin(teams)] if teams else t[t.matches >= min_matches].sort_values("matches", ascending=False).head(top_n)
    if len(d) < 2:
        return unavailable("comparison_heatmap", "select at least two teams with played matches (or lower the minimum matches)")
    cols = [("Win %", "win_pct", 1), ("Points / match", "ppm", 1), ("Goals for / match", "gf_pm", 1), ("Goals against / match", "ga_pm", -1), ("Clean sheets %", "cs_pct", 1), ("Knockout win %", "ko_win_pct", 1)]
    ref = t[t.matches >= min_matches]
    z = pd.DataFrame({lab: sign * (d[c] - ref[c].mean()) / ref[c].std(ddof=0) for lab, c, sign in cols})
    z.index = d.team_name
    raw = d.set_index("team_name")[[c for _, c, _ in cols]]
    fig = go.Figure(go.Heatmap(z=z.values, x=z.columns, y=z.index, colorscale=C.DIVERGING[::-1] if False else [[0, "#e34948"], [0.5, "#f0efec"], [1, "#2a78d6"]], zmid=0, zmin=-2.5, zmax=2.5,
                               customdata=raw.values, colorbar=dict(title="better ↑<br>z-score"), xgap=2, ygap=2, hovertemplate="<b>%{y}</b> · %{x}<br>z = %{z:.2f} (blue = better than the typical team)<br>raw = %{customdata:.2f}<extra></extra>"))
    C.style(fig, "Team comparison heatmap (z-scores; blue = better than the reference teams)", None, None, legend=False, height=max(320, 28 * len(d) + 140))
    fig.update_yaxes(autorange="reversed")
    return Chart(fig, pd.concat([z.round(3).add_suffix(" (z)"), raw.round(3)], axis=1).reset_index(), int(d.matches.sum()), SRC,
                 f"z-scores relative to the {len(ref)} teams with {min_matches}+ matches; 'against' is inverted so blue is always better. Missing knockout record (<3 matches) is blank, not zero.", name="team_heatmap")


def edition_heatmap(tm: pd.DataFrame, teams: list[str] | None = None, top_n: int = 15) -> Chart:
    d = tm[tm.team_name.isin(teams)] if teams else tm[tm.team_name.isin(tm.groupby("team_name").size().sort_values(ascending=False).head(top_n).index)]
    if d.empty:
        return unavailable("team_edition_heatmap", "no team-matches in the current selection")
    p = d.groupby(["team_name", "season_id"]).agg(ppm=("points", "mean"), n=("match_key", "size")).reset_index()
    pv = p.pivot(index="team_name", columns="season_id", values="ppm")
    nv = p.pivot(index="team_name", columns="season_id", values="n")
    fig = go.Figure(go.Heatmap(z=pv.values, x=pv.columns, y=pv.index, colorscale=C.SEQ, zmin=0, zmax=3, customdata=nv.values, xgap=2, ygap=2, colorbar=dict(title="points<br>/ match"),
                               hovertemplate="<b>%{y}</b> · %{x}<br>%{z:.2f} points per match over %{customdata} matches<extra></extra>"))
    C.style(fig, "Points per match by edition (blank = did not play)", None, None, legend=False, height=max(320, 28 * len(pv) + 160))
    fig.update_xaxes(tickangle=60)
    fig.update_yaxes(autorange="reversed")
    return Chart(fig, p.round(3), len(d), SRC, "Blank cells = the team did not take part (missing, not zero). 0 = lost every match.", name="team_edition_heatmap")


def timeline(tm: pd.DataFrame, teams: list[str]) -> Chart:
    d = tm[tm.team_name.isin(teams[:5])]
    if d.empty:
        return unavailable("team_timeline", "select teams that have played matches in the current filters")
    g = d.groupby(["team_name", "season_id", "season_year", "comp"]).agg(ppm=("points", "mean"), gf=("goals_for", "mean"), ga=("goals_against", "mean"), n=("match_key", "size"), furthest=("stage_name", lambda s: s.iloc[-1])).reset_index()
    fig = go.Figure()
    for i, name in enumerate(teams[:5]):
        x = g[g.team_name == name].sort_values("season_year")
        fig.add_scatter(x=x.season_year, y=x.ppm, mode="lines+markers", name=name, line=dict(color=C.CAT[i], width=2), marker=dict(size=9, color=C.CAT[i], symbol=[C.COMP_SYMBOL[c] for c in x.comp], line=dict(color=C.SURFACE, width=2)),
                        customdata=np.c_[x.season_id, x.n, x.gf, x.ga, x.furthest], hovertemplate="<b>" + name + "</b> · %{customdata[0]}<br>%{y:.2f} points per match (%{customdata[1]} matches)<br>scored %{customdata[2]:.2f} · conceded %{customdata[3]:.2f}<br>last stage played: %{customdata[4]}<extra></extra>")
    C.style(fig, "Performance timeline (marker shape = competition)", "Edition year", "Points per match (0–3)")
    fig.update_yaxes(range=[0, 3.1])
    return Chart(fig, g.round(3), len(d), SRC, "Marker shapes: circle = World Cup, square = Euro, diamond = Copa América, triangle = Nations League. Few matches per edition (3–8) make single points noisy.", name="team_timeline")


def head_to_head(m: pd.DataFrame, a: str, b: str) -> tuple[Chart, Chart]:
    """m = played matches (stg_matches columns). Returns (summary chart, timeline chart)."""
    x = m[((m.home_team_name == a) & (m.away_team_name == b)) | ((m.home_team_name == b) & (m.away_team_name == a))].copy()
    if a == b or x.empty:
        why = "choose two different teams" if a == b else f"{a} and {b} have not met in the selected competitions/dates"
        return unavailable("h2h_summary", why), unavailable("h2h_timeline", why)
    isa = x.home_team_name == a
    x["ga"], x["gb"] = np.where(isa, x.home_score, x.away_score), np.where(isa, x.away_score, x.home_score)
    x["result"] = np.where(x.ga > x.gb, f"{a} win", np.where(x.ga == x.gb, "draw", f"{b} win"))
    cnt = x.groupby(["competition_id", "result"]).size().unstack(fill_value=0)
    fig = go.Figure()
    for col, color in ((f"{a} win", C.OUTCOME_COLOR["win"]), ("draw", C.OUTCOME_COLOR["draw"]), (f"{b} win", C.OUTCOME_COLOR["loss"])):
        if col in cnt:
            fig.add_bar(x=[C.COMP_LABEL[c] for c in cnt.index], y=cnt[col], name=col, marker_color=color, hovertemplate="%{x}: %{y} " + col + "<extra></extra>")
    fig.update_layout(barmode="stack")
    C.style(fig, f"{a} v {b}: meetings by competition", None, "Matches (count)", height=360)
    C.bar_gap(fig)
    fig.update_yaxes(dtick=1)
    x["gd"] = x.ga - x.gb
    x["shootout"] = np.where(x.shootout_winner_side.notna(), np.where((x.shootout_winner_side == "home") == isa, a, b), None)
    t = go.Figure()
    for res, col in ((f"{a} win", C.OUTCOME_COLOR["win"]), ("draw", C.OUTCOME_COLOR["draw"]), (f"{b} win", C.OUTCOME_COLOR["loss"])):
        s = x[x.result == res]
        if len(s):
            t.add_scatter(x=pd.to_datetime(s.match_date), y=s.gd, mode="markers", name=res, marker=dict(size=14, color=col, symbol=[C.COMP_SYMBOL[c] for c in s.competition_id], line=dict(color=C.SURFACE, width=2)),
                          customdata=np.c_[s.season_id, s.stage_name, s.ga, s.gb, s.shootout.fillna("–")], hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>" + f"{a} %{{customdata[2]}}–%{{customdata[3]}} {b}" + "<br>shoot-out winner: %{customdata[4]}<extra></extra>")
    t.add_hline(y=0, line=dict(color=C.AXIS, width=1))
    C.style(t, f"{a} v {b}: every meeting", "Date", f"Goal difference ({a} minus {b})", height=380)
    cols = ["match_date", "season_id", "stage_name", "home_team_name", "home_score", "away_score", "away_team_name", "shootout_winner_side"]
    note = "Result = recorded score (extra time included); shoot-outs shown in the hover. Meetings are different contexts (competition, stage, era, squads) – context, not a prediction. " + (f"Only {len(x)} meeting(s): treat as anecdote." if len(x) < 5 else "")
    return (Chart(fig, x[cols], len(x), SRC, note, name="h2h_summary"), Chart(t, x[cols], len(x), SRC, note, name="h2h_timeline"))


def rankings(tm: pd.DataFrame, min_matches: int = 15, top_n: int = 20) -> Chart:
    t = team_table(tm)
    d = t[t.matches >= min_matches].copy()
    if len(d) < 3:
        return unavailable("team_rankings", f"fewer than 3 teams with {min_matches}+ matches in the current selection")
    per = tm.groupby("team_name").points.agg(["std", "size"])
    d["se"] = d.team_name.map(per["std"] / np.sqrt(per["size"]))
    d = d.sort_values("ppm", ascending=False).head(top_n).sort_values("ppm")
    fig = go.Figure(go.Bar(y=d.team_name, x=d.ppm, orientation="h", marker_color=C.CAT[0], error_x=dict(type="data", array=1.96 * d.se, color=C.INK2, thickness=1.2, width=3),
                           customdata=np.c_[d.matches, d.win_pct, 1.96 * d.se], hovertemplate="<b>%{y}</b><br>%{x:.2f} points per match ± %{customdata[2]:.2f} (95% CI)<br>%{customdata[0]} matches · win rate %{customdata[1]:.0f}%<extra></extra>"))
    C.style(fig, f"Team ranking by points per match (teams with {min_matches}+ matches)", "Points per match (95% confidence interval)", None, legend=False, height=max(340, 26 * len(d) + 140))
    C.bar_gap(fig)
    fig.update_xaxes(range=[0, 3.1])
    return Chart(fig, d[["team_name", "matches", "ppm", "se", "win_pct"]].round(3), int(d.matches.sum()), SRC, "Whiskers = ±1.96 standard errors of the per-match points: neighbours whose whiskers overlap cannot be separated reliably.", name="team_rankings")


def consistency(tm: pd.DataFrame, min_editions: int = 4) -> Chart:
    e = tm.groupby(["team_name", "season_id"]).points.mean().reset_index()
    g = e.groupby("team_name").agg(editions=("season_id", "nunique"), mean_ppm=("points", "mean"), sd_ppm=("points", "std")).reset_index()
    g = g[g.editions >= min_editions].dropna()
    if len(g) < 4:
        return unavailable("team_consistency", f"fewer than 4 teams with {min_editions}+ editions in the current selection")
    fig = go.Figure(go.Scatter(x=g.mean_ppm, y=g.sd_ppm, mode="markers+text", text=g.team_name, textposition="top center", textfont=dict(size=10, color=C.INK2),
                               marker=dict(size=np.clip(g.editions * 1.6, 8, 28), color=C.CAT[0], opacity=0.85, line=dict(color=C.SURFACE, width=2)), customdata=g.editions,
                               hovertemplate="<b>%{text}</b><br>mean %{x:.2f} points/match over %{customdata} editions<br>edition-to-edition SD %{y:.2f}<extra></extra>"))
    C.style(fig, "Strength vs consistency across editions", "Mean points per match across editions", "Edition-to-edition SD of points per match (lower = steadier)", legend=False, height=520)
    return Chart(fig, g.round(3), int(g.editions.sum()), SRC, "Bubble size = number of editions. Small samples per edition (3–8 matches) inflate the SD: compare teams with similar numbers of editions.", name="team_consistency")
