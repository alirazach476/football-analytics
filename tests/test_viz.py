"""Tests for the visualisation system: filters, chart data preparation, availability rules (never invent data), exports, pages."""
import io
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
import pytest
from fbplatform.warehouse.load import dsn

try:
    psycopg.connect(dsn(), connect_timeout=3).close()
    UP = True
except Exception:
    UP = False
needs_db = pytest.mark.skipif(not UP, reason="warehouse not running")
VIEWS = Path(__file__).resolve().parents[1] / "src" / "fbplatform" / "dashboard" / "views"


# ---------------------------------------------------------------- fixtures (loaded once)
@pytest.fixture(scope="module")
def m_played():
    from fbplatform.analysis import data as D
    return D.matches()


@pytest.fixture(scope="module")
def m_all():
    from fbplatform.analysis import data as D
    return D.matches(played_only=False)


@pytest.fixture(scope="module")
def tm():
    from fbplatform.analysis import data as D
    return D.team_matches()


# ---------------------------------------------------------------- filters (pure functions, synthetic data)
def _toy():
    return pd.DataFrame({"competition_id": ["WC", "WC", "EURO", "COPA"], "season_id": ["WC-2018", "WC-2022", "EURO-2020", "COPA-2024"],
                         "match_date": pd.to_datetime(["2018-06-20", "2022-12-01", "2021-06-15", "2024-07-01"]), "stage_name": ["Group stage", "Final", "Group stage", "Final"],
                         "home_team_name": ["A", "B", "C", "A"], "away_team_name": ["B", "C", "D", "D"]})


def test_filters_combine_with_and_semantics_and_describe_themselves():
    from fbplatform.viz.filters import Filters, apply_matches
    t = _toy()
    assert len(apply_matches(t, Filters())) == 4
    assert list(apply_matches(t, Filters(competitions=["WC"])).season_id) == ["WC-2018", "WC-2022"]
    assert list(apply_matches(t, Filters(competitions=["WC"], stages=["Final"])).season_id) == ["WC-2022"]
    assert set(apply_matches(t, Filters(teams=["A"])).season_id) == {"WC-2018", "COPA-2024"}                # any selected team plays
    assert list(apply_matches(t, Filters(date_from=pd.Timestamp("2021-01-01"), date_to=pd.Timestamp("2022-01-01"))).season_id) == ["EURO-2020"]
    assert apply_matches(t, Filters(competitions=["UNL"])).empty
    assert "WC" in Filters(competitions=["WC"]).describe() and "no filters" in Filters().describe()


def test_team_match_filters_follow_the_same_rules():
    from fbplatform.viz.filters import Filters, apply_team_matches
    t = pd.DataFrame({"comp": ["WC", "EURO"], "season_id": ["WC-2018", "EURO-2020"], "match_date": pd.to_datetime(["2018-06-20", "2021-06-15"]), "stage_name": ["Group stage", "Final"], "team_name": ["A", "B"]})
    assert list(apply_team_matches(t, Filters(competitions=["EURO"])).team_name) == ["B"]
    assert list(apply_team_matches(t, Filters(teams=["A"])).team_name) == ["A"]


# ---------------------------------------------------------------- competition charts
@needs_db
def test_furthest_stage_matches_known_results(m_all):
    from fbplatform.viz.competition import furthest_stage
    f = furthest_stage(m_all[m_all.season_id == "WC-2022"]).set_index("team_name").stage_level
    assert f["Argentina"] == 6 and f["France"] == 5 and f["Croatia"] == 4 and f["Morocco"] == 4 and f["Qatar"] == 0 and len(f) == 32


