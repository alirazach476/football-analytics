"""React dashboard backend: every chart id answers, tournament pages exist for every edition, Coming soon is kept, WC 2030 has no results, no Champions League."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from fbplatform.api import charts, wc2030
from fbplatform.api.main import app

c = TestClient(app)
NEEDS_PARAMS = {"match.goal_timeline", "match.progress", "match.events", "match.shots_match", "match.net", "match.shots_team", "an.player_edition", "an.player_compare"}


@pytest.fixture(scope="module", autouse=True)
def _db():
    if not c.get("/api/health").json()["ok"]:
        pytest.skip("warehouse not running")


def test_every_chart_id_answers():
    assert len(charts.REGISTRY) >= 85
    for cid in charts.REGISTRY:
        if cid in NEEDS_PARAMS:
            continue
        r = c.post("/api/chart", json={"id": cid, "filters": {}, "params": {}})
        assert r.status_code == 200, (cid, r.text[:200])
        p = r.json()
        assert p["available"] or p["reason"], cid                      # an unavailable chart must say why


def test_unknown_chart_is_an_error_not_a_crash():
    assert c.post("/api/chart", json={"id": "nope", "filters": {}, "params": {}}).status_code in (400, 404)


def test_tournament_page_for_every_edition_and_no_ucl():
    eds = c.get("/api/tournaments").json()["editions"]
    assert len(eds) >= 29 and not any("CHAMPIONS LEAGUE" in e["competitionName"].upper() or e["competition"] == "UCL" for e in eds)
    for e in eds:
        r = c.get(f"/api/tournament/{e['seasonId']}")
        assert r.status_code == 200, e["seasonId"]


def test_coming_soon_fixtures_are_kept_and_have_no_result():
    d = c.get("/api/tournament/EURO-2028").json()
    rows = d["matches"]["rows"]
    assert d["meta"]["status"] == "upcoming" and len(rows) == 51
    assert all(not r["is_played"] and r["status_label"] == "Coming soon" and r["home_score"] is None for r in rows)
    assert d["meta"]["champion"] is None


def test_unl_editions_share_one_theme():
    eds = [e for e in c.get("/api/tournaments").json()["editions"] if e["competition"] == "UNL"]
    assert len(eds) >= 4 and {e["themeKey"] for e in eds} == {"unl"}


def test_wc2030_is_coming_soon_without_results():
    r = c.get("/api/wc2030").json()
    f = r["facts"]
    assert f["status"] == "COMING SOON" and len(f["undecided"]) >= 5 and r["sources"]
    assert "not been played" in f["note"]
    assert not any(e["seasonId"] == "WC-2030" for e in c.get("/api/tournaments").json()["editions"])


def test_query_whitelist_and_lab_endpoints():
    assert c.post("/api/query", json={"name": "os.system", "args": {}}).status_code == 400
    lists = c.post("/api/lab/lists", json={"filters": {}, "matches": True}).json()
    assert lists["sample"]["played"] > 0
    assert c.post("/api/filtered", json={"kind": "matches", "filters": {}}).status_code == 200


def test_every_real_team_has_a_flag_or_is_an_explained_exception():
    """Flag coverage: every national team in the data maps to a flag code, except defunct states and bracket placeholders (neutral badge, never a wrong flag)."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "data" / "countries.ts").read_text(encoding="utf-8")
    mapped = {k.strip().strip('"').lower() for k in re.findall(r'(?:^|[,{]\s*)("?[A-Za-zÀ-ÿ \']+"?):\s*"[a-z-]+"', src.split("const ALIASES")[0])}
    exceptions = {"serbia and montenegro", "yugoslavia"}
    placeholder = re.compile(r"^([A-H][1-4]|(winner|runner-up|loser|3rd)\b.*)$", re.I)
    missing = [t for t in c.get("/api/teams/all").json() if not placeholder.match(t) and t.lower() not in mapped and t.lower() not in exceptions
               and t.replace("ç", "c").lower() not in mapped]
    assert not missing, missing


