"""Chart registry for the API. Each entry takes a Ctx (filters + parameters) and returns a `viz.common.Chart`; nothing is re-implemented here:
the same functions that fed the Streamlit pages build the figures. Parameters and shared filters arrive from the React app."""
from __future__ import annotations

from functools import cached_property, lru_cache
from typing import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..analysis import data as D
from ..dashboard import queries as Q
from ..viz import common as C
from ..viz import competition as VC
from ..viz import engineering as VE
from ..viz import matches as VM
from ..viz import players as VP
from ..viz import teams as VT
from ..viz.common import Chart, unavailable
from ..viz.filters import Filters, apply_matches, apply_seasons, apply_team_matches
from . import store


class _Lazy:
    """Import a heavy module (scikit-learn / statsmodels) the first time a chart uses it, so the API starts small (matters on a 512 MB free host)."""

    def __init__(self, name):
        self._name, self._mod = name, None

    def __getattr__(self, attr):
        if self._mod is None:
            import importlib
            self._mod = importlib.import_module(self._name, package=__package__)
        return getattr(self._mod, attr)


VL = _Lazy("..viz.mlplots")
VS = _Lazy("..viz.statplots")

REGISTRY: dict[str, Callable] = {}


def chart(cid: str):
    def deco(fn):
        REGISTRY[cid] = fn
        return fn
    return deco


class Ctx:
    def __init__(self, f: Filters, p: dict):
        self.f, self.p = f, p or {}

    def get(self, k, default=None):
        v = self.p.get(k, default)
        return default if v in (None, "") else v

    @cached_property
    def mf(self):
        return apply_matches(store.matches_played(), self.f)

    @cached_property
    def maf(self):
        return apply_matches(store.matches_all(), self.f)

    @cached_property
    def tr(self):
        return apply_seasons(store.tournaments(), self.f)

    @cached_property
    def tm(self):
        return apply_team_matches(store.team_matches(), self.f, "team_name")

    @cached_property
    def ps(self):
        ps = store.player_seasons()
        m = pd.Series(True, index=ps.index)
        if self.f.seasons:
            m &= ps.season_id.isin(self.f.seasons)
        if self.f.competitions:
            m &= ps.season_id.str.split("-").str[0].isin(self.f.competitions)
        ps = ps[m]
        return ps[ps.team_name.isin(self.f.teams)] if self.f.teams else ps

    def teams(self):
        t = self.p.get("teams") or []
        return [x for x in t if x] if isinstance(t, list) else [t]

    def row(self):
        mk = int(self.p["match_key"])
        d = store.matches_all()
        d = d[d.match_key == mk]
        if d.empty:
            raise KeyError(f"unknown match_key {mk}")
        return d.iloc[0]


def build(cid: str, filters: Filters, params: dict) -> Chart:
    if cid not in REGISTRY:
        raise KeyError(cid)
    return REGISTRY[cid](Ctx(filters, params))


# ======================================================================= competition (viz lab)
chart("comp.history")(lambda x: VC.edition_history(x.tr, x.get("measure", "goals_per_match")))
chart("comp.champions")(lambda x: VC.champions_timeline(x.tr))
chart("comp.titles")(lambda x: VC.title_counts(x.tr))
chart("comp.compare")(lambda x: VC.edition_comparison(x.tr, x.get("metric", "goals_per_match")))
chart("comp.compare_heat")(lambda x: VC.edition_heatmap(x.tr))
chart("comp.funnel")(lambda x: VC.progression_funnel(x.maf[x.maf.season_id == x.get("season", "")], x.get("season", "")))
chart("comp.groups")(lambda x: VC.group_standings(store.standings(), x.get("season", "")))
chart("comp.bracket")(lambda x: VC.knockout_bracket(store.matches_all()[store.matches_all().season_id == x.get("season", "")], x.get("season", "")))
chart("comp.gdist")(lambda x: VC.goal_distribution(x.mf, regulation=bool(x.get("regulation", True))))
chart("comp.gminutes")(lambda x: VC.goal_minutes(store.goals()[store.goals().match_key.isin(x.mf.match_key)] if len(x.mf) else store.goals().iloc[0:0]))

