"""Competition analytics: history, champions, edition comparison, tournament progression, group standings, knockout brackets, goal distributions.
Every function takes plain DataFrames (see analysis.data / staging.stg_matches columns) and returns a `Chart`. Upcoming fixtures are shown as 'Coming soon'."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as ss

from ..analysis import data as D
from . import common as C
from .common import Chart, unavailable

SRC = "staging.stg_matches / gold.mart_tournament_summary (warehouse)"
STAGE_LEVEL = {"Group stage": 0, "Play-off": 0, "Promotion/relegation play-off": 0, "Round of 32": 1, "Round of 16": 2, "Quarter-finals": 3, "Semi-finals": 4, "Third place": 4, "Final": 5}
LEVEL_NAME = {0: "Group / league stage", 1: "Round of 32", 2: "Round of 16", 3: "Quarter-finals", 4: "Semi-finals (incl. third place)", 5: "Final", 6: "Champion"}
KO_ROUNDS = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]


# ------------------------------------------------------------------ data loaders
def load_standings() -> pd.DataFrame:
    return D.q("""select s.season_id, s.competition_key, t.team_name, st.group_name, st.group_position, st.played, st.wins, st.draws, st.losses, st.goals_for, st.goals_against,
                         st.goal_difference, st.points, st.basis from wh.fact_tournament_standings st join wh.dim_season s using (season_key) join wh.dim_team t using (team_key)
                  order by 1, 4, 5""")


# ------------------------------------------------------------------ 1. historical goals and matches
def edition_history(tr: pd.DataFrame, measure: str = "total_goals") -> Chart:
    d = tr[tr.matches_played > 0].copy()
    if d.empty:
        return unavailable("edition_history", "no played editions in the current selection")
    labels = {"total_goals": "Goals scored", "matches_played": "Matches played", "goals_per_match": "Goals per match"}
    d = d.sort_values(["competition_id", "season_year"])
    d["competition"] = d.competition_id.map(C.COMP_LABEL)
    if measure == "goals_per_match":
        fig = go.Figure()
        for c in C.COMPS:
            g = d[d.competition_id == c]
            if g.empty:
                continue
            fig.add_scatter(x=g.season_year, y=g.goals_per_match, mode="lines+markers", name=C.COMP_LABEL[c], line=dict(color=C.COMP_COLOR[c], width=2),
                            marker=dict(size=9, symbol=C.COMP_SYMBOL[c], color=C.COMP_COLOR[c], line=dict(color=C.SURFACE, width=2)), customdata=np.c_[g.season_id, g.matches_played, g.total_goals],
                            hovertemplate="<b>%{customdata[0]}</b><br>%{y:.2f} goals per match<br>%{customdata[1]} matches, %{customdata[2]} goals<extra></extra>")
        C.style(fig, "Goals per match by edition", "Edition year", "Goals per match (regulation + extra time)")
    else:
        fig = go.Figure()
        for c in C.COMPS:
            g = d[d.competition_id == c]
            if g.empty:
                continue
            fig.add_bar(x=g.season_id, y=g[measure], name=C.COMP_LABEL[c], marker_color=C.COMP_COLOR[c], customdata=np.c_[g.matches_played, g.total_goals, g.goals_per_match],
                        hovertemplate=f"<b>%{{x}}</b><br>{labels[measure]}: %{{y}}<br>%{{customdata[0]}} matches · %{{customdata[1]}} goals · %{{customdata[2]:.2f}} per match<extra></extra>")
        C.style(fig, f"{labels[measure]} by edition", "Edition", labels[measure] + " (count)")
        C.bar_gap(fig)
        fig.update_xaxes(tickangle=60)

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(figsize=(9, 4.5))
        sns.lineplot(data=d, x="season_year", y="goals_per_match", hue="competition", style="competition", markers=True, dashes=False, palette={C.COMP_LABEL[k]: v for k, v in C.COMP_COLOR.items()}, ax=ax)
        ax.set_xlabel("Edition year"); ax.set_ylabel("Goals per match"); ax.set_title("Goals per match by edition"); return f
    cols = ["season_id", "competition_id", "teams", "matches_played", "total_goals", "goals_per_match", "draw_pct", "champion"]
    return Chart(fig, d[cols], int(d.matches_played.sum()), SRC, "Per-match rates are comparable across editions; raw counts are not (formats differ: 4–104 matches per edition).", static=static, name=f"edition_history_{measure}")


# ------------------------------------------------------------------ 2. champions and runners-up
def champions_timeline(tr: pd.DataFrame) -> Chart:
    d = tr[tr.champion.notna() & (tr.matches_played > 0)].copy()
    if d.empty:
        return unavailable("champions_timeline", "no completed edition with a decided final in the selection")
    d["y"] = d.competition_id.map({c: i for i, c in enumerate(C.COMPS[::-1])})
    fig = go.Figure()
    for c, g in d.groupby("competition_id"):
        fig.add_scatter(x=g.season_year, y=g.y, mode="markers+text", name=C.COMP_LABEL[c], text=g.champion, textposition="top center", textfont=dict(size=10, color=C.INK2),
                        marker=dict(size=13, symbol=C.COMP_SYMBOL[c], color=C.COMP_COLOR[c], line=dict(color=C.SURFACE, width=2)), customdata=np.c_[g.season_id, g.champion, g.runner_up],
                        hovertemplate="<b>%{customdata[0]}</b><br>Champion: %{customdata[1]}<br>Runner-up: %{customdata[2]}<extra></extra>")
    fig.update_yaxes(tickvals=list(range(4)), ticktext=[C.COMP_LABEL[c] for c in C.COMPS[::-1]], range=[-0.6, 3.7])
    C.style(fig, "Champions by edition (hover for the runner-up)", "Edition year", None, height=360)
    fig.update_yaxes(title=None)
    return Chart(fig, d[["season_id", "competition_id", "champion", "runner_up"]], len(d), SRC,
                 "Champion = winner of the final (shoot-out winner where level). Editions without a decided final (in progress / upcoming) are absent, not blank.", name="champions_timeline")


def title_counts(tr: pd.DataFrame) -> Chart:
    d = tr[tr.champion.notna()]
    if d.empty:
        return unavailable("title_counts", "no champions in the selection")
    cnt = d.groupby(["champion", "competition_id"]).size().rename("titles").reset_index()
    order = cnt.groupby("champion").titles.sum().sort_values().index
    fig = go.Figure()
    for c in C.COMPS:
        g = cnt[cnt.competition_id == c]
        if len(g):
            fig.add_bar(y=g.champion, x=g.titles, name=C.COMP_LABEL[c], orientation="h", marker_color=C.COMP_COLOR[c], hovertemplate="<b>%{y}</b><br>%{x} title(s) – " + C.COMP_LABEL[c] + "<extra></extra>")
    fig.update_layout(barmode="stack", yaxis=dict(categoryorder="array", categoryarray=list(order)))
    C.style(fig, "Titles in the collected editions", "Titles (count)", None, height=max(300, 24 * len(order) + 120))
    C.bar_gap(fig)
    fig.update_xaxes(dtick=1)
    return Chart(fig, cnt, int(cnt.titles.sum()), SRC, "Counts only the editions in the dataset (World Cup from 2002, Euro from 2000, Copa from 2001, Nations League from 2018-19).", name="title_counts")


# ------------------------------------------------------------------ 3. edition comparison
METRICS = {"goals_per_match": "Goals per match", "draw_pct": "Draw share (%)", "avg_attendance": "Average attendance", "shootout_rate": "Shoot-outs per 100 matches", "beyond90_rate": "Matches beyond 90 min (%)"}


def edition_comparison(tr: pd.DataFrame, metric: str = "goals_per_match") -> Chart:
    d = tr[tr.matches_played > 0].copy()
    d["shootout_rate"] = 100 * d.shootouts / d.matches_played
    d["beyond90_rate"] = 100 * d.matches_beyond_90 / d.matches_played
    d = d.dropna(subset=[metric])
    if d.empty:
        return unavailable("edition_comparison", f"no data for {METRICS[metric]}")
    d = d.sort_values(metric)
    fig = go.Figure()
    for c in C.COMPS:
        g = d[d.competition_id == c]
        if len(g):
            fig.add_bar(y=g.season_id, x=g[metric], orientation="h", name=C.COMP_LABEL[c], marker_color=C.COMP_COLOR[c], customdata=np.c_[g.matches_played, g.teams],
                        hovertemplate="<b>%{y}</b><br>" + METRICS[metric] + ": %{x:,.2f}<br>%{customdata[0]} matches · %{customdata[1]} teams<extra></extra>")
    fig.update_layout(yaxis=dict(categoryorder="array", categoryarray=list(d.season_id)))
    C.style(fig, f"Edition comparison: {METRICS[metric]}", METRICS[metric], None, height=max(360, 18 * len(d) + 120))
    C.bar_gap(fig)
    note = "Nations League extra time is not recorded, so 'beyond 90' is understated there. " if metric == "beyond90_rate" else ""
    return Chart(fig, d[["season_id", "competition_id", "teams", "matches_played", metric]], int(d.matches_played.sum()), SRC, note + "Bars start at zero; colour = competition.", name=f"edition_comparison_{metric}")


def edition_heatmap(tr: pd.DataFrame) -> Chart:
    d = tr[tr.matches_played >= 20].copy()
    if d.empty:
        return unavailable("edition_heatmap", "needs editions with at least 20 played matches")
    d["shootouts_per_100"] = 100 * d.shootouts / d.matches_played
    cols = ["goals_per_match", "draw_pct", "avg_attendance", "shootouts_per_100"]
    z = d.groupby("competition_id")[cols].transform(lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else s * 0)
    z.index = d.season_id
    z.columns = ["Goals / match", "Draw %", "Avg attendance", "Shoot-outs / 100"]
    raw = d.set_index("season_id")[cols]
    fig = go.Figure(go.Heatmap(z=z.T.values, x=z.index, y=z.columns, colorscale=C.DIVERGING, zmid=0, zmin=-2.5, zmax=2.5, customdata=raw.T.values, colorbar=dict(title="z-score<br>vs own<br>competition"),
                               hovertemplate="<b>%{x}</b> · %{y}<br>z = %{z:.2f}<br>raw = %{customdata:.2f}<extra></extra>", xgap=2, ygap=2))
    C.style(fig, "Is an edition above or below its own competition's average?", "Edition", None, height=360, legend=False)
    fig.update_xaxes(tickangle=60)
    return Chart(fig, z.reset_index().round(3), len(d), SRC, "z-scores are computed within each competition (blue = below its own average, red = above); they say nothing across competitions.", name="edition_heatmap")


# ------------------------------------------------------------------ 4. tournament progression
def furthest_stage(m_season: pd.DataFrame) -> pd.DataFrame:
    """Per team: furthest stage level reached in one edition (6 = champion). Uses played matches only; level 0 = group/league stage."""
    rows = []
    for r in m_season[m_season.is_played & m_season.home_team_key.notna() & m_season.away_team_key.notna()].itertuples():
        lv = STAGE_LEVEL.get(r.stage_name, 0)
        for side, name in (("home", r.home_team_name), ("away", r.away_team_name)):
            rows.append((name, lv))
        if r.stage_name == "Final":
            win = r.home_team_name if (r.home_score > r.away_score or (r.home_score == r.away_score and r.shootout_winner_side == "home")) else (r.away_team_name if (r.away_score > r.home_score or r.shootout_winner_side == "away") else None)
            if win:
                rows.append((win, 6))
    if not rows:
        return pd.DataFrame(columns=["team_name", "stage_level", "stage"])
    d = pd.DataFrame(rows, columns=["team_name", "stage_level"]).groupby("team_name")["stage_level"].max().reset_index()
    d["stage"] = d.stage_level.map(LEVEL_NAME)
    return d.sort_values(["stage_level", "team_name"], ascending=[False, True])


def progression_funnel(m_season: pd.DataFrame, season_id: str) -> Chart:
    f = furthest_stage(m_season)
    if f.empty or f.stage_level.max() == 0:
        return unavailable("progression_funnel", f"{season_id} has no knockout stage played yet (or no teams decided)")
    reach = [(LEVEL_NAME[lv], int((f.stage_level >= lv).sum())) for lv in sorted(LEVEL_NAME) if (f.stage_level >= lv).any()]
    names, counts = zip(*reach)
    ramp = ["#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"][-len(reach):] if len(reach) <= 6 else C.SEQ
    fig = go.Figure(go.Bar(y=list(names), x=list(counts), orientation="h", marker_color=ramp[:len(names)], text=list(counts), textposition="outside",
                           hovertemplate="%{y}: %{x} teams reached at least this stage<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    C.style(fig, f"{season_id}: teams reaching each stage", "Teams (count)", None, height=340, legend=False)
    C.bar_gap(fig)
    fig.update_xaxes(range=[0, max(counts) * 1.12])
    return Chart(fig, f, len(f), SRC, "Stage = furthest stage with a played match; third-place play-off counts as semi-final level. Ordered stages use one blue ramp (ordinal).", name="progression_funnel")


# ------------------------------------------------------------------ 5. group standings
def group_standings(st: pd.DataFrame, season_id: str) -> Chart:
    d = st[st.season_id == season_id].copy()
    if d.empty:
        return unavailable("group_standings", f"no group stage for {season_id} (no group-stage matches played yet, or the competition has no groups)")
    d["group_name"] = d.group_name.astype(str)
    groups = sorted(d.group_name.unique())
    cols = min(4, len(groups))
    rows_n = int(np.ceil(len(groups) / cols))
    fig = make_subplots(rows=rows_n, cols=cols, subplot_titles=[f"Group {g}" for g in groups], shared_yaxes=False, vertical_spacing=0.14 if rows_n > 1 else 0.1, horizontal_spacing=0.17)
    for i, g in enumerate(groups):
        x = d[d.group_name == g].sort_values("group_position", ascending=False)
        fig.add_bar(y=x.team_name, x=x.points, orientation="h", marker_color=C.CAT[0], showlegend=False, text=[f"{int(p)} pts · GD {int(gd):+d}" for p, gd in zip(x.points, x.goal_difference)], textposition="outside",
                    customdata=np.c_[x.played, x.wins, x.draws, x.losses, x.goals_for, x.goals_against], row=i // cols + 1, col=i % cols + 1,
                    hovertemplate="<b>%{y}</b><br>P%{customdata[0]} W%{customdata[1]} D%{customdata[2]} L%{customdata[3]}<br>GF %{customdata[4]} GA %{customdata[5]}<br>%{x} points<extra></extra>")
        fig.update_xaxes(range=[0, max(d.points.max() * 2.3, 6)], row=i // cols + 1, col=i % cols + 1)
    C.style(fig, f"{season_id}: group tables (points)", None, None, legend=False, height=max(300, 230 * rows_n))
    C.bar_gap(fig)
    fig.update_xaxes(showgrid=False, showticklabels=False)
    fig.update_yaxes(gridcolor=C.SURFACE, automargin=True, tickfont=dict(size=11))
    basis = d.basis.iloc[0]
    return Chart(fig, d.drop(columns=["competition_key"]), len(d), SRC, f"DERIVED from played group-stage matches ({basis}); not official tables - head-to-head and fair-play tie-breaks are not applied.", name="group_standings")


# ------------------------------------------------------------------ 6. knockout bracket
def _winner(r) -> str | None:
    if not r.is_played or pd.isna(r.home_score):
        return None
    if r.home_score != r.away_score:
        return r.home_team_name if r.home_score > r.away_score else r.away_team_name
    return {"home": r.home_team_name, "away": r.away_team_name}.get(r.shootout_winner_side)


def bracket_layout(ko: pd.DataFrame):
    """Order the matches of every round so that the two feeder matches of a match sit next to each other (found from who won them).
    Matches that cannot be linked (unknown winners / placeholders) are appended in date order. Returns {round: [rows]} and {match_key: y}."""
    rounds = {r: ko[ko.stage_name == r].sort_values(["match_date", "match_key"]).to_dict("records") for r in KO_ROUNDS if (ko.stage_name == r).any()}
    names = [r for r in KO_ROUNDS if r in rounds]
    ordered = {names[-1]: rounds[names[-1]]}
    for r_i in range(len(names) - 2, -1, -1):
        cur, nxt = rounds[names[r_i]], ordered[names[r_i + 1]]
        placed, out = set(), []
        for parent in nxt:
            for team in (parent["home_team_name"], parent["away_team_name"]):
                for cand in cur:
                    if cand["match_key"] not in placed and _winner(pd.Series(cand)) == team and team is not None:
                        out.append(cand)
                        placed.add(cand["match_key"])
                        break
        out += [c for c in cur if c["match_key"] not in placed]
        ordered[names[r_i]] = out
    pos = {}
    first = names[0]
    for i, m in enumerate(ordered[first]):
        pos[m["match_key"]] = float(i)
    for r_i in range(1, len(names)):
        prev = {m["match_key"]: m for m in ordered[names[r_i - 1]]}
        for j, m in enumerate(ordered[names[r_i]]):
            kids = [pos[k] for k, c in prev.items() if _winner(pd.Series(c)) in (m["home_team_name"], m["away_team_name"]) and _winner(pd.Series(c)) is not None]
            pos[m["match_key"]] = float(np.mean(kids)) if len(kids) == 2 else (j + 0.5) * (len(ordered[names[r_i - 1]]) / max(len(ordered[names[r_i]]), 1)) - 0.5
    return ordered, names, pos


def knockout_bracket(m_season: pd.DataFrame, season_id: str) -> Chart:
    ko = m_season[m_season.is_knockout.astype(bool) & (m_season.stage_name != "Third place") & m_season.stage_name.isin(KO_ROUNDS)]
    if ko.empty:
        return unavailable("knockout_bracket", f"{season_id} has no knockout bracket in the data (league format or not yet scheduled)")
    ordered, names, pos = bracket_layout(ko)
    fig = go.Figure()
    shapes, anns, hx, hy, ht = [], [], [], [], []
    w, h = 0.86, 0.34
    for xi, r in enumerate(names):
        anns.append(dict(x=xi + w / 2, y=-1.05, text=f"<b>{r}</b>", showarrow=False, font=dict(size=12, color=C.INK2)))
        for m in ordered[r]:
            y = pos[m["match_key"]]
            played = bool(m["is_played"])
            win = _winner(pd.Series(m))
            shapes.append(dict(type="rect", x0=xi, x1=xi + w, y0=y - h, y1=y + h, line=dict(color=C.AXIS, width=1), fillcolor="#ffffff"))
            for k, side in enumerate(("home", "away")):
                nm = m[f"{side}_team_name"]
                sc = m[f"{side}_score"]
                pen = m.get(f"{side}_pen")
                label = f"{nm}"
                score = "" if not played or pd.isna(sc) else f"{int(sc)}" + (f" ({int(pen)})" if pd.notna(pen) else "")
                bold = played and win == nm
                anns.append(dict(x=xi + 0.04, y=y - h / 2 + k * h, text=(f"<b>{label[:20]}</b>" if bold else label[:20]) if played else f"<span style='color:{C.MUTED}'>{label[:20]}</span>",
                                 showarrow=False, xanchor="left", font=dict(size=11, color=C.INK if played else C.MUTED)))
                anns.append(dict(x=xi + w - 0.04, y=y - h / 2 + k * h, text=(f"<b>{score}</b>" if bold else score), showarrow=False, xanchor="right", font=dict(size=11, color=C.INK)))
            if not played:
                anns.append(dict(x=xi + w / 2, y=y + h + 0.16, text="Coming soon", showarrow=False, font=dict(size=9, color=C.MUTED)))
            so = (" · decided on penalties" if m.get("shootout_winner_side") in ("home", "away") else "") if played else ""
            hx.append(xi + w / 2); hy.append(y)
            ht.append(f"<b>{m['home_team_name']} v {m['away_team_name']}</b><br>{m['stage_name']} · {m['match_date']}" + (f"<br>{int(m['home_score'])}–{int(m['away_score'])}{so}" if played else "<br>Coming soon (no result yet)")
                      + (f"<br>{m['venue_name']}" if isinstance(m.get("venue_name"), str) else ""))
            if xi < len(names) - 1:
                nxt = [mm for mm in ordered[names[xi + 1]] if m["match_key"] is not None and win is not None and win in (mm["home_team_name"], mm["away_team_name"])]
                if nxt:
                    y2 = pos[nxt[0]["match_key"]]
                    fig.add_scatter(x=[xi + w, xi + w + (1 - w) / 2, xi + w + (1 - w) / 2, xi + 1], y=[y, y, y2, y2], mode="lines", line=dict(color=C.AXIS, width=1), hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=hx, y=hy, mode="markers", marker=dict(size=26, opacity=0), hovertext=ht, hoverinfo="text", showlegend=False)
    ymax = max(pos.values()) + 1
    fig.update_layout(shapes=shapes, annotations=anns)
    C.style(fig, f"{season_id}: knockout bracket", None, None, legend=False, height=int(max(420, 62 * ymax + 140)))
    fig.update_xaxes(visible=False, range=[-0.05, len(names) + 0.05])
    fig.update_yaxes(visible=False, range=[ymax, -1.4])
    data = ko[["season_id", "stage_name", "match_date", "home_team_name", "home_score", "away_score", "away_team_name", "shootout_winner_side", "status_label"]]
    return Chart(fig, data, len(ko), SRC, "Bold = winner (penalty shoot-out score in brackets where known). Lines link a match to the next round only when the winner is known; third-place play-off is not part of the tree. Undecided/future matches show 'Coming soon'.", name="knockout_bracket")


# ------------------------------------------------------------------ 7. goal-scoring distributions
def goal_distribution(m: pd.DataFrame, regulation: bool = True) -> Chart:
    col = "goals90" if regulation else "goals_total"
    d = m[m[col].notna()]
    if len(d) < 30:
        return unavailable("goal_distribution", "fewer than 30 matches with a known score in the selection")
    cats = list(range(7))
    rows = []
    fig = go.Figure()
    for c in C.COMPS:
        g = d[d.competition_id == c]
        if len(g) < 10:
            continue
        k = g[col].clip(upper=6).astype(int).value_counts().reindex(cats, fill_value=0)
        share = 100 * k / k.sum()
        lam = g[col].mean()
        fig.add_bar(x=[str(i) if i < 6 else "6+" for i in cats], y=share, name=f"{C.COMP_LABEL[c]} (n={len(g)})", marker_color=C.COMP_COLOR[c], customdata=np.c_[k.values, ss.poisson.pmf(cats, lam) * 100],
                    hovertemplate="%{x} goals: %{y:.1f}% of matches (%{customdata[0]} matches)<br>Poisson with the same mean: %{customdata[1]:.1f}%<extra></extra>")
        for i in cats:
            rows.append(dict(competition_id=c, goals=str(i) if i < 6 else "6+", matches=int(k[i]), share_pct=round(share[i], 2), poisson_expected_pct=round(ss.poisson.pmf(i, lam) * 100, 2)))
    if not rows:
        return unavailable("goal_distribution", "no competition has 10+ matches with a known score in the selection")
    C.style(fig, "Goals per match: share of matches", "Goals in the match" + (" (regulation time)" if regulation else " (incl. extra time)"), "Share of matches (%)")
    fig.update_layout(barmode="group")
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=[str(i) if i < 6 else "6+" for i in cats])
    C.bar_gap(fig)
    note = "Matches that went to extra time with an unknown 90-minute score are excluded from the regulation view. " if regulation else ""

    def static():
        import matplotlib.pyplot as plt
        import seaborn as sns
        f, ax = plt.subplots(figsize=(8, 4.2))
        sns.barplot(data=pd.DataFrame(rows), x="goals", y="share_pct", hue="competition_id", palette=C.COMP_COLOR, ax=ax)
        ax.set_xlabel("Goals in the match"); ax.set_ylabel("Share of matches (%)"); ax.set_title("Goals per match"); return f
    return Chart(fig, pd.DataFrame(rows), len(d), SRC, note + "Hover shows the Poisson expectation with the same mean (a reference, not a fit claim).", static=static, name="goal_distribution")


def goal_minutes(g: pd.DataFrame, bin_width: int = 5) -> Chart:
    d = g[g.minute.notna() & (g.period != 5) & ~g.is_own_goal.fillna(False).astype(bool)] if len(g) else g
    if len(d) < 50:
        return unavailable("goal_minutes", "fewer than 50 goal events with a known minute in the selection")
    d = d.assign(bin=(np.minimum(d.minute, 119) // bin_width * bin_width).astype(int))
    fig = go.Figure()
    rows = []
    for c in C.COMPS:
        x = d[d.competition_id == c]
        if len(x) < 30:
            continue
        k = x.groupby("bin").size().reindex(range(0, 120, bin_width), fill_value=0)
        share = 100 * k / k.sum()
        rows += [dict(competition_id=c, minute_from=int(b), goals=int(k[b]), share_pct=round(share[b], 2)) for b in k.index]
        fig.add_scatter(x=[f"{b}-{b + bin_width - 1}" for b in k.index], y=share, mode="lines+markers", name=f"{C.COMP_LABEL[c]} (n={len(x)})", line=dict(color=C.COMP_COLOR[c], width=2),
                        marker=dict(size=7, symbol=C.COMP_SYMBOL[c], color=C.COMP_COLOR[c], line=dict(color=C.SURFACE, width=1.5)), hovertemplate="minutes %{x}: %{y:.1f}% of goals<extra>" + C.COMP_LABEL[c] + "</extra>")
    C.style(fig, f"When goals are scored ({bin_width}-minute bands)", "Match minute", "Share of the competition's goals (%)")
    fig.update_xaxes(tickangle=60)
    return Chart(fig, pd.DataFrame(rows), len(d), "gold.mart_goal_analysis (goal events with a minute)",
                 "Own goals and shoot-out kicks excluded. Stoppage-time goals sit in the 40–44 and 85–89 bands (minute 45/90 entries); 90+ bands are extra time and are only played in some matches, so they are not comparable per minute.", name="goal_minutes")
