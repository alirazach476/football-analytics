"""Player analytics charts. Covers ONLY the collected competitions (not careers). Goals = goals linked to a player id (Nations League scorers are not linked);
assists exist only in editions with event-level data (`reliable_seasons`); per-90 rates count goals only in matches where the player's minutes are known."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import common as C
from .common import Chart, unavailable


def pos_group(*args, **kwargs):
    """Imported on first use: ml.clustering pulls in scikit-learn and mlflow, which the API should not load at start-up."""
    from ..ml.clustering import pos_group as _pos_group
    return _pos_group(*args, **kwargs)

SRC = "gold.mart_player_performance / wh.fact_player_match_stats (warehouse)"
POS_COLOR = {"Forward": C.CAT[0], "Midfielder": C.CAT[1], "Defender": C.CAT[2], "Goalkeeper": C.CAT[3], "Other": C.CAT[4]}
RADAR = [("Goals", "goals_p90"), ("xG", "xg_p90"), ("Shots", "shots_p90"), ("Assists", "assists_p90"), ("xA", "xa_p90"), ("Key passes", "key_passes_p90"), ("Passes", "passes_p90"),
         ("Pass accuracy", "pass_acc"), ("Tackles", "tackles_p90"), ("Interceptions", "interceptions_p90")]


def with_position(ps: pd.DataFrame) -> pd.DataFrame:
    d = ps.copy()
    d["position"] = d.primary_position.map(pos_group)
    return d


def top_players(ps: pd.DataFrame, measure: str = "goals", n: int = 20, reliable_seasons: set[str] | None = None) -> Chart:
    if ps.empty:
        return unavailable("top_players", "no player-season rows in the current selection")
    d = ps.copy()
    if measure == "assists":
        if not reliable_seasons:
            return unavailable("top_players", "assists are not recorded for any edition in the selection")
        d = d[d.season_id.isin(reliable_seasons)]
        if d.empty:
            return unavailable("top_players", "none of the selected editions records assists (only StatsBomb-covered editions do: WC 2018/22, Euro 2020/24, Copa 2024)")
    g = d.groupby(["player_key", "full_name"]).agg(value=(measure, "sum"), appearances=("appearances", "sum"), editions=("season_id", "nunique")).reset_index()
    g = g[g.value > 0].sort_values("value", ascending=False).head(n).sort_values("value")
    if g.empty:
        return unavailable("top_players", f"no player has a recorded {measure} in the selection")
    fig = go.Figure(go.Bar(y=g.full_name, x=g.value, orientation="h", marker_color=C.CAT[0], text=g.value.astype(int), textposition="outside", customdata=np.c_[g.appearances, g.editions],
                           hovertemplate="<b>%{y}</b><br>%{x} " + measure + "<br>%{customdata[0]} appearances · %{customdata[1]} editions<extra></extra>"))
    C.style(fig, f"Top {measure} in the selected editions", f"{measure.capitalize()} (count)", None, legend=False, height=max(340, 24 * len(g) + 140))
    C.bar_gap(fig)
    fig.update_xaxes(range=[0, g.value.max() * 1.12])
    note = ("Assists are a PARTIAL measure: counted only in editions with event-level data" if measure == "assists" else "Goals linked to a player id; Nations League scorers are names only (not linked), so they are absent here. Not career totals.")
    return Chart(fig, g.sort_values("value", ascending=False), int(g.value.sum()), SRC, note, name=f"top_{measure}")


def per90(ps: pd.DataFrame, measure: str = "goals", min_minutes: int = 270, reliable_seasons: set[str] | None = None) -> Chart:
    col_p90, col_n = ("goals_in_minute_matches", "goals") if measure == "goals" else ("assists_in_minute_matches", "assists")
    d = ps.copy()
    if measure == "assists":
        d = d[d.season_id.isin(reliable_seasons or set())]
    d = d[d.minutes_played.notna()]
    g = d.groupby(["player_key", "full_name"]).agg(ev=(col_p90, "sum"), minutes=("minutes_played", "sum")).reset_index()
    g = g[g.minutes >= min_minutes].copy()
    g["per90"] = 90 * g.ev / g.minutes
    if len(g) < 5:
        return unavailable("per90", f"fewer than 5 players with {min_minutes}+ known minutes{' in editions that record assists' if measure == 'assists' else ''} in the selection")
    lab = g.sort_values("per90", ascending=False).head(10)
    fig = go.Figure(go.Scatter(x=g.minutes, y=g.per90, mode="markers", marker=dict(size=9, color=C.CAT[0], opacity=0.75, line=dict(color=C.SURFACE, width=1.5)), customdata=np.c_[g.full_name, g.ev],
                               hovertemplate="<b>%{customdata[0]}</b><br>%{y:.2f} per 90 (%{customdata[1]} in %{x:,.0f} min)<extra></extra>", showlegend=False))
    fig.add_scatter(x=lab.minutes, y=lab.per90, mode="text", text=lab.full_name, textposition="top center", textfont=dict(size=10, color=C.INK2), showlegend=False, hoverinfo="skip")
    C.style(fig, f"{measure.capitalize()} per 90 minutes vs minutes played", "Minutes played (known minutes only, log scale)", f"{measure.capitalize()} per 90 minutes", legend=False, height=500)
    fig.update_xaxes(type="log")
    note = f"Players with {min_minutes}+ known minutes. Rates from few minutes are volatile (the fan on the left): read them together with the x-axis. Goals/assists are counted only in matches where the player's minutes are known."
    return Chart(fig, g.sort_values("per90", ascending=False).round(3), len(g), SRC, note + (" Assists: only editions with event-level data." if measure == "assists" else ""), name=f"per90_{measure}")


def radar(stats: pd.DataFrame, players: list[str]) -> Chart:
    """stats = ml.clustering.player_stat_table() (StatsBomb event-level per-90 stats, >=270 min). Percentiles are WITHIN the player's position group."""
    d = stats[stats.position.isin(["Defender", "Midfielder", "Forward"])].dropna(subset=[c for _, c in RADAR])
    sel = d[d.full_name.isin(players)].head(4)
    if sel.empty:
        return unavailable("player_radar", "the selected players have no event-level data with 270+ minutes (StatsBomb-covered matches only: WC 2018/22, Euro 2020/24, Copa 2024)")
    fig = go.Figure()
    rows = []
    for i, r in enumerate(sel.itertuples()):
        ref = d[d.position == r.position]
        vals = [100 * float((ref[c] < getattr(r, c)).mean() + 0.5 * (ref[c] == getattr(r, c)).mean()) for _, c in RADAR]
        labs = [l for l, _ in RADAR]
        fig.add_scatterpolar(r=vals + vals[:1], theta=labs + labs[:1], name=f"{r.full_name} ({r.position}, {r.mins:,.0f} min)", line=dict(color=C.CAT[i], width=2), fill="toself", fillcolor=C.CAT[i] + "22",
                             customdata=[[getattr(r, c)] for _, c in RADAR] + [[getattr(r, RADAR[0][1])]], hovertemplate="%{theta}: percentile %{r:.0f}<br>raw %{customdata[0]:.2f} per 90<extra>" + r.full_name + "</extra>")
        rows += [dict(player=r.full_name, position=r.position, metric=l, raw_per90=round(float(getattr(r, c)), 3), percentile_within_position=round(v, 1)) for (l, c), v in zip(RADAR, vals)]
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickvals=[25, 50, 75, 100], gridcolor=C.GRID, tickfont=dict(size=10)), angularaxis=dict(gridcolor=C.GRID)))
    C.style(fig, "Player profile: percentile within position (per 90 minutes)", None, None, legend=True, height=540)
    return Chart(fig, pd.DataFrame(rows), len(sel), "wh.fact_player_match_stats (StatsBomb event data)", f"Percentiles among {len(d)} outfield players with 270+ minutes, compared only with the SAME position group. Event-level data exists for {d.full_name.nunique()} players (≈313 matches): other players cannot be shown.", name="player_radar")