@needs_db
def test_bracket_places_feeders_next_to_each_other_and_links_winners(m_all):
    from fbplatform.viz.competition import _winner, bracket_layout, knockout_bracket
    ms = m_all[m_all.season_id == "WC-2022"]
    ko = ms[ms.is_knockout.astype(bool) & (ms.stage_name != "Third place")]
    ordered, names, pos = bracket_layout(ko)
    assert names == ["Round of 16", "Quarter-finals", "Semi-finals", "Final"] and [len(ordered[n]) for n in names] == [8, 4, 2, 1]
    for r_i in range(1, len(names)):                                        # each match's two feeders exist, win their match, and sit side by side
        prev = ordered[names[r_i - 1]]
        for j, parent in enumerate(ordered[names[r_i]]):
            kids = [k for k in prev if _winner(pd.Series(k)) in (parent["home_team_name"], parent["away_team_name"])]
            assert len(kids) == 2 and abs(prev.index(kids[0]) - prev.index(kids[1])) == 1 and sorted(prev.index(k) for k in kids) == [2 * j, 2 * j + 1]
    c = knockout_bracket(ms, "WC-2022")
    assert c.available and c.n == 15 and set(c.data.status_label) == {"Full time"}


@needs_db
def test_upcoming_bracket_is_labelled_coming_soon_and_never_has_a_score(m_all):
    from fbplatform.viz.competition import knockout_bracket
    c = knockout_bracket(m_all[m_all.season_id == "EURO-2028"], "EURO-2028")
    assert c.available and set(c.data.status_label) == {"Coming soon"} and c.data.home_score.isna().all()
    assert "Coming soon" in str(c.fig.layout.annotations)


@needs_db
def test_group_standings_available_only_where_groups_exist_and_are_labelled_derived():
    from fbplatform.viz import competition as V
    st = V.load_standings()
    c = V.group_standings(st, "WC-2022")
    assert c.available and c.n == 32 and "DERIVED" in c.note and (c.data.points == 3 * c.data.wins + c.data.draws).all()
    assert not V.group_standings(st, "EURO-2028").available and "no group" in V.group_standings(st, "EURO-2028").reason


@needs_db
def test_history_champions_titles_and_distributions_are_consistent(m_played):
    from fbplatform.analysis import data as D
    from fbplatform.viz import competition as V
    tr = D.tournaments()
    h = V.edition_history(tr)
    assert h.n == len(m_played) and "EURO-2028" not in set(h.data.season_id)                                 # upcoming edition is not a played edition
    ch, tt = V.champions_timeline(tr), V.title_counts(tr)
    assert ch.n == tt.n == int(tr.champion.notna().sum()) and "EURO-2028" not in set(ch.data.season_id)
    g = V.goal_distribution(m_played)
    assert g.available
    assert np.allclose(g.data.groupby("competition_id").share_pct.sum(), 100, atol=0.1)
    nr = V.goal_distribution(m_played.iloc[:10])
    assert not nr.available


# ---------------------------------------------------------------- availability rules: nothing is invented
@needs_db
def test_shot_map_only_from_real_coordinates():
    from fbplatform.viz import matches as V
    assert not V.shot_map(V.load_shots(season_id="WC-2002")).available                                       # no coordinates exist for 2002
    c = V.shot_map(V.load_shots(season_id="WC-2022", team="Argentina"))
    assert c.available and c.n > 50 and c.data.x.between(-0.1, 100.5).all() and c.data.y.between(-0.1, 100.5).all()
    assert (c.data.team_name == "Argentina").all() and set(c.data.provider) == {"statsbomb"}
    w = V.shot_map(V.load_shots(season_id="EURO-2016", team="Portugal"))
    assert w.available and "no xG" in w.note and set(w.data.provider) == {"wyscout"}                        # Wyscout shots carry no xG: said, not invented


@needs_db
def test_passing_network_needs_recorded_recipients(m_played):
    from fbplatform.viz import matches as V
    sb = m_played[(m_played.season_id == "WC-2022") & (m_played.home_team_name == "Argentina") & (m_played.away_team_name == "France")].iloc[0]
    passes = V.load_passes(int(sb.match_key))
    c = V.passing_network(passes, "Argentina", 60)
    assert c.available and (c.data.passes_between >= 3).all()
    wy = m_played[m_played.season_id == "EURO-2016"].iloc[0]
    bad = V.passing_network(V.load_passes(int(wy.match_key)), wy.home_team_name)
    assert not bad.available and "recipient" in bad.reason
    # spot-check one edge against the raw completed passes of the same window
    d = passes[(passes.team_name == "Argentina") & passes.outcome.isna() & passes.recipient_key.notna() & (passes.minute <= 60)]
    r = c.data.iloc[0]
    a = d[(d.passer == r.player_a) & (d.recipient == r.player_b)].shape[0] + d[(d.passer == r.player_b) & (d.recipient == r.player_a)].shape[0]
    assert a == r.passes_between


