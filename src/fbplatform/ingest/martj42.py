"""martj42/international_results (CC0): men's full internationals - results, goal scorers, shoot-out winners.

Used for
  * matches missing from other sources (Copa America 2004-2019, UEFA Nations League, ...), added with
    primary_provider='martj42' and a row-level source URL (#L<csv line>);
  * cross-checking every match we already hold (score/date) - conflicts are reported, never overwritten;
  * goal events (scorer, minute, penalty/own goal, assist name where given) for matches with no better source.
Limits (null, not guessed): no stage, group, referee, attendance, kickoff time; venue is only city + country;
score = full time incl. extra time, excl. shoot-out; shoot-out has a winner but no kick score.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pandas as pd

from ..config import DATA
from ..registry import build_registry
from .build import PROC, norm, match_id
from .teams import NATIONAL_ALIASES, _alias_map

RAWDIR = DATA / "raw" / "martj42"
URL = "https://raw.githubusercontent.com/martj42/international_results/master"
TOURN = {"FIFA World Cup": "WC", "UEFA Euro": "EURO", "Copa América": "COPA", "UEFA Nations League": "UNL"}
UNL_WINDOWS = [("UNL-2018-19", "2018-09-01", "2019-12-31"), ("UNL-2020-21", "2020-09-01", "2022-04-30"),   # incl. play-offs of March 2022
               ("UNL-2022-23", "2022-06-01", "2024-04-30"), ("UNL-2024-25", "2024-09-01", "2025-12-31"),
               ("UNL-2026-27", "2026-06-01", "2027-12-31")]
_NAT = _alias_map(NATIONAL_ALIASES)


def cn_strict(name: str) -> str:
    """canonical national-team key (alias-aware, accent/case-insensitive). Serbia and Serbia and Montenegro stay distinct."""
    n = norm(name)
    return norm(_NAT.get(n, name))


def cn(name: str) -> str:
    """cn_strict, plus: martj42 files WC 2006's Serbia and Montenegro under 'Serbia' - merged for LINKING ONLY."""
    k = cn_strict(name)
    return "serbia" if k == "serbia and montenegro" else k


def season_for(cid: str, d: date) -> str | None:
    y = d.year
    if cid == "WC":
        return f"WC-{y}" if y >= 2002 and y % 4 == 2 else None
    if cid == "EURO":
        if y == 2021:
            return "EURO-2020"
        return f"EURO-{y}" if y >= 2000 and y % 4 == 0 else None
    if cid == "COPA":
        return f"COPA-{y}" if y >= 2001 else None
    if cid == "UNL":
        s = d.isoformat()
        return next((sid for sid, a, b in UNL_WINDOWS if a <= s <= b), None)


def load():
    res = pd.read_csv(RAWDIR / "results.csv")
    res["csv_line"] = res.index + 2
    res["cid"] = res.tournament.map(TOURN)
    res = res[res.cid.notna()].copy()
    res["date"] = pd.to_datetime(res.date).dt.date
    res["season_id"] = [season_for(c, d) for c, d in zip(res.cid, res.date)]
    res = res[res.season_id.notna()].copy()
    so = pd.read_csv(RAWDIR / "shootouts.csv")
    so["date"] = pd.to_datetime(so.date).dt.date
    gs = pd.read_csv(RAWDIR / "goalscorers.csv")
    gs["date"] = pd.to_datetime(gs.date).dt.date
    return res, so, gs


def link(res: pd.DataFrame, ours: pd.DataFrame):
    """map each martj42 row to one of our matches (same season, date +-1, same team pair), else None."""
    idx = {}
    for r in ours.itertuples():
        idx.setdefault((r.season_id, frozenset((cn(r.home_team_raw), cn(r.away_team_raw)))), []).append(r)
    links = {}
    for r in res.itertuples():
        cands = idx.get((r.season_id, frozenset((cn(r.home_team), cn(r.away_team)))), [])
        cands = [c for c in cands if abs((c.match_date - r.date).days) <= 1]
        links[r.Index] = ("one", cands[0]) if len(cands) == 1 else (("ambiguous", cands) if len(cands) > 1 else None)
    return links