# ======================================================================= teams
chart("team.wdl")(lambda x: VT.wdl_distribution(x.tm, x.teams() or None, top_n=int(x.get("top_n", 20)), min_matches=int(x.get("min_matches", 10))))
chart("team.gfga")(lambda x: VT.goals_scored_conceded(x.tm, None, min_matches=int(x.get("min_matches", 15))))
chart("team.radar")(lambda x: VT.radar(x.tm, x.teams()))
chart("team.heat")(lambda x: VT.comparison_heatmap(x.tm, x.teams() or None))
chart("team.timeline")(lambda x: VT.timeline(x.tm, x.teams()))
chart("team.edheat")(lambda x: VT.edition_heatmap(x.tm, x.teams() or None))
chart("team.h2h_summary")(lambda x: VT.head_to_head(x.mf, x.get("a", ""), x.get("b", ""))[0])
chart("team.h2h_timeline")(lambda x: VT.head_to_head(x.mf, x.get("a", ""), x.get("b", ""))[1])
chart("team.rank")(lambda x: VT.rankings(x.tm, int(x.get("min", 15))))
chart("team.cons")(lambda x: VT.consistency(x.tm, 4))

# ======================================================================= players
chart("player.top_goals")(lambda x: VP.top_players(x.ps, "goals", int(x.get("n", 20)), set(store.reliable_seasons())))
chart("player.top_assists")(lambda x: VP.top_players(x.ps, "assists", int(x.get("n", 20)), set(store.reliable_seasons())))
chart("player.per90_goals")(lambda x: VP.per90(x.ps, "goals", int(x.get("min", 270)), set(store.reliable_seasons())))
chart("player.per90_assists")(lambda x: VP.per90(x.ps, "assists", int(x.get("min", 270)), set(store.reliable_seasons())))
chart("player.radar")(lambda x: VP.radar(store.player_stats(), x.p.get("players") or []))
chart("player.trends")(lambda x: VP.trends(x.ps, x.p.get("players") or [], x.get("measure", "goals")))
chart("player.age")(lambda x: VP.age_vs_performance(x.ps))
chart("player.position")(lambda x: VP.position_comparison(x.ps))
chart("player.pci")(lambda x: VP.contribution(store.contribution_index(), int(x.get("min", 900))))

# ======================================================================= matches
chart("match.goal_timeline")(lambda x: VM.goal_timeline(x.row(), VM.load_match_events(int(x.p["match_key"]))))
chart("match.progress")(lambda x: VM.score_progression(x.row(), VM.load_match_events(int(x.p["match_key"]))))
chart("match.events")(lambda x: VM.event_timeline(x.row(), VM.load_match_events(int(x.p["match_key"]))))
chart("match.shots_match")(lambda x: VM.shot_map(VM.load_shots([int(x.p["match_key"])]), "Shots in this match"))
chart("match.net")(lambda x: VM.passing_network(VM.load_passes(int(x.p["match_key"])), x.get("team", ""), float(x.get("upto", 60))))
chart("match.shots_team")(lambda x: VM.shot_map(VM.load_shots(season_id=x.get("season"), team=x.get("team")), f"{x.get('team')}: all shots, {x.get('season')}"))
chart("match.scoreline")(lambda x: VM.scoreline_heatmap(x.mf))
chart("match.outcome")(lambda x: VM.outcome_distribution(x.mf, x.get("by", "competition_id")))
chart("match.homeaway")(lambda x: VM.home_away(x.mf, store.team_country()))
chart("match.so_edition")(lambda x: VM.shootouts(x.mf)[0])
chart("match.so_scores")(lambda x: VM.shootouts(x.mf)[1])
chart("match.so_records")(lambda x: VM.shootouts(x.mf)[2])

# ======================================================================= statistics
_COLS = {"gf_pm": "Goals for / match", "ga_pm": "Goals against / match", "ppm": "Points / match", "win_pct": "Win %", "cs_pct": "Clean sheets %"}
_te = lambda x: VS.team_edition_table(x.tm)
chart("stat.corr")(lambda x: VS.correlation_matrix(_te(x), _COLS, x.get("method", "spearman")))
chart("stat.dist")(lambda x: VS.distribution(x.mf, x.get("var", "goals90")))
chart("stat.box")(lambda x: VS.box_plot(x.mf, x.get("var", "goals90"), x.get("by", "stage_name")))
chart("stat.violin")(lambda x: VS.violin_plot(x.mf, "margin", "competition_id"))
chart("stat.scatter")(lambda x: VS.scatter_regression(_te(x), x.get("x", "gf_pm"), x.get("y", "ppm"), _COLS[x.get("x", "gf_pm")], _COLS[x.get("y", "ppm")]))
chart("stat.forest")(lambda x: VS.ci_forest(VS.load_results(), x.get("kind", "ratio")))
chart("stat.hyp")(lambda x: VS.hypothesis_summary(VS.load_results()))
chart("stat.diag")(lambda x: VS.regression_diagnostics(x.mf))

