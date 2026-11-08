from datetime import date

import pandas as pd
import pytest

from fbplatform.config import DATA
from fbplatform.ingest import wikipedia_matches as W

P = DATA / "processed"


@pytest.mark.parametrize("tpl,expected", [
    ("{{fb|GER}}", ("GER", None)),
    ("{{fb-rt|FRA|1974}}", ("FRA", None)),
    ("{{fb-rt|Venezuela|1930}}", (None, "Venezuela")),          # Copa 2004 writes country NAMES
    ("{{fb|Colombia}}", (None, "Colombia")),
    ("{{#invoke:flag|fb-rt|CAN}}", ("CAN", None)),
    ("{{#invoke:flagg|main|unpre|avar=fb|QAT}}", ("QAT", None)),  # World Cup 2022
    ("{{fbaicon|ENG}} [[Chelsea F.C.|Chelsea]]", ("ENG", None)),
])
def test_flag_templates_in_every_form_seen(tpl, expected):
    assert W.flag_arg(tpl) == expected


def test_score_inside_template_is_not_deleted():
    # score link templates used to be stripped as markup, silently dropping every World Cup / Euro group match
    assert W.score_text("{{score link|2018 FIFA World Cup Group A#Russia vs Saudi Arabia|5–0}}") == "5–0"
    assert W.score_text("[[2011 Copa América final stages#Colombia vs Peru|0–2]]") == "0–2"


def test_dates_template_and_plain_text():
    assert W.parse_date("{{Start date|2018|6|14|df=y}}") == date(2018, 6, 14)
    assert W.parse_date("16 July 2011") == date(2011, 7, 16)
    assert W.parse_date("July 16, 2011") == date(2011, 7, 16)
    assert W.parse_date("not a date") is None


def test_goal_templates_and_plain_text_fallback():
    g = W.parse_goals("*[[Enner Valencia|Valencia]] {{goal|16|pen.|31}}")
    assert [(x["minute"], x["flag"]) for x in g] == [(16, "penalty"), (31, None)]
    g = W.parse_goals("*[[Azzedine Ounahi|Ounahi]] 50', 82'\n*[[X Y|Y]] 90+2' (pen.)")
    assert [(x["scorer"], x["minute"], x["added"], x["flag"]) for x in g] == [
        ("Ounahi", 50, None, None), ("Ounahi", 82, None, None), ("Y", 90, 2, "penalty")]


@pytest.mark.parametrize("title,expected", [
    ("2018 FIFA World Cup Group A", ("WC", "WC-2018", "A", None)),
    ("UEFA Euro 2020 knockout stage", ("EURO", "EURO-2020", None, None)),
    ("2019 Copa América final", ("COPA", "COPA-2019", None, None)),
    ("Copa América Centenario Group B", ("COPA", "COPA-2016", "B", None)),
    ("2018–19 UEFA Nations League A", ("UNL", "UNL-2018-19", None, "A")),
    ("2021 UEFA Nations League Finals", ("UNL", "UNL-2020-21", None, None)),
])
def test_page_to_season_mapping(title, expected):
    assert W.season_of_page(title) == expected


@pytest.mark.parametrize("title", ["2018 FIFA World Cup qualification", "UEFA Euro 2016 statistics",
                                   "2008–09 UEFA Champions League group stage", "UEFA Euro 2016 squads"])
def test_out_of_scope_pages_are_ignored(title):
    assert W.season_of_page(title) is None            # qualifying, statistics, squads and the Champions League


def test_stage_group_rules():
    assert W.stage_group("2018 FIFA World Cup Group A", None, "A", None) == ("Group stage", "A")
    assert W.stage_group("2019–20 UEFA Nations League A", "Group 2", None, "A") == ("Group stage", "A2")
    assert W.stage_group("2018 FIFA World Cup knockout stage", "Quarter-finals", None, None)[0] == "Quarter-finals"
    assert W.stage_group("x", "Match for third place", None, None)[0] == "Third place"


need = pytest.mark.skipif(not (P / "matches.parquet").exists(), reason="run the pipeline first")


@need
def test_scope_is_exactly_the_four_competitions_and_wikipedia_links_everything():
    m = pd.read_parquet(P / "matches.parquet")
    assert set(m.competition_id) == {"WC", "EURO", "COPA", "UNL"}
    t = pd.read_parquet(P / "teams.parquet")
    assert set(t.team_type) == {"national"}                       # no clubs left
    q = DATA / "quality"
    assert len(pd.read_csv(q / "wikipedia_unresolved_teams.csv")) == 0
    conf = pd.read_csv(q / "wikipedia_vs_matches_conflicts.csv")
    assert (conf.kind == "no_unique_match").sum() == 0           # every box found exactly one of our matches
    assert len(conf) <= 3                                          # only genuine disagreements (abandoned / awarded results)


@need
def test_date_corrections_are_recorded_and_ids_stay_stable():
    m = pd.read_parquet(P / "matches.parquet")
    fixed = m[m.date_check.fillna("").str.startswith("corrected")]
    assert len(fixed) == 2 and set(fixed.season_id) == {"EURO-2016"}
    assert fixed.date_check.str.contains("agree against openfootball").all()
    assert m.match_id.is_unique


@need
def test_wikipedia_enrichment_is_fill_null_only():
    m = pd.read_parquet(P / "matches.parquet")
    # 0 and tiny values are genuine: matches behind closed doors (COVID 2020-21, UEFA punishments), per Wikipedia's footnotes
    assert m.attendance.dropna().between(0, 200000).all()
    stage = m[m.stage.notna()]
    assert set(stage.stage) <= {"Group stage", "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals",
                                "Third place", "Final", "Play-off", "Promotion/relegation play-off", "Knockout play-off", "League phase"}


def test_infobox_only_final_becomes_a_match_record():
    # the Euro 2020 final page has an infobox but no match box: it must still give attendance / referee / man of the match
    import pandas as pd
    df = W.scope_boxes()
    f = df[(df.season_id == "EURO-2020") & (df.stage == "Final")]
    assert len(f) == 1 and f.iloc[0].attendance == 67173 and "Kuipers" in f.iloc[0].referee
    assert "Bonucci" in f.iloc[0].detail["man_of_the_match"]


def test_duplicate_boxes_keep_the_most_detailed_copy_and_merge_fields():
    df = W.scope_boxes()
    c = df[df.season_id == "COPA-2007"]
    assert len(c) == 26 and c.detail.notna().all()                  # details come from the group/knockout pages, not the bare main-page copy
    assert df.groupby(["season_id", "date", "home_cc", "away_cc"]).size().max() == 1
