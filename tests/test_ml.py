import json

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


def test_elo_update_known_values():
    from fbplatform.ml.features import elo_update
    ra, rb = elo_update(1500, 1500, 1, 0, k=50)
    assert ra == pytest.approx(1525) and rb == pytest.approx(1475)                   # equal ratings, 1-goal win: +K*0.5
    assert sum(elo_update(1600, 1400, 2, 2, 40)) == pytest.approx(3000)               # zero-sum
    assert elo_update(1500, 1500, 3, 0, 50)[0] - 1500 > elo_update(1500, 1500, 1, 0, 50)[0] - 1500   # bigger wins move more
    ra2, _ = elo_update(1500, 1500, 1, 1, 50, host_a=True)
    assert ra2 < 1500                                                                  # the host was expected to win: a draw costs rating


@needs_db
def test_features_never_use_future_matches():
    """Change every result AFTER a cutoff date: features of matches on/before the cutoff must not change at all."""
    from fbplatform.analysis import data as D
    from fbplatform.ml import features as F
    m = D.matches()
    base = F.FeatureBuilder().build(m)
    cutoff = pd.Timestamp("2016-06-30")
    m2 = m.copy()
    late = m2.match_date > cutoff
    m2.loc[late, ["home_score", "away_score"]] = m2.loc[late, ["away_score", "home_score"]].values + 3
    alt = F.FeatureBuilder().build(m2)
    a = base[base.match_date <= cutoff].set_index("match_key")[F.MATCH_FEATS].sort_index()
    b = alt[alt.match_date <= cutoff].set_index("match_key")[F.MATCH_FEATS].sort_index()
    pd.testing.assert_frame_equal(a, b)
    after_a = base[base.match_date > cutoff].set_index("match_key")[F.MATCH_FEATS].sort_index()
    after_b = alt[alt.match_date > cutoff].set_index("match_key")[F.MATCH_FEATS].sort_index()
    assert not after_a.equals(after_b)                                                 # the test is able to detect a change


@needs_db
def test_prior_counts_use_strictly_earlier_dates_only():
    from fbplatform.analysis import data as D
    from fbplatform.ml import features as F
    m = D.matches()
    f = F.FeatureBuilder().build(m)
    pm = pd.concat([m[["match_date", "home_team_key"]].rename(columns={"home_team_key": "t"}),
                    m[["match_date", "away_team_key"]].rename(columns={"away_team_key": "t"})]).dropna()
    for r in f.sample(60, random_state=1).itertuples():
        assert r.a_n_prior == ((pm.t == r.team_a_key) & (pm.match_date < r.match_date)).sum()
        assert r.b_n_prior == ((pm.t == r.team_b_key) & (pm.match_date < r.match_date)).sum()


@needs_db
def test_chronological_split_has_no_time_overlap_and_excludes_scheduled():
    from fbplatform.ml import features as F
    df = F.build_match_features()
    tr, va, te = F.chronological_split(df)
    assert tr.match_date.max() < va.match_date.min() and va.match_date.max() < te.match_date.min()
    assert len(tr) + len(va) + len(te) == len(df) and not df.season_id.eq("EURO-2028").any()
    assert df.y.isin([0, 1, 2]).all()


@needs_db
def test_outcome_pipeline_quick_run_metrics_and_probabilities():
    from fbplatform.ml import outcome
    r = outcome.run(track=False, quick=True, save=False)
    res = r["results"]
    assert {"baseline_prior", "baseline_elo_logreg", "logreg", "random_forest", "xgboost"} <= set(res.model)
    t = res[res.split == "test"].set_index("model")
    assert (t.log_loss > 0).all() and t.accuracy.between(0, 1).all()
    assert t.loc["baseline_elo_logreg", "log_loss"] < t.loc["baseline_prior", "log_loss"]      # Elo carries real signal
    assert np.allclose(r["final_proba"].sum(axis=1), 1.0)
    assert r["selected"] in {"logreg", "random_forest", "xgboost"}
    assert not r["explain"]["permutation"].empty and not r["explain"]["pdp"].empty


@needs_db
def test_goal_pipeline_quick_run_beats_mean_baseline_and_reports_diagnostics():
    from fbplatform.ml import goals
    r = goals.run(track=False, quick=True, save=False)
    t = r["results"][r["results"].split == "test"].set_index("model")
    assert t.loc[r["selected"], "poisson_deviance"] < t.loc["baseline_train_mean", "poisson_deviance"]
    assert r["diagnostics"]["pearson_dispersion"] > 0 and 0 < r["over_under"]["brier"] < 1
    assert (r["calibration"].mean_predicted > 0).all()


