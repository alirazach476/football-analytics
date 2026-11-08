"""Wyscout public match-event dataset (Pappalardo et al. 2019, figshare, CC BY 4.0).

Attribution required: Pappalardo, L. et al. "A public data set of spatio-temporal match events in
soccer competitions", Scientific Data 6:236 (2019), https://doi.org/10.1038/s41597-019-0247-7
(figshare collection 4415000; DOIs of the files used are in data/raw/wyscout/ provenance.json).

Used for: UEFA Euro 2016 (full events, lineups, substitutions, players incl. DOB/height/foot) and
World Cup 2018 (cross-check only: StatsBomb is primary there).

Rules: tags are copied (as labels) and only mapped to flags where the tag label is unambiguous.
Coordinates stay in Wyscout's 0-100 percentage system (`coordinate_system` column); they are NOT
rescaled to StatsBomb's 120x80. Wyscout has no xG, no pass recipient and no VAR events: null/absent.
Minute/second are arithmetic on `eventSec` plus the period offset (1H 0, 2H 45, E1 90, E2 105, P 120).
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date, timedelta

import pandas as pd

from ..config import DATA
from .build import PROC, norm

W = DATA / "raw" / "wyscout"
OFFSET = {"1H": 0, "2H": 45, "E1": 90, "E2": 105, "P": 120}
PERIOD = {"1H": 1, "2H": 2, "E1": 3, "E2": 4, "P": 5}
CARD = {1701: "Red Card", 1702: "Yellow Card", 1703: "Second Yellow"}


def _snake(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def load_tags():
    with open(W / "tags2name.csv", encoding="utf-8") as f:
        return {int(r["Tag"]): r["Label"] for r in csv.DictReader(f)}


def team_lookup():
    """Wyscout team name -> our team_id via the alias table (no fuzzy matching)."""
    t = pd.read_parquet(PROC / "teams.parquet")
    a = pd.read_csv(PROC / "team_aliases.csv")
    out = {}
    for r in t.itertuples():
        out[norm(r.team_name)] = r.team_id
    for r in a.itertuples():
        out[norm(r.alias)] = r.team_id
    from .teams import NATIONAL_ALIASES
    for canon, vs in NATIONAL_ALIASES.items():
        tid = out.get(norm(canon))
        for v in vs:
            if tid:
                out.setdefault(norm(v), tid)
    return out


def parse_events(events, match_id, tags, team_id_of):
    rows = []
    for e in events:
        tg = [t["id"] for t in e.get("tags", [])]
        labels = [tags.get(i, str(i)) for i in tg]
        pos = e.get("positions") or []
        sec = float(e["eventSec"])
        per = e["matchPeriod"]
        minute = OFFSET[per] + int(sec // 60)
        card = next((CARD[i] for i in tg if i in CARD), None)
        sub = e.get("subEventName") or None
        # Wyscout tags the goal on the scoring event AND on the goalkeeper's mirrored "Save attempt" event
        scored = 101 in tg and e["eventName"] != "Save attempt"
        conceded = 101 in tg and e["eventName"] == "Save attempt"
        acc = "Accurate" if 1801 in tg else ("Not accurate" if 1802 in tg else None)
        duel = "Won" if 703 in tg else ("Lost" if 701 in tg else ("Neutral" if 702 in tg else None))
        rows.append(dict(
            event_id=f"WY-{e['id']}", match_id=match_id, event_type=_snake(e["eventName"]), detail_type=sub,
            player_id=f"P-WY-{e['playerId']}" if e.get("playerId") else None, team_id=team_id_of.get(e["teamId"]),
            timestamp=f"00:{int(sec // 60):02d}:{sec % 60:06.3f}", minute=minute, second=int(sec % 60),
            period=PERIOD[per],
            location_x=float(pos[0]["x"]) if pos else None, location_y=float(pos[0]["y"]) if pos else None,
            end_location_x=float(pos[1]["x"]) if len(pos) > 1 else None,
            end_location_y=float(pos[1]["y"]) if len(pos) > 1 else None,
            outcome="Goal" if scored else ("Goal conceded" if conceded else (duel or acc)), related_player_id=None,
            source_id=str(e["id"]), source_event_index=None, xg=None, card=card,
            is_goal=scored or None, is_penalty=(sub == "Penalty") or None,
            is_key_pass=(302 in tg or 301 in tg) or None, is_assist=(301 in tg) or None,
            is_corner=(sub == "Corner") or None, under_pressure=None, play_pattern=None, position=None,
            is_own_goal=(102 in tg) or None, tags=json.dumps(labels), provider="wyscout",
            coordinate_system="wyscout_pct_0_100"))
    return rows


FIGSHARE = {7770599: "events.zip", 7770422: "matches.zip", 7765316: "competitions.json", 7765310: "teams.json",
            7765196: "players.json", 11743818: "tags2name.csv", 11743836: "eventid2name.csv"}


def download():
    """Fetch the CC BY 4.0 files from the figshare API (skips files already present; sha256 logged)."""
    import hashlib
    import zipfile

    import requests
    from ..config import USER_AGENT
    h = {"User-Agent": USER_AGENT}
    W.mkdir(parents=True, exist_ok=True)
    (W / "extracted").mkdir(exist_ok=True)
    log = []
    for aid in FIGSHARE:
        a = requests.get(f"https://api.figshare.com/v2/articles/{aid}", headers=h, timeout=60).json()
        if a["license"]["name"] != "CC BY 4.0":
            raise RuntimeError(f"unexpected licence for {aid}: {a['license']}")
        for f in a["files"]:
            dst = W / f["name"]
            if not dst.exists():
                r = requests.get(f["download_url"], headers=h, timeout=600)
                r.raise_for_status()
                dst.write_bytes(r.content)
            log.append(dict(file=f["name"], doi=a["doi"], sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
    for z, names in (("events.zip", ["events_European_Championship.json", "events_World_Cup.json"]),
                     ("matches.zip", ["matches_European_Championship.json", "matches_World_Cup.json"])):
        with zipfile.ZipFile(W / z) as zf:
            for n in names:
                if not (W / "extracted" / n).exists():
                    zf.extract(n, W / "extracted")
    (W / "downloads.json").write_text(json.dumps(log, indent=1), encoding="utf-8")


def run():
    if not (W / "extracted" / "events_European_Championship.json").exists():
        download()
    tags = load_tags()
    m = pd.read_parquet(PROC / "matches.parquet")
    tl = team_lookup()
    players_raw = {p["wyId"]: p for p in json.load(open(W / "players.json", encoding="utf-8"))}
    wteams = {t["wyId"]: t for t in json.load(open(W / "teams.json", encoding="utf-8"))}
    ev_all, lu_all, pl_ids, subs_all, links = [], [], set(), [], []
    for comp, season, fn in (("European_Championship", "EURO-2016", "European_Championship"),
                             ("World_Cup", "WC-2018", "World_Cup")):
        wm = json.load(open(W / f"extracted/matches_{fn}.json", encoding="utf-8"))
        wev = json.load(open(W / f"extracted/events_{fn}.json", encoding="utf-8"))
        by_match = {}
        for e in wev:
            by_match.setdefault(e["matchId"], []).append(e)
        ours = m[m.season_id == season]
        for x in wm:
            tids = {int(k): v for k, v in x["teamsData"].items()}
            team_id_of = {k: tl.get(norm(wteams[k]["name"])) for k in tids}
            if None in team_id_of.values():
                raise ValueError(f"unresolved Wyscout team in {x['label']}: {team_id_of}")
            d = date.fromisoformat(x["dateutc"][:10])
            pair = set(team_id_of.values())
            cand = ours[ours.apply(lambda r: {r.home_team_id, r.away_team_id} == pair and abs((r.match_date - d).days) <= 1, axis=1)]
            if len(cand) != 1:
                raise ValueError(f"cannot link Wyscout match {x['wyId']} {x['label']} ({len(cand)} candidates)")
            mid = cand.iloc[0].match_id
            links.append(dict(match_id=mid, season_id=season, wyscout_match_id=x["wyId"], label=x["label"]))
            if season != "EURO-2016":
                # World Cup 2018: linked only (StatsBomb is primary); squads are used for player enrichment
                for td in tids.values():
                    for grp in ("lineup", "bench"):
                        pl_ids |= {p["playerId"] for p in (td.get("formation") or {}).get(grp) or []}
                continue
            evs = parse_events(by_match.get(x["wyId"], []), mid, tags, team_id_of)
            end = max([r["minute"] + r["second"] / 60 for r in evs if r["period"] <= 4] or [0])
            ev_all += evs
            for tid, td in tids.items():
                f = td.get("formation") or {}
                subs = f.get("substitutions") or []
                off = {s["playerOut"]: s["minute"] for s in subs}
                on = {s["playerIn"]: s["minute"] for s in subs}
                for s in subs:
                    subs_all.append(dict(
                        event_id=f"WY-sub-{x['wyId']}-{s['playerOut']}-{s['playerIn']}", match_id=mid,
                        event_type="substitution", detail_type=None, player_id=f"P-WY-{s['playerOut']}",
                        team_id=team_id_of[tid], timestamp=None, minute=s["minute"], second=None, period=None,
                        location_x=None, location_y=None, end_location_x=None, end_location_y=None, outcome=None,
                        related_player_id=f"P-WY-{s['playerIn']}", source_id=f"{x['wyId']}:{s['playerOut']}>{s['playerIn']}",
                        provider="wyscout", coordinate_system=None, tags="[]"))
                for grp, starter in (("lineup", True), ("bench", False)):
                    for p in f.get(grp) or []:
                        pid = p["playerId"]
                        pl_ids.add(pid)
                        appeared = starter or pid in on
                        a = 0 if starter else on.get(pid)
                        b = off.get(pid, end) if appeared else None
                        lu_all.append(dict(
                            match_id=mid, team_id=team_id_of[tid], player_id=f"P-WY-{pid}", jersey_number=None,
                            is_starter=starter, appeared=appeared, positions="[]", cards="[]",
                            minutes_played_derived=(round(max(b - a, 0), 1) if appeared and a is not None else (0.0 if not appeared else None)),
                            source_player_id=pid, provider="wyscout",
                            yellow_cards_source=int(p.get("yellowCards", 0)), red_cards_source=int(p.get("redCards", 0))))
    ev = pd.DataFrame(ev_all + subs_all)
    lu = pd.DataFrame(lu_all)
    pl = []
    for pid in sorted(pl_ids | {int(e.split("-")[-1]) for e in ev.player_id.dropna().unique() if e.startswith("P-WY-")}):
        p = players_raw.get(pid)
        if not p:
            continue
        full = " ".join(x for x in (p.get("firstName"), p.get("middleName"), p.get("lastName")) if x)
        foot = (p.get("foot") or "").lower() or None
        pl.append(dict(player_id=f"P-WY-{pid}", full_name=full, display_name=p.get("shortName") or full,
                       name_variants="[]", nationality=(p.get("passportArea") or {}).get("name"),
                       date_of_birth=p.get("birthDate") or None,
                       height_cm=float(p["height"]) if p.get("height") else None,
                       preferred_foot=foot, primary_position=(p.get("role") or {}).get("name"),
                       team_ids="[]", source_identifiers=json.dumps({"wyscout_player_id": pid})))
    pl = pd.DataFrame(pl)
    (PROC / "wyscout").mkdir(exist_ok=True)
    ev.to_parquet(PROC / "wyscout" / "events_wyscout.parquet", index=False)
    lu.to_parquet(PROC / "wyscout" / "lineups_wyscout.parquet", index=False)
    pl.to_parquet(PROC / "wyscout" / "players_wyscout.parquet", index=False)
    pd.DataFrame(links).to_csv(PROC / "wyscout" / "match_links.csv", index=False)
    (W / "provenance.json").write_text(json.dumps({
        "license": "CC BY 4.0", "citation": "Pappalardo et al., Scientific Data 6:236 (2019), doi:10.1038/s41597-019-0247-7",
        "figshare_files": {"events.zip": "10.6084/m9.figshare.7770599.v1", "matches.zip": "10.6084/m9.figshare.7770422.v1",
                           "players.json": "10.6084/m9.figshare.7765196.v3", "teams.json": "10.6084/m9.figshare.7765310.v3",
                           "tags2name.csv": "10.6084/m9.figshare.11743818.v1"}}, indent=1), encoding="utf-8")
    return ev, lu, pl, pd.DataFrame(links)


if __name__ == "__main__":
    ev, lu, pl, links = run()
    print(len(ev), "events;", len(lu), "lineup rows;", len(pl), "players;", len(links), "matches linked")
    print(ev.event_type.value_counts().to_dict())
