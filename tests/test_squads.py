from datetime import date

import pandas as pd
import pytest

from fbplatform.config import DATA
from fbplatform.ingest import squads as S

P = DATA / "processed"


def one(line: str, title="2018 FIFA World Cup squads"):
    text = "==Group A==\n===Egypt===\nHead coach: [[Hector Cuper]]\n{{nat fs g start}}\n" + line + "\n{{nat fs end}}\n"
    sid, rows, coaches = S.parse_squads_page(title, 1, text, None)
    assert len(rows) == 1
    return rows[0], coaches


def test_player_row_fields_and_captain_markers():
    r, c = one("{{nat fs g player|no=10|pos=FW|name=[[Lionel Messi]]|other=[[Captain (association football)|captain]]"
               "|age={{birth date and age2|df=y|2022|11|20|1987|6|24}}|caps=165|goals=91|club=[[Paris Saint-Germain F.C.|Paris Saint-Germain]]|clubnat=FRA}}")
    assert (r["shirt_number"], r["position"], r["player_name_raw"], r["caps"], r["goals"], r["club_raw"]) == (10, "FW", "Lionel Messi", 165, 91, "Paris Saint-Germain")
    assert r["is_captain"] and r["date_of_birth"] == date(1987, 6, 24)        # df=y before the numbers, captain in other=
    assert c == {"Egypt": "Hector Cuper"} and r["season_id"] == "WC-2018"


def test_vice_captain_is_not_the_captain():
    r, _ = one("{{nat fs g player|no=11|pos=FW|name=[[Ángel Di María]]|other=[[Captain (association football)#Vice-captain|vice-captain]]"
               "|age={{birth date and age2|2022|11|20|1988|2|14}}|caps=1|goals=1|club=[[Juventus F.C.|Juventus]]|clubnat=ITA}}")
    assert not r["is_captain"]


@pytest.mark.parametrize("name,expected", [
    ("{{sortname|Antonios|Nikopolidis}}", "Antonios Nikopolidis"),                 # Euro 2004
    ("{{sort|Hjortur|[[Hjörtur Hermannsson]]}}", "Hjörtur Hermannsson"),           # Euro 2016
    ("[[Cafu]] ([[Captain (association football)|c]])", "Cafu"),                    # captain in the name
])
def test_name_template_forms(name, expected):
    r, _ = one("{{nat fs player|no=2|pos=DF|name=" + name + "|age={{birth date and age2|2002|5|31|1970|6|7|df=y}}|caps=1|club=[[AS Roma|Roma]]|clubnat=ITA}}")
    assert r["player_name_raw"] == expected


@pytest.mark.parametrize("tpl", ["nat fs g player", "nat fs player", "National football squad player"])   # three template names across editions
def test_all_squad_template_names_are_read(tpl):
    r, _ = one("{{" + tpl + "|no=1|pos=GK|name=[[X Y]]|age={{birth date and age2|df=yes|2014|6|12|1992|4|14}}|caps=2|club=[[Z]]|clubnat=BRA}}")
    assert r["date_of_birth"] == date(1992, 4, 14)


def test_squad_page_titles_map_to_seasons():
    assert S.season_of_squad_page("2018 FIFA World Cup squads") == "WC-2018"
    assert S.season_of_squad_page("UEFA Euro 2016 squads") == "EURO-2016"
    assert S.season_of_squad_page("Copa América Centenario squads") == "COPA-2016"
    assert S.season_of_squad_page("2004 Copa América squads") == "COPA-2004"
    assert S.season_of_squad_page("2018 FIFA World Cup qualification") is None


need = pytest.mark.skipif(not (P / "squads" / "squads.parquet").exists(), reason="run the pipeline first")


@need
def test_every_tournament_has_the_right_number_of_squads_and_one_captain_each():
    d = pd.read_parquet(P / "squads" / "squads.parquet")
    teams = d[d.team_played].groupby("season_id").team_id.nunique().to_dict()     # teams that actually played
    withdrawn = d[~d.team_played]
    assert set(withdrawn.season_id) == {"COPA-2001"} and set(withdrawn.team_id) == {"T-NAT-argentina", "T-NAT-canada"}  # squads named, then withdrew
    expected = {**{f"WC-{y}": 32 for y in (2002, 2006, 2010, 2014, 2018, 2022)}, "WC-2026": 48,
                **{f"EURO-{y}": n for y, n in ((2000, 16), (2004, 16), (2008, 16), (2012, 16), (2016, 24), (2020, 24), (2024, 24))},
                **{f"COPA-{y}": n for y, n in ((2001, 12), (2004, 12), (2007, 12), (2011, 12), (2015, 12), (2016, 16), (2019, 12), (2021, 10), (2024, 16))}}
    assert teams == expected
    assert d.team_id.notna().all() and (d.player_name_raw.str.strip() != "").all()
    assert (d[d.team_played].groupby(["season_id", "team_id"]).is_captain.sum() == 1).all()    # withdrawn squads (Copa 2001) name no captain


@need
def test_squads_match_fjelstul_and_cover_every_appearance():
    v = pd.read_csv(DATA / "quality" / "squads_validation.csv").dropna(subset=["squad_size_fjelstul"])
    assert len(v) == 192 and (v.squad_size_wikipedia == v.squad_size_fjelstul).all() and v.numbers_equal.all()
    assert len(pd.read_csv(DATA / "quality" / "squads_appearance_check.csv")) == 0     # nobody played who is not in a squad


@need
def test_squad_rows_are_linked_to_unique_registered_players():
    d = pd.read_parquet(P / "squads" / "squads.parquet")
    pl = pd.read_parquet(P / "players_all.parquet")
    assert pl.player_id.is_unique and d.player_id.notna().all()
    assert d.player_id.isin(pl.player_id).all()
    assert set(d.link_rule) == {"S1_fjelstul_shirt_number", "S2_dob_and_name", "S3_team_dob"}
    # one real person never appears twice in the same squad
    assert not d.duplicated(["season_id", "team_id", "player_id"]).any()
