# Database schema

_Generated 2026-11-06. Engine: PostgreSQL 16 (Docker, host port 5442). DDL: `sql/warehouse_schema.sql`; loader: `src/fbplatform/warehouse/load.py`._

```text
                      dim_competition ─┐
                                       ├─ dim_season ─┬─ fact_matches ─┬─ fact_team_match_stats
   dim_tournament_stage ────────────────┘             │                ├─ fact_player_match_stats
   dim_date ─────────────────────────────────────────┤                ├─ fact_player_appearances
   dim_venue ────────────────────────────────────────┤                ├─ fact_match_events
   dim_referee ──────────────────────────────────────┘                └─ (fact_tournament_standings via season)
   dim_team ─(name history)─ used by every fact       dim_player ◄─ dim_player_xref (original source ids)
```

## Design decisions

* **Surrogate keys** are deterministic (sorted natural key → 1..n), so reloads give identical keys. The schema is dropped and rebuilt from Silver on each load (idempotent).
* **Historical entities:** `dim_team_name_history` keeps former names; teams that no longer exist (e.g. Yugoslavia, Serbia and Montenegro) are separate teams, never merged. Validity dates are NULL because no source gives them.
* **Identity resolution:** `dim_player_xref` maps every original source id to the canonical player and records the rule.
* **Scheduled fixtures** are rows in `fact_matches` with `match_status='scheduled'`; a CHECK constraint forces their scores to be NULL.
* **Constraints:** primary keys, foreign keys, CHECKs (status values, non-negative attendance, scheduled⇒no score) and indexes on the join/filter columns.

## Row counts

| table | rows |
|---|---|
| dim_competition | 4 |
| dim_season | 29 |
| dim_team | 103 |
| dim_team_name_history | 108 |
| dim_player | 8,410 |
| dim_player_xref | 9,978 |
| dim_venue | 338 |
| dim_referee | 516 |
| dim_date | 10,257 |
| dim_tournament_stage | 9 |
| fact_matches | 1,830 |
| fact_team_match_stats | 3,406 |
| fact_player_match_stats | 15,006 |
| fact_player_appearances | 35,351 |
| fact_match_events | 1,033,220 |
| fact_tournament_standings | 762 |
| fact_player_awards | 391 |
| fact_team_awards | 16 |

## Foreign keys

| table | column | → table | column |
|---|---|---|---|
| fact_player_appearances | team_key | dim_team | team_key |
| fact_player_appearances | player_key | dim_player | player_key |
| fact_match_events | match_key | fact_matches | match_key |
| fact_match_events | team_key | dim_team | team_key |
| fact_match_events | player_key | dim_player | player_key |
| fact_match_events | related_player_key | dim_player | player_key |
| fact_tournament_standings | season_key | dim_season | season_key |
| fact_tournament_standings | team_key | dim_team | team_key |
| fact_player_awards | season_key | dim_season | season_key |
| fact_player_awards | player_key | dim_player | player_key |
| fact_player_awards | team_key | dim_team | team_key |
| fact_team_awards | season_key | dim_season | season_key |
| fact_team_awards | team_key | dim_team | team_key |
| dim_season | competition_key | dim_competition | competition_key |
| dim_team_name_history | team_key | dim_team | team_key |
| dim_player_xref | player_key | dim_player | player_key |
| fact_matches | competition_key | dim_competition | competition_key |
| fact_matches | season_key | dim_season | season_key |
| fact_matches | date_key | dim_date | date_key |
| fact_matches | stage_key | dim_tournament_stage | stage_key |
| fact_matches | home_team_key | dim_team | team_key |
| fact_matches | away_team_key | dim_team | team_key |
| fact_matches | venue_key | dim_venue | venue_key |
| fact_matches | referee_key | dim_referee | referee_key |
| fact_team_match_stats | match_key | fact_matches | match_key |
| fact_team_match_stats | team_key | dim_team | team_key |
| fact_player_match_stats | match_key | fact_matches | match_key |
| fact_player_match_stats | team_key | dim_team | team_key |
| fact_player_match_stats | player_key | dim_player | player_key |
| fact_player_appearances | match_key | fact_matches | match_key |