@needs_db
def test_score_progression_refuses_when_events_do_not_reproduce_the_score(m_played):
    from fbplatform.viz import matches as V
    fin = m_played[(m_played.season_id == "WC-2022") & (m_played.home_team_name == "Argentina") & (m_played.away_team_name == "France")].iloc[0]
    ok = V.score_progression(fin, V.load_match_events(int(fin.match_key)))
    assert ok.available and ok.data.iloc[:, 1].max() == 3 and ok.data.iloc[:, 2].max() == 3
    tampered = V.load_match_events(int(fin.match_key))
    tampered = tampered[~(tampered.is_goal & (tampered.minute == tampered[tampered.is_goal].minute.min()))]    # drop a goal
    bad = V.score_progression(fin, tampered)
    assert not bad.available and "do not reproduce" in bad.reason


@needs_db
def test_players_assists_and_radar_respect_data_coverage(tm):
    from fbplatform.analysis import data as D
    from fbplatform.ml.clustering import player_stat_table
    from fbplatform.viz import players as V
    ps = D.player_seasons()
    rel = set(D.q("select distinct s.season_id from wh.fact_match_events e join wh.fact_matches m using (match_key) join wh.dim_season s using (season_key) where e.provider='statsbomb'").season_id)
    assert not V.top_players(ps[ps.season_id == "COPA-2001"], "assists", reliable_seasons=rel).available      # no assists recorded for that edition
    a = V.top_players(ps, "assists", reliable_seasons=rel)
    assert a.available and "PARTIAL" in a.note
    stats = player_stat_table()
    assert not V.radar(stats, ["Nobody Here"]).available
    r = V.radar(stats, ["Harry Kane"])
    assert r.available and r.data.percentile_within_position.between(0, 100).all()
    p = V.per90(ps, "goals", 270, rel)
    assert (p.data.minutes >= 270).all() and np.allclose(p.data.per90, 90 * p.data.ev / p.data.minutes, atol=1e-2)


@needs_db
def test_position_chart_omits_unknown_positions_instead_of_guessing(m_played):
    from fbplatform.analysis import data as D
    from fbplatform.viz import players as V
    c = V.position_comparison(D.player_seasons())
    assert c.available and set(c.data.position) <= {"Forward", "Midfielder", "Defender", "Goalkeeper"} and "omitted, not guessed" in c.note


def test_missing_is_never_drawn_as_zero():
    from fbplatform.viz.engineering import missing_heatmap
    df = pd.DataFrame({"g": ["a"] * 10, "attendance": [0, 0, 0, np.nan, np.nan, 100, 200, 300, 400, 500]})
    c = missing_heatmap(df, ["attendance"], "g", "t", ["attendance"])
    assert c.data.iloc[0]["a"] == 20.0                                           # 2 NaN of 10; the three genuine zeros are NOT counted as missing
    assert "genuine zeros: 3" in str(c.fig.data[0].customdata)


# ---------------------------------------------------------------- teams, matches, statistics
@needs_db
def test_team_tables_and_radar_are_consistent(tm):
    from fbplatform.viz import teams as V
    t = V.team_table(tm)
    assert (t.wins + t.draws + t.losses == t.matches).all() and np.allclose(t.win_pct + t.draw_pct + t.loss_pct, 100)
    w = V.wdl_distribution(tm, ["Argentina", "Brazil"])
    assert w.available and np.allclose(w.data[["win_pct", "draw_pct", "loss_pct"]].sum(axis=1), 100, atol=0.02)
    r = V.radar(tm, ["Argentina", "Qatar"])
    assert r.available and r.data.percentile.dropna().between(0, 100).all()
    d = r.data
    assert d[(d.team == "Argentina") & (d.metric == "Defence")].percentile.iloc[0] > d[(d.team == "Qatar") & (d.metric == "Defence")].percentile.iloc[0]   # fewer goals conceded = higher
    assert d[(d.team == "Qatar") & (d.metric == "Knockout record")].percentile.isna().all()                    # <3 knockout matches: missing, not 0


