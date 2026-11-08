from pathlib import Path

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


# ---- data queries behind the pages
@needs_db
def test_kpis_reconcile_with_the_warehouse_and_keep_upcoming_separate():
    from fbplatform.dashboard import queries as Q
    k = Q.kpis()
    assert k["competitions"] == 4 and k["matches_played"] == 1779 and k["matches_coming_soon"] == 51 and k["editions_upcoming"] == 1
    assert k["matches_played"] + k["matches_coming_soon"] == Q.q("select count(*) c from wh.fact_matches").c.iloc[0]
    assert k["goals"] == int(Q.q("select sum(home_score + away_score) s from wh.fact_matches where match_status='completed'").s.iloc[0])


@needs_db
def test_upcoming_fixtures_query_never_returns_results():
    from fbplatform.dashboard import queries as Q
    up = Q.upcoming_fixtures()
    assert len(up) == 51 and (up.status_label == "Coming soon").all() and up.fixture_detail.notna().all()
    ms = Q.match_search("EURO-2028")
    assert (ms.status_label == "Coming soon").all() and ms.home_score.isna().all()
    assert Q.match_search("EURO-2028", include_upcoming=False).empty


@needs_db
def test_team_and_competition_queries_are_internally_consistent():
    from fbplatform.dashboard import queries as Q
    s = Q.team_summary("Argentina").iloc[0]
    assert s.wins + s.draws + s.losses == s.matches and s.goal_diff == s.goals_for - s.goals_against
    ed = Q.team_by_edition("Argentina")
    assert ed.played.sum() == s.matches
    wc = Q.edition_table("WC")
    assert wc.matches_played.sum() == 488
    o = Q.outcome_table("WC")
    assert (o.drop(columns="season_id").sum(axis=1).values == wc[wc.matches_played > 0].matches_played.values).all()


@needs_db
def test_match_detail_queries_and_player_search():
    from fbplatform.dashboard import queries as Q
    mk = int(Q.match_search("WC-2022", "Argentina").match_key.iloc[-1])
    row = Q.match_row(mk).iloc[0]
    assert row.home_team_name == "Argentina" and row.away_team_name == "Saudi Arabia" and (row.home_score, row.away_score) == (1, 2)
    tl = Q.match_timeline(mk)
    assert set(tl.kind) <= {"Goal", "Own goal", "Substitution"} | {k for k in tl.kind if k.startswith("Card")} and (tl.kind == "Goal").sum() == 3
    p = Q.player_search("Messi")
    assert len(p) == 1 and p.goals.iloc[0] > 20


@needs_db
def test_data_engineering_queries_expose_monitoring_tables():
    from fbplatform.dashboard import queries as Q
    assert len(Q.pipeline_runs()) > 0 and len(Q.ingestion_status()) > 0 and len(Q.dq_results()) > 0
    d = Q.duplicate_checks().set_index("check").found
    assert d["duplicate match ids"] == 0 and d["duplicate event ids"] == 0 and d["duplicate (match, team, player) line-up rows"] == 0
    assert set(Q.db_stats().table) == set(Q.WH_TABLES) and (Q.db_stats().rows >= 0).all()
    assert Q.data_quality_score()["score"] is not None


def test_ml_report_loaders_return_labelled_prediction_files():
    from fbplatform.dashboard import queries as Q
    pr = Q.ml_outcome_predictions() if UP else pd.DataFrame()
    if UP:
        assert (pr.note.str.contains("PREDICTION")).all() and pr[["p_A_win", "p_draw", "p_B_win"]].sum(axis=1).sub(1).abs().lt(1e-6).all()
    assert not Q.ml_outcome_comparison().empty and Q.ml_meta()["selected_model"]


# ---- every page renders without an exception (Streamlit's headless AppTest)
@needs_db
@pytest.mark.parametrize("page", ["overview", "competition", "teams", "players", "matches", "ml", "data_engineering"])
def test_each_page_renders_without_errors(page):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(VIEWS / f"{page}.py"), default_timeout=120).run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert len(at.title) >= 1


@needs_db
def test_overview_shows_coming_soon_and_prediction_banner_present_on_ml_page():
    from streamlit.testing.v1 import AppTest
    ov = AppTest.from_file(str(VIEWS / "overview.py"), default_timeout=120).run()
    assert any("Coming soon" in str(m.label) for m in ov.metric) and any("Coming soon" in i.value for i in ov.info)
    ml = AppTest.from_file(str(VIEWS / "ml.py"), default_timeout=120).run()
    assert any("prediction" in w.value.lower() for w in ml.warning)


@needs_db
def test_match_page_shows_coming_soon_for_a_scheduled_fixture():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(VIEWS / "matches.py"), default_timeout=120).run()
    at.sidebar.selectbox[0].select("EURO-2028").run()
    assert not at.exception
    assert any("Coming soon" in i.value for i in at.info) or any("COMING SOON" in str(o) for sb in at.selectbox for o in sb.options)
