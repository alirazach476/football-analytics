"""Analysis data access: everything is read from the PostgreSQL warehouse / dbt Gold layer (never from raw files).

Conventions used by every analysis:
  * only PLAYED matches are analysed; scheduled fixtures ("Coming soon") have no result and are excluded from every statistic and model target;
  * `goals90` = goals in regulation time: the recorded 90-minute score when known, the recorded score when the match ended inside 90 minutes,
    otherwise NaN (extra-time match whose 90-minute score is unknown) - never guessed;
  * `goals_total` = recorded score (includes extra time, excludes shoot-out).
"""
from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import threading

import psycopg

from ..warehouse.load import dsn

COMP_ORDER = ["WC", "EURO", "COPA", "UNL"]
# Okabe-Ito colour-blind-safe palette, one fixed colour per competition across all figures
COMP_COLOR = {"WC": "#0072B2", "EURO": "#D55E00", "COPA": "#009E73", "UNL": "#CC79A7"}
COMP_NAME = {"WC": "FIFA World Cup", "EURO": "UEFA Euro", "COPA": "Copa América", "UNL": "UEFA Nations League"}


_local = threading.local()


def _query(sql, params):
    """One reusable connection per thread: a hosted database (SSL, tens of ms per connect) would otherwise add a connect to every query."""
    for attempt in (0, 1):
        c = getattr(_local, "conn", None)
        if c is None or c.closed:
            c = _local.conn = psycopg.connect(dsn(), autocommit=True)
        try:
            cur = c.execute(sql, params)
            return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        except (psycopg.OperationalError, psycopg.InterfaceError):
            _local.conn = None                                  # stale connection (server slept or restarted): reconnect once
            if attempt:
                raise


def q(sql: str, params=None) -> pd.DataFrame:
    df = _query(sql, params)
    for col in df.columns:                                    # PostgreSQL numeric -> float
        if df[col].dtype == object:
            v = df[col].dropna()
            if len(v) and isinstance(v.iloc[0], Decimal):
                df[col] = df[col].astype(float)
    return df


def _num(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def matches(played_only: bool = True) -> pd.DataFrame:
    m = q("select * from staging.stg_matches" + (" where is_played" if played_only else ""))
    m = _num(m, ["home_score", "away_score", "home_score_ft90", "away_score_ft90", "home_score_ht", "away_score_ht", "home_score_et", "away_score_et",
                 "home_pen", "away_pen", "attendance", "season_year", "stage_order"])
    m["match_date"] = pd.to_datetime(m.match_date)
    m["goals_total"] = m.home_score + m.away_score
    ft = m.home_score_ft90.notna() & m.away_score_ft90.notna()
    m["goals90"] = np.where(ft, m.home_score_ft90 + m.away_score_ft90, np.where(~m.went_beyond_90.astype(bool), m.goals_total, np.nan))
    m["home_goals90"] = np.where(ft, m.home_score_ft90, np.where(~m.went_beyond_90.astype(bool), m.home_score, np.nan))
    m["away_goals90"] = np.where(ft, m.away_score_ft90, np.where(~m.went_beyond_90.astype(bool), m.away_score, np.nan))
    m["margin"] = (m.home_score - m.away_score).abs()
    m["outcome"] = np.select([m.home_score > m.away_score, m.home_score < m.away_score], ["home win", "away win"], "draw")
    m["phase"] = np.where(m.is_knockout.astype(bool), "knockout", "group/league")
    return m


def team_matches() -> pd.DataFrame:
    t = q("""select t.*, tm.team_name, om.team_name as opponent_name, s.season_year, s.competition_id as comp
             from intermediate.int_team_matches t
             join staging.stg_teams tm using (team_key) join staging.stg_teams om on om.team_key = t.opponent_key
             join (select distinct season_id, season_year, competition_id from staging.stg_matches) s using (season_id)""")
    return _num(t, ["goals_for", "goals_against", "goal_diff", "points", "stage_order", "season_year"]).assign(match_date=lambda d: pd.to_datetime(d.match_date))


def goals() -> pd.DataFrame:
    g = q("select * from gold.mart_goal_analysis")
    g["match_date"] = pd.to_datetime(g.match_date)
    return _num(g, ["minute", "minute_added", "period"])


def tournaments() -> pd.DataFrame:
    return _num(q("select * from gold.mart_tournament_summary order by season_id"), ["goals_per_match", "draw_pct", "matches_played", "teams", "season_year"])


def players() -> pd.DataFrame:
    return q("select * from gold.mart_player_career")


def player_seasons() -> pd.DataFrame:
    p = q("""select pp.*, d.primary_position, d.date_of_birth, s.season_year, ts.first_match_date
             from gold.mart_player_performance pp join wh.dim_player d using (player_key)
             join (select distinct season_id, season_year from staging.stg_matches) s using (season_id)
             join gold.mart_tournament_summary ts using (season_id)""")
    p["date_of_birth"] = pd.to_datetime(p.date_of_birth, errors="coerce")
    p["first_match_date"] = pd.to_datetime(p.first_match_date)
    p["age"] = (p.first_match_date - p.date_of_birth).dt.days / 365.25
    return _num(p, ["appearances", "starts", "minutes_played", "matches_with_minutes", "goals", "assists", "goal_contributions", "goals_per_90", "assists_per_90", "goals_in_minute_matches", "assists_in_minute_matches", "season_year"])


def awards() -> pd.DataFrame:
    return q("""select a.*, s.season_id, pl.full_name from staging.stg_awards a join wh.dim_season s using (season_key)
                left join staging.stg_players pl using (player_key)""")