# ======================================================================= machine learning (saved models)
chart("ml.confusion")(lambda x: VL.confusion(store.outcome_test(), x.get("model", "xgboost"), bool(x.get("norm", True))))
chart("ml.roc")(lambda x: VL.roc_curves(store.outcome_test(), int(x.get("cls", 0))))
chart("ml.pr")(lambda x: VL.pr_curves(store.outcome_test(), int(x.get("cls", 0))))
chart("ml.imp_perm")(lambda x: VL.feature_importance("permutation"))
chart("ml.imp_gain")(lambda x: VL.feature_importance("gain"))
chart("ml.shap_bar")(lambda x: VL.shap_bar(store.shap_values()))
chart("ml.shap_swarm")(lambda x: VL.shap_beeswarm(store.shap_values(), int(x.get("cls", 0))))
chart("ml.shap_dep")(lambda x: VL.shap_dependence(store.shap_values(), x.get("feature", "elo_diff"), int(x.get("cls", 0))))
chart("ml.calib")(lambda x: VL.calibration(store.outcome_test(), x.get("model", "xgboost"), int(x.get("cls", 0))))
chart("ml.goals_avp")(lambda x: VL.goals_actual_vs_predicted(store.goal_test()))
chart("ml.resid")(lambda x: VL.residual_plots(store.goal_test()))
chart("ml.team_clusters")(lambda x: VL.team_cluster_scatter())
chart("ml.dendro")(lambda x: VL.team_dendrogram())
chart("ml.sil")(lambda x: VL.silhouette_by_k())
chart("ml.player_clusters")(lambda x: VL.player_cluster_scatter(x.get("position", "Forward")))
chart("ml.cmp")(lambda x: VL.model_comparison(x.get("metric", "log_loss")))
chart("ml.gcmp")(lambda x: VL.goal_model_comparison(x.get("metric", "poisson_deviance")))


# ======================================================================= data engineering
@lru_cache(maxsize=None)
def _eng():
    return dict(lc=VE.layer_counts(), log=VE.pipeline_log(), dq=VE.dq_log(), fr=VE.freshness_rows(), cov=VE.coverage(), dup=Q.duplicate_checks(), m=VE.silver_table("matches"), p=VE.silver_table("players"),
                l=VE.silver_table("lineups", ["match_id", "team_id", "player_id", "minutes_played_derived", "is_starter"]), v=VE.silver_table("venues"), sq=VE.silver_table("squads"),
                latest=Q.q("select max(d.full_date)::text as d from wh.fact_matches m join wh.dim_date d using (date_key) where m.match_status='completed'").d.iloc[0])


def _eng_fresh():
    _eng.cache_clear()
    return _eng()


chart("eng.layers")(lambda x: VE.layer_record_counts(_eng()["lc"]))
chart("eng.miss_matches")(lambda x: VE.missing_heatmap(_eng()["m"][_eng()["m"].match_status == "completed"], ["attendance", "referee_raw", "venue_id", "man_of_the_match_raw", "home_score_ht", "home_score_ft90", "kickoff_time_local", "stage", "home_team_id"],
                                                        "competition_id", "Missing values in matches (played matches), by competition", ["attendance"]))
chart("eng.miss_players")(lambda x: VE.missing_heatmap(_eng()["p"].assign(source_id_prefix=lambda d: d.player_id.str[:4]), ["nationality", "date_of_birth", "height_cm", "preferred_foot", "primary_position"], "source_id_prefix", "Missing values in players, by source of the canonical id"))
chart("eng.complete")(lambda x: VE.completeness_bars({"matches": _eng()["m"][_eng()["m"].match_status == "completed"], "players": _eng()["p"], "lineups": _eng()["l"], "venues": _eng()["v"], "squads": _eng()["sq"]},
                                                      {"matches": ["attendance", "referee_raw", "venue_id", "man_of_the_match_raw", "home_score_ht", "home_score_ft90"], "players": ["date_of_birth", "nationality", "primary_position", "height_cm"],
                                                       "lineups": ["player_id", "minutes_played_derived"], "venues": ["latitude", "capacity"], "squads": ["date_of_birth", "caps", "club_raw"]}))
