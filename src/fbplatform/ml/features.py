"""Leakage-free feature engineering.

THE RULE: a feature of match M may only use matches played on a STRICTLY EARLIER DATE than M. Matches are processed date by date; all
matches of one date are featurised from the state before that date and only then added to the state, so same-day results never leak.
No final standing, tournament outcome or later player statistic is ever used. `FeatureBuilder` also offers `row_for` to featurise a
hypothetical/upcoming pairing from everything known up to a given date (used for predictions).

Elo: computed only from the four competitions in this dataset (no friendlies/qualifiers), starting at 1500 in 2000, K by competition,
goal-difference multiplier, +100 for the host. It is a documented, partial strength measure, not the official World Football Elo.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..analysis import data as D

K_BY_COMP = {"WC": 60, "EURO": 50, "COPA": 50, "UNL": 40}
HOST_ELO = 100
ELO0 = 1500.0
RECENT = 5
STAGE_RANK = {"Group stage": 1, "Play-off": 2, "Promotion/relegation play-off": 2, "Round of 32": 3, "Round of 16": 4, "Quarter-finals": 5,
              "Semi-finals": 6, "Third place": 6, "Final": 7}

TEAM_FEATS = ["n_prior", "win_pct", "ppm", "gf_avg", "ga_avg", "gd_avg", "cs_pct", "form_ppm", "form_gd", "editions", "ko_n", "ko_win_pct",
              "att_strength", "def_strength", "rest_days", "elo"]
PAIR_DIFFS = ["ppm", "gd_avg", "form_ppm", "form_gd", "att_strength", "def_strength", "elo", "win_pct", "editions"]
MATCH_FEATS = (["a_" + f for f in TEAM_FEATS] + ["b_" + f for f in TEAM_FEATS] + [d + "_diff" for d in PAIR_DIFFS] +
               ["h2h_n", "h2h_pts_share_a", "h2h_gd_avg_a", "is_knockout", "stage_rank", "a_is_host", "b_is_host", "comp_WC", "comp_EURO", "comp_COPA", "comp_UNL"])


def elo_update(ra, rb, goals_a, goals_b, k, host_a=False, host_b=False, shootout_winner=None):
    """Return the new (ra, rb). Draws (incl. shoot-out decided) count 0.5."""
    adj_a, adj_b = ra + (HOST_ELO if host_a else 0), rb + (HOST_ELO if host_b else 0)
    ea = 1.0 / (1.0 + 10 ** (-(adj_a - adj_b) / 400.0))
    wa = 1.0 if goals_a > goals_b else (0.5 if goals_a == goals_b else 0.0)
    diff = abs(goals_a - goals_b)
    g = 1.0 if diff <= 1 else (1.5 if diff == 2 else (11 + diff) / 8.0)
    delta = k * g * (wa - ea)
    return ra + delta, rb - delta


@dataclass
class TeamState:
    hist: list = field(default_factory=list)                    # (date, gf, ga, pts, is_ko, season_id)
    elo: float = ELO0


class FeatureBuilder:
    def __init__(self):
        self.teams: dict[int, TeamState] = defaultdict(TeamState)
        self.h2h: dict[frozenset, list] = defaultdict(list)     # (date, a_key, goals_a, goals_b)
        self.gf_total = 0.0
        self.n_total = 0
        self.country = D.q("select team_key, country from staging.stg_teams").set_index("team_key").country.to_dict()

    # ---- feature extraction from the CURRENT state (everything in state is strictly earlier than the date being featurised)
    def _team_vec(self, key, date, league_gf):
        st = self.teams[key]
        h = st.hist
        n = len(h)
        v = dict(n_prior=n, elo=st.elo)
        if n:
            gf, ga, pts = np.array([x[1] for x in h]), np.array([x[2] for x in h]), np.array([x[3] for x in h])
            ko = np.array([x[4] for x in h])
            v.update(win_pct=(pts == 3).mean(), ppm=pts.mean(), gf_avg=gf.mean(), ga_avg=ga.mean(), gd_avg=(gf - ga).mean(), cs_pct=(ga == 0).mean(),
                     editions=len({x[5] for x in h}), ko_n=int(ko.sum()), ko_win_pct=(pts[ko] == 3).mean() if ko.any() else np.nan,
                     rest_days=(date - h[-1][0]).days)
            last = h[-RECENT:]
            v.update(form_ppm=np.mean([x[3] for x in last]), form_gd=np.mean([x[1] - x[2] for x in last]))
            v.update(att_strength=gf.mean() / league_gf if league_gf else np.nan, def_strength=ga.mean() / league_gf if league_gf else np.nan)
        else:
            v.update(win_pct=np.nan, ppm=np.nan, gf_avg=np.nan, ga_avg=np.nan, gd_avg=np.nan, cs_pct=np.nan, editions=0, ko_n=0, ko_win_pct=np.nan,
                     rest_days=np.nan, form_ppm=np.nan, form_gd=np.nan, att_strength=np.nan, def_strength=np.nan)
        return v

    def row_for(self, a, b, date, comp, stage_name, is_knockout, venue_country=None) -> dict:
        """Features for the pairing (a, b) on `date` from the state as it is NOW (callers must have added only strictly earlier matches)."""
        league_gf = self.gf_total / self.n_total if self.n_total else np.nan
        va, vb = self._team_vec(a, date, league_gf), self._team_vec(b, date, league_gf)
        r = {"a_" + k: v for k, v in va.items()} | {"b_" + k: v for k, v in vb.items()}
        for d in PAIR_DIFFS:
            r[d + "_diff"] = (va[d] - vb[d]) if pd.notna(va[d]) and pd.notna(vb[d]) else np.nan
        meet = self.h2h[frozenset((a, b))]
        r["h2h_n"] = len(meet)
        if meet:
            ga_ = [(g1 if ka == a else g2, g2 if ka == a else g1) for _, ka, g1, g2 in meet]
            r["h2h_pts_share_a"] = np.mean([3 if x > y else (1 if x == y else 0) for x, y in ga_]) / 3.0
            r["h2h_gd_avg_a"] = np.mean([x - y for x, y in ga_])
        else:
            r["h2h_pts_share_a"], r["h2h_gd_avg_a"] = np.nan, np.nan
        r["is_knockout"] = int(bool(is_knockout))
        r["stage_rank"] = STAGE_RANK.get(stage_name, np.nan)
        r["a_is_host"] = int(venue_country is not None and self.country.get(a) == venue_country)
        r["b_is_host"] = int(venue_country is not None and self.country.get(b) == venue_country)
        for c in K_BY_COMP:
            r["comp_" + c] = int(comp == c)
        return r

    # ---- state update with a finished match
    def _update(self, row):
        a, b = row.home_team_key, row.away_team_key
        ga, gb = int(row.home_score), int(row.away_score)
        ko = bool(row.is_knockout)
        pa, pb = (3 if ga > gb else (1 if ga == gb else 0)), (3 if gb > ga else (1 if ga == gb else 0))
        self.teams[a].hist.append((row.match_date, ga, gb, pa, ko, row.season_id))
        self.teams[b].hist.append((row.match_date, gb, ga, pb, ko, row.season_id))
        self.h2h[frozenset((a, b))].append((row.match_date, a, ga, gb))
        self.gf_total += ga + gb
        self.n_total += 2

    def build(self, matches: pd.DataFrame) -> pd.DataFrame:
        """Featurise every played match with both teams known, strictly from earlier dates. Returns one row per match."""
        m = matches[matches.is_played & matches.home_team_key.notna() & matches.away_team_key.notna()].copy()
        m = m.sort_values(["match_date", "match_key"]).reset_index(drop=True)
        out = []
        for date, day in m.groupby("match_date", sort=True):
            pending = []
            for row in day.itertuples():
                a, b = int(row.home_team_key), int(row.away_team_key)
                f = self.row_for(a, b, date, row.competition_id, row.stage_name, row.is_knockout, row.venue_country)
                f["a_elo"], f["b_elo"] = self.teams[a].elo, self.teams[b].elo
                f["elo_diff"] = f["a_elo"] - f["b_elo"]
                f.update(match_key=row.match_key, match_id=row.match_id, match_date=date, season_id=row.season_id, competition_id=row.competition_id,
                         team_a_key=a, team_b_key=b, home_score=int(row.home_score), away_score=int(row.away_score),
                         home_goals90=row.home_goals90, away_goals90=row.away_goals90)
                out.append(f)
                pending.append(row)
            for row in pending:                                                   # state changes only AFTER the whole date is featurised
                a, b = int(row.home_team_key), int(row.away_team_key)
                ha, hb = (self.country.get(a) == row.venue_country), (self.country.get(b) == row.venue_country)
                ra, rb = elo_update(self.teams[a].elo, self.teams[b].elo, int(row.home_score), int(row.away_score), K_BY_COMP[row.competition_id], ha, hb)
                self.teams[a].elo, self.teams[b].elo = ra, rb
                self._update(row)
        df = pd.DataFrame(out)
        df["elo_diff"] = df.a_elo - df.b_elo
        df["result"] = np.select([df.home_score > df.away_score, df.home_score < df.away_score], ["A", "B"], "D")
        df["y"] = df.result.map({"A": 0, "D": 1, "B": 2})
        return df


def build_match_features() -> pd.DataFrame:
    return FeatureBuilder().build(D.matches())


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    X = df[MATCH_FEATS].copy()
    return X.astype(float)


def chronological_split(df: pd.DataFrame, train=0.70, val=0.15):
    """Train / validation / test by DATE (never mixing a date across sets): earliest 70%, next 15%, latest 15% of matches."""
    d = df.sort_values(["match_date", "match_key"]).reset_index(drop=True)
    n = len(d)
    dates = d.match_date.values
    t_cut = dates[int(n * train)]
    v_cut = dates[int(n * (train + val))]
    tr = d[d.match_date < t_cut]
    va = d[(d.match_date >= t_cut) & (d.match_date < v_cut)]
    te = d[d.match_date >= v_cut]
    return tr, va, te


# ------------------------------------------------------------------ team-centric rows for goal models
def team_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Two rows per match (each team's expected goals): own attack vs opponent defence, past-only."""
    rows = []
    for side, other in (("a", "b"), ("b", "a")):
        t = pd.DataFrame({
            "match_key": df.match_key, "match_date": df.match_date, "season_id": df.season_id, "competition_id": df.competition_id,
            "side": side, "own_att": df[f"{side}_att_strength"], "opp_def": df[f"{other}_def_strength"], "own_gf_avg": df[f"{side}_gf_avg"], "opp_ga_avg": df[f"{other}_ga_avg"],
            "own_form_gd": df[f"{side}_form_gd"], "opp_form_gd": df[f"{other}_form_gd"], "own_elo": df[f"{side}_elo"], "opp_elo": df[f"{other}_elo"],
            "elo_diff": df[f"{side}_elo"] - df[f"{other}_elo"], "own_n_prior": df[f"{side}_n_prior"], "opp_n_prior": df[f"{other}_n_prior"],
            "own_is_host": df[f"{side}_is_host"], "opp_is_host": df[f"{other}_is_host"], "is_knockout": df.is_knockout, "stage_rank": df.stage_rank,
            "comp_WC": df.comp_WC, "comp_EURO": df.comp_EURO, "comp_COPA": df.comp_COPA, "comp_UNL": df.comp_UNL,
            "goals": df.home_goals90 if side == "a" else df.away_goals90, "goals_recorded": df.home_score if side == "a" else df.away_score})
        rows.append(t)
    return pd.concat(rows, ignore_index=True).sort_values(["match_date", "match_key", "side"]).reset_index(drop=True)


GOAL_FEATS = ["own_att", "opp_def", "own_gf_avg", "opp_ga_avg", "own_form_gd", "opp_form_gd", "own_elo", "opp_elo", "elo_diff", "own_n_prior", "opp_n_prior",
              "own_is_host", "opp_is_host", "is_knockout", "stage_rank", "comp_WC", "comp_EURO", "comp_COPA", "comp_UNL"]
