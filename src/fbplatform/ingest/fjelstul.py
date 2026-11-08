"""Fjelstul World Cup Database (CC BY-SA 4.0) - men's World Cups 2002-2022.

Attribution (required): Fjelstul, Joshua C. "The Fjelstul World Cup Database v.1.2.0." July 19, 2023.
https://www.github.com/jfjelstul/worldcup  - licence CC BY-SA 4.0: derived data carries the same licence.

Provides for every match: goals (minute + stoppage, penalty/own-goal), bookings, substitutions,
appearances (starter/substitute + position), referee, shoot-out kicks. Not provided: coordinates,
passes, xG, minutes played (so none are derived here).
Rules: events are written only for matches that have no richer provider (StatsBomb/Wyscout); for the
others Fjelstul is used to validate. Nothing is overwritten; disagreements are reported.
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from ..config import DATA
from .build import PROC, norm
from .martj42 import cn_strict as cn

RAWDIR = DATA / "raw" / "fjelstul"
BASE = "https://github.com/jfjelstul/worldcup/blob/master/data-csv"
PERIOD = {"first half": 1, "second half": 2, "extra time, first half": 3, "extra time, second half": 4,
          "penalty shootout": 5, "extra time": 3}


def _csv(name):
    return pd.read_csv(RAWDIR / f"{name}.csv")


def team_index():
    t = pd.read_parquet(PROC / "teams.parquet")
    a = pd.read_csv(PROC / "team_aliases.csv")
    idx = {}
    for r in t[t.team_type == "national"].itertuples():
        idx[cn(r.team_name)] = r.team_id
    for r in a.itertuples():
        if r.team_id.startswith("T-NAT"):
            idx.setdefault(cn(r.alias), r.team_id)
    return idx


def link_matches(fj: pd.DataFrame, ours: pd.DataFrame, tid):
    out, unlinked = {}, []
    ours = ours[ours.competition_id == "WC"]
    by = {}
    for r in ours.itertuples():
        by.setdefault((r.season_id, frozenset((r.home_team_id, r.away_team_id))), []).append(r)
    for r in fj.itertuples():
        d = date.fromisoformat(r.match_date)
        key = (f"WC-{d.year}", frozenset((tid.get(cn(r.home_team_name)), tid.get(cn(r.away_team_name)))))
        c = [x for x in by.get(key, []) if abs((x.match_date - d).days) <= 1]
        if len(c) == 1:
            out[r.match_id] = c[0]
        else:
            unlinked.append(dict(fj_match=r.match_id, name=r.match_name, date=r.match_date, candidates=len(c)))
    return out, unlinked


def run():
    tid = team_index()
    m = pd.read_parquet(PROC / "matches.parquet")
    fm = _csv("matches")
    fm = fm[fm.tournament_id.isin([f"WC-{y}" for y in (2002, 2006, 2010, 2014, 2018, 2022)])]
    link, unlinked = link_matches(fm, m, tid)
    prov_full = set(pd.read_parquet(PROC / "events.parquet", columns=["match_id"]).match_id) | \
        set(pd.read_parquet(PROC / "wyscout" / "events_wyscout.parquet", columns=["match_id"]).match_id)
    now = pd.Timestamp.utcnow().isoformat()

    # ---- cross-check scores / extra time / penalties
    conflicts = []
    for r in fm.itertuples():
        o = link.get(r.match_id)
        if o is None:
            continue
        a = (int(r.home_team_score), int(r.away_team_score))
        same_side = tid.get(cn(r.home_team_name)) == o.home_team_id
        b = (int(o.home_score), int(o.away_score)) if same_side else (int(o.away_score), int(o.home_score))
        pens = (int(r.home_team_score_penalties), int(r.away_team_score_penalties))
        opens = (o.home_pen, o.away_pen) if same_side else (o.away_pen, o.home_pen)
        if a != b or (r.penalty_shootout and pd.notna(opens[0]) and pens != (int(opens[0]), int(opens[1]))):
            conflicts.append(dict(season=o.season_id, match=r.match_name, fjelstul=f"{a} pens {pens}", ours=f"{b} pens {opens}"))

    # ---- referees (fill only where we have none)
    ref = _csv("referee_appearances")
    ref["name"] = (ref.given_name.fillna("") + " " + ref.family_name.fillna("")).str.strip()
    ref["ref"] = ref.name + " (" + ref.country_name + ")"
    refmap = {link[r.match_id].match_id: r.ref for r in ref.itertuples() if r.match_id in link}

    ev = []

    def base(r, mid):
        return dict(match_id=mid, provider="fjelstul", coordinate_system=None, location_x=None, location_y=None,
                    end_location_x=None, end_location_y=None, timestamp=None, second=None, xg=None, tags="[]")

    pname = lambda r: (str(r.given_name) if pd.notna(r.given_name) and r.given_name != "not applicable" else "") + " " + str(r.family_name)

    def team_of(code_name):
        return tid.get(cn(code_name))

    goals = _csv("goals")
    for r in goals[goals.match_id.isin(link)].itertuples():
        o = link[r.match_id]
        if o.match_id in prov_full:
            continue
        ev.append({**base(r, o.match_id), "event_id": f"FJ-{r.goal_id}", "event_type": "goal",
                   "detail_type": "own_goal" if r.own_goal else ("penalty" if r.penalty else None),
                   "player_id": f"P-FJ-{r.player_id[2:]}", "player_name_raw": pname(r).strip(), "team_id": team_of(r.team_name),
                   "minute": int(r.minute_regulation), "minute_added": int(r.minute_stoppage) or None,
                   "period": PERIOD.get(r.match_period), "outcome": "Goal", "related_player_id": None, "card": None,
                   "is_goal": True, "is_penalty": bool(r.penalty) or None, "is_own_goal": bool(r.own_goal) or None,
                   "source_id": r.goal_id, "source_url": f"{BASE}/goals.csv"})
    book = _csv("bookings")
    for r in book[book.match_id.isin(link)].itertuples():
        o = link[r.match_id]
        if o.match_id in prov_full:
            continue
        card = "Second Yellow" if r.second_yellow_card else ("Red Card" if r.red_card else "Yellow Card")
        ev.append({**base(r, o.match_id), "event_id": f"FJ-{r.booking_id}", "event_type": "card", "detail_type": card,
                   "player_id": f"P-FJ-{r.player_id[2:]}", "player_name_raw": pname(r).strip(), "team_id": team_of(r.team_name),
                   "minute": int(r.minute_regulation), "minute_added": int(r.minute_stoppage) or None,
                   "period": PERIOD.get(r.match_period), "outcome": None, "related_player_id": None, "card": card,
                   "is_goal": None, "is_penalty": None, "is_own_goal": None, "source_id": r.booking_id,
                   "source_url": f"{BASE}/bookings.csv"})
    # substitutions: pair the 'going off' and 'coming on' rows (adjacent, same match/team/minute)
    sub = _csv("substitutions")
    sub = sub[sub.match_id.isin(link)].sort_values("key_id")
    unpaired = 0
    for (mid, team, minute, per), g in sub.groupby(["match_id", "team_id", "minute_label", "match_period"], sort=False):
        offs, ons = g[g.going_off == 1].to_dict("records"), g[g.coming_on == 1].to_dict("records")
        if len(offs) != len(ons):
            unpaired += 1
        o = link[mid]
        if o.match_id in prov_full:
            continue
        for a, b in zip(offs, ons):  # rows are listed in order, so the n-th off pairs with the n-th on
            ev.append({"match_id": o.match_id, "provider": "fjelstul", "coordinate_system": None, "location_x": None,
                       "location_y": None, "end_location_x": None, "end_location_y": None, "timestamp": None,
                       "second": None, "xg": None, "tags": "[]", "event_id": f"FJ-{a['substitution_id']}",
                       "event_type": "substitution", "detail_type": None, "player_id": f"P-FJ-{a['player_id'][2:]}",
                       "player_name_raw": (str(a["given_name"]) + " " + str(a["family_name"])).replace("not applicable ", "").strip(),
                       "team_id": team_of(a["team_name"]), "minute": int(a["minute_regulation"]),
                       "minute_added": int(a["minute_stoppage"]) or None, "period": PERIOD.get(a["match_period"]),
                       "outcome": None, "related_player_id": f"P-FJ-{b['player_id'][2:]}", "card": None, "is_goal": None,
                       "is_penalty": None, "is_own_goal": None, "source_id": f"{a['substitution_id']}>{b['substitution_id']}",
                       "source_url": f"{BASE}/substitutions.csv"})
    pk = _csv("penalty_kicks")
    for r in pk[pk.match_id.isin(link)].itertuples():
        o = link[r.match_id]
        if o.match_id in prov_full:
            continue
        ev.append({**base(r, o.match_id), "event_id": f"FJ-{r.penalty_kick_id}", "event_type": "shootout_kick",
                   "detail_type": None, "player_id": f"P-FJ-{r.player_id[2:]}", "player_name_raw": pname(r).strip(),
                   "team_id": team_of(r.team_name), "minute": None, "minute_added": None, "period": 5,
                   "outcome": "Scored" if r.converted else "Missed", "related_player_id": None, "card": None,
                   "is_goal": None, "is_penalty": True, "is_own_goal": None, "source_id": r.penalty_kick_id,
                   "source_url": f"{BASE}/penalty_kicks.csv"})
    events = pd.DataFrame(ev)

    # ---- lineups (appearances) for every linked match not covered by a richer provider
    app = _csv("player_appearances")
    lu = []
    for r in app[app.match_id.isin(link)].itertuples():
        o = link[r.match_id]
        if o.match_id in prov_full:
            continue
        lu.append(dict(match_id=o.match_id, team_id=team_of(r.team_name), player_id=f"P-FJ-{r.player_id[2:]}",
                       jersey_number=int(r.shirt_number) if pd.notna(r.shirt_number) else None,
                       is_starter=bool(r.starter), appeared=True,
                       positions=json.dumps([{"position": r.position_name, "code": r.position_code}]), cards="[]",
                       minutes_played_derived=None, source_player_id=r.player_id, provider="fjelstul"))
    lineups = pd.DataFrame(lu)

    # ---- players
    pl = _csv("players")
    used = set(events.player_id.dropna()) | set(lineups.player_id)
    pl["pid"] = "P-FJ-" + pl.player_id.str[2:]
    pl = pl[pl.pid.isin(used)]
    pos = lambda r: "Goalkeeper" if r.goal_keeper else ("Defender" if r.defender else ("Midfielder" if r.midfielder else ("Forward" if r.forward else None)))
    players = pd.DataFrame([dict(
        player_id=r.pid, full_name=(r.given_name if r.given_name != "not applicable" else "") + " " + r.family_name,
        display_name=r.family_name, name_variants="[]", nationality=None,
        date_of_birth=r.birth_date if r.birth_date != "not available" else None, height_cm=None, preferred_foot=None,
        primary_position=pos(r), team_ids="[]", source_identifiers=json.dumps({"fjelstul_player_id": r.player_id}))
        for r in pl.itertuples()])
    players["full_name"] = players.full_name.str.strip()

    # ---- validation against richer providers on the same matches
    val = []
    sbev = pd.read_parquet(PROC / "events.parquet", columns=["match_id", "event_type", "card", "outcome", "period", "is_goal"])
    sbcards = sbev[sbev.card.notna()].groupby("match_id").size()
    sbsubs = sbev[sbev.event_type == "substitution"].groupby("match_id").size()
    sbgoals = sbev[(sbev.event_type == "shot") & (sbev.outcome == "Goal") & (sbev.period <= 4)].groupby("match_id").size()
    og = sbev[sbev.event_type == "own_goal_for"].groupby("match_id").size()
    fg = goals[goals.match_id.isin(link)].groupby("match_id").size()
    fb = book[book.match_id.isin(link)].groupby("match_id").size()
    fs = sub[sub.going_off == 1].groupby("match_id").size()
    for fid, o in link.items():
        if o.match_id in set(sbev.match_id):
            val.append(dict(match_id=o.match_id, season_id=o.season_id,
                            goals_fj=int(fg.get(fid, 0)), goals_sb=int(sbgoals.get(o.match_id, 0) + og.get(o.match_id, 0)),
                            cards_fj=int(fb.get(fid, 0)), cards_sb=int(sbcards.get(o.match_id, 0)),
                            subs_fj=int(fs.get(fid, 0)), subs_sb=int(sbsubs.get(o.match_id, 0))))
    val = pd.DataFrame(val)
    out = PROC / "fjelstul"
    out.mkdir(exist_ok=True)
    events.to_parquet(out / "events_fjelstul.parquet", index=False)
    lineups.to_parquet(out / "lineups_fjelstul.parquet", index=False)
    players.to_parquet(out / "players_fjelstul.parquet", index=False)
    pd.DataFrame([dict(fj_match_id=k, match_id=v.match_id) for k, v in link.items()]).to_csv(out / "match_links.csv", index=False)
    pd.DataFrame(refmap.items(), columns=["match_id", "referee"]).to_csv(out / "referees.csv", index=False)
    # fill missing referees on the matches table (never overwrite an existing value)
    mm = pd.read_parquet(PROC / "matches.parquet")
    need = mm.referee_raw.isna() & mm.match_id.isin(refmap)
    if need.any():
        mm.loc[need, "referee_raw"] = mm.loc[need, "match_id"].map(refmap)
        mm.to_parquet(PROC / "matches.parquet", index=False)
        mm.to_csv(PROC / "matches.csv", index=False)
    (DATA / "quality").mkdir(exist_ok=True)
    pd.DataFrame(conflicts, columns=["season", "match", "fjelstul", "ours"]).to_csv(DATA / "quality" / "fjelstul_vs_matches_conflicts.csv", index=False)
    pd.DataFrame(unlinked, columns=["fj_match", "name", "date", "candidates"]).to_csv(DATA / "quality" / "fjelstul_unlinked.csv", index=False)
    val.to_csv(DATA / "quality" / "fjelstul_vs_statsbomb.csv", index=False)
    return events, lineups, players, link, unlinked, conflicts, val, unpaired


if __name__ == "__main__":
    ev, lu, pl, link, unl, conf, val, unp = run()
    print("fjelstul WC matches linked:", len(link), "| unlinked:", len(unl), "| score/pen conflicts:", len(conf), "| unpaired sub groups:", unp)
    print(len(ev), "events", ev.event_type.value_counts().to_dict(), "|", len(lu), "lineup rows |", len(pl), "players")
    if len(val):
        print("vs StatsBomb on", len(val), "matches: goals equal", int((val.goals_fj == val.goals_sb).sum()), "| cards equal", int((val.cards_fj == val.cards_sb).sum()), "| subs equal", int((val.subs_fj == val.subs_sb).sum()))
    if conf:
        print(pd.DataFrame(conf).head(10).to_string())
    if unl:
        print(pd.DataFrame(unl).head(10).to_string())