chart("eng.dups")(lambda x: VE.duplicates(_eng()["dup"]))
chart("eng.durations")(lambda x: VE.pipeline_durations(_eng()["log"]))
chart("eng.failures")(lambda x: VE.pipeline_failures(_eng()["log"]))
chart("eng.fresh")(lambda x: VE.freshness(_eng()["fr"], _eng()["latest"]))
chart("eng.coverage")(lambda x: VE.source_coverage(_eng()["cov"]))
chart("eng.dq")(lambda x: VE.dq_trends(_eng()["dq"]))


# ======================================================================= analytics pages (the original Streamlit 'Analytics' group)
def _bar(df, x, y, title, xlab, ylab, name, color=None, note="", source="warehouse"):
    if df is None or df.empty:
        return unavailable(name, "no data for this selection")
    fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=color or C.CAT[0], hovertemplate="%{x}<br>%{y}<extra></extra>"))
    C.style(fig, title, xlab, ylab, legend=False, height=380)
    C.bar_gap(fig)
    fig.update_xaxes(tickangle=45 if len(df) > 8 else 0, type="category")
    return Chart(fig, df, int(len(df)), source, note, name=name)


@chart("ov.coverage")
def _ov_cov(x):
    cov = Q.coverage_report()
    m = x.get("measure", "pct_lineups")
    h = cov.pivot_table(index="competition_id", columns="season_id", values=m)
    if h.empty:
        return unavailable("ov_coverage", "no coverage report yet")
    h = h.reindex([c for c in C.COMPS if c in h.index])
    fig = go.Figure(go.Heatmap(z=h.values, x=h.columns, y=[C.COMP_LABEL[c] for c in h.index], colorscale=C.SEQ, zmin=0, zmax=100, xgap=2, ygap=2, text=np.round(h.values), texttemplate="%{text:.0f}",
                               colorbar=dict(title="%"), hovertemplate="<b>%{x}</b> · %{y}<br>%{z:.1f}%<extra></extra>"))
    C.style(fig, "Dataset coverage by edition", None, None, legend=False, height=360)
    fig.update_xaxes(tickangle=60)
    return Chart(fig, cov[["season_id", "competition_id", m]], int(cov.matches_played.sum()), "monitoring.source_coverage_report",
                 "Blank = nothing to measure yet (upcoming edition). Low values are real source limits, e.g. Nations League group matches have no lineups.", name="ov_coverage")


_AN_LAB = {"goals_per_match": "Goals per match", "draw_pct": "Draw %", "avg_attendance": "Average attendance", "matches_beyond_90": "Matches beyond 90 min (count)"}


@chart("an.edition_metric")
def _an_edition(x):
    ed = Q.edition_table(x.get("comp", "WC"))
    ed = ed[ed.matches_played > 0]
    met = x.get("metric", "goals_per_match")
    return _bar(ed, "season_id", met, f"{_AN_LAB[met]} by edition", "Edition", _AN_LAB[met], "an_edition_metric", C.COMP_COLOR.get(x.get("comp", "WC")),
                "Per-match rates are comparable across editions; counts are not. Nations League extra time is not recorded." if met == "matches_beyond_90" else "Bars start at zero.")


@chart("an.outcomes")
def _an_outcomes(x):
    o = Q.outcome_table(x.get("comp", "WC"))
    if o.empty:
        return unavailable("an_outcomes", "no played matches")
    fig = go.Figure()
    for col, lab, color in (("team_listed_first_wins", "Team listed first wins", C.OUTCOME_COLOR["win"]), ("draws", "Draws", C.OUTCOME_COLOR["draw"]), ("team_listed_second_wins", "Team listed second wins", C.OUTCOME_COLOR["loss"])):
        fig.add_bar(x=o.season_id, y=o[col], name=lab, marker_color=color)
    fig.update_layout(barmode="stack")
    C.style(fig, "Match outcomes by edition", "Edition", "Matches (count)", height=380)
    C.bar_gap(fig)
    fig.update_xaxes(type="category")
    return Chart(fig, o, int(o.drop(columns="season_id").sum().sum()), "gold.mart_match_performance", "'Listed first' is not 'home': most tournament matches are on neutral ground.", name="an_outcomes")


