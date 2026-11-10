"""Dashboard data access. Pure functions returning DataFrames (no Streamlit import) so they can be unit-tested.
Everything comes from the PostgreSQL warehouse / dbt Gold layer / monitoring schema, or from the saved ML report files.
Scheduled fixtures are always returned with status_label 'Coming soon'; model output is always labelled as a prediction."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..analysis.data import q
from ..config import ROOT

REPORTS = ROOT / "reports"
MODELS = ROOT / "models"
WH_TABLES = ["dim_competition", "dim_season", "dim_team", "dim_team_name_history", "dim_player", "dim_player_xref", "dim_venue", "dim_referee", "dim_date",
             "dim_tournament_stage", "fact_matches", "fact_team_match_stats", "fact_player_match_stats", "fact_player_appearances", "fact_match_events",
             "fact_tournament_standings", "fact_player_awards", "fact_team_awards"]


def db_available() -> bool:
    try:
        q("select 1")
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ overview
def kpis() -> dict:
    r = q("""select (select count(*) from wh.dim_competition) competitions,
                    (select count(*) from wh.dim_season where matches_played > 0) editions_played,
                    (select count(*) from wh.dim_season where matches_played = 0) editions_upcoming,
                    (select count(*) from wh.fact_matches where match_status='completed') matches_played,
                    (select count(*) from wh.fact_matches where match_status='scheduled') matches_coming_soon,
                    (select count(*) from wh.dim_team) teams, (select count(*) from wh.dim_player) players,
                    (select coalesce(sum(home_score + away_score), 0) from wh.fact_matches where match_status='completed') goals,
                    (select count(*) from wh.fact_match_events) events, (select count(*) from wh.dim_venue) venues""").iloc[0].to_dict()
    return {k: int(v) for k, v in r.items()}


def data_quality_score() -> dict:
    """Share of checks that passed in the most recent run of each check family (Pandera on Silver + dbt on Gold). Definition shown in the UI."""
    d = q("""with last as (select max(run_id) as run_id from monitoring.data_quality_results where layer='silver'),
                  lastg as (select max(run_id) as run_id from monitoring.data_quality_results where layer='gold')
             select layer, table_name, check_name, severity, status, failed_rows, total_rows, checked_at, detail from monitoring.data_quality_results
             where run_id in (select run_id from last union select run_id from lastg)""")
    if d.empty:
        return dict(score=None, passed=0, total=0, failed=0)
    ok = int((d.status == "pass").sum())
    return dict(score=100 * ok / len(d), passed=ok, total=len(d), failed=len(d) - ok, checked_at=str(d.checked_at.max()))


def coverage_report() -> pd.DataFrame:
    return q("""select * from monitoring.source_coverage_report where run_id = (select run_id from monitoring.source_coverage_report order by generated_at desc limit 1)
                order by season_id""")


def upcoming_fixtures() -> pd.DataFrame:
    return q("select u.*, m.match_key from gold.mart_upcoming_fixtures u join staging.stg_matches m using (match_id) order by u.match_date, u.match_id")


# ------------------------------------------------------------------ competitions
def competitions() -> pd.DataFrame:
    return q("select competition_id, competition_name from wh.dim_competition order by competition_key")


def edition_table(comp: str) -> pd.DataFrame:
    return q("select * from gold.mart_tournament_summary where competition_id = %s order by season_year", (comp,))


def outcome_table(comp: str) -> pd.DataFrame:
    return q("""select season_id, count(*) filter (where outcome_recorded_score='home win') as team_listed_first_wins, count(*) filter (where outcome_recorded_score='draw') as draws,
                       count(*) filter (where outcome_recorded_score='away win') as team_listed_second_wins
                from gold.mart_match_performance where competition_id = %s and match_status='completed' group by 1 order by 1""", (comp,))


def records(comp: str) -> dict:
    cols = "match_key, season_id, match_date, stage_name, home_team_name, away_team_name, home_score, away_score, total_goals, goal_margin"
    base = f"from gold.mart_match_performance where competition_id = %s and match_status='completed'"
    return dict(highest_scoring=q(f"select {cols} {base} order by total_goals desc, match_date limit 5", (comp,)),
                biggest_margin=q(f"select {cols} {base} order by goal_margin desc, total_goals desc limit 5", (comp,)),
                top_scorers=q("""select player_key, full_name, max(team_name) as team_name, sum(goals) as goals from gold.mart_player_performance
                                 where season_id like %s group by player_key, full_name order by 3 desc limit 10""", (comp + "-%",)))


def goals_by_minute(comp: str | None = None, season: str | None = None) -> pd.DataFrame:
    return q("""select minute_band, count(*) goals from gold.mart_goal_analysis where (%s::text is null or competition_id = %s) and (%s::text is null or season_id = %s)
                group by 1 order by 1""", (comp, comp, season, season))


# ------------------------------------------------------------------ teams
def team_names() -> list[str]:
    return q("select team_name from staging.stg_teams order by 1").team_name.tolist()


def team_summary(team: str) -> pd.DataFrame:
    return q("""select count(*) matches, count(*) filter (where result='W') wins, count(*) filter (where result='D') draws, count(*) filter (where result='L') losses,
                       sum(goals_for) goals_for, sum(goals_against) goals_against, sum(goal_diff) goal_diff,
                       round(100.0 * count(*) filter (where result='W') / count(*), 1) win_pct, round(avg(points)::numeric, 2) points_per_match,
                       count(*) filter (where clean_sheet) clean_sheets
                from intermediate.int_team_matches t join staging.stg_teams tm using (team_key) where tm.team_name = %s""", (team,))


def team_by_edition(team: str) -> pd.DataFrame:
    return q("""select season_id, competition_id, played, wins, draws, losses, goals_for, goals_against, goal_diff, points, win_pct, goals_for_per_match, furthest_stage_played
                from gold.mart_team_performance where team_name = %s order by season_id""", (team,))


def team_results(team: str, limit: int = 300) -> pd.DataFrame:
    return q("""select m.match_key, m.match_date, m.season_id, m.stage_name, m.home_team_name, m.home_score, m.away_score, m.away_team_name, m.venue_name
                from staging.stg_matches m where m.is_played and (m.home_team_name = %s or m.away_team_name = %s) order by m.match_date desc limit %s""", (team, team, limit))


def team_upcoming(team: str) -> pd.DataFrame:
    return q("select m.match_key, u.match_date, u.season_id, u.stage_name, u.home_team_name, u.away_team_name, u.venue_name, u.status_label, u.fixture_detail from gold.mart_upcoming_fixtures u join staging.stg_matches m using (match_id) where u.home_team_name = %s or u.away_team_name = %s order by u.match_date", (team, team))


def head_to_head_table(a: str, b: str) -> pd.DataFrame:
    return q("""select match_key, match_date, season_id, stage_name, home_team_name, home_score, away_score, away_team_name from staging.stg_matches
                where is_played and ((home_team_name = %s and away_team_name = %s) or (home_team_name = %s and away_team_name = %s)) order by match_date desc""", (a, b, b, a))


# ------------------------------------------------------------------ players
def player_search(term: str, limit: int = 50) -> pd.DataFrame:
    return q("""select c.player_key, c.full_name, c.nationality, c.appearances, c.goals, c.assists, c.minutes_played, c.tournaments, c.first_season_year, c.last_season_year, (select mode() within group (order by pp.team_name) from gold.mart_player_performance pp where pp.player_key = c.player_key) as plays_for
                from gold.mart_player_career c where c.full_name ilike %s order by c.goals desc, c.appearances desc limit %s""", (f"%{term}%", limit))


def top_players(metric: str = "goals", limit: int = 20) -> pd.DataFrame:
    assert metric in {"goals", "assists", "appearances", "minutes_played"}
    return q(f"select c.player_key, c.full_name, c.nationality, c.goals, c.assists, c.appearances, c.minutes_played, c.tournaments, (select mode() within group (order by pp.team_name) from gold.mart_player_performance pp where pp.player_key = c.player_key) as plays_for from gold.mart_player_career c order by c.{metric} desc nulls last limit %s", (limit,))


def player_by_edition(player_key: int) -> pd.DataFrame:
    return q("""select season_id, team_name, appearances, starts, minutes_played, goals, assists, yellow_cards, red_cards, goals_per_90 from gold.mart_player_performance pp
                where pp.player_key = %s order by season_id""", (int(player_key),))


def player_awards(player_key: int) -> pd.DataFrame:
    return q("""select s.season_id, a.award_name, a.rank, a.value_text from wh.fact_player_awards a join wh.dim_season s using (season_key) where a.player_key = %s order by 1""", (int(player_key),))


def player_profile(player_key: int) -> pd.DataFrame:
    return q("select player_key, full_name, nationality, date_of_birth, primary_position, n_source_ids from wh.dim_player where player_key = %s", (int(player_key),))


# ------------------------------------------------------------------ matches
def season_ids() -> list[str]:
    return q("select season_id from wh.dim_season order by season_id").season_id.tolist()


def match_search(season: str | None = None, team: str | None = None, include_upcoming: bool = True, limit: int = 200) -> pd.DataFrame:
    return q("""select match_key, match_id, match_date, season_id, stage_name, group_name, home_team_name, home_score, away_score, away_team_name, status_label, venue_name, venue_city
                from staging.stg_matches where (%s::text is null or season_id = %s) and (%s::text is null or home_team_name = %s or away_team_name = %s)
                and (%s or is_played) order by match_date desc, match_key limit %s""", (season, season, team, team, team, include_upcoming, limit))


def match_row(match_key: int) -> pd.DataFrame:
    return q("select * from staging.stg_matches where match_key = %s", (int(match_key),))


def match_timeline(match_key: int) -> pd.DataFrame:
    return q("""select e.minute, e.minute_added,
                       case when e.event_type = 'own_goal_against' or coalesce(e.is_own_goal, false) then 'Own goal' when e.is_goal or e.event_type = 'goal' then 'Goal'      -- openfootball goals carry event_type 'goal' without the is_goal flag
                            when e.event_type = 'card' then 'Card: ' || coalesce(e.card, 'card') else 'Substitution' end as kind,
                       e.event_type, e.detail_type, e.card, t.team_name, coalesce(p.full_name, e.player_name_raw) as player,
                       coalesce(rp.full_name, e.related_player_name_raw) as other_player, e.provider
                from wh.fact_match_events e left join wh.dim_team t using (team_key) left join wh.dim_player p on p.player_key = e.player_key left join wh.dim_player rp on rp.player_key = e.related_player_key
                where e.match_key = %s and (e.is_goal or e.card is not null or e.event_type in ('goal','own_goal_against','card','substitution')) and e.minute is not null and coalesce(e.period, 0) <> 5
                and e.event_type <> 'own_goal_for' order by e.minute, e.minute_added nulls first, e.event_key""", (int(match_key),)).drop_duplicates()


def match_team_stats(match_key: int) -> pd.DataFrame:
    return q("""select t.team_name, s.shots, s.shots_on_target, s.passes, s.pass_accuracy, s.corners_taken, s.fouls_committed, s.yellow_cards, s.red_cards, s.xg
                from wh.fact_team_match_stats s join wh.dim_team t using (team_key) where s.match_key = %s""", (int(match_key),))


def match_lineups(match_key: int) -> pd.DataFrame:
    return q("""select t.team_name, coalesce(p.full_name, a.player_name_raw) player, a.jersey_number, a.is_starter, a.minutes_played from wh.fact_player_appearances a
                join wh.dim_team t using (team_key) left join wh.dim_player p using (player_key) where a.match_key = %s order by t.team_name, a.is_starter desc nulls last, a.jersey_number""", (int(match_key),))


# ------------------------------------------------------------------ data engineering
def pipeline_runs(limit: int = 60) -> pd.DataFrame:
    return q("select run_id, step, attempt, status, started_at, duration_seconds, rows_processed, left(coalesce(error, detail), 160) as detail from monitoring.pipeline_execution_logs order by log_id desc limit %s", (limit,))


def pipeline_summary() -> pd.DataFrame:
    return q("""select run_id, min(started_at) started_at, round(sum(duration_seconds)::numeric, 1) total_seconds, count(*) filter (where status='failed') failed_attempts,
                       count(*) filter (where status='skipped') skipped_steps, count(*) steps from monitoring.pipeline_execution_logs group by 1 order by 2 desc limit 20""")


def ingestion_status() -> pd.DataFrame:
    return q("""select source, count(*) files, round(sum(size_bytes) / 1048576.0, 1) mb, max(version) max_version, max(ingested_at) last_ingested, count(*) filter (where excluded_ucl) excluded_ucl_files
                from monitoring.ingestion_history group by 1 order by 2 desc""")


def dq_results(only_failed: bool = False) -> pd.DataFrame:
    d = q("select layer, table_name, check_name, severity, status, failed_rows, total_rows, checked_at, detail from monitoring.data_quality_results order by result_id desc limit 300")
    return d[d.status == "fail"] if only_failed else d


def duplicate_checks() -> pd.DataFrame:
    return q("""select 'duplicate match ids' as check, count(*) as found from (select match_id from wh.fact_matches group by 1 having count(*) > 1) x
                union all select 'duplicate (match, team, player) line-up rows', count(*) from (select match_key, team_key, player_key from wh.fact_player_appearances where player_key is not null group by 1,2,3 having count(*) > 1) x
                union all select 'duplicate event ids', count(*) from (select event_id from wh.fact_match_events group by 1 having count(*) > 1) x
                union all select 'player ids merged into another canonical id (entity resolution)', count(*) from wh.dim_player_xref x join wh.dim_player p using (player_key) where x.player_id_original <> p.player_id
                union all select 'players with the same name and date of birth still separate', count(*) from (select full_name, date_of_birth from wh.dim_player where date_of_birth is not null group by 1,2 having count(*) > 1) x""")


def db_stats() -> pd.DataFrame:
    rows = []
    for t in WH_TABLES:
        n = q(f"select count(*) c from wh.{t}").c.iloc[0]
        s = q("select pg_total_relation_size(%s::regclass) b", (f"wh.{t}",)).b.iloc[0]
        rows.append(dict(table=t, rows=int(n), size_mb=round(int(s) / 1048576, 2)))
    return pd.DataFrame(rows)


def freshness() -> pd.DataFrame:
    return q("""select 'last pipeline run' item, max(finished_at)::text value from monitoring.pipeline_execution_logs
                union all select 'last successful dbt build', max(finished_at)::text from monitoring.pipeline_execution_logs where step='dbt_gold' and status='success'
                union all select 'warehouse last loaded', max(loaded_at)::text from wh.etl_load_log
                union all select 'latest played match date', max(d.full_date)::text from wh.fact_matches m join wh.dim_date d using (date_key) where m.match_status='completed'
                union all select 'next scheduled match date', min(d.full_date)::text from wh.fact_matches m join wh.dim_date d using (date_key) where m.match_status='scheduled'""")


# ------------------------------------------------------------------ machine learning (saved reports; never recomputed in the UI)
def _csv(*parts) -> pd.DataFrame:
    p = REPORTS.joinpath(*parts)
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def ml_outcome_comparison() -> pd.DataFrame:
    return _csv("ml", "outcome", "match_outcome_model_comparison.csv")


def ml_outcome_predictions() -> pd.DataFrame:
    d = _csv("ml", "outcome", "test_period_predictions.csv")
    if d.empty:
        return d
    names = q("select team_key, team_name from staging.stg_teams").set_index("team_key").team_name
    d["team_a"], d["team_b"] = d.team_a_key.map(names), d.team_b_key.map(names)
    return d


def ml_importance() -> dict:
    return dict(permutation=_csv("ml", "outcome", "permutation_importance.csv"), shap=_csv("ml", "outcome", "shap_mean_abs.csv"), gain=_csv("ml", "outcome", "xgboost_gain_importance.csv"),
                pdp=_csv("ml", "outcome", "partial_dependence.csv"), confusion=_csv("ml", "outcome", "confusion_matrices_test.csv"))


def ml_goals() -> dict:
    return dict(comparison=_csv("ml", "goals", "goal_model_comparison.csv"), calibration=_csv("ml", "goals", "calibration_by_predicted_rate_decile.csv"),
                diagnostics=_csv("ml", "goals", "count_model_diagnostics.csv"), over_under=_csv("ml", "goals", "over_under_2_5_experiment.csv"), expected=_csv("ml", "goals", "test_period_expected_goals.csv"))


def ml_clusters() -> dict:
    return dict(team_profiles=_csv("ml", "clustering", "team_cluster_profiles.csv"), team_summary=_csv("ml", "clustering", "team_clustering_summary.csv"),
                teams=_csv("ml", "clustering", "team_clusters.csv"), player_profiles=_csv("ml", "clustering", "player_cluster_profiles.csv"),
                player_summary=_csv("ml", "clustering", "player_clustering_summary.csv"), team_k4=_csv("ml", "clustering", "team_cluster_profiles_k4_exploratory.csv"))


def ml_meta(name: str = "match_outcome_selected") -> dict:
    p = MODELS / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
