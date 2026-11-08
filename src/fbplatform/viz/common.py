"""Shared building blocks of the visualisation system.

Design rules applied (validated palette, see docs/VISUALIZATION_GUIDE.md):
  * colour follows the ENTITY (a competition keeps its hue everywhere), categorical hues in fixed order, magnitude = one-hue sequential blue,
    polarity = blue<->red around a neutral grey; no dual axes; no value-ramp on nominal categories; solid hairline grid; thin marks with a surface gap.
  * every chart is a `Chart`: figure + the exact data behind it (table view / CSV) + sample size + source + limitations.
  * a chart is rendered ONLY when its required fields exist; otherwise `unavailable()` explains why. Missing is never drawn as zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go

SURFACE = "#fcfcfb"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]       # validated categorical order (light)
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]                   # one-hue sequential blue
DIVERGING = [[0.0, "#2a78d6"], [0.5, "#f0efec"], [1.0, "#e34948"]]                                        # blue <-> neutral <-> red
COMP_COLOR = {"WC": CAT[0], "EURO": CAT[1], "COPA": CAT[2], "UNL": CAT[3]}
COMP_SYMBOL = {"WC": "circle", "EURO": "square", "COPA": "diamond", "UNL": "triangle-up"}       # secondary encoding (4 hues exceed the all-pairs cap)
COMP_LABEL = {"WC": "FIFA World Cup", "EURO": "UEFA Euro", "COPA": "Copa América", "UNL": "UEFA Nations League"}
OUTCOME_COLOR = {"win": CAT[0], "draw": "#b4b2a9", "loss": CAT[1]}          # categories (not status): blue / neutral / orange
COMPS = ["WC", "EURO", "COPA", "UNL"]
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


@dataclass
class Chart:
    fig: go.Figure | None
    data: pd.DataFrame
    n: int = 0
    source: str = "PostgreSQL warehouse (collected datasets)"
    note: str = ""                       # limitations / reading guide shown under the chart
    available: bool = True
    reason: str = ""                     # why a chart is not rendered
    static: Callable | None = None       # optional Matplotlib/Seaborn renderer -> matplotlib Figure (PNG export)
    name: str = "chart"


def unavailable(name: str, reason: str, source: str = "") -> Chart:
    return Chart(fig=None, data=pd.DataFrame(), n=0, source=source, note="", available=False, reason=reason, name=name)


def style(fig: go.Figure, title: str | None = None, x: str | None = None, y: str | None = None, legend: bool | None = None, height: int = 420) -> go.Figure:
    """Apply the house style: recessive solid hairlines, system sans, horizontal legend only for >= 2 series, axis titles WITH units."""
    n_series = len([t for t in fig.data if t.showlegend is not False and t.name])
    fig.update_layout(template=None, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font=dict(family=FONT, size=13, color=INK2), height=height,
                      title=dict(text=title, x=0, xanchor="left", font=dict(size=15, color=INK)) if title else None,
                      margin=dict(l=64, r=24, t=(92 if (n_series >= 2 or legend) else 56) if title else (60 if (n_series >= 2 or legend) else 24), b=64), hovermode="closest", hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONT, color=INK)),
                      showlegend=(n_series >= 2) if legend is None else legend, legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(color=INK2), traceorder="normal"))
    if x is not None:
        fig.update_xaxes(title=x)                      # only overwrite axis titles that were asked for (subplot titles set earlier survive)
    if y is not None:
        fig.update_yaxes(title=y)
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickcolor=AXIS, zeroline=False, title_font=dict(color=INK2), automargin=True, title_standoff=10)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, linecolor=AXIS, zeroline=False, title_font=dict(color=INK2), automargin=True)
    return fig


def bar_gap(fig: go.Figure) -> go.Figure:
    """2px surface gap between adjacent / stacked fills (instead of drawing borders)."""
    fig.update_traces(marker_line_color=SURFACE, marker_line_width=2, selector=dict(type="bar"))
    fig.update_layout(bargap=0.35)
    return fig


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval for a proportion (honest intervals for small samples)."""
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def pct(a, b) -> float:
    return float(100 * a / b) if b else np.nan


