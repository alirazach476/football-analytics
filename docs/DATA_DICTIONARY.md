# Data dictionary

_Generated 2026-11-06 from the live PostgreSQL warehouse (`python -m fbplatform.docs_gen`). Schema `wh` = star schema; `gold` = dbt marts; `monitoring` = pipeline/quality tables._

Conventions: surrogate keys end in `_key`; natural keys are `*_id`. NULL means *unknown or not applicable* and is never filled with an estimate. Scheduled fixtures keep NULL scores.

## gold.mart_competition_comparison



| column | type | null | key | description |
|---|---|---|---|---|
| `competition_id` | text | yes |  |  |
| `competition_name` | text | yes |  |  |
| `seasons` | bigint | yes |  |  |
| `matches_played` | bigint | yes |  |  |
| `goals_per_match` | numeric | yes |  |  |
| `draw_pct` | numeric | yes |  |  |
| `home_win_pct` | numeric | yes |  |  |
| `beyond_90_pct` | numeric | yes |  |  |
| `avg_attendance` | numeric | yes |  |  |
| `goals_stddev` | numeric | yes |  |  |

## gold.mart_goal_analysis



| column | type | null | key | description |
|---|---|---|---|---|
| `event_key` | bigint | yes |  |  |
| `match_key` | integer | yes |  | Surrogate key of the match. |
| `season_id` | text | yes |  |  |
| `competition_id` | text | yes |  |  |
| `stage_name` | text | yes |  |  |
| `match_date` | date | yes |  |  |
| `provider` | text | yes |  | Event/line-up source. |
| `team_key` | integer | yes |  | Surrogate key of the team. |
| `event_team_name` | text | yes |  |  |
| `player_key` | integer | yes |  | Surrogate key of the canonical player. |
| `player_name_raw` | text | yes |  | Player name as published by the source. |
| `assist_name_raw` | text | yes |  | Assist provider's name where known. |
| `assist_source` | text | yes |  | Where the assist name came from. |
| `minute` | numeric | yes |  | Match minute (regulation + extra time). |
| `minute_added` | numeric | yes |  |  |
| `period` | integer | yes |  | 1,2 = halves, 3,4 = extra time, 5 = shoot-out. |
| `is_penalty` | boolean | yes |  |  |
| `is_own_goal` | boolean | yes |  | Event is an own goal. |
| `minute_band` | text | yes |  |  |
| `goal_type` | text | yes |  |  |

## gold.mart_group_stage_analysis



| column | type | null | key | description |
|---|---|---|---|---|
| `season_id` | text | yes |  |  |
| `competition_id` | text | yes |  |  |
| `group_name` | text | yes |  |  |
| `matches` | bigint | yes |  |  |
| `goals` | bigint | yes |  |  |
| `draws` | bigint | yes |  |  |
| `goals_per_match` | numeric | yes |  |  |
| `draw_pct` | numeric | yes |  |  |
| `top_team` | text | yes |  |  |
| `top_points` | integer | yes |  |  |
| `top_goal_diff` | integer | yes |  |  |

## gold.mart_head_to_head



| column | type | null | key | description |
|---|---|---|---|---|
| `team_a` | text | yes |  |  |
| `team_b` | text | yes |  |  |
| `team_a_key` | integer | yes |  |  |
| `team_b_key` | integer | yes |  |  |
| `matches` | bigint | yes |  |  |
| `team_a_wins` | bigint | yes |  |  |
| `draws` | bigint | yes |  |  |
| `team_b_wins` | bigint | yes |  |  |
| `team_a_goals` | bigint | yes |  |  |
| `team_b_goals` | bigint | yes |  |  |
| `team_a_shootout_wins` | bigint | yes |  |  |
| `team_b_shootout_wins` | bigint | yes |  |  |
| `first_meeting` | date | yes |  |  |
| `last_meeting` | date | yes |  |  |

## gold.mart_knockout_analysis