def test_match_center_payload_and_fixtures():
    r = c.get("/api/match-center/439").json()                          # 2022 final: extra time + penalties, StatsBomb stats, line-ups
    m = r["match"]
    assert m["home_team_name"] == "Argentina" and m["had_shootout"] and r["goalsComplete"] and r["teamStats"]["rows"] and r["lineups"]["rows"]
    assert all(e["scoring_side"] in ("home", "away") for e in r["timeline"]["rows"])
    up = c.post("/api/fixtures", json={"filters": {"seasons": ["EURO-2028"]}, "status": "upcoming", "limit": 400}).json()
    assert up["total"] == 51 and all(not x["is_played"] for x in up["rows"])
    assert c.get("/api/match-center/999999999").status_code == 404


def test_managers_and_assists_in_match_center():
    final = c.get("/api/match-center/439").json()                      # StatsBomb match: manager per match + assist links
    assert final["managers"]["home"]["name"].endswith("Scaloni") and final["managers"]["away"]["name"] == "Didier Deschamps"
    assert final["assistsRecorded"] and any(e["assist"] for e in final["timeline"]["rows"] if e["kind"] == "Goal")
    assert all(e["assist"] is None for e in final["timeline"]["rows"] if e["kind"] != "Goal")        # a penalty or non-goal event never invents an assist
    from fbplatform.api import store
    wc10 = store.matches_played().query("season_id == 'WC-2010'").match_key.iloc[0]
    r = c.get(f"/api/match-center/{wc10}").json()                      # Wikipedia match box manager; assists from the martj42 column
    assert r["managers"]["home"]["source"] in ("wikipedia_match", "statsbomb_match") and r["managers"]["home"]["level"] == "match"


def test_manager_name_cleaning():
    from fbplatform.ingest.managers import clean_name
    assert clean_name("|colspan=3| Carlos Alberto Parreira") == "Carlos Alberto Parreira"
    assert clean_name("[[Javier Aguirre|Javier Aguirre]]") == "Javier Aguirre" and clean_name("|colspan=3|") is None and clean_name(None) is None


def test_goals_from_openfootball_are_shown_as_goals():
    """openfootball goals have event_type 'goal' but no is_goal flag: they used to be labelled Substitution, hiding the scorers of whole editions."""
    r = c.get("/api/match-center/1041").json()                        # Euro 2004 final, Greece 1-0
    goals = [e for e in r["timeline"]["rows"] if e["kind"] == "Goal"]
    assert [(g["player"], g["scoring_side"]) for g in goals] == [("Angelos Charisteas", "away")] and r["goalsComplete"]


def test_finalissima_section_is_sourced_and_separate():
    eds = {e["seasonId"]: e for e in c.get("/api/finalissima").json()["editions"]}
    f22, f26 = eds["FIN-2022"], eds["FIN-2026"]
    m = f22["match"]
    assert (m["home_team_name"], m["away_team_name"], m["home_score"], m["away_score"]) == ("Italy", "Argentina", 0, 3) and m["venue_name"] == "Wembley Stadium"
    goals = [(e["player"], e["minute"], e["minute_added"]) for e in f22["timeline"] if e["kind"] == "Goal"]
    assert goals == [("Lautaro Martínez", 28, None), ("Ángel Di María", 45, 1), ("Paulo Dybala", 90, 4)]
    assert all(e["assist"] is None for e in f22["timeline"]) and f22["sources"]
    assert sum(p["is_starter"] for p in f22["lineups"]) == 22
    assert f26["status"] == "cancelled" and f26["match"]["home_score"] is None and not f26["timeline"] and not f26["lineups"] and "cancel" in f26["match"]["fixture_detail"].lower()
    cat = c.get("/api/tournaments").json()["editions"]
    assert {e["seasonId"] for e in cat if e["competition"] == "FIN"} == {"FIN-2022", "FIN-2026"}
    assert c.get("/api/tournament/FIN-2026").status_code == 200 and c.get("/api/tournament/FIN-1999").status_code == 404
    assert "FIN" not in {e["competition_id"] for e in c.post("/api/fixtures", json={"filters": {}, "limit": 400}).json()["rows"]}      # not part of the four-competition warehouse
