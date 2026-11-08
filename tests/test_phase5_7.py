import json

import pandas as pd
import pytest

from fbplatform.config import DATA
from fbplatform.ingest.statsbomb_events import parse_events, parse_lineups, span_minutes
from fbplatform.ingest.teams import CLUB_ALIASES, PLACEHOLDER, build_teams

P = DATA / "processed"


def _mk(rows):
    return pd.DataFrame(rows, columns=["competition_id", "season_id", "home_team_raw", "away_team_raw",
                                       "home_team_country_code", "away_team_country_code"])


def test_placeholders_never_become_teams():
    for s in ("A1", "3rd Group A/B/C", "Winner Match 37", "Runner-up Group B", "W49"):
        assert PLACEHOLDER.match(s)
    for s in ("Australia", "Austria", "Wales", "Spain"):
        assert not PLACEHOLDER.match(s)
    m = _mk([("EURO", "EURO-2028", "A1", "Winner Match 37", None, None)])
    m = m.assign(match_id="x")
    t, a, rv, m2 = build_teams(m, {})
    assert len(t) == 0 and m2.home_team_id.isna().all()


def test_similar_but_different_teams_are_not_merged():
    m = _mk([("WC", "WC-2022", "Australia", "Austria", None, None),
             ("WC", "WC-2022", "Iran", "Iraq", None, None),
             ("UCL", "UCL-2015-16", "Sporting Clube de Portugal", "Sporting Clube de Braga", "POR", "POR"),
             ("UCL", "UCL-2015-16", "Manchester City", "Manchester United", "ENG", "ENG")]).assign(match_id="x")
    t, a, rv, m2 = build_teams(m, {})
    assert len(t) == 8


def test_aliases_merge_and_no_code_name_joins_unique_club():
    m = _mk([("UCL", "UCL-2012-13", "Bayern München", "Juventus", "GER", "ITA"),
             ("UCL", "UCL-2013-14", "FC Bayern München", "Juventus FC", "GER", "ITA"),
             ("UCL", "UCL-2016-17", "Bayern Munich", "Liverpool", None, None)]).assign(match_id="x")
    t, a, rv, m2 = build_teams(m, {})
    assert m2.home_team_id.nunique() == 1  # all three Bayern spellings
    assert m2.loc[2, "home_team_id"] == m2.loc[0, "home_team_id"]
    assert "R4_no_code_unique_stripped_match" in set(a.rule) or "R1_alias" in set(a.rule)


def test_alias_table_has_no_cross_club_collisions():
    seen = {}
    for canon, vs in CLUB_ALIASES.items():
        for v in [canon] + vs:
            assert seen.setdefault(v.lower(), canon) == canon, v


def test_span_minutes_ignores_overlapping_intervals():
    pos = [{"from": "00:00", "to": "115:26"}, {"from": "62:25", "to": None}]
    assert span_minutes(pos, 120.0) == 120.0           # not 175.1
    assert span_minutes([], 95.0) == 0.0               # unused substitute
    assert span_minutes([{"from": "61:00", "to": None}], 94.5) == 33.5


def test_parse_events_shot_pass_and_shootout_fields():
    ev = [
        {"id": "p1", "index": 1, "period": 1, "timestamp": "00:10:00.000", "minute": 10, "second": 0,
         "type": {"name": "Pass"}, "team": {"id": 1}, "player": {"id": 7}, "location": [60.0, 40.0],
         "pass": {"recipient": {"id": 9}, "end_location": [100.0, 40.0], "shot_assist": True, "goal_assist": True}},
        {"id": "s1", "index": 2, "period": 1, "timestamp": "00:10:05.000", "minute": 10, "second": 5,
         "type": {"name": "Shot"}, "team": {"id": 1}, "player": {"id": 9}, "location": [110.0, 40.0],
         "shot": {"statsbomb_xg": 0.4, "outcome": {"name": "Goal"}, "key_pass_id": "p1", "type": {"name": "Open Play"}}},
        {"id": "f1", "index": 3, "period": 2, "timestamp": "00:50:00.000", "minute": 50, "second": 0,
         "type": {"name": "Foul Committed"}, "team": {"id": 2}, "player": {"id": 4},
         "foul_committed": {"card": {"name": "Yellow Card"}}},
    ]
    rows = parse_events(ev, "M1", {1: "T1", 2: "T2"})
    p, s, f = rows
    assert p["is_assist"] and p["is_key_pass"] and p["related_player_id"] == "P-SB-9" and p["end_location_x"] == 100.0
    assert s["is_goal"] and s["xg"] == 0.4 and s["related_player_id"] == "P-SB-7"  # passer, via key_pass_id
    assert f["card"] == "Yellow Card" and f["is_goal"] is None and f["xg"] is None   # nothing fabricated
    assert all(r["event_id"].startswith("SB-") and r["source_id"] for r in rows)