| column | type | null | key | description |
|---|---|---|---|---|
| `season_id` | text | yes |  |  |
| `competition_id` | text | yes |  |  |
| `stage_name` | text | yes |  |  |
| `matches` | bigint | yes |  |  |
| `goals` | bigint | yes |  |  |
| `goals_per_match` | numeric | yes |  |  |
| `matches_beyond_90` | bigint | yes |  |  |
| `shootouts` | bigint | yes |  |  |
| `one_goal_margin` | bigint | yes |  |  |
| `drawn_after_et_or_90` | bigint | yes |  |  |

## gold.mart_match_performance



| column | type | null | key | description |
|---|---|---|---|---|
| `match_key` | integer | yes |  | Surrogate key of the match. |
| `match_id` | text | yes |  | Stable natural key: FBM- + hash of (season, date, home, away) as first ingested. |
| `competition_id` | text | yes |  |  |
| `season_id` | text | yes |  |  |
| `match_date` | date | yes |  |  |
| `stage_name` | text | yes |  |  |
| `group_name` | text | yes |  |  |
| `home_team_name` | text | yes |  |  |
| `away_team_name` | text | yes |  |  |
| `venue_name` | text | yes |  |  |
| `venue_city` | text | yes |  |  |
| `venue_country` | text | yes |  |  |
| `referee_name` | text | yes |  |  |
| `attendance` | integer | yes |  | Recorded attendance (0 = a genuine closed-door match). |
| `match_status` | text | yes |  | completed or scheduled. |
| `status_label` | text | yes |  | 'Full time' or 'Coming soon'. |
| `fixture_detail` | text | yes |  | Human-readable summary of what is known about a scheduled fixture. |
| `home_score` | integer | yes |  | Goals incl. extra time, excl. shoot-out (NULL for scheduled). |
| `away_score` | integer | yes |  | As home_score. |
| `total_goals` | integer | yes |  |  |
| `goal_margin` | integer | yes |  |  |
| `outcome_recorded_score` | text | yes |  |  |
| `went_beyond_90` | boolean | yes |  |  |
| `home_pen` | integer | yes |  | Shoot-out goals where known. |
| `away_pen` | integer | yes |  |  |
| `goal_events` | bigint | yes |  |  |
| `shots` | bigint | yes |  |  |
| `shots_on_target` | bigint | yes |  |  |
| `xg_total` | numeric | yes |  |  |
| `has_goal_events` | boolean | yes |  |  |
| `has_team_stats` | boolean | yes |  |  |

## gold.mart_player_career



| column | type | null | key | description |
|---|---|---|---|---|
| `player_key` | integer | yes |  | Surrogate key of the canonical player. |
| `full_name` | text | yes |  |  |
| `nationality` | text | yes |  | From the source, or the single national team the player appears for (see nationality_basis in Silver). |
| `date_of_birth` | date | yes |  |  |
| `tournaments` | bigint | yes |  |  |
| `teams` | bigint | yes |  |  |
| `first_season_year` | integer | yes |  |  |
| `last_season_year` | integer | yes |  |  |
| `appearances` | numeric | yes |  |  |
| `starts` | numeric | yes |  |  |
| `minutes_played` | numeric | yes |  | Minutes on the pitch (whole minutes for Wikipedia-derived rows, nominal 90/120 end, stoppage ignored). |
| `goals` | numeric | yes |  |  |
| `assists` | numeric | yes |  |  |
| `goals_in_minute_matches` | numeric | yes |  |  |
| `assists_in_minute_matches` | numeric | yes |  |  |
| `yellow_cards` | numeric | yes |  |  |
| `red_cards` | numeric | yes |  |  |
| `competitions` | bigint | yes |  |  |

## gold.mart_player_performance



