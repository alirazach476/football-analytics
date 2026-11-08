"""Phase 6: team/player match statistics derived ONLY from StatsBomb event + lineup rows, plus the
field-availability report and the events-vs-score validation.

Definitions (all computed from source fields, shoot-out period 5 excluded from goals/shots):
  goals            shot with outcome "Goal"                    own_goals   event "own_goal_against"
  shots_on_target  shot outcome in Goal / Saved / Saved to Post
  passes_completed pass events with no outcome (StatsBomb leaves outcome empty for complete passes)
  pass_accuracy    passes_completed / passes   (null when no passes)
  key_passes       pass.shot_assist or goal_assist             assists   pass.goal_assist
  tackles          duel events of type "Tackle"                saves     goalkeeper events of save types
  xg               sum of shot xG                              xa        sum of xG of shots whose key pass is by the player
  yellow / red     card names; "Second Yellow" counts as one yellow and one red
Possession and anything not listed is NOT computed (null / absent), never estimated.
"""
from __future__ import annotations

import json

import pandas as pd

from ..config import DATA
from .build import PROC

QDIR = DATA / "quality"
ON_TARGET = {"Goal", "Saved", "Saved to Post"}
SAVE_TYPES = {"Save", "Shot Saved", "Penalty Saved", "Saved to Post", "Shot Saved Off Target", "Shot Saved to Post"}


def player_stats(ev: pd.DataFrame, lu: pd.DataFrame) -> pd.DataFrame:
    e = ev[(ev.period <= 4) & ev.player_id.notna()].copy()
    g = e.groupby(["match_id", "player_id", "team_id"])

    def cnt(mask):
        return e[mask].groupby(["match_id", "player_id", "team_id"]).size()

    sh = e.event_type.eq("shot")
    ps = e.event_type.eq("pass")
    stats = pd.DataFrame({
        "goals": cnt(sh & e.outcome.eq("Goal")),
        "own_goals": cnt(e.event_type.eq("own_goal_against")),
        "assists": cnt(ps & e.is_assist.eq(True)),
        "shots": cnt(sh),
        "shots_on_target": cnt(sh & e.outcome.isin(ON_TARGET)),
        "passes": cnt(ps),
        "passes_completed": cnt(ps & e.outcome.isna()),
        "key_passes": cnt(ps & e.is_key_pass.eq(True)),
        "tackles": cnt(e.event_type.eq("duel") & e.detail_type.eq("Tackle")),
        "interceptions": cnt(e.event_type.eq("interception")),
        "clearances": cnt(e.event_type.eq("clearance")),
        "blocks": cnt(e.event_type.eq("block")),
        "fouls_committed": cnt(e.event_type.eq("foul_committed")),
        "fouls_won": cnt(e.event_type.eq("foul_won")),
        "yellow_cards": cnt(e.card.isin(["Yellow Card", "Second Yellow"])),
        "red_cards": cnt(e.card.isin(["Red Card", "Second Yellow"])),
        "saves": cnt(e.event_type.eq("goal_keeper") & e.detail_type.isin(SAVE_TYPES)),
        "corners_taken": cnt(ps & e.is_corner.eq(True)),
        "offsides": cnt(e.event_type.eq("offside")),
    }).fillna(0).astype(int)
    stats["xg"] = e[sh].groupby(["match_id", "player_id", "team_id"]).xg.sum()
    # xA: xG of shots, credited to the passer recorded as the shot's related player
    xa = ev[(ev.period <= 4) & ev.event_type.eq("shot") & ev.related_player_id.notna()]
    xa = xa.groupby(["match_id", "related_player_id"]).xg.sum().rename("xa")
    stats = stats.reset_index().merge(xa, left_on=["match_id", "player_id"], right_index=True, how="left")
    stats["xg"] = stats.xg.fillna(0.0)
    stats["xa"] = stats.xa.fillna(0.0)
    stats["pass_accuracy"] = (stats.passes_completed / stats.passes).where(stats.passes > 0)
    # lineup: minutes, starter, substitutions
    pos = lu.copy()
    pos["sub_on"] = pos.positions.map(lambda s: any((p["start_reason"] or "").startswith("Substitution") for p in json.loads(s)))
    pos["sub_off"] = pos.positions.map(lambda s: any((p["end_reason"] or "").startswith("Substitution") for p in json.loads(s)))
    out = pos[["match_id", "team_id", "player_id", "jersey_number", "is_starter", "minutes_played_derived", "sub_on", "sub_off"]] \
        .merge(stats, on=["match_id", "team_id", "player_id"], how="outer")
    for c in stats.columns.difference(["match_id", "player_id", "team_id", "pass_accuracy", "xg", "xa"]):
        out[c] = out[c].fillna(0).astype(int)  # lineup players with no events: genuine zeros of recorded events
    out[["xg", "xa"]] = out[["xg", "xa"]].fillna(0.0)
    return out.rename(columns={"minutes_played_derived": "minutes_played"})


