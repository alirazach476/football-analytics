import pytest

from fbplatform.http import HttpClient
from fbplatform.registry import build_registry
from fbplatform.sources import openfootball as of
from fbplatform.sources.base import row


def test_registry_unique_and_future_results_null():
    df = build_registry()
    assert df.season_id.is_unique
    assert set(df.competition_id) == {"WC", "EURO", "COPA", "UNL"}   # scope: no club competitions
    assert {"WC-2002", "WC-2026", "EURO-2028", "COPA-2019", "UNL-2026-27"} <= set(df.season_id)
    fut = df[df.verification_status == "scheduled"]
    assert len(fut) > 0


def test_row_coverage_math_and_nulls():
    reg = {"competition_id": "X", "season_id": "X-1", "expected_matches": 64}
    r = row(reg, "S", collected=60)
    assert (r["missing_matches"], r["coverage_percentage"]) == (4, 93.8)
    unknown = row({**reg, "expected_matches": None}, "S", collected=60)
    assert unknown["coverage_percentage"] is None and unknown["missing_matches"] is None


def test_txt_counter_ignores_goal_detail_lines():
    text = "June 12   Portugal  1-2 Greece\n           (Cristiano Ronaldo 90+3; Giorgos Karagounis 7)\n# 1-0 note\n"
    assert of.count_txt_matches(text) == (1, 1)


@pytest.mark.network
@pytest.mark.parametrize("repo,path,expected", [
    ("euro", "2004--portugal/euro.txt", 31),
    ("euro", "2016--france/euro.txt", 51),
    ("europe-champions-league", "2013-14/cl.txt", 125),
    ("copa-america", "2011--argentina/copa.txt", 26),
])
def test_txt_heuristic_matches_known_totals(repo, path, expected):
    c = HttpClient("openfootball", 0.3)
    text = c.get(f"{of.RAW}/{repo}/master/{path}").content.decode("utf-8")
    assert of.count_txt_matches(text)[0] == expected


@pytest.mark.network
def test_worldcup_txt_group_plus_finals_is_64():
    c = HttpClient("openfootball", 0.3)
    d = "2002--south_korea-n-japan"
    total = sum(of.count_txt_matches(c.get(f"{of.RAW}/worldcup/master/{d}/{f}").content.decode("utf-8"))[0]
                for f in ("cup.txt", "cup_finals.txt"))
    assert total == 64