@needs_db
def test_head_to_head_chart_matches_the_head_to_head_tool(m_played):
    from fbplatform.analysis.advanced import head_to_head
    from fbplatform.viz import teams as V
    s, t = V.head_to_head(m_played, "Argentina", "Brazil")
    h = head_to_head("Argentina", "Brazil")
    assert s.available and s.n == h.meetings == t.n
    assert not V.head_to_head(m_played, "Argentina", "Argentina")[0].available


@needs_db
def test_match_distributions_sum_correctly(m_played):
    from fbplatform.viz import matches as V
    sc = V.scoreline_heatmap(m_played)
    assert sc.data.matches.sum() == len(m_played)
    o = V.outcome_distribution(m_played)
    assert np.allclose(o.data[["home_win_pct", "draw_pct", "away_win_pct"]].sum(axis=1), 100, atol=0.2)
    a, b, c = V.shootouts(m_played)
    assert a.n == 68 and b.n == 52 and (c.data.won <= c.data.shootouts).all()
    ha = V.home_away(m_played, V.team_country())
    assert ha.available and ha.data.n.sum() <= len(m_played)


@needs_db
def test_statistical_charts_have_consistent_data_and_static_twins(m_played, tm):
    from fbplatform.viz import statplots as V
    te = V.team_edition_table(tm)
    cols = {"gf_pm": "GF", "ga_pm": "GA", "ppm": "PPM", "win_pct": "Win%", "cs_pct": "CS%"}
    c = V.correlation_matrix(te, cols)
    r = c.data.set_index("variable")
    assert np.allclose(np.diag(r.values), 1) and np.allclose(r.values, r.values.T, atol=1e-3)
    charts = [c, V.distribution(m_played), V.box_plot(m_played), V.violin_plot(m_played), V.scatter_regression(te, "gf_pm", "ppm", "GF", "PPM"), V.regression_diagnostics(m_played)]
    import matplotlib.pyplot as plt
    for ch in charts:
        assert ch.available and ch.static is not None
        f = ch.static()
        assert hasattr(f, "savefig")
        plt.close(f)
    diag = charts[-1].data
    assert diag.cooks_distance.max() < 0.5 and 0 < diag.leverage.max() < 1


def test_ci_and_hypothesis_charts_use_only_rows_with_the_needed_fields():
    from fbplatform.viz import statplots as V
    assert not V.ci_forest(pd.DataFrame(columns=["ci_low", "ci_high", "estimate_name"]), "ratio").available
    res = V.load_results()
    if res.empty:
        pytest.skip("results.csv not generated")
    f = V.ci_forest(res, "difference")
    assert f.available and f.data.ci_low.notna().all() and (f.data.ci_low <= f.data.ci_high).all()
    h = V.hypothesis_summary(res)
    p = h.data.p_adj_holm.fillna(h.data.p_value)
    assert p.is_monotonic_increasing and p.between(0, 1).all()


# ---------------------------------------------------------------- machine learning (saved models, nothing retrained)
@needs_db
def test_ml_charts_reproduce_the_saved_evaluation():
    from fbplatform.viz import mlplots as V
    t = V.load_outcome_test()
    assert t is not None
    saved = pd.read_csv(Path(V.REPORTS) / "outcome" / "match_outcome_model_comparison.csv")
    saved = saved[saved.split == "test"].set_index("model")
    for name, p in t["proba"].items():
        assert np.isclose((p.argmax(1) == t["y"]).mean(), saved.loc[name, "accuracy"], atol=1e-6)            # same numbers as the recorded report
    cm = V.confusion(t, "xgboost")
    assert cm.data.drop(columns="actual").values.sum() == len(t["y"])
    roc = V.roc_curves(t, 0)
    assert roc.data.set_index("model").auc["baseline_prior"] == pytest.approx(0.5, abs=1e-6)
    cal = V.calibration(t, "xgboost", 0)
    assert cal.data.n.sum() == len(t["y"])