def team_stats(ps: pd.DataFrame, matches: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    cols = ["goals", "own_goals", "assists", "shots", "shots_on_target", "passes", "passes_completed", "key_passes", "tackles",
            "interceptions", "clearances", "blocks", "fouls_committed", "fouls_won", "yellow_cards", "red_cards", "saves",
            "corners_taken", "offsides", "xg", "xa"]
    t = ps.groupby(["match_id", "team_id"])[cols].sum().reset_index()
    own = t.set_index(["match_id", "team_id"]).own_goals
    # own goals count for the opponent
    opp = {}
    for r in matches.itertuples():
        opp[(r.match_id, r.home_team_id)] = r.away_team_id
        opp[(r.match_id, r.away_team_id)] = r.home_team_id
    t["goals_for_incl_own_goals"] = [g + own.get((m, opp.get((m, tid))), 0) for m, tid, g in zip(t.match_id, t.team_id, t.goals)]
    t["pass_accuracy"] = (t.passes_completed / t.passes).where(t.passes > 0)
    t["possession_pct"] = None  # not computed: no verified possession field
    t["substitutions"] = ps.groupby(["match_id", "team_id"]).sub_on.sum().reindex(pd.MultiIndex.from_frame(t[["match_id", "team_id"]])).values
    return t


def validate_goals(tstats: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """Events must reproduce the recorded on-pitch score (incl. extra time, excl. shoot-out)."""
    m = matches.set_index("match_id")
    rows = []
    for r in tstats.itertuples():
        mm = m.loc[r.match_id]
        exp = mm.home_score if r.team_id == mm.home_team_id else mm.away_score
        if pd.notna(exp) and int(exp) != r.goals_for_incl_own_goals:
            rows.append(dict(match_id=r.match_id, season_id=mm.season_id, team_id=r.team_id,
                             score_in_matches=int(exp), goals_from_events=int(r.goals_for_incl_own_goals)))
    return pd.DataFrame(rows, columns=["match_id", "season_id", "team_id", "score_in_matches", "goals_from_events"])


def availability(matches, ev, lu, ps) -> pd.DataFrame:
    rows = []
    sea = matches.set_index("match_id").season_id
    comp = matches.set_index("match_id").competition_id
    for name, df in (("matches", matches), ("events", ev), ("lineups", lu), ("player_match_stats", ps)):
        d = df.copy()
        d["season_id"] = d.season_id if name == "matches" else d.match_id.map(sea)
        d["competition_id"] = d.season_id.str.split("-").str[0]
        for (c, s), g in d.groupby(["competition_id", "season_id"]):
            for col in g.columns.difference(["season_id", "competition_id"]):
                nn = int(g[col].notna().sum())
                rows.append(dict(competition_id=c, season_id=s, table=name, field=col, rows=len(g), non_null=nn,
                                 pct_non_null=round(100 * nn / len(g), 1)))
    return pd.DataFrame(rows)


def run():
    m = pd.read_parquet(PROC / "matches.parquet")
    ev = pd.read_parquet(PROC / "events.parquet")
    lu = pd.read_parquet(PROC / "lineups.parquet")
    ps = player_stats(ev, lu)
    ts = team_stats(ps, m, ev)
    bad = validate_goals(ts, m)
    av = availability(m, ev, lu, ps)
    ps.to_parquet(PROC / "player_match_stats.parquet", index=False)
    ts.to_parquet(PROC / "team_match_stats.parquet", index=False)
    QDIR.mkdir(exist_ok=True)
    bad.to_csv(QDIR / "events_vs_score_mismatches.csv", index=False)
    av.to_csv(QDIR / "field_availability.csv", index=False)
    return ps, ts, bad, av


if __name__ == "__main__":
    ps, ts, bad, av = run()
    print(len(ps), "player-match rows;", len(ts), "team-match rows;", len(bad), "team rows where events != recorded score")
    if len(bad):
        print(bad.to_string(index=False))
