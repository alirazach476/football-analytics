"""Validate Wikipedia match details against independent providers on the matches both cover.

  Fjelstul   : World Cup 2002-2014 (cards, substitutions, appearances)
  StatsBomb  : World Cup 2018/22, Euro 2020/24, Copa 2024 (cards, substitutions, line-ups)
Per match we compare: starters' shirt numbers per team (set equality), number of substitutions, and the multiset of
(team, minute) of cards.  Output: data/quality/wikipedia_details_validation.csv (+ printed agreement rates).
"""
from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from ..config import DATA
from .build import PROC


def _cards(a, b, tol=1):
    """True if, per team, the sorted card minutes pair up one-to-one within +-tol minutes (sources round minutes differently)."""
    for t in set(a.team_id) | set(b.team_id):
        x = sorted(a[a.team_id == t].minute.astype(int))
        y = sorted(b[b.team_id == t].minute.astype(int))
        if len(x) != len(y) or any(abs(i - j) > tol for i, j in zip(x, y)):
            return False
    return True


def run():
    wl = pd.read_parquet(PROC / "wikipedia" / "lineups_wikipedia.parquet")
    we = pd.read_parquet(PROC / "wikipedia" / "detail_events_wikipedia.parquet")
    m = pd.read_parquet(PROC / "matches.parquet").set_index("match_id")
    fe = pd.read_parquet(PROC / "fjelstul" / "events_fjelstul.parquet")
    fl = pd.read_parquet(PROC / "fjelstul" / "lineups_fjelstul.parquet")
    sbe = pd.read_parquet(PROC / "events.parquet", columns=["match_id", "event_type", "card", "team_id", "minute", "period"])
    sbl = pd.read_parquet(PROC / "lineups.parquet", columns=["match_id", "team_id", "jersey_number", "is_starter"])
    rows = []
    for mid in sorted(set(wl.match_id)):
        src = "fjelstul" if mid in set(fe.match_id) else ("statsbomb" if mid in set(sbe.match_id) else None)
        if src is None:
            continue
        w_st = wl[(wl.match_id == mid) & wl.is_starter]
        w_cd = we[(we.match_id == mid) & (we.event_type == "card")].copy()
        if src == "statsbomb":     # StatsBomb counts stoppage time inside the minute (45+2 -> 47)
            w_cd["minute"] = w_cd.minute + w_cd.minute_added.fillna(0)
        w_sb = we[(we.match_id == mid) & (we.event_type == "substitution")]
        if src == "fjelstul":
            o_cd = fe[(fe.match_id == mid) & (fe.event_type == "card")]
            o_sb = fe[(fe.match_id == mid) & (fe.event_type == "substitution")]
            o_st = fl[(fl.match_id == mid) & fl.is_starter]
        else:
            ev = sbe[sbe.match_id == mid]
            o_cd = ev[ev.card.notna() & (ev.period <= 4)]
            o_sb = ev[ev.event_type == "substitution"]
            o_st = sbl[(sbl.match_id == mid) & (sbl.is_starter == True)]
        sets = lambda df: {t: set(g.jersey_number.dropna().astype(int)) for t, g in df.groupby("team_id")}
        a, b = sets(w_st), sets(o_st)
        starters_equal = all(a.get(t) == b.get(t) for t in set(a) | set(b))
        rows.append(dict(match_id=mid, season_id=m.loc[mid, "season_id"], other=src,
                         starters_equal=starters_equal, subs_wikipedia=len(w_sb), subs_other=len(o_sb),
                         cards_wikipedia=len(w_cd), cards_other=len(o_cd),
                         card_minutes_equal=_cards(w_cd, o_cd, tol=2 if src == "statsbomb" else 1)))
    v = pd.DataFrame(rows)
    (DATA / "quality").mkdir(exist_ok=True)
    v.to_csv(DATA / "quality" / "wikipedia_details_validation.csv", index=False)
    return v


if __name__ == "__main__":
    v = run()
    print(len(v), "matches compared")
    for src, g in v.groupby("other"):
        print(f"{src:10s} n={len(g):4d} | starters equal {g.starters_equal.mean():.1%} | subs count equal {(g.subs_wikipedia == g.subs_other).mean():.1%}"
              f" | cards count equal {(g.cards_wikipedia == g.cards_other).mean():.1%} | card minutes within tolerance (SB 2 min: elapsed vs current minute; Fjelstul 1) {g.card_minutes_equal.mean():.1%}")
    print(v.groupby("season_id").agg(n=("match_id", "size"), starters=("starters_equal", "mean"), subs=("subs_wikipedia", "sum"),
                                     subs_o=("subs_other", "sum"), cards=("cards_wikipedia", "sum"), cards_o=("cards_other", "sum")).round(3).to_string())