def trends(ps: pd.DataFrame, players: list[str], measure: str = "goals") -> Chart:
    d = ps[ps.full_name.isin(players[:5])]
    if d.empty:
        return unavailable("player_trends", "select players that appear in the current selection")
    fig = go.Figure()
    for i, name in enumerate(players[:5]):
        x = d[d.full_name == name].groupby(["season_id", "season_year"]).agg(v=(measure, "sum"), apps=("appearances", "sum"), mins=("minutes_played", "sum")).reset_index().sort_values(["season_year", "season_id"])
        if x.empty:
            continue
        fig.add_scatter(x=x.season_id, y=x.v, mode="lines+markers", name=name, line=dict(color=C.CAT[i], width=2), marker=dict(size=9, color=C.CAT[i], line=dict(color=C.SURFACE, width=2)), customdata=np.c_[x.apps, x.mins.fillna(-1)],
                        hovertemplate="<b>" + name + "</b> · %{x}<br>%{y} " + measure + " in %{customdata[0]} appearances<extra></extra>")
    C.style(fig, f"{measure.capitalize()} per tournament", "Tournament", f"{measure.capitalize()} in the tournament (count)")
    fig.update_xaxes(tickangle=60, type="category")
    fig.update_yaxes(rangemode="tozero", dtick=1)
    return Chart(fig, d[["full_name", "season_id", "team_name", "appearances", "minutes_played", "goals", "assists"]], len(d), SRC,
                 "A gap = the player did not take part in that edition (missing); a point at 0 = played and did not score. Assists only exist for editions with event-level data.", name="player_trends")