| column | type | null | key | description |
|---|---|---|---|---|
| `player_key` | integer | yes |  | Surrogate key of the canonical player. |
| `full_name` | text | yes |  |  |
| `nationality` | text | yes |  | From the source, or the single national team the player appears for (see nationality_basis in Silver). |
| `team_name` | text | yes |  |  |
| `season_id` | text | yes |  |  |
| `appearances` | bigint | yes |  |  |
| `starts` | bigint | yes |  |  |
| `minutes_played` | numeric | yes |  | Minutes on the pitch (whole minutes for Wikipedia-derived rows, nominal 90/120 end, stoppage ignored). |
| `matches_with_minutes` | bigint | yes |  |  |
| `goals` | bigint | yes |  |  |
| `penalty_goals` | bigint | yes |  |  |
| `own_goals` | bigint | yes |  |  |
| `assists` | bigint | yes |  |  |
| `goal_contributions` | bigint | yes |  |  |
| `yellow_cards` | bigint | yes |  |  |
| `red_cards` | bigint | yes |  |  |
| `goals_in_minute_matches` | bigint | yes |  |  |
| `assists_in_minute_matches` | bigint | yes |  |  |
| `goals_per_90` | numeric | yes |  |  |
| `assists_per_90` | numeric | yes |  |  |

## gold.mart_team_performance



| column | type | null | key | description |
|---|---|---|---|---|
| `team_key` | integer | yes |  | Surrogate key of the team. |
| `team_name` | text | yes |  |  |
| `season_id` | text | yes |  |  |
| `competition_id` | text | yes |  |  |
| `played` | bigint | yes |  |  |
| `wins` | bigint | yes |  |  |
| `draws` | bigint | yes |  |  |
| `losses` | bigint | yes |  |  |
| `goals_for` | bigint | yes |  |  |
| `goals_against` | bigint | yes |  |  |
| `goal_diff` | bigint | yes |  |  |
| `points` | bigint | yes |  |  |
| `win_pct` | numeric | yes |  |  |
| `goals_for_per_match` | numeric | yes |  |  |
| `clean_sheets` | bigint | yes |  |  |
| `shootouts_won` | bigint | yes |  |  |
| `shootouts_lost` | bigint | yes |  |  |
| `furthest_stage_order` | integer | yes |  |  |
| `furthest_stage_played` | text | yes |  |  |

## gold.mart_tournament_summary



| column | type | null | key | description |
|---|---|---|---|---|
| `season_id` | text | yes |  |  |
| `competition_id` | text | yes |  |  |
| `competition_name` | text | yes |  |  |
| `season_year` | integer | yes |  |  |
| `matches_in_dataset` | bigint | yes |  |  |
| `matches_played` | bigint | yes |  |  |
| `matches_coming_soon` | bigint | yes |  |  |
| `total_goals` | bigint | yes |  |  |
| `goals_per_match` | numeric | yes |  |  |
| `draw_pct` | numeric | yes |  |  |
| `matches_beyond_90` | bigint | yes |  |  |
| `shootouts` | bigint | yes |  |  |
| `avg_attendance` | numeric | yes |  |  |
| `teams` | bigint | yes |  |  |
| `first_match_date` | date | yes |  |  |
| `last_match_date` | date | yes |  |  |
| `champion` | text | yes |  |  |
| `runner_up` | text | yes |  |  |
| `tournament_status` | text | yes |  |  |

## gold.mart_upcoming_fixtures



| column | type | null | key | description |
|---|---|---|---|---|
| `match_id` | text | yes |  | Stable natural key: FBM- + hash of (season, date, home, away) as first ingested. |
| `competition_id` | text | yes |  |  |
| `season_id` | text | yes |  |  |
| `match_date` | date | yes |  |  |
| `stage_name` | text | yes |  |  |
| `group_name` | text | yes |  |  |
| `home_team_name` | text | yes |  |  |
| `away_team_name` | text | yes |  |  |
| `venue_name` | text | yes |  |  |
| `venue_city` | text | yes |  |  |
| `venue_country` | text | yes |  |  |
| `status_label` | text | yes |  | 'Full time' or 'Coming soon'. |
| `fixture_detail` | text | yes |  | Human-readable summary of what is known about a scheduled fixture. |

## monitoring.data_quality_results



| column | type | null | key | description |
|---|---|---|---|---|
| `result_id` | bigint | no | PK |  |
| `run_id` | text | no |  |  |
| `checked_at` | timestamp with time zone | no |  |  |
| `layer` | text | no |  |  |
| `table_name` | text | no |  |  |
| `check_name` | text | no |  |  |
| `severity` | text | no |  |  |
| `status` | text | no |  |  |
| `failed_rows` | bigint | yes |  |  |
| `total_rows` | bigint | yes |  |  |
| `detail` | text | yes |  |  |