@needs_db
def test_shap_goal_and_cluster_charts_are_wired_to_real_outputs():
    from fbplatform.viz import mlplots as V
    sv, X = V.load_shap()
    assert sv.shape == (len(X), X.shape[1], 3)
    bar = V.shap_bar((sv, X))
    assert bar.available and (bar.data.drop(columns="feature").min() >= 0).all()
    g = V.load_goal_test()
    ap = V.goals_actual_vs_predicted(g)
    assert ap.available and (ap.data.predicted > 0).all() and ap.data.goals.isin(range(0, 12)).all()
    assert V.team_cluster_scatter().available and V.silhouette_by_k().available and V.team_dendrogram().available
    assert V.model_comparison("log_loss").available and V.goal_model_comparison().available


# ---------------------------------------------------------------- data engineering
@needs_db
def test_engineering_charts_reflect_the_monitoring_tables():
    from fbplatform.dashboard import queries as Q
    from fbplatform.viz import engineering as V
    lc = V.layer_counts()
    assert set(lc.layer) == {"Bronze (frozen snapshot)", "Silver", "Gold (dbt marts)"} and (lc.rows > 0).all()
    log = V.pipeline_log()
    pf = V.pipeline_failures(log)
    assert pf.available and int(pf.data.drop(columns="step").sum().sum()) == len(log)
    dq = V.dq_trends(V.dq_log())
    assert dq.available and dq.data.pass_rate.between(0, 100).all()
    d = V.duplicates(Q.duplicate_checks())
    assert d.available and d.data[d.data.kind.str.startswith("integrity")].found.eq(0).all()
    assert V.source_coverage(V.coverage()).available and V.freshness(V.freshness_rows()).available


# ---------------------------------------------------------------- exports, UCL, units
def test_exports_roundtrip_and_png_strategy():
    import plotly.graph_objects as go
    from fbplatform.viz import export
    from fbplatform.viz.common import Chart, unavailable
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "é"]})
    assert pd.read_csv(io.BytesIO(export.csv_bytes(df)), encoding="utf-8-sig").equals(df)
    ch = Chart(go.Figure(go.Bar(x=[1], y=[1])), df, 2, name="demo")
    assert b"plotly" in export.html_bytes(ch)
    assert export.png_bytes(ch)[1] in ("kaleido", "unavailable")                      # no static twin: PNG only if kaleido exists
    import matplotlib.pyplot as plt
    ch.static = lambda: (plt.subplots()[0])
    png, how = export.png_bytes(ch)
    assert how == "matplotlib" and png[:8] == b"\x89PNG\r\n\x1a\n"
    assert export.html_bytes(unavailable("x", "because")) is None and export.png_bytes(unavailable("x", "because")) == (None, "unavailable")


@needs_db
def test_no_champions_league_in_any_chart_data(m_played, tm):
    from fbplatform.analysis import data as D
    from fbplatform.viz import competition as VC
    from fbplatform.viz import teams as VT
    frames = [VC.edition_history(D.tournaments()).data, VC.goal_distribution(m_played).data, VC.goal_minutes(D.goals()).data, VT.team_table(tm)]
    for f in frames:
        for col in ("competition_id", "season_id", "team_name"):
            if col in f.columns:
                assert not f[col].astype(str).str.contains(r"\bUCL\b|Champions League", case=False, regex=True).any()
    assert set(frames[0].competition_id) <= {"WC", "EURO", "COPA", "UNL"}


def test_every_chart_note_names_its_unit_and_never_says_matches_for_other_things():
    from fbplatform.viz import common as C
    assert C.unit_for("importance_permutation") == "features" and C.unit_for("shot_map") == "shots" and C.unit_for("shootout_records") == "shoot-outs"
    assert C.unit_for("roc_0") == "test matches" and C.unit_for("something_new") == "matches"


