from datetime import date

import pandas as pd
import pytest

from fbplatform.config import DATA
from fbplatform.ingest.parse_txt import normalize_stage, parse_file, parse_score_block

URL = "http://x/f.txt"


def one(text, year=2016, **kw):
    rows, un = parse_file(text, year, URL, **kw)
    assert not un
    assert len(rows) == 1
    return rows[0]


def test_plain_score_with_halftime():
    r = parse_score_block("0-5 (0-3)")
    assert (r["score"], r["ft"], r["ht"], r["went_et"]) == ((0, 5), (0, 5), (0, 3), False)


def test_pen_and_aet_single_paren_is_not_interpreted():
    # Euro 2016/2008: "(0-0)" may be half-time or 90-minute score -> must stay null
    r = parse_score_block("6-5 pen. 1-1 a.e.t. (0-0)")
    assert r["pen"] == (6, 5) and r["et"] == (1, 1) and r["ht"] is None and r["ft"] is None
    assert "not interpreted" in r["note"]


def test_champions_league_two_value_paren():
    r = parse_score_block("4-1 a.e.t. (1-1, 0-1)")
    assert (r["score"], r["ft"], r["ht"]) == ((4, 1), (1, 1), (0, 1))


def test_pen_only_form_keeps_basis_unspecified():
    r = parse_score_block("4-3 pen. (3-3)")
    assert r["pen"] == (4, 3) and r["score"] == (3, 3) and r["basis"].startswith("unspecified")


def test_euro2004_style_extra_after_team():
    row = one("▪ Quarter-finals\nJune 24 19:45  Portugal  2-2 England  (aet, 6-5 pen)  @ Estadio da Luz, Lisbon\n", 2004)
    assert (row["home_raw"], row["away_raw"], row["pen"], row["venue_raw"]) == ("Portugal", "England", (6, 5), "Estadio da Luz, Lisbon")
    assert row["stage"] == "Quarter-finals" and row["date"] == date(2004, 6, 24)


def test_timezone_and_weekday_check():
    row = one("Thu Jun 20 20:00 UTC-4   Argentina  2-0   Canada  @ Atlanta\n", 2024)
    assert row["tz_offset_min"] == -240 and row["time_local"] == "20:00" and row["date_check"] == "weekday_ok"


def test_ucl_year_from_weekday_not_line_order():
    txt = ("▪ Group B\n  Tue Sep 17\n    20:45  A FC (ENG) v B FC (ESP)   1-0 (0-0)\n"
           "▪ Group A\n  Wed Aug 12\n    21:00  C (ITA) v D (GER)  2-1 (1-0)\n")
    rows, _ = parse_file(txt, 2019, URL, inherit_time=True, split_season=True)
    assert rows[0]["date"] == date(2019, 9, 17)
    assert rows[1]["date"] == date(2020, 8, 12) and "adjusted" in rows[1]["date_check"]  # COVID-era August


def test_cl_time_inherited_within_date_only():
    txt = "  Tue Sep 17 2013\n    20:45  A (ENG) v B (ESP)  1-0\n           C (ITA) v D (GER)  0-0\n  Wed Sep 18\n           E (FRA) v F (POR)  2-2\n"
    rows, _ = parse_file(txt, 2013, URL, inherit_time=True, split_season=True)
    assert [r["time_local"] for r in rows] == ["20:45", "20:45", None]


def test_goal_detail_lines_attach_to_match_not_counted():
    r = one("▪ Group A\nJune 12   Portugal  1-2 Greece\n  (Ronaldo 90+3; Karagounis 7,\n   Basinas 51pen)\n", 2004)
    assert "Basinas" in r["raw_text"]


@pytest.mark.parametrize("hdr,expected", [("Group C", "Group stage"), ("Gruppe G", "Group stage"),
                                          ("League, Matchday 3", "League phase"), ("Playoffs, Matchday 2", "Knockout play-off"),
                                          ("Finals, Quarterfinals", "Quarter-finals"), ("Third-place play-off", "Third place"),
                                          ("Semifinals", "Semi-finals"), ("Round of 16", "Round of 16")])
def test_stage_normalization(hdr, expected):
    assert normalize_stage(hdr)[0] == expected


# ---- checks on the generated dataset (skipped if the pipeline has not been run)
M = DATA / "processed" / "matches.parquet"


@pytest.mark.skipif(not M.exists(), reason="run python -m fbplatform.ingest.build first")
def test_generated_matches_invariants():
    m = pd.read_parquet(M)
    assert m.match_id.is_unique
    assert m.source_url.notna().all() and m.retrieval_timestamp.notna().all()
    assert m.match_duration_minutes.isna().all()  # no source has it -> never fabricated (attendance now comes from Wikipedia)
    sched = m[m.match_status == "scheduled"]
    assert sched[["home_score", "away_score", "home_pen", "winner"]].isna().all().all()
    exp = {"WC-2022": 64, "WC-2026": 104, "EURO-2024": 51, "EURO-2004": 31, "COPA-2024": 32, "COPA-2019": 26,
           "COPA-2016": 32, "WC-2006": 64}
    got = m.groupby("season_id").size()
    for k, v in exp.items():
        assert got[k] == v
    assert "UCL" not in set(m.competition_id)                       # Champions League is out of scope
    f = m[(m.season_id == "WC-2022") & (m.stage == "Final")].iloc[0]
    assert (f.home_team_raw, f.home_score, f.away_score, f.home_pen, f.away_pen) == ("Argentina", 3, 3, 4, 2)


def test_two_letter_weekday_headers_set_the_date():
    # Euro 2008 writes "Th Jun 19": previously unparsed, so the previous date was silently inherited
    txt = "▪ Quarter-finals\nTh Jun 19\n  20:45   Portugal    2-3    Germany    @ Basel\nFr Jun 20\n  20:45   Croatia  1-1  Turkey  @ Wien\n"
    rows, un = parse_file(txt, 2008, URL)
    assert [r["date"] for r in rows] == [date(2008, 6, 19), date(2008, 6, 20)]
    assert all(r["date_check"] == "weekday_ok" for r in rows)



def test_leading_venue_layout_of_euro_2000():
    # "@ Venue   Team  score  Team": the venue used to be glued onto the home team's name ("Liege Germany")
    txt = "▪ Group A\nJune 12 18:00 @ Liège       Germany            1-1 Romania\n                              (Scholl 28; Moldovan 5)\n" \
          "        20:45 @ Eindhoven   Portugal           3-2 England\n"
    rows, un = parse_file(txt, 2000, URL)
    assert not un
    assert [(r["home_raw"], r["away_raw"], r["venue_raw"]) for r in rows] == [("Germany", "Romania", "Liège"), ("Portugal", "England", "Eindhoven")]
    assert rows[1]["time_local"] == "20:45" and rows[1]["date"] == date(2000, 6, 12)