## monitoring.ingestion_history



| column | type | null | key | description |
|---|---|---|---|---|
| `path` | text | no | PK |  |
| `original_name` | text | yes |  |  |
| `source` | text | yes |  |  |
| `sha256` | text | no |  |  |
| `size_bytes` | bigint | yes |  |  |
| `version` | integer | no | PK |  |
| `ingested_at` | timestamp with time zone | yes |  |  |
| `excluded_ucl` | boolean | yes |  |  |
| `origin` | text | yes |  |  |

## monitoring.pipeline_execution_logs



| column | type | null | key | description |
|---|---|---|---|---|
| `log_id` | bigint | no | PK |  |
| `run_id` | text | no |  |  |
| `step` | text | no |  |  |
| `attempt` | integer | no |  |  |
| `status` | text | no |  |  |
| `started_at` | timestamp with time zone | no |  |  |
| `finished_at` | timestamp with time zone | no |  |  |
| `duration_seconds` | numeric | yes |  |  |
| `rows_processed` | bigint | yes |  |  |
| `detail` | text | yes |  |  |
| `error` | text | yes |  |  |

## monitoring.pipeline_state



| column | type | null | key | description |
|---|---|---|---|---|
| `key` | text | no | PK |  |
| `value` | text | yes |  |  |
| `updated_at` | timestamp with time zone | yes |  |  |

## monitoring.source_coverage_report



| column | type | null | key | description |
|---|---|---|---|---|
| `run_id` | text | no | PK |  |
| `generated_at` | timestamp with time zone | no |  |  |
| `season_id` | text | no | PK |  |
| `competition_id` | text | no |  |  |
| `expected_matches` | integer | yes |  |  |
| `matches_in_dataset` | integer | yes |  |  |
| `matches_played` | integer | yes |  |  |
| `matches_coming_soon` | integer | yes |  |  |
| `pct_referee` | numeric | yes |  |  |
| `pct_venue` | numeric | yes |  |  |
| `pct_attendance` | numeric | yes |  |  |
| `pct_lineups` | numeric | yes |  |  |
| `pct_events` | numeric | yes |  |  |
| `pct_team_stats` | numeric | yes |  |  |
| `pct_man_of_match` | numeric | yes |  |  |
| `pct_events_with_coordinates` | numeric | yes |  |  |
| `goal_events` | integer | yes |  |  |
| `goal_events_with_player` | integer | yes |  |  |
| `awards` | integer | yes |  |  |
| `coverage_flag` | text | no |  |  |
| `goals_recorded` | integer | yes |  |  |
| `pct_goals_with_event` | numeric | yes |  |  |

## wh.dim_competition (4 rows)

The four competitions in scope (WC, EURO, COPA, UNL).

| column | type | null | key | description |
|---|---|---|---|---|
| `competition_key` | integer | no | PK | FK to dim_competition. |
| `competition_id` | text | no |  |  |
| `competition_name` | text | no |  |  |

## wh.dim_date (10,257 rows)

Calendar dimension covering all match dates.

| column | type | null | key | description |
|---|---|---|---|---|
| `date_key` | integer | no | PK | YYYYMMDD, FK to dim_date. |
| `full_date` | date | no |  |  |
| `year` | integer | yes |  |  |
| `quarter` | integer | yes |  |  |
| `month` | integer | yes |  |  |
| `month_name` | text | yes |  |  |
| `day` | integer | yes |  |  |
| `day_of_week` | integer | yes |  |  |
| `day_name` | text | yes |  |  |
| `is_weekend` | boolean | yes |  |  |

## wh.dim_player (8,410 rows)

Canonical players after entity resolution (merged ids listed in `merged_player_ids`).

| column | type | null | key | description |
|---|---|---|---|---|
| `player_key` | integer | no | PK | Surrogate key of the canonical player. |
| `player_id` | text | no |  |  |
| `full_name` | text | yes |  |  |
| `display_name` | text | yes |  |  |
| `nationality` | text | yes |  | From the source, or the single national team the player appears for (see nationality_basis in Silver). |
| `date_of_birth` | date | yes |  |  |
| `height_cm` | numeric | yes |  |  |
| `preferred_foot` | text | yes |  |  |
| `primary_position` | text | yes |  |  |
| `merged_player_ids` | text | yes |  | JSON list of all source ids merged into this player. |
| `n_source_ids` | integer | yes |  |  |

