"""Goal events for matches WITHOUT StatsBomb event data, from scorer lines in OpenFootball files.

What this gives: scorer name (raw text), minute (+ stoppage), penalty / own-goal flag, beneficiary team.
What it does NOT give (stays null): player_id, coordinates, xG, assists, period, second, timestamp.
Own goals are listed by OpenFootball under the team that BENEFITS (verified on Germany 3-1 Portugal and
Brazil 3-1 Croatia); the scorer's own team is the opponent.
Side attribution in text files: "(home goals; away goals)". With one part only, the side is fixed by
the score (the other side scored 0); if both sides scored and there is no ';' the match is marked
`ambiguous_side` and no events are emitted for it.
Completeness is measured against the on-pitch score and reported per match; partial lists are kept as
partial, never padded.
"""
from __future__ import annotations

import json
import re

import pandas as pd

from ..config import DATA
from .build import PROC

QDIR = DATA / "quality"
MIN = re.compile(r"(?P<min>\d{1,3})(?:\+(?P<add>\d{1,2}))?'?(?:\s*(?:\((?P<f1>pen|o\.g)\.?\)|(?P<f2>pen|og)\b))?")


def parse_part(text: str) -> list[dict]:
    out, pos, last = [], 0, None
    for m in MIN.finditer(text):
        name = text[pos:m.start()].strip(" ,;")
        if name:
            last = name
        if last is None:
            pos = m.end()
            continue
        flag = (m["f1"] or m["f2"] or "").lower()
        out.append(dict(player_name_raw=last, minute=int(m["min"]), minute_added=int(m["add"]) if m["add"] else None,
                        detail_type="penalty" if flag == "pen" else ("own_goal" if flag in ("o.g", "og") else None)))
        pos = m.end()
    return out


def from_json(raw: str):
    d = json.loads(raw)
    if "goals1" not in d and "goals2" not in d:
        return None
    side = lambda lst: [dict(player_name_raw=g["name"], minute=int(re.match(r"\d+", str(g["minute"]))[0]),
                             minute_added=(int(g["offset"]) if g.get("offset") else
                                          (int(str(g["minute"]).split("+")[1]) if "+" in str(g["minute"]) else None)),
                             detail_type="penalty" if g.get("penalty") else ("own_goal" if g.get("owngoal") else None))
                        for g in lst or []]
    return side(d.get("goals1")), side(d.get("goals2")), "complete_format"


def from_txt(raw: str, hs, as_):
    lines = raw.split("\n")
    if len(lines) < 2:
        return None
    body = " ".join(x.strip() for x in lines[1:]).strip()
    if body.startswith("("):
        body = body[1:]
    if body.endswith(")"):
        body = body[:-1]
    parts = body.split(";")
    if len(parts) > 2:
        return None
    if len(parts) == 2:
        return parse_part(parts[0]), parse_part(parts[1]), "ok"
    if hs == 0 and as_ and as_ > 0:
        return [], parse_part(parts[0]), "ok"
    if as_ == 0 and hs and hs > 0:
        return parse_part(parts[0]), [], "ok"
    return "ambiguous", None, None


def build(matches: pd.DataFrame, sr: pd.DataFrame, sb_match_ids: set):
    ev, cov = [], []
    src = sr[sr.provider == "openfootball"].set_index("match_id")
    for r in matches.itertuples():
        if r.match_status != "completed":
            continue
        if r.match_id in sb_match_ids:
            cov.append(dict(match_id=r.match_id, season_id=r.season_id, event_coverage="statsbomb_full_events"))
            continue
        raw = src.raw.get(r.match_id)
        res = from_json(raw) if raw and raw.startswith("{") else (from_txt(raw, r.home_score, r.away_score) if raw else None)
        if res is None:
            scoreless = int(r.home_score) + int(r.away_score) == 0
            cov.append(dict(match_id=r.match_id, season_id=r.season_id,
                            event_coverage="goals_complete_scoreless_0-0" if scoreless else "none"))
            continue
        if res[0] == "ambiguous":
            cov.append(dict(match_id=r.match_id, season_id=r.season_id, event_coverage="goal_lines_present_but_side_ambiguous"))
            continue
        home, away, _ = res
        n = 0
        for team, goals in ((r.home_team_id, home), (r.away_team_id, away)):
            for g in goals:
                n += 1
                ev.append(dict(event_id=f"OF-{r.match_id}-g{n}", match_id=r.match_id, event_type="goal",
                               detail_type=g["detail_type"], player_id=None, player_name_raw=g["player_name_raw"],
                               team_id=team, minute=g["minute"], minute_added=g["minute_added"], second=None, period=None,
                               timestamp=None, location_x=None, location_y=None, outcome="Goal",
                               related_player_id=None, source_id=f"{r.source_url}#goal{n}", provider="openfootball",
                               source_url=r.source_url))
        exp = (int(r.home_score), int(r.away_score))
        got = (len(home), len(away))
        status = "goals_complete" if got == exp else ("goals_partial" if got[0] <= exp[0] and got[1] <= exp[1] else "goals_inconsistent")
        cov.append(dict(match_id=r.match_id, season_id=r.season_id, event_coverage=status,
                        goals_listed=sum(got), goals_in_score=sum(exp)))
    return pd.DataFrame(ev), pd.DataFrame(cov)


def validate_against_statsbomb(matches, sr, sb_events, sb_match_ids) -> pd.DataFrame:
    """Parse the same matches from OpenFootball and compare with StatsBomb goal events (test of the parser)."""
    m = matches[matches.match_id.isin(sb_match_ids)]
    ev, cov = build(m.assign(match_status="completed"), sr, set())
    g = sb_events[((sb_events.event_type == "shot") & (sb_events.outcome == "Goal") & (sb_events.period <= 4)) |
                  (sb_events.event_type == "own_goal_for")]
    g = g.assign(total=g.minute)
    rows = []
    for mid, grp in ev.groupby("match_id"):
        of_min = sorted(grp.minute + grp.minute_added.fillna(0))
        sb_min = sorted(g[g.match_id == mid].total)
        ok = len(of_min) == len(sb_min) and all(abs(a - b) <= 1 for a, b in zip(of_min, sb_min))
        rows.append(dict(match_id=mid, openfootball_goals=len(of_min), statsbomb_goals=len(sb_min), minutes_agree_within_1=ok))
    return pd.DataFrame(rows)


def run():
    m = pd.read_parquet(PROC / "matches.parquet")
    sr = pd.read_parquet(PROC / "source_records.parquet")
    sb = pd.read_parquet(PROC / "events.parquet", columns=["match_id", "event_type", "outcome", "period", "minute"])
    sbm = set(sb.match_id)
    ev, cov = build(m, sr, sbm)
    chk = validate_against_statsbomb(m, sr, sb, sbm)
    ev.to_parquet(PROC / "goal_events_openfootball.parquet", index=False)
    ev.to_csv(PROC / "goal_events_openfootball.csv", index=False)
    cov.to_csv(PROC / "match_event_coverage.csv", index=False)
    QDIR.mkdir(exist_ok=True)
    chk.to_csv(QDIR / "goal_parser_vs_statsbomb.csv", index=False)
    return ev, cov, chk


if __name__ == "__main__":
    ev, cov, chk = run()
    print(len(ev), "goal events")
    print(cov.groupby(["season_id", "event_coverage"]).size().unstack(fill_value=0).to_string())
    print("parser vs StatsBomb on", len(chk), "matches: minutes agree", int(chk.minutes_agree_within_1.sum()),
          "| goal count equal", int((chk.openfootball_goals == chk.statsbomb_goals).sum()))