UNITS = {"champions_timeline": "editions", "title_counts": "titles", "progression_funnel": "teams", "group_standings": "team rows", "top_goals": "goals", "top_assists": "assists", "per90_": "players",
         "player_radar": "players", "player_trends": "player-tournaments", "age_vs_performance": "player-seasons", "position_comparison": "player-seasons", "player_contribution": "players",
         "team_consistency": "team-editions", "h2h_": "meetings", "shot_map": "shots", "passing_network": "passes", "event_timeline": "events", "goal_timeline": "goals", "score_progression": "goals",
         "correlation_matrix": "team-editions", "scatter_regression": "team-editions", "ci_forest": "estimates", "hypothesis_summary": "tests", "importance_": "features", "team_clusters": "teams",
         "team_dendrogram": "teams", "silhouette_by_k": "values of k", "player_clusters": "players", "layer_counts": "records in all tables", "duplicates": "checks", "completeness_bars": "rows in the largest table",
         "pipeline_durations": "runs", "pipeline_failures": "logged attempts", "freshness": "items", "source_coverage": "played matches", "dq_trends": "run × layer groups", "shootout": "shoot-outs",
         "goals_actual_vs_predicted": "team-matches", "residual_plots": "team-matches", "goal_models": "team-matches", "roc_": "test matches", "pr_": "test matches", "confusion_": "test matches",
         "calibration_": "test matches", "model_comparison_": "test matches", "shap_": "test matches", "missing_heatmap": "rows", "radar": "matches (selected teams)", "team_radar": "matches (selected teams)",
         "an_edition_metric": "editions", "an_goal_minutes": "minute bands", "an_team_edition": "editions", "an_team_trend": "editions", "an_player_edition": "tournaments", "an_top_players": "players", "an_player_compare": "player-tournaments", "ov_coverage": "played matches"}


def unit_for(name: str) -> str:
    for k in sorted(UNITS, key=len, reverse=True):
        if name.startswith(k):
            return UNITS[k]
    return "matches"


def sample_text(n: int, what: str = "matches") -> str:
    return f"n = {n:,} {what}"


# ---------------------------------------------------------------- pitch (shapes only: nothing is drawn from data we do not have)
def pitch_shapes(width: float = 100.0, height: float = 100.0) -> list[dict]:
    """Outline, halfway line, centre circle, penalty and six-yard boxes on a 0-100 x 0-100 canvas (coordinates are normalised percentages)."""
    line = dict(color=AXIS, width=1)
    rect = lambda x0, y0, x1, y1: dict(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=line)
    s = [rect(0, 0, 100, 100), dict(type="line", x0=50, y0=0, x1=50, y1=100, line=line), dict(type="circle", x0=40.8, y0=36.5, x1=59.2, y1=63.5, line=line),
         rect(0, 20.4, 16.5, 79.6), rect(83.5, 20.4, 100, 79.6), rect(0, 36.8, 5.5, 63.2), rect(94.5, 36.8, 100, 63.2)]
    return s


def pitch_figure(title: str | None = None, half: bool = False) -> go.Figure:
    """half=True shows the attacking half only (x 40-102): both teams attack left->right in the source data, so shots/passes cluster there."""
    fig = go.Figure()
    fig.update_layout(shapes=pitch_shapes())
    fig.update_xaxes(range=[40, 102] if half else [-2, 102], visible=False, constrain="domain")
    fig.update_yaxes(range=[102, -2], visible=False, scaleanchor="x", scaleratio=0.68)      # y grows downward like the source data; pitch ~ 105 x 68 m
    return style(fig, title, legend=True, height=470)


def normalise_xy(df: pd.DataFrame, x="location_x", y="location_y", system="coordinate_system") -> pd.DataFrame:
    """Map each provider's own coordinate system to 0-100 (%). StatsBomb 120x80 and Wyscout 0-100 are both left->right for the attacking team."""
    d = df.copy()
    sb = d[system] == "statsbomb_120x80"
    d["x"] = np.where(sb, d[x] / 120 * 100, d[x])
    d["y"] = np.where(sb, d[y] / 80 * 100, d[y])
    return d


def table_note(c: Chart) -> str:
    parts = [sample_text(c.n, unit_for(c.name)) if c.n else "", f"source: {c.source}" if c.source else "", c.note]
    return " · ".join(p for p in parts if p)