# ---------------------------------------------------------------- Streamlit pages
@needs_db
@pytest.mark.parametrize("page", ["viz_competition", "viz_team", "viz_player", "viz_match", "viz_stats", "viz_ml", "viz_engineering"])
def test_visualisation_pages_render_without_errors(page):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(VIEWS / f"{page}.py"), default_timeout=300).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(at.title) == 1 and len(at.tabs) >= 5


@needs_db
def test_competition_filter_changes_the_sample_and_cross_filter_sets_the_edition():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(VIEWS / "viz_competition.py"), default_timeout=300).run()
    assert any("**1,779** of 1,779" in c.value for c in at.caption)
    at.sidebar.multiselect(key="f_comps").select("WC").run()
    assert not at.exception and any("**488** of 1,779" in c.value for c in at.caption)
    # cross-filtering: a selected edition (set by clicking a chart) becomes the default of the detail tabs
    at2 = AppTest.from_file(str(VIEWS / "viz_competition.py"), default_timeout=300)
    at2.session_state["xf_season"] = "WC-2018"
    at2.run()
    assert not at2.exception and any("WC-2018" in s.value for s in at2.success)
    assert [s for s in at2.selectbox if s.key == "v_bracket_season"][0].value == "WC-2018"


@needs_db
def test_match_page_defaults_to_a_played_match_and_keeps_fixtures_selectable():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(VIEWS / "viz_match.py"), default_timeout=300).run()
    box = at.selectbox[0]
    assert "COMING SOON" not in box.options[box.index] and any("COMING SOON" in o for o in box.options)               # default is played; fixtures remain in the list
    assert not at.exception


@needs_db
def test_team_page_falls_back_gracefully_when_filters_leave_no_team():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(VIEWS / "viz_team.py"), default_timeout=300).run()
    at.sidebar.multiselect(key="f_comps").select("UNL").run()
    at.sidebar.multiselect(key="f_seasons").select("UNL-2018-19").run()
    assert not at.exception


@needs_db
def test_every_chart_table_view_is_serialisable_by_streamlit(m_played, tm):
    """The table view of each chart goes through pyarrow; a column mixing numbers and text (e.g. '6+') breaks the live app."""
    import pyarrow as pa
    from fbplatform.analysis import data as D
    from fbplatform.viz import competition as VC
    from fbplatform.viz import matches as VM
    from fbplatform.viz import statplots as VS
    from fbplatform.viz import teams as VT
    tr = D.tournaments()
    charts = [VC.edition_history(tr), VC.champions_timeline(tr), VC.title_counts(tr), VC.edition_comparison(tr), VC.edition_heatmap(tr), VC.goal_distribution(m_played), VC.goal_minutes(D.goals()),
              VT.wdl_distribution(tm), VT.goals_scored_conceded(tm), VT.radar(tm, ["Argentina", "France"]), VT.comparison_heatmap(tm), VT.timeline(tm, ["Argentina"]), VT.rankings(tm), VT.consistency(tm),
              VM.scoreline_heatmap(m_played), VM.outcome_distribution(m_played), VM.home_away(m_played, VM.team_country()), *VM.shootouts(m_played), VS.regression_diagnostics(m_played),
              VS.box_plot(m_played), VS.distribution(m_played)]
    assert sum(c.available for c in charts) >= 20
    for c in charts:
        if c.available:
            pa.Table.from_pandas(c.data)


def test_visualization_guide_only_names_functions_that_exist():
    import importlib
    import re
    text = (Path(__file__).resolve().parents[1] / "docs" / "VISUALIZATION_GUIDE.md").read_text(encoding="utf-8")
    refs = set(re.findall(r"`(competition|teams|players|matches|statplots|mlplots|engineering)\.(\w+)`", text))
    assert len(refs) >= 50
    missing = [f"{m}.{f}" for m, f in refs if not hasattr(importlib.import_module(f"fbplatform.viz.{m}"), f)]
    assert missing == [], missing
