import pandas as pd
import pytest
import psycopg
from fbplatform.config import DATA
from fbplatform.warehouse.load import dsn

try:
    CONN = psycopg.connect(dsn(), connect_timeout=3)
except Exception:  # warehouse container not running
    CONN = None
pytestmark = pytest.mark.skipif(CONN is None, reason="PostgreSQL warehouse not running (docker compose up -d)")
S = DATA / "silver"


def q(sql):
    with CONN.cursor() as c:
        c.execute(sql)
        return c.fetchall()


def test_row_counts_match_silver():
    for t, f in [("fact_matches", "matches"), ("fact_match_events", "events"), ("fact_player_appearances", "lineups"),
                 ("dim_player", "players"), ("dim_player_xref", "player_xref"), ("dim_venue", "venues"), ("dim_team", "teams")]:
        assert q(f"select count(*) from wh.{t}")[0][0] == len(pd.read_parquet(S / f"{f}.parquet")), t


def test_upcoming_fixtures_kept_with_null_scores():
    r = q("select count(*), count(home_score), min(status_label) from wh.fact_matches where match_status='scheduled'")[0]
    assert r == (51, 0, "Coming soon")


def test_score_goal_reconciliation_played_matches():
    # goals rebuilt per match from event rows equal the recorded score for every played match that has goal events
    bad = q("""select count(*) from (
      select m.match_key from wh.fact_matches m join wh.fact_team_match_stats t using (match_key)
      where m.match_status='completed' and m.home_score is not null
      group by m.match_key, m.home_score, m.away_score
      having sum(t.goals_for_incl_own_goals) <> m.home_score + m.away_score) x""")[0][0]
    assert bad == 0


def test_no_orphans_and_scope():
    assert q("select count(*) from wh.fact_match_events e left join wh.fact_matches m using(match_key) where m.match_key is null")[0][0] == 0
    assert {r[0] for r in q("select competition_id from wh.dim_competition")} == {"WC", "EURO", "COPA", "UNL"}


def test_player_merge_resolves_through_xref():
    assert q("select count(*) from wh.dim_player_xref x left join wh.dim_player p using(player_key) where p.player_key is null")[0][0] == 0


def test_standings_points_consistent():
    assert q("select count(*) from wh.fact_tournament_standings where points <> 3*wins+draws or played <> wins+draws+losses")[0][0] == 0


def test_awards_loaded_with_raw_names_and_known_winners():
    n = q("select (select count(*) from wh.fact_player_awards)+(select count(*) from wh.fact_team_awards)")[0][0]
    assert n > 300
    assert q("select count(*) from wh.fact_player_awards where entity_name_raw is null")[0][0] == 0
    # facts that must hold: Mbappe won the 2022 Golden Boot with 8 goals; Argentina's Emiliano Martinez the 2022 Golden Glove
    r = q("select entity_name_raw, value_text from wh.fact_player_awards a join wh.dim_season s using(season_key) "
          "where s.season_id='WC-2022' and award_name='Golden Boot' and rank=1")
    assert r == [("Kylian Mbappé", "8 goals")]
    assert q("select count(*) from wh.fact_player_awards a join wh.dim_season s using(season_key) where s.season_id='WC-2022' and award_name like 'Golden Glove%' and entity_name_raw like 'Emiliano%'")[0][0] == 1
    # unlinked winners keep a status instead of a guess
    assert q("select count(*) from wh.fact_player_awards where player_key is null and link_status in ('squad_name_match','squad_name_match_other_season')")[0][0] == 0