## wh.dim_player_xref (9,978 rows)

Every original source player id -> canonical player and the rule that merged it.

| column | type | null | key | description |
|---|---|---|---|---|
| `player_id_original` | text | no | PK |  |
| `player_key` | integer | no |  | Surrogate key of the canonical player. |
| `resolution_rule` | text | no |  | Entity-resolution rule: D1 same name+DOB; D2 name containment + shared national team + never in one line-up. |

## wh.dim_referee (516 rows)

Referees parsed from 'Name (Country)'.

| column | type | null | key | description |
|---|---|---|---|---|
| `referee_key` | integer | no | PK |  |
| `referee_name` | text | no |  |  |
| `referee_country` | text | no |  |  |

## wh.dim_season (29 rows)

One row per edition with expected/actual/played/scheduled match counts.

| column | type | null | key | description |
|---|---|---|---|---|
| `season_key` | integer | no | PK | FK to dim_season. |
| `season_id` | text | no |  |  |
| `competition_key` | integer | no |  | FK to dim_competition. |
| `season_year` | integer | no |  |  |
| `expected_matches` | integer | yes |  |  |
| `matches_in_dataset` | integer | yes |  |  |
| `matches_played` | integer | yes |  |  |
| `matches_scheduled` | integer | yes |  |  |

## wh.dim_team (103 rows)

National teams (surrogate key; `team_id` is the stable natural key).

| column | type | null | key | description |
|---|---|---|---|---|
| `team_key` | integer | no | PK | Surrogate key of the team. |
| `team_id` | text | no |  |  |
| `team_name` | text | no |  |  |
| `team_type` | text | yes |  |  |
| `country` | text | yes |  |  |
| `country_code` | text | yes |  |  |
| `confederation` | text | yes |  |  |
| `is_current` | boolean | no |  |  |

## wh.dim_team_name_history (108 rows)

Former/alternative team names. Validity dates are NULL: no source gives them.

| column | type | null | key | description |
|---|---|---|---|---|
| `team_key` | integer | no | PK | Surrogate key of the team. |
| `name` | text | no | PK |  |
| `name_type` | text | no |  |  |
| `valid_from` | date | yes |  |  |
| `valid_to` | date | yes |  |  |

## wh.dim_tournament_stage (9 rows)

Stages with order and knockout flag.

| column | type | null | key | description |
|---|---|---|---|---|
| `stage_key` | integer | no | PK | FK to dim_tournament_stage. |
| `stage_name` | text | no |  |  |
| `stage_order` | integer | yes |  |  |
| `is_knockout` | boolean | no |  |  |

## wh.dim_venue (338 rows)

Stadiums (identity = Wikipedia article) with coordinates and capacity where known.

| column | type | null | key | description |
|---|---|---|---|---|
| `venue_key` | integer | no | PK |  |
| `venue_id` | text | no |  |  |
| `venue_name` | text | yes |  |  |
| `city` | text | yes |  |  |
| `country` | text | yes |  |  |
| `latitude` | numeric | yes |  | Venue latitude. |
| `longitude` | numeric | yes |  |  |
| `capacity` | integer | yes |  | Current stadium capacity from Wikipedia (renovations make historic attendances exceed it sometimes). |
| `wikidata_id` | text | yes |  |  |

## wh.etl_load_log

Row counts of the last warehouse load.

| column | type | null | key | description |
|---|---|---|---|---|
| `load_id` | integer | no | PK |  |
| `loaded_at` | timestamp with time zone | yes |  |  |
| `table_name` | text | yes |  |  |
| `rows_loaded` | bigint | yes |  |  |
| `source_rows` | bigint | yes |  |  |

## wh.fact_match_events (1,033,220 rows)

All event rows (goals, cards, substitutions, and for StatsBomb/Wyscout every on-ball event with coordinates).