def test_parse_lineups_flags_starters():
    lu = [{"team_id": 1, "lineup": [
        {"player_id": 7, "player_name": "A B", "player_nickname": None, "jersey_number": 9, "country": {"name": "X"},
         "positions": [{"position": "Striker", "from": "00:00", "to": None, "start_reason": "Starting XI", "end_reason": "Final Whistle"}]},
        {"player_id": 8, "player_name": "C D", "jersey_number": 12, "country": {"name": "X"}, "positions": []}]}]
    rows, players = parse_lineups(lu, "M1", {1: "T1"}, 95.0)
    assert rows[0]["is_starter"] and rows[0]["minutes_played_derived"] == 95.0
    assert rows[1]["minutes_played_derived"] == 0.0 and not rows[1]["is_starter"] is False


need = pytest.mark.skipif(not (P / "events.parquet").exists() or not (P / "player_match_stats.parquet").exists(),
                          reason="run the ingest pipeline first")


@need
def test_events_reproduce_recorded_scores_and_known_facts():
    m = pd.read_parquet(P / "matches.parquet")
    ts = pd.read_parquet(P / "team_match_stats.parquet")
    mm = m.set_index("match_id")
    for r in ts.itertuples():
        x = mm.loc[r.match_id]
        exp = x.home_score if r.team_id == x.home_team_id else x.away_score
        assert r.goals_for_incl_own_goals == exp
    ps = pd.read_parquet(P / "player_match_stats.parquet").merge(m[["match_id", "season_id"]], on="match_id")
    pl = pd.read_parquet(P / "players.parquet").set_index("player_id")
    top = ps[ps.season_id == "WC-2022"].groupby("player_id").goals.sum().sort_values(ascending=False)
    assert top.iloc[0] == 8 and "Mbapp" in pl.loc[top.index[0], "full_name"]   # shoot-out goals excluded


@need
def test_events_players_teams_referential_integrity():
    e = pd.read_parquet(P / "events.parquet")
    p = pd.read_parquet(P / "players.parquet")
    t = pd.read_parquet(P / "teams.parquet")
    m = pd.read_parquet(P / "matches.parquet")
    assert e.event_id.is_unique
    assert e.player_id.dropna().isin(p.player_id).all()
    assert e.team_id.isin(t.team_id).all() and e.match_id.isin(m.match_id).all()
    assert not any("var" in x for x in e.event_type.unique())         # source has no VAR events
    assert e.location_x.dropna().between(0, 121).all() and e.location_y.dropna().between(0, 81).all()
    assert m[["home_team_id", "away_team_id"]].stack().isin(t.team_id).all()
    lu = pd.read_parquet(P / "lineups.parquet")
    assert lu.minutes_played_derived.max() <= 130
    assert (lu[lu.is_starter == True].groupby(["match_id", "team_id"]).size() == 11).all()


# ---------------- goal events (OpenFootball) and Wyscout ----------------
from fbplatform.ingest import goals as G
from fbplatform.ingest.wyscout import parse_events as wy_parse


def test_goal_text_parser_variants():
    assert [(g["player_name_raw"], g["minute"], g["minute_added"], g["detail_type"]) for g in
            G.parse_part("Fredrik Ljungberg 32, Henrik Larsson 57, 58, Zlatan Ibrahimovic 78pen, Marcus Allbäck 90+1")] == [
        ("Fredrik Ljungberg", 32, None, None), ("Henrik Larsson", 57, None, None), ("Henrik Larsson", 58, None, None),
        ("Zlatan Ibrahimovic", 78, None, "penalty"), ("Marcus Allbäck", 90, 1, None)]
    g = G.parse_part("Palmer 13' (o.g.) Páez 45+4' (pen.) Minda 90+1'")
    assert [(x["player_name_raw"], x["detail_type"]) for x in g] == [("Palmer", "own_goal"), ("Páez", "penalty"), ("Minda", None)]


def test_goal_side_attribution_by_semicolon_and_score():
    raw = "June 12   A  1-2 B\n(Karagounis 7; Basinas 51pen)"
    h, a, _ = G.from_txt(raw, 1, 2)
    assert (len(h), len(a)) == (1, 1) and a[0]["detail_type"] == "penalty"
    h, a, _ = G.from_txt("x  0-1 y\n(Charisteas 65)", 0, 1)           # only one part: away scored
    assert (len(h), len(a)) == (0, 1)
    assert G.from_txt("x  2-1 y\n(Someone 5, Other 9, Third 80)", 2, 1)[0] == "ambiguous"  # both scored, no ';'


def test_json_goal_offset_and_own_goal_beneficiary():
    raw = json.dumps({"team1": "A", "team2": "B", "goals1": [{"name": "X", "minute": "90", "offset": 5}],
                      "goals2": [{"name": "Y", "minute": "10", "owngoal": True}]})
    h, a, _ = G.from_json(raw)
    assert h[0]["minute_added"] == 5 and a[0]["detail_type"] == "own_goal"


