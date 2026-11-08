import numpy as np
import pandas as pd
import pytest
import psycopg
from fbplatform.warehouse.load import dsn

try:
    psycopg.connect(dsn(), connect_timeout=3).close()
    UP = True
except Exception:
    UP = False
needs_db = pytest.mark.skipif(not UP, reason="warehouse not running")


# ---- statistical helpers: known answers
def test_cliffs_delta_known_values():
    from fbplatform.analysis.stats import cliffs_delta
    assert cliffs_delta([5, 6, 7], [1, 2, 3]) == pytest.approx(1.0)
    assert cliffs_delta([1, 2, 3], [5, 6, 7]) == pytest.approx(-1.0)
    assert cliffs_delta([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)


def test_cohens_d_known_value():
    from fbplatform.analysis.stats import cohens_d
    a, b = np.array([2.0, 4.0, 6.0]), np.array([1.0, 3.0, 5.0])
    assert cohens_d(a, b) == pytest.approx(0.5)             # mean diff 1, pooled sd 2


def test_icc_detects_team_structure_and_noise():
    from fbplatform.analysis.stats import icc1
    rng = np.random.default_rng(0)
    strong = pd.DataFrame({"g": np.repeat(range(30), 5)})
    strong["v"] = np.repeat(rng.normal(0, 3, 30), 5) + rng.normal(0, .3, 150)
    noise = pd.DataFrame({"g": np.repeat(range(30), 5), "v": rng.normal(0, 1, 150)})
    assert icc1(strong, "g", "v")[0] > 0.9 and abs(icc1(noise, "g", "v")[0]) < 0.2


def test_holm_adjustment_is_monotone_and_not_smaller_than_raw():
    from fbplatform.analysis import stats
    stats.ROWS.clear()
    for p in (0.001, 0.02, 0.04):
        stats.add("QX", "t", "a", "m", "ok", 10, "e", 0.0, 0, 0, 0, p, "es", 0.0, "l", family="fam")
    df = stats.holm_within_family()
    stats.ROWS.clear()
    assert (df.p_adj_holm >= df.p_value).all() and df.p_adj_holm.is_monotonic_increasing and df.p_adj_holm.iloc[0] == pytest.approx(0.003)


# ---- generated outputs
@needs_db
def test_statistics_results_cover_all_ten_questions_and_are_well_formed():
    from fbplatform.analysis import stats
    stats.ROWS.clear()
    r = stats.run()
    assert set(r.q) == {f"Q{i}" for i in range(1, 11)}
    assert r.p_value.dropna().between(0, 1).all() and r.p_adj_holm.dropna().between(0, 1).all()
    assert ((r.ci_low <= r.ci_high) | r.ci_low.isna()).all()
    for c in ("assumption_checks", "limitations", "method", "effect_size_name"):
        assert r[c].notna().all() and (r[c].str.len() > 3).all()
    assert (r.n > 0).all()


@needs_db
def test_statistics_exclude_scheduled_fixtures():
    from fbplatform.analysis import data as D
    m = D.matches()
    assert m.is_played.all() and not (m.season_id == "EURO-2028").any()


@needs_db
def test_goals90_never_invents_a_regulation_score():
    from fbplatform.analysis import data as D
    m = D.matches()
    unknown = m[m.went_beyond_90 & m.home_score_ft90.isna()]
    assert len(unknown) > 0 and unknown.goals90.isna().all()                     # extra-time match, 90-min score unknown -> NaN
    known = m[m.home_score_ft90.notna()]
    assert (known.goals90 == known.home_score_ft90 + known.away_score_ft90).all()


@needs_db
def test_eda_tables_are_consistent_with_the_warehouse():
    from fbplatform.analysis import eda
    res = eda.build()
    T = res["tables"]
    assert len(T) >= 40 and len(res["figures"]) >= 9
    a1 = T["A1_competition_summary"].set_index("competition_id")
    assert set(a1.index) == {"WC", "EURO", "COPA", "UNL"} and a1.matches_played.sum() == 1779
    assert len(T["E5_upcoming_fixtures_coming_soon"]) == 51 and (T["E5_upcoming_fixtures_coming_soon"].status_label == "Coming soon").all()
    c1 = T["C1_top_scorers"]
    assert c1.full_name.is_unique and c1.goals.is_monotonic_decreasing
    assert not c1.full_name.str.contains(chr(92), regex=False).any()
    assert (T["C5_goals_per_90_min270"].goals_per_90 < 3).all()                  # no inflated rates from missing minutes