@needs_db
def test_predict_matchup_is_a_labelled_probability_from_past_matches_only():
    from fbplatform.ml import outcome
    p = outcome.predict_matchup("Argentina", "Brazil", "2022-12-01", competition="WC", stage_name="Quarter-finals")
    assert sum(p["probabilities"].values()) == pytest.approx(1.0) and "PREDICTION" in p["label"]
    early = outcome.predict_matchup("Argentina", "Brazil", "2003-01-01", competition="WC")
    assert early["probabilities"] != p["probabilities"]                                    # different history -> different numbers


@needs_db
def test_clustering_outputs_are_valid_and_labels_follow_profiles():
    from fbplatform.ml import clustering
    t = clustering.cluster_teams(track=False)
    assert t["teams"].kmeans.notna().all() and -1 <= t["summary"].silhouette_kmeans.iloc[0] <= 1
    assert t["profiles"].suggested_description.str.len().gt(3).all() and t["profiles"].n_teams.sum() == len(t["teams"])
    p = clustering.cluster_players(track=False)
    assert set(p["players"].position) <= {"Defender", "Midfielder", "Forward"}                # position-aware, goalkeepers separate
    assert (p["players"].mins >= 270).all() and len(p["goalkeepers"]) > 10


@needs_db
def test_next_tournament_features_use_only_earlier_editions():
    from fbplatform.ml import players
    ps = players.player_season_table()
    nt = players.next_tournament_table(ps)
    for r in nt.sample(40, random_state=2).itertuples():
        earlier = ps[(ps.player_key == r.player_key) & ((ps.season_year < r.season_year) | ((ps.season_year == r.season_year) & (ps.season_id < r.season_id)))]
        assert r.prior_editions == len(earlier) and r.prior_minutes == pytest.approx(earlier.minutes_played.sum())
    pred, _, tr, te = players.prediction(nt)
    assert tr.season_year.max() < te.season_year.min() and set(pred.model) >= {"baseline_train_mean", "ridge", "random_forest"}


@needs_db
def test_head_to_head_is_symmetric_and_validates_input():
    from fbplatform.analysis import advanced as A
    ab, ba = A.head_to_head("Argentina", "Brazil"), A.head_to_head("Brazil", "Argentina")
    assert ab.meetings == ba.meetings > 0 and ab.wins_a == ba.wins_b and ab.draws == ba.draws and ab.goals_a == ba.goals_b
    assert ab.wins_a + ab.draws + ab.wins_b == ab.meetings and any("context" in c.lower() for c in ab.caveats)
    with pytest.raises(KeyError):
        A.head_to_head("Argentina", "Atlantis")
    assert A.head_to_head("Argentina", "Brazil", competition="COPA").meetings <= ab.meetings


@needs_db
def test_advanced_indices_are_bounded_and_forecasts_labelled_exploratory():
    from fbplatform.analysis import advanced as A
    ci, sens = A.competitiveness()
    assert ci.competitiveness_index.between(0, 1).all() and len(ci) >= 25 and (ci.margin_ci_low <= ci.margin_ci_high).all()
    dom = A.dominance()
    assert dom.dominance_score.between(0, 1).all() and (dom.editions >= 3).all()
    pci = A.player_contribution()
    assert pci.position.isin(["Defender", "Midfielder", "Forward"]).all() and (pci[pci.minutes < 900].sample_size_flag.str.startswith("low")).all()
    bt, fc = A.forecast()
    assert fc.status.str.contains("EXPLORATORY").all() and (fc.pi_low < fc.forecast_goals_per_match).all() and (fc.forecast_goals_per_match < fc.pi_high).all()


@needs_db
def test_mlflow_runs_are_tracked_and_models_saved_with_metadata():
    import mlflow
    from fbplatform.ml import tracking as T
    mlflow.set_tracking_uri(T.URI)
    names = {e.name for e in mlflow.search_experiments()}
    assert {"match_outcome", "goal_prediction"} <= names
    meta = json.loads((T.MODELS / "match_outcome_selected.json").read_text(encoding="utf-8"))
    assert meta["features"] and meta["split"]["train"][1] < meta["split"]["test"][0] and "lightgbm" in meta
    assert (T.MODELS / "match_outcome_selected.joblib").exists()
