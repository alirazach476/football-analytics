"""Cached data access for the API (the data changes only when the pipeline runs: caches live for the process and can be cleared with refresh())."""
from __future__ import annotations

import os
import pickle
from functools import lru_cache, wraps
from pathlib import Path

import pandas as pd

from ..analysis import data as D

CACHE_DIR = Path(os.environ["FB_CACHE_DIR"]) if os.environ.get("FB_CACHE_DIR") else None


def persisted(name):
    """Heavy loaders (scoring the test period, SHAP, event-level player stats) take ~1 minute each. When FB_CACHE_DIR is set (deployment) the result is pickled
    at build time (tools/warm_cache via api/warm.py) and loaded from disk afterwards; without it behaviour is unchanged."""
    def deco(fn):
        @wraps(fn)
        def inner():
            f = CACHE_DIR / f"{name}.pkl" if CACHE_DIR else None
            if f is not None and f.exists():
                return pickle.loads(f.read_bytes())
            v = fn()
            if f is not None:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(pickle.dumps(v))
            return v
        return inner
    return deco


@lru_cache(maxsize=None)
def matches_played() -> pd.DataFrame:
    return D.matches()


@lru_cache(maxsize=None)
def matches_all() -> pd.DataFrame:
    return D.matches(played_only=False)


@lru_cache(maxsize=None)
def team_matches() -> pd.DataFrame:
    return D.team_matches()


@lru_cache(maxsize=None)
def tournaments() -> pd.DataFrame:
    return D.tournaments()


@lru_cache(maxsize=None)
def goals() -> pd.DataFrame:
    return D.goals()


@lru_cache(maxsize=None)
def standings() -> pd.DataFrame:
    from ..viz.competition import load_standings
    return load_standings()


@lru_cache(maxsize=None)
def player_seasons() -> pd.DataFrame:
    return D.player_seasons()


@lru_cache(maxsize=None)
@persisted("player_stats")
def player_stats() -> pd.DataFrame:
    from ..ml.clustering import player_stat_table
    return player_stat_table()


@lru_cache(maxsize=None)
def reliable_seasons() -> frozenset:
    return frozenset(D.q("select distinct s.season_id from wh.fact_match_events e join wh.fact_matches m using (match_key) join wh.dim_season s using (season_key) where e.provider='statsbomb'").season_id)


@lru_cache(maxsize=None)
@persisted("contribution_index")
def contribution_index() -> pd.DataFrame:
    from ..analysis.advanced import player_contribution
    return player_contribution()


@lru_cache(maxsize=None)
def team_country() -> dict:
    from ..viz.matches import team_country as tc
    return tc()


@lru_cache(maxsize=None)
@persisted("outcome_test")
def outcome_test():
    from ..viz import mlplots
    return mlplots.load_outcome_test()


@lru_cache(maxsize=None)
@persisted("goal_test")
def goal_test():
    from ..viz import mlplots
    return mlplots.load_goal_test()


@lru_cache(maxsize=None)
@persisted("shap_values")
def shap_values():
    from ..viz import mlplots
    return mlplots.load_shap()


@lru_cache(maxsize=None)
def registry() -> pd.DataFrame:
    from ..config import ROOT
    return pd.read_csv(ROOT / "data" / "registry" / "competition_seasons.csv")


def refresh():
    for f in list(globals().values()):
        if hasattr(f, "cache_clear"):
            f.cache_clear()