def age_vs_performance(ps: pd.DataFrame, min_minutes: int = 270) -> Chart:
    d = ps[(ps.age.between(16, 42)) & (ps.minutes_played >= min_minutes)].copy()
    d["rate"] = 90 * d.goals_in_minute_matches / d.minutes_played
    if len(d) < 40:
        return unavailable("age_vs_performance", f"fewer than 40 player-seasons with a known age and {min_minutes}+ known minutes")
    d["band"] = pd.cut(d.age, [16, 21, 24, 27, 30, 33, 42], labels=["≤21", "22–24", "25–27", "28–30", "31–33", "34+"])
    fig = go.Figure()
    order = ["≤21", "22–24", "25–27", "28–30", "31–33", "34+"]
    for b in order:
        s = d[d.band == b]
        if len(s):
            fig.add_box(y=s.rate, x=[f"{b}<br>n={len(s)}"] * len(s), name=b, marker_color=C.CAT[0], line=dict(color=C.CAT[0], width=1.5), fillcolor="#cde2fb", boxpoints="outliers", showlegend=False,
                        hovertemplate="age band " + b + "<br>%{y:.2f} goals per 90<extra></extra>")
    C.style(fig, "Goals per 90 by age band", "Age at the start of the tournament (n = player-seasons)", "Goals per 90 minutes", legend=False, height=440)
    sub = d[["full_name", "season_id", "age", "minutes_played", "goals_in_minute_matches", "rate", "primary_position"]].rename(columns={"rate": "goals_per_90"})
    return Chart(fig, sub.round(3), len(d), SRC, f"Age known for player-seasons with a date of birth ({len(d)} shown, {min_minutes}+ known minutes). Mixes all positions: defenders (few goals) are not comparable with forwards - see the position chart. An association, not an ageing curve.", name="age_vs_performance")


def position_comparison(ps: pd.DataFrame, min_minutes: int = 270) -> Chart:
    d = with_position(ps)
    known = d.position.notna().mean()
    d = d[d.position.isin(["Forward", "Midfielder", "Defender", "Goalkeeper"]) & (d.minutes_played >= min_minutes)].copy()
    d["rate"] = 90 * d.goals_in_minute_matches / d.minutes_played
    if len(d) < 30:
        return unavailable("position_comparison", f"fewer than 30 player-seasons with a known position and {min_minutes}+ known minutes")
    fig = go.Figure()
    for pos in ["Forward", "Midfielder", "Defender", "Goalkeeper"]:
        s = d[d.position == pos]
        if len(s) >= 5:
            fig.add_violin(y=s.rate, x=[f"{pos}<br>n={len(s)}"] * len(s), name=pos, line_color=POS_COLOR[pos], fillcolor=POS_COLOR[pos] + "55", meanline_visible=True, box_visible=True, points=False, showlegend=False, spanmode="hard",
                           hovertemplate=pos + "<br>%{y:.2f} goals per 90<extra></extra>")
    C.style(fig, "Goals per 90 by position", "Position group (n = player-seasons)", "Goals per 90 minutes", legend=False, height=440)
    return Chart(fig, d[["full_name", "position", "season_id", "minutes_played", "rate"]].rename(columns={"rate": "goals_per_90"}).round(3), len(d), SRC,
                 f"Position is known for {100 * known:.0f}% of player-seasons (event-data and squad sources); the rest are omitted, not guessed. Roles differ fundamentally: compare within a position, not across.", name="position_comparison")


def contribution(pci: pd.DataFrame, min_minutes: int = 900, top: int = 15) -> Chart:
    d = pci[pci.minutes >= min_minutes]
    if len(d) < 10:
        return unavailable("player_contribution", f"fewer than 10 players with {min_minutes}+ known minutes")
    fig = go.Figure()
    for pos in ["Forward", "Midfielder", "Defender"]:
        s = d[d.position == pos]
        if len(s):
            fig.add_scatter(x=s.minutes, y=s.rate_shrunk_p90, mode="markers", name=f"{pos} (n={len(s)})", marker=dict(size=np.clip(s.goals * 1.6 + 6, 7, 30), color=POS_COLOR[pos], opacity=0.8, line=dict(color=C.SURFACE, width=1.5)),
                            customdata=np.c_[s.full_name, s.goals, s.pci_z_within_position], hovertemplate="<b>%{customdata[0]}</b><br>%{y:.2f} contributions per 90 (shrunk)<br>%{customdata[1]} goals · z within position %{customdata[2]:.1f}<extra>" + pos + "</extra>")
    lab = d.sort_values("pci_z_within_position", ascending=False).head(top // 2)
    fig.add_scatter(x=lab.minutes, y=lab.rate_shrunk_p90, mode="text", text=lab.full_name, textposition="top center", textfont=dict(size=9, color=C.INK2), showlegend=False, hoverinfo="skip")
    C.style(fig, "Player contribution index: shrunk contributions per 90 vs minutes", "Known minutes played (log scale)", "Goals + 0.5 × assists per 90 (shrunk toward the position mean)", height=520)
    fig.update_xaxes(type="log")
    return Chart(fig, d[["full_name", "position", "minutes", "goals", "rate_raw_p90", "rate_shrunk_p90", "pci_z_within_position", "sample_size_flag"]].round(3), len(d), "reports/advanced (player contribution index)",
                 f"Players with {min_minutes}+ known minutes; bubble size = goals. Assists weigh 0.5 and count only in editions with event-level data. Shrinkage pulls small samples toward the position average. Positions have different scoring levels: compare within a colour.", name="player_contribution")
