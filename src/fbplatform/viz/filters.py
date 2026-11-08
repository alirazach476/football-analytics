"""Filters shared by every visualisation page and the pure functions that apply them (testable without Streamlit).
Scheduled fixtures ('Coming soon') are never part of statistics: callers pass played data unless a chart is explicitly about fixtures."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Filters:
    competitions: list[str] = field(default_factory=list)       # empty = all
    seasons: list[str] = field(default_factory=list)
    teams: list[str] = field(default_factory=list)              # a match is kept when ANY selected team plays in it
    stages: list[str] = field(default_factory=list)
    date_from: pd.Timestamp | None = None
    date_to: pd.Timestamp | None = None
    players: list[int] = field(default_factory=list)            # player_key values

    def describe(self) -> str:
        bits = []
        if self.competitions:
            bits.append("competitions: " + ", ".join(self.competitions))
        if self.seasons:
            bits.append(f"{len(self.seasons)} edition(s)")
        if self.teams:
            bits.append("teams: " + ", ".join(self.teams[:4]) + ("…" if len(self.teams) > 4 else ""))
        if self.stages:
            bits.append("stages: " + ", ".join(self.stages))
        if self.date_from is not None or self.date_to is not None:
            bits.append(f"dates {self.date_from.date() if self.date_from is not None else '…'} → {self.date_to.date() if self.date_to is not None else '…'}")
        return "; ".join(bits) or "no filters (all competitions, editions, teams)"


def _in(s: pd.Series, values) -> pd.Series:
    return s.isin(values) if values else pd.Series(True, index=s.index)


def apply_matches(m: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Columns used: competition_id, season_id, match_date, stage_name, home_team_name, away_team_name."""
    ok = _in(m.competition_id, f.competitions) & _in(m.season_id, f.seasons) & _in(m.stage_name, f.stages)
    if f.teams:
        ok &= m.home_team_name.isin(f.teams) | m.away_team_name.isin(f.teams)
    d = pd.to_datetime(m.match_date)
    if f.date_from is not None:
        ok &= d >= pd.Timestamp(f.date_from)
    if f.date_to is not None:
        ok &= d <= pd.Timestamp(f.date_to)
    return m[ok]


def apply_team_matches(t: pd.DataFrame, f: Filters, team_col="team_name") -> pd.DataFrame:
    """Columns used: comp (or competition_id), season_id, match_date, stage_name, team_name. Team filter keeps the selected teams' rows."""
    comp = "comp" if "comp" in t.columns else "competition_id"
    ok = _in(t[comp], f.competitions) & _in(t.season_id, f.seasons) & _in(t.stage_name, f.stages) & _in(t[team_col], f.teams)
    d = pd.to_datetime(t.match_date)
    if f.date_from is not None:
        ok &= d >= pd.Timestamp(f.date_from)
    if f.date_to is not None:
        ok &= d <= pd.Timestamp(f.date_to)
    return t[ok]


def apply_seasons(df: pd.DataFrame, f: Filters, comp_col="competition_id", season_col="season_id") -> pd.DataFrame:
    return df[_in(df[comp_col], f.competitions) & _in(df[season_col], f.seasons)]