def run():
    reg = build_registry()
    res, so, gs = load()
    m = pd.read_parquet(PROC / "matches.parquet")
    m = m[m.primary_provider != "martj42"].copy()  # idempotent: drop rows added by an earlier run
    links = link(res, m)
    retrieved = datetime.fromtimestamp((RAWDIR / "results.csv").stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    so_key = {(r.date, cn(r.home_team), cn(r.away_team)): r.winner for r in so.itertuples()}

    # seasons where a full tournament is already held by OpenFootball/StatsBomb-complete sources
    cnt = m.groupby("season_id").size()
    exp = reg.set_index("season_id").expected_matches
    held_seasons = {sid for sid, n in cnt.items() if pd.notna(exp.get(sid)) and n >= exp.get(sid) * 0.9}
    conflicts, new_rows, ambiguous, unlinked = [], [], [], []
    for r in res.itertuples():
        lk = links[r.Index]
        if lk is not None and lk[0] == "ambiguous":
            ambiguous.append(dict(date=r.date, home=r.home_team, away=r.away_team, season=r.season_id))
            continue
        l = lk[1] if lk is not None else None
        if l is None and r.season_id in held_seasons:
            # another source already holds this whole tournament: an unlinked row is a discrepancy, not a new match
            unlinked.append(dict(season_id=r.season_id, date=r.date, home=r.home_team, away=r.away_team,
                                 score=f"{r.home_score}-{r.away_score}"))
            continue
        if l is not None:  # cross-check existing match
            if pd.notna(r.home_score) and pd.notna(l.home_score):
                same_o = (int(r.home_score), int(r.away_score)) == (int(l.home_score), int(l.away_score))
                swap = (int(r.away_score), int(r.home_score)) == (int(l.home_score), int(l.away_score)) and cn(r.home_team) == cn(l.away_team_raw)
                if not (same_o or swap) or (r.date != l.match_date):
                    conflicts.append(dict(season_id=r.season_id, our_date=l.match_date, martj42_date=r.date,
                                          match=f"{l.home_team_raw} v {l.away_team_raw}",
                                          ours=f"{l.home_score}-{l.away_score}", martj42=f"{r.home_team} {r.home_score}-{r.away_score} {r.away_team}"))
            continue
        # not held by any other source -> new match
        has_score = pd.notna(r.home_score)
        hs, as_ = (int(r.home_score), int(r.away_score)) if has_score else (None, None)
        sw = so_key.get((r.date, cn(r.home_team), cn(r.away_team)))
        winner = None
        if has_score:
            winner = "home" if hs > as_ else "away" if as_ > hs else ("draw" if sw is None else ("home" if cn(sw) == cn(r.home_team) else "away"))
        new_rows.append(dict(
            match_id=match_id(r.season_id, r.date, r.home_team, r.away_team), competition_id=r.cid, season_id=r.season_id,
            stage=None, stage_raw=None, group=None, matchday=None, leg=None,
            home_team_raw=r.home_team, away_team_raw=r.away_team, match_date=r.date,
            venue_raw=f"{r.city}, {r.country}", home_score=hs, away_score=as_,
            score_basis="unspecified_full_time_incl_extra_time_excl_shootout" if has_score else None,
            went_extra_time=None, score_raw=f"{hs}-{as_}" if has_score else None,
            score_note=("shoot-out winner: " + sw) if sw else None,
            primary_provider="martj42", provider_match_ids="{}",
            source_url=f"https://github.com/martj42/international_results/blob/master/results.csv#L{r.csv_line}",
            source_line=r.csv_line, retrieval_timestamp=retrieved, date_check="csv_iso",
            match_status="completed" if has_score else "scheduled", winner=winner))
    new = pd.DataFrame(new_rows)
    for c in m.columns:
        if c not in new.columns:
            new[c] = None
    new = new[m.columns]
    for c in ("home_score", "away_score", "matchday", "leg", "source_line"):
        new[c] = new[c].astype("Int64")
    out = pd.concat([m, new], ignore_index=True)
    out = out.sort_values(["competition_id", "season_id", "match_date", "kickoff_time_local", "match_id"]).reset_index(drop=True)
    out.to_parquet(PROC / "matches.parquet", index=False)
    out.to_csv(PROC / "matches.csv", index=False)
    pd.DataFrame(conflicts, columns=["season_id", "our_date", "martj42_date", "match", "ours", "martj42"]).to_csv(DATA / "quality" / "martj42_vs_matches_conflicts.csv", index=False)
    pd.DataFrame(ambiguous, columns=["date", "home", "away", "season"]).to_csv(DATA / "quality" / "martj42_ambiguous_links.csv", index=False)
    pd.DataFrame(unlinked, columns=["season_id", "date", "home", "away", "score"]).to_csv(DATA / "quality" / "martj42_unlinked_in_held_seasons.csv", index=False)
    linked = sum(1 for v in links.values() if v is not None and v[0] == "one")
    return out, new, conflicts, linked, ambiguous + [dict(unlinked=u) for u in unlinked][:0] if False else (out, new, conflicts, linked, ambiguous, unlinked)[:5]


def goal_events(matches: pd.DataFrame) -> pd.DataFrame:
    """Goal events for ALL in-scope matches; the caller decides which matches get them (provider priority).
    `team` in goalscorers.csv is the credited team (verified: with this reading all 1,463 matches that list
    scorers reproduce their score exactly), so an own goal's player belongs to the opponent."""
    res, so, gs = load()
    idx = {}
    for r in matches.itertuples():
        for dd in (0, 1, -1):
            idx.setdefault((r.match_date.toordinal() + dd, frozenset((cn(r.home_team_raw), cn(r.away_team_raw)))), []).append(r)
    gs = gs.reset_index().rename(columns={"index": "row"})
    rows = []
    n = {}
    for r in gs.itertuples():
        cands = idx.get((r.date.toordinal(), frozenset((cn(r.home_team), cn(r.away_team)))), [])
        exact = [c for c in cands if c.match_date == r.date] or cands
        if len(exact) != 1:
            continue
        mt = exact[0]
        n[mt.match_id] = n.get(mt.match_id, 0) + 1
        credited_home = cn(r.team) == cn(mt.home_team_raw)
        rows.append(dict(
            event_id=f"MJ-{mt.match_id}-g{n[mt.match_id]}", match_id=mt.match_id, event_type="goal",
            detail_type="own_goal" if r.own_goal else ("penalty" if r.penalty else None), player_id=None,
            player_name_raw=r.scorer, team_id=mt.home_team_id if credited_home else mt.away_team_id,
            minute=int(r.minute) if pd.notna(r.minute) else None, minute_added=None, second=None, period=None,
            timestamp=None, location_x=None, location_y=None, end_location_x=None, end_location_y=None, outcome="Goal",
            related_player_id=None, assist_name_raw=r.assist if pd.notna(r.assist) else None, card=None, xg=None,
            is_goal=True, is_penalty=bool(r.penalty) or None, is_own_goal=bool(r.own_goal) or None,
            source_id=f"goalscorers.csv#L{r.row + 2}", provider="martj42", coordinate_system=None, tags="[]",
            source_url=f"https://github.com/martj42/international_results/blob/master/goalscorers.csv#L{r.row + 2}",
            _credited_home=credited_home))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    (DATA / "quality").mkdir(exist_ok=True)
    out, new, conflicts, linked, amb = run()
    unl = pd.read_csv(DATA / "quality" / "martj42_unlinked_in_held_seasons.csv")
    print("martj42 rows in scope:", len(load()[0]), "| linked to existing matches:", linked, "| NEW matches added:", len(new),
          "| score/date conflicts:", len(conflicts), "| ambiguous links:", len(amb), "| unlinked rows in seasons we already hold:", len(unl))
    print(unl.to_string() if len(unl) else "")
    print(new.groupby("season_id").size().to_string())
    print(pd.DataFrame(conflicts).head(15).to_string() if conflicts else "no conflicts")