@chart("an.goal_minutes")
def _an_gm(x):
    g = Q.goals_by_minute(x.get("comp"), x.get("season"))
    return _bar(g, "minute_band", "goals", "Goals by minute band", "Minute band", "Goals (count)", "an_goal_minutes", C.COMP_COLOR.get(x.get("comp") or "WC"),
                "Own goals included; the last band is extra time. Stoppage-time goals sit in the 45 and 90 minute bands.", "gold.mart_goal_analysis")


@chart("an.team_edition")
def _an_team_ed(x):
    ed = Q.team_by_edition(x.get("team", ""))
    met = x.get("measure", "goals_for_per_match")
    lab = {"goals_for_per_match": "Goals scored per match", "win_pct": "Win rate (%)", "goals_against": "Goals conceded (total)", "points": "Points"}[met]
    return _bar(ed, "season_id", met, lab + " by edition", "Edition", lab, "an_team_edition", note="One measure per chart (different scales are never put on one axis).", source="gold.mart_team_performance")


@chart("an.team_trend")
def _an_team_trend(x):
    ed = Q.team_by_edition(x.get("team", ""))
    if ed.empty:
        return unavailable("an_team_trend", "no played matches for this team")
    ed = ed.assign(year=ed.season_id.str.extract(r"(\d{4})")[0].astype(int))
    fig = go.Figure()
    for c in C.COMPS:
        s = ed[ed.competition_id == c]
        if len(s):
            fig.add_scatter(x=s.year, y=s.goals_for_per_match, mode="lines+markers", name=C.COMP_LABEL[c], line=dict(color=C.COMP_COLOR[c], width=2), marker=dict(size=9, symbol=C.COMP_SYMBOL[c], color=C.COMP_COLOR[c], line=dict(color=C.SURFACE, width=2)),
                            customdata=s.season_id, hovertemplate="%{customdata}: %{y:.2f} goals per match<extra></extra>")
    C.style(fig, "Scoring trend", "Edition year", "Goals scored per match", height=380)
    return Chart(fig, ed, len(ed), "gold.mart_team_performance", "Few matches per edition (3-8): single points are noisy.", name="an_team_trend")


@chart("an.player_edition")
def _an_player_ed(x):
    by = Q.player_by_edition(int(x.get("player_key", 0)))
    return _bar(by, "season_id", "goals", "Goals by tournament", "Tournament", "Goals (count)", "an_player_edition",
                note="Linked goals only. A missing tournament means the player did not take part.", source="gold.mart_player_performance")


@chart("an.top_players")
def _an_top(x):
    m = x.get("measure", "goals")
    top = Q.top_players(m, int(x.get("n", 25))).iloc[::-1]
    if top.empty:
        return unavailable("an_top_players", "no players")
    fig = go.Figure(go.Bar(y=top.full_name, x=top[m], orientation="h", marker_color=C.CAT[0], customdata=np.c_[top.nationality.fillna(""), top.tournaments], hovertemplate="<b>%{y}</b><br>%{x}<br>%{customdata[0]} · %{customdata[1]} tournaments<extra></extra>"))
    C.style(fig, f"Top players by {m.replace('_', ' ')}", m.replace("_", " ").capitalize(), None, legend=False, height=max(380, 22 * len(top) + 140))
    C.bar_gap(fig)
    return Chart(fig, top.iloc[::-1], len(top), "gold.mart_player_career", "Collected competitions only (not careers). Assists are partial; minutes for Wikipedia-based editions are approximate.", name="an_top_players")


@chart("an.player_compare")
def _an_compare(x):
    a, b = int(x.get("p1", 0)), int(x.get("p2", 0))
    na = Q.player_profile(a); nb = Q.player_profile(b)
    if na.empty or nb.empty:
        return unavailable("an_player_compare", "choose two players")
    ea, eb = Q.player_by_edition(a).assign(player=na.full_name.iloc[0]), Q.player_by_edition(b).assign(player=nb.full_name.iloc[0])
    both = pd.concat([ea, eb])
    fig = go.Figure()
    for i, (n, g) in enumerate(both.groupby("player", sort=False)):
        fig.add_scatter(x=g.season_id, y=g.goals, mode="lines+markers", name=n, line=dict(color=C.CAT[i], width=2), marker=dict(size=9, color=C.CAT[i], line=dict(color=C.SURFACE, width=2)))
    C.style(fig, "Goals by tournament", "Tournament", "Goals (count)", height=380)
    fig.update_xaxes(type="category", tickangle=60)
    return Chart(fig, both, len(both), "gold.mart_player_performance", "Different positions, eras and competitions: totals are not a verdict on who is better.", name="an_player_compare")