| column | type | null | key | description |
|---|---|---|---|---|
| `event_key` | bigint | no | PK |  |
| `event_id` | text | no |  |  |
| `match_key` | integer | no |  | Surrogate key of the match. |
| `provider` | text | yes |  | Event/line-up source. |
| `event_type` | text | yes |  | Event class as normalised from the provider. |
| `detail_type` | text | yes |  |  |
| `team_key` | integer | yes |  | Surrogate key of the team. |
| `player_key` | integer | yes |  | Surrogate key of the canonical player. |
| `related_player_key` | integer | yes |  |  |
| `player_name_raw` | text | yes |  | Player name as published by the source. |
| `related_player_name_raw` | text | yes |  | Second player of the event (e.g. player coming on for a substitution). |
| `assist_name_raw` | text | yes |  | Assist provider's name where known. |
| `assist_source` | text | yes |  | Where the assist name came from. |
| `period` | integer | yes |  | 1,2 = halves, 3,4 = extra time, 5 = shoot-out. |
| `minute` | numeric | yes |  | Match minute (regulation + extra time). |
| `minute_added` | numeric | yes |  |  |
| `second` | numeric | yes |  |  |
| `location_x` | numeric | yes |  | Pitch coordinate (system in coordinate_system). |
| `location_y` | numeric | yes |  |  |
| `end_location_x` | numeric | yes |  |  |
| `end_location_y` | numeric | yes |  |  |
| `coordinate_system` | text | yes |  | statsbomb_120x80 or wyscout_pct_0_100. |
| `outcome` | text | yes |  |  |
| `card` | text | yes |  |  |
| `xg` | numeric | yes |  | Expected goals of the shot (StatsBomb only). |
| `is_goal` | boolean | yes |  | Event is a goal. |
| `is_penalty` | boolean | yes |  |  |
| `is_own_goal` | boolean | yes |  | Event is an own goal. |
| `is_assist` | boolean | yes |  |  |
| `is_key_pass` | boolean | yes |  |  |

## wh.fact_matches (1,830 rows)

One row per match, played or scheduled. Scheduled fixtures have status 'scheduled', label 'Coming soon' and NULL scores.

| column | type | null | key | description |
|---|---|---|---|---|
| `match_key` | integer | no | PK | Surrogate key of the match. |
| `match_id` | text | no |  | Stable natural key: FBM- + hash of (season, date, home, away) as first ingested. |
| `competition_key` | integer | no |  | FK to dim_competition. |
| `season_key` | integer | no |  | FK to dim_season. |
| `date_key` | integer | no |  | YYYYMMDD, FK to dim_date. |
| `stage_key` | integer | yes |  | FK to dim_tournament_stage. |
| `group_name` | text | yes |  |  |
| `matchday` | integer | yes |  |  |
| `leg` | integer | yes |  |  |
| `home_team_key` | integer | yes |  | FK to dim_team; NULL while the team is undecided (placeholder such as A1). |
| `away_team_key` | integer | yes |  | FK to dim_team; NULL while undecided. |
| `home_team_display` | text | no |  | Team label as known (placeholder text for undecided fixtures). |
| `away_team_display` | text | no |  | Team label as known. |
| `venue_key` | integer | yes |  |  |
| `referee_key` | integer | yes |  |  |
| `match_status` | text | no |  | completed or scheduled. |
| `status_label` | text | no |  | 'Full time' or 'Coming soon'. |
| `fixture_detail` | text | yes |  | Human-readable summary of what is known about a scheduled fixture. |
| `kickoff_local` | text | yes |  |  |
| `kickoff_utc` | text | yes |  |  |
| `attendance` | integer | yes |  | Recorded attendance (0 = a genuine closed-door match). |
| `home_score` | integer | yes |  | Goals incl. extra time, excl. shoot-out (NULL for scheduled). |
| `away_score` | integer | yes |  | As home_score. |
| `score_basis` | text | yes |  | What home_score/away_score include. |
| `home_score_ht` | integer | yes |  |  |
| `away_score_ht` | integer | yes |  |  |
| `home_score_ft90` | integer | yes |  | Score after 90 minutes where known. |
| `away_score_ft90` | integer | yes |  |  |
| `home_score_et` | integer | yes |  |  |
| `away_score_et` | integer | yes |  |  |
| `home_pen` | integer | yes |  | Shoot-out goals where known. |
| `away_pen` | integer | yes |  |  |
| `shootout_winner_side` | text | yes |  | home/away winner of a shoot-out (martj42 shootouts file; no kick scores). |
| `went_extra_time` | text | yes |  | Source flag; use stg_matches.went_beyond_90 for the derived indicator. |
| `winner` | text | yes |  |  |
| `score_note` | text | yes |  |  |
| `man_of_the_match_raw` | text | yes |  | Man of the match name as published. |
| `primary_provider` | text | yes |  | Provider that supplied the match's score row. |
| `source_url` | text | yes |  | Where the row came from (line number for text sources). |
| `retrieval_timestamp` | text | yes |  |  |