def test_wyscout_goal_flag_not_on_goalkeeper_mirror():
    tags = {101: "Goal", 1801: "Accurate"}
    ev = [{"id": 1, "eventName": "Shot", "subEventName": "Shot", "tags": [{"id": 101}], "playerId": 5, "teamId": 10,
           "matchPeriod": "2H", "eventSec": 125.5, "positions": [{"x": 90, "y": 50}]},
          {"id": 2, "eventName": "Save attempt", "subEventName": "Reflexes", "tags": [{"id": 101}], "playerId": 6,
           "teamId": 11, "matchPeriod": "2H", "eventSec": 125.9, "positions": [{"x": 5, "y": 50}]}]
    s, k = wy_parse(ev, "M", tags, {10: "T10", 11: "T11"})
    assert s["is_goal"] is True and s["outcome"] == "Goal" and (s["minute"], s["second"], s["period"]) == (47, 5, 2)
    assert k["is_goal"] is None and k["outcome"] == "Goal conceded"
    assert s["xg"] is None and s["coordinate_system"] == "wyscout_pct_0_100"


A = DATA / "processed" / "events_all.parquet"


@pytest.mark.skipif(not A.exists(), reason="run the pipeline first")
def test_unified_tables_invariants():
    ev = pd.read_parquet(A)
    m = pd.read_parquet(P / "matches.parquet")
    cov = pd.read_csv(P / "match_event_coverage.csv")
    assert ev.event_id.is_unique
    assert ev.match_id.isin(m.match_id).all()
    assert set(ev.provider) == {"statsbomb", "wyscout", "fjelstul", "openfootball", "martj42", "wikipedia"}
    # no double counting: a match with full events (StatsBomb / Wyscout) has no other provider, and goals, cards and
    # substitutions each come from exactly ONE provider per match (goals may come from martj42, cards from Wikipedia)
    full = set(ev[ev.provider.isin(["statsbomb", "wyscout"])].match_id)
    assert (ev[ev.match_id.isin(full)].groupby("match_id").provider.nunique() == 1).all()
    cls = ev[ev.event_type.isin(["goal", "card", "substitution"])]
    assert (cls.groupby(["match_id", "event_type"]).provider.nunique() == 1).all()
    goal_level = ev[ev.provider.isin(["openfootball", "martj42", "fjelstul"])]
    assert goal_level.xg.isna().all() and goal_level.location_x.isna().all()      # never fabricated
    assert set(cov[cov.event_coverage == "wyscout_full_events"].season_id) == {"EURO-2016"}
    assert len(cov) == (m.match_status == "completed").sum()
    ts = pd.read_parquet(P / "team_match_stats_all.parquet")
    mm = m.set_index("match_id")
    for r in ts.itertuples():
        x = mm.loc[r.match_id]
        assert r.goals_for_incl_own_goals == (x.home_score if r.team_id == x.home_team_id else x.away_score)
    wy = ts[ts.provider == "wyscout"]
    assert wy.tackles.isna().all() and wy.xg.isna().all()               # undefined for Wyscout -> null, not 0
    pl = pd.read_parquet(P / "players_all.parquet")
    assert pl.player_id.is_unique
    links = pd.read_csv(P / "player_links.csv")
    assert links.source_id.is_unique and links.canonical_id.isin(pl.player_id).all()
    assert not links.source_id.isin(pl.player_id).any()          # linked ids no longer exist as separate players


from fbplatform.ingest import martj42 as MJ


def test_serbia_distinct_in_strict_key_but_merged_for_linking_only():
    assert MJ.cn_strict("Serbia") != MJ.cn_strict("Serbia and Montenegro")
    assert MJ.cn("Serbia") == MJ.cn("Serbia and Montenegro")
    assert MJ.cn("USA") == MJ.cn("United States") and MJ.cn("Côte d'Ivoire") == MJ.cn("Ivory Coast")


def test_unl_windows_cover_playoffs():
    from datetime import date
    assert MJ.season_for("UNL", date(2022, 3, 24)) == "UNL-2020-21"   # 2022 relegation play-offs
    assert MJ.season_for("UNL", date(2024, 3, 21)) == "UNL-2022-23"
    assert MJ.season_for("EURO", date(2021, 6, 11)) == "EURO-2020" and MJ.season_for("WC", date(2006, 6, 9)) == "WC-2006"


@pytest.mark.skipif(not (P / "fjelstul" / "events_fjelstul.parquet").exists(), reason="run the pipeline first")
def test_fjelstul_matches_validated_against_independent_sources():
    qd = DATA / "quality"
    assert len(pd.read_csv(qd / "fjelstul_unlinked.csv")) == 0
    assert len(pd.read_csv(qd / "fjelstul_vs_matches_conflicts.csv")) == 0
    v = pd.read_csv(qd / "fjelstul_vs_statsbomb.csv")
    assert (v.goals_fj == v.goals_sb).all() and (v.subs_fj == v.subs_sb).all()   # 128/128 each
    assert (v.cards_fj == v.cards_sb).mean() > 0.8                                # sources genuinely differ on some cards
