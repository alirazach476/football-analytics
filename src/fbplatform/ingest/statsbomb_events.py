"""Phase 5b/6/7: StatsBomb lineups, players and event data (only where the source provides it).

Nothing is derived beyond arithmetic on source fields:
  * event rows keep StatsBomb's own type names; extra columns are flags read directly from source
    fields (goal = shot outcome "Goal", key pass = pass.shot_assist/goal_assist, ...).
  * coordinates / xG are copied verbatim, null where the source has none.
  * VAR decisions: StatsBomb open data has no VAR event type -> zero rows, reported in availability.
Raw downloads are not cached for events (800 MB uncompressed); instead each fetch is logged with its
SHA-256 in data/raw/manifest.jsonl and each parsed match is checkpointed in data/staging/ so a
failed run resumes where it stopped.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata

import pandas as pd

from ..config import DATA
from ..http import HttpClient
from ..sources.statsbomb import RAW as SB_RAW
from .build import PROC

log = logging.getLogger("fbplatform.events")
STAGE = DATA / "staging" / "statsbomb"


def _snake(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _xy(loc, i):
    return float(loc[i]) if isinstance(loc, list) and len(loc) > i else None


def _mm(ts):
    m = re.match(r"(\d+):(\d+)", ts or "")
    return int(m[1]) + int(m[2]) / 60 if m else None


def parse_events(events: list, match_id: str, team_map: dict) -> list[dict]:
    by_uuid = {e["id"]: e for e in events}
    rows = []
    for e in events:
        tname = e["type"]["name"]
        sub = e.get(_snake(tname).replace("goal_keeper", "goalkeeper")) or e.get(_snake(tname)) or {}
        if tname == "Goal Keeper":
            sub = e.get("goalkeeper", {})
        if tname == "50/50":
            sub = e.get("50_50", {})
        outcome = (sub.get("outcome") or {}).get("name") if isinstance(sub, dict) else None
        detail = (sub.get("type") or {}).get("name") if isinstance(sub, dict) else None
        card = None
        if tname in ("Foul Committed", "Bad Behaviour") and isinstance(sub, dict):
            card = (sub.get("card") or {}).get("name")
        related = None
        if tname == "Pass":
            related = (sub.get("recipient") or {}).get("id")
        elif tname == "Substitution":
            related = (sub.get("replacement") or {}).get("id")
        elif tname == "Shot" and sub.get("key_pass_id") in by_uuid:
            related = (by_uuid[sub["key_pass_id"]].get("player") or {}).get("id")
        end = sub.get("end_location") if isinstance(sub, dict) else None
        p = e.get("player") or {}
        rows.append(dict(
            event_id="SB-" + e["id"], match_id=match_id, event_type=_snake(tname), detail_type=detail,
            player_id=f"P-SB-{p['id']}" if p else None, team_id=team_map.get(e["team"]["id"]),
            timestamp=e.get("timestamp"), minute=e.get("minute"), second=e.get("second"), period=e.get("period"),
            location_x=_xy(e.get("location"), 0), location_y=_xy(e.get("location"), 1),
            end_location_x=_xy(end, 0), end_location_y=_xy(end, 1),
            outcome=outcome, related_player_id=f"P-SB-{related}" if related else None,
            source_id=e["id"], source_event_index=e.get("index"),
            xg=sub.get("statsbomb_xg") if tname == "Shot" else None, card=card,
            is_goal=(tname == "Shot" and outcome == "Goal") or None,
            is_penalty=(tname == "Shot" and detail == "Penalty") or None,
            is_key_pass=(bool(sub.get("shot_assist") or sub.get("goal_assist")) or None) if tname == "Pass" else None,
            is_assist=(bool(sub.get("goal_assist")) or None) if tname == "Pass" else None,
            is_corner=(detail == "Corner") or None if tname == "Pass" else None,
            under_pressure=e.get("under_pressure"), play_pattern=(e.get("play_pattern") or {}).get("name"),
            position=(e.get("position") or {}).get("name")))
    return rows


def span_minutes(pos: list, match_end: float | None):
    """Minutes on the pitch = first entry to last exit. StatsBomb position intervals can overlap
    (a tactical shift entry overlapping the previous one), so intervals are NOT summed.
    No positions = never appeared = 0. None if a bound cannot be read."""
    if not pos:
        return 0.0
    a = [_mm(q.get("from")) for q in pos]
    b = [(_mm(q.get("to")) if q.get("to") else match_end) for q in pos]
    if any(x is None for x in a + b):
        return None
    return round(max(b) - min(a), 1)


def parse_lineups(lineups: list, match_id: str, team_map: dict, match_end: float | None):
    lu, pl = [], []
    for t in lineups:
        tid = team_map.get(t["team_id"])
        for p in t["lineup"]:
            pos = p.get("positions") or []
            mins = span_minutes(pos, match_end)
            lu.append(dict(match_id=match_id, team_id=tid, player_id=f"P-SB-{p['player_id']}",
                           jersey_number=p.get("jersey_number"),
                           is_starter=(pos[0].get("start_reason") == "Starting XI") if pos else None,
                           positions=json.dumps([{k: q.get(k) for k in ("position", "from", "to", "start_reason", "end_reason")} for q in pos]),
                           minutes_played_derived=mins, cards=json.dumps(p.get("cards") or []),
                           source_player_id=p["player_id"]))
            pl.append(dict(player_id=f"P-SB-{p['player_id']}", full_name=p["player_name"],
                           display_name=p.get("player_nickname") or p["player_name"],
                           nationality=(p.get("country") or {}).get("name"), team_id=tid,
                           positions=[q["position"] for q in pos]))
    return lu, pl


def run(limit: int | None = None):
    STAGE.mkdir(parents=True, exist_ok=True)
    m = pd.read_parquet(PROC / "matches.parquet")
    sr = pd.read_parquet(PROC / "source_records.parquet")
    teams = pd.read_parquet(PROC / "teams.parquet")
    team_map = {}
    for r in teams.itertuples():
        d = json.loads(r.source_identifiers)
        if "statsbomb_team_id" in d:
            team_map[d["statsbomb_team_id"]] = r.team_id
    sb = sr[sr.provider == "statsbomb"].drop_duplicates("provider_match_id")
    c = HttpClient("statsbomb", 0.05)
    todo = list(sb.itertuples())[:limit]
    for n, r in enumerate(todo, 1):
        f = STAGE / f"{r.provider_match_id}.parquet"
        if f.exists():
            continue
        ev_url = f"{SB_RAW}/events/{r.provider_match_id}.json"
        lu_url = f"{SB_RAW}/lineups/{r.provider_match_id}.json"
        ev = c.get(ev_url, cache=False)
        lu = c.get(lu_url)
        if ev is None:
            log.warning("no events file for %s (%s)", r.provider_match_id, r.season_id)
            pd.DataFrame().to_parquet(f)
            continue
        events = json.loads(ev.content)
        end = max([e["minute"] + e["second"] / 60 for e in events if e["period"] <= 4] or [0])
        rows = parse_events(events, r.match_id, team_map)
        lus, pls = parse_lineups(json.loads(lu.content), r.match_id, team_map, end) if lu is not None else ([], [])
        pd.DataFrame(rows).assign(_kind="event").to_parquet(STAGE / f"{r.provider_match_id}.events.tmp")
        pd.DataFrame(lus).assign(_kind="lineup").to_parquet(STAGE / f"{r.provider_match_id}.lineups.tmp")
        pd.DataFrame([{**p, "positions": json.dumps(p["positions"])} for p in pls]).to_parquet(STAGE / f"{r.provider_match_id}.players.tmp")
        pd.DataFrame({"done": [1]}).to_parquet(f)  # checkpoint marker written last
        if n % 20 == 0:
            log.info("%d/%d matches", n, len(todo))
    return combine()


def combine():
    ev, lu, pl = [], [], []
    for f in sorted(STAGE.glob("*.events.tmp")):
        ev.append(pd.read_parquet(f))
    for f in sorted(STAGE.glob("*.lineups.tmp")):
        lu.append(pd.read_parquet(f))
    for f in sorted(STAGE.glob("*.players.tmp")):
        pl.append(pd.read_parquet(f))
    events = pd.concat(ev, ignore_index=True).drop(columns="_kind")
    lineups = pd.concat([x for x in lu if len(x)], ignore_index=True).drop(columns="_kind")
    raw_players = pd.concat([x for x in pl if len(x)], ignore_index=True)
    # staging may hold matches that have since left the project scope: keep only current matches
    cur = set(pd.read_parquet(PROC / "matches.parquet", columns=["match_id"]).match_id)
    events, lineups = events[events.match_id.isin(cur)], lineups[lineups.match_id.isin(cur)]
    raw_players = raw_players[raw_players.player_id.isin(set(lineups.player_id))]
    end = events[events.period <= 4].assign(t=lambda d: d.minute + d.second / 60).groupby("match_id").t.max()
    lineups["minutes_played_derived"] = [span_minutes(json.loads(po), end.get(mid)) for po, mid in zip(lineups.positions, lineups.match_id)]
    lineups["appeared"] = lineups.positions != "[]"
    events.to_parquet(PROC / "events.parquet", index=False)
    lineups.to_parquet(PROC / "lineups.parquet", index=False)
    players = build_players(raw_players)
    players.to_parquet(PROC / "players.parquet", index=False)
    players.to_csv(PROC / "players.csv", index=False)
    return events, lineups, players


def _n(s):
    return re.sub(r"[^a-z ]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


def build_players(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per StatsBomb player_id. Identity = provider id only; names are never used to merge."""
    out = []
    for pid, g in raw.groupby("player_id"):
        names = g.full_name.value_counts()
        pos = pd.Series([p for lst in g.positions.map(json.loads) for p in lst])
        out.append(dict(player_id=pid, full_name=names.index[0], display_name=g.display_name.value_counts().index[0],
                        name_variants=json.dumps(sorted(set(g.full_name) - {names.index[0]}), ensure_ascii=False),
                        nationality=g.nationality.value_counts().index[0] if g.nationality.notna().any() else None,
                        date_of_birth=None, height_cm=None, preferred_foot=None,   # not in StatsBomb lineups
                        primary_position=pos.value_counts().index[0] if len(pos) else None,
                        team_ids=json.dumps(sorted(set(g.team_id.dropna()))),
                        source_identifiers=json.dumps({"statsbomb_player_id": int(pid.split("-")[-1])})))
    df = pd.DataFrame(out)
    return df


if __name__ == "__main__":
    import sys
    (DATA / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(DATA / "logs" / "pipeline.log", encoding="utf-8")])
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    e, l, p = run(lim)
    print(len(e), "events;", len(l), "lineup rows;", len(p), "players")