## wh.fact_player_appearances (35,351 rows)

Line-up rows: who played, starter flag, minutes (provider-derived or Wikipedia-derived, see `fact_player_appearances` notes).

| column | type | null | key | description |
|---|---|---|---|---|
| `appearance_key` | bigint | no | PK |  |
| `match_key` | integer | no |  | Surrogate key of the match. |
| `team_key` | integer | yes |  | Surrogate key of the team. |
| `player_key` | integer | yes |  | Surrogate key of the canonical player. |
| `player_name_raw` | text | yes |  | Player name as published by the source. |
| `provider` | text | yes |  | Event/line-up source. |
| `jersey_number` | integer | yes |  |  |
| `is_starter` | boolean | yes |  | Started the match. |
| `appeared` | boolean | yes |  |  |
| `is_captain` | boolean | yes |  |  |
| `minute_on` | numeric | yes |  |  |
| `minute_off` | numeric | yes |  |  |
| `minutes_played` | numeric | yes |  | Minutes on the pitch (whole minutes for Wikipedia-derived rows, nominal 90/120 end, stoppage ignored). |
| `yellow_cards` | integer | yes |  |  |
| `red_cards` | integer | yes |  |  |

## wh.fact_player_awards (391 rows)

Individual awards from Wikipedia award pages; keys NULL when the winner could not be linked uniquely.

| column | type | null | key | description |
|---|---|---|---|---|
| `award_key` | integer | no | PK |  |
| `season_key` | integer | no |  | FK to dim_season. |
| `player_key` | integer | yes |  | Surrogate key of the canonical player. |
| `team_key` | integer | yes |  | Surrogate key of the team. |
| `award_name` | text | no |  | Award as named on the source page. |
| `award_category` | text | no |  | Standardised category (Best player, Top scorer, ...). |
| `position_label` | text | yes |  |  |
| `rank` | integer | yes |  | 1 = winner, 2/3 = runners-up where the award has them. |
| `entity_name_raw` | text | no |  | Winner as published. |
| `value_text` | text | yes |  | e.g. '8 goals', '5 clean sheets'. |
| `link_status` | text | yes |  | How the winner was linked: squad_name_match, ambiguous, not_in_season_squads, ... |
| `source_page` | text | yes |  |  |
| `source_revid` | bigint | yes |  |  |

## wh.fact_player_match_stats (15,006 rows)

Player statistics per match (StatsBomb-covered matches only).

| column | type | null | key | description |
|---|---|---|---|---|
| `match_key` | integer | no | PK | Surrogate key of the match. |
| `team_key` | integer | no | PK | Surrogate key of the team. |
| `player_key` | integer | no | PK | Surrogate key of the canonical player. |
| `provider` | text | yes |  | Event/line-up source. |
| `jersey_number` | integer | yes |  |  |
| `is_starter` | boolean | yes |  | Started the match. |
| `minutes_played` | numeric | yes |  | Minutes on the pitch (whole minutes for Wikipedia-derived rows, nominal 90/120 end, stoppage ignored). |
| `sub_on` | boolean | yes |  |  |
| `sub_off` | boolean | yes |  |  |
| `goals` | integer | yes |  |  |
| `own_goals` | integer | yes |  |  |
| `assists` | integer | yes |  |  |
| `shots` | integer | yes |  |  |
| `shots_on_target` | integer | yes |  |  |
| `passes` | integer | yes |  |  |
| `passes_completed` | integer | yes |  |  |
| `key_passes` | integer | yes |  |  |
| `tackles` | integer | yes |  |  |
| `interceptions` | integer | yes |  |  |
| `clearances` | integer | yes |  |  |
| `blocks` | integer | yes |  |  |
| `fouls_committed` | integer | yes |  |  |
| `fouls_won` | integer | yes |  |  |
| `yellow_cards` | integer | yes |  |  |
| `red_cards` | integer | yes |  |  |
| `saves` | integer | yes |  |  |
| `corners_taken` | integer | yes |  |  |
| `offsides` | integer | yes |  |  |
| `xg` | numeric | yes |  | Expected goals of the shot (StatsBomb only). |
| `xa` | numeric | yes |  |  |
| `pass_accuracy` | numeric | yes |  |  |

## wh.fact_team_awards (16 rows)

Team awards (fair play, most entertaining team).

| column | type | null | key | description |
|---|---|---|---|---|
| `award_key` | integer | no | PK |  |
| `season_key` | integer | no |  | FK to dim_season. |
| `team_key` | integer | yes |  | Surrogate key of the team. |
| `award_name` | text | no |  | Award as named on the source page. |
| `award_category` | text | no |  | Standardised category (Best player, Top scorer, ...). |
| `entity_name_raw` | text | no |  | Winner as published. |
| `source_page` | text | yes |  |  |
| `source_revid` | bigint | yes |  |  |

## wh.fact_team_match_stats (3,406 rows)

Team statistics per match (StatsBomb-covered matches only).

| column | type | null | key | description |
|---|---|---|---|---|
| `match_key` | integer | no | PK | Surrogate key of the match. |
| `team_key` | integer | no | PK | Surrogate key of the team. |
| `provider` | text | yes |  | Event/line-up source. |
| `goals` | integer | yes |  |  |
| `own_goals` | integer | yes |  |  |
| `assists` | integer | yes |  |  |
| `shots` | integer | yes |  |  |
| `shots_on_target` | integer | yes |  |  |
| `passes` | integer | yes |  |  |
| `passes_completed` | integer | yes |  |  |
| `key_passes` | integer | yes |  |  |
| `tackles` | integer | yes |  |  |
| `interceptions` | integer | yes |  |  |
| `clearances` | integer | yes |  |  |
| `blocks` | integer | yes |  |  |
| `fouls_committed` | integer | yes |  |  |
| `fouls_won` | integer | yes |  |  |
| `yellow_cards` | integer | yes |  |  |
| `red_cards` | integer | yes |  |  |
| `saves` | integer | yes |  |  |
| `corners_taken` | integer | yes |  |  |
| `offsides` | integer | yes |  |  |
| `xg` | numeric | yes |  | Expected goals of the shot (StatsBomb only). |
| `xa` | numeric | yes |  |  |
| `goals_for_incl_own_goals` | integer | yes |  |  |
| `pass_accuracy` | numeric | yes |  |  |
| `possession_pct` | numeric | yes |  |  |
| `substitutions` | integer | yes |  |  |

## wh.fact_tournament_standings (762 rows)

Group tables DERIVED from played group-stage matches (basis column states the rules).

| column | type | null | key | description |
|---|---|---|---|---|
| `season_key` | integer | no | PK | FK to dim_season. |
| `team_key` | integer | no | PK | Surrogate key of the team. |
| `group_name` | text | no | PK |  |
| `group_position` | integer | yes |  | Position in the derived group table (tiebreak: points, goal difference, goals for only). |
| `played` | integer | yes |  |  |
| `wins` | integer | yes |  |  |
| `draws` | integer | yes |  |  |
| `losses` | integer | yes |  |  |
| `goals_for` | integer | yes |  |  |
| `goals_against` | integer | yes |  |  |
| `goal_difference` | integer | yes |  |  |
| `points` | integer | yes |  |  |
| `basis` | text | no |  | Rules used to derive the standing. |
