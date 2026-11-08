-- Warehouse schema (PostgreSQL 16). Rebuilt from the Silver layer; Bronze stays the system of record.
DROP SCHEMA IF EXISTS wh CASCADE;
CREATE SCHEMA wh;
SET search_path = wh;

CREATE TABLE dim_competition (competition_key int PRIMARY KEY, competition_id text UNIQUE NOT NULL, competition_name text NOT NULL);
CREATE TABLE dim_season (season_key int PRIMARY KEY, season_id text UNIQUE NOT NULL, competition_key int NOT NULL REFERENCES dim_competition,
  season_year int NOT NULL, expected_matches int, matches_in_dataset int, matches_played int, matches_scheduled int);
CREATE TABLE dim_team (team_key int PRIMARY KEY, team_id text UNIQUE NOT NULL, team_name text NOT NULL, team_type text, country text,
  country_code text, confederation text, is_current boolean NOT NULL DEFAULT true);
-- Historical names: validity dates are NOT known from the sources, so they stay NULL (never invented).
CREATE TABLE dim_team_name_history (team_key int NOT NULL REFERENCES dim_team, name text NOT NULL, name_type text NOT NULL,
  valid_from date, valid_to date, PRIMARY KEY (team_key, name));
CREATE TABLE dim_player (player_key int PRIMARY KEY, player_id text UNIQUE NOT NULL, full_name text, display_name text, nationality text,
  date_of_birth date, height_cm numeric, preferred_foot text, primary_position text, merged_player_ids text, n_source_ids int);
CREATE TABLE dim_player_xref (player_id_original text PRIMARY KEY, player_key int NOT NULL REFERENCES dim_player, resolution_rule text NOT NULL);
CREATE TABLE dim_venue (venue_key int PRIMARY KEY, venue_id text UNIQUE NOT NULL, venue_name text, city text, country text,
  latitude numeric, longitude numeric, capacity int, wikidata_id text);
CREATE TABLE dim_referee (referee_key int PRIMARY KEY, referee_name text NOT NULL, referee_country text NOT NULL DEFAULT '', UNIQUE (referee_name, referee_country));
CREATE TABLE dim_date (date_key int PRIMARY KEY, full_date date UNIQUE NOT NULL, year int, quarter int, month int, month_name text, day int,
  day_of_week int, day_name text, is_weekend boolean);
CREATE TABLE dim_tournament_stage (stage_key int PRIMARY KEY, stage_name text UNIQUE NOT NULL, stage_order int, is_knockout boolean NOT NULL);

CREATE TABLE fact_matches (
  match_key int PRIMARY KEY, match_id text UNIQUE NOT NULL,
  competition_key int NOT NULL REFERENCES dim_competition, season_key int NOT NULL REFERENCES dim_season,
  date_key int NOT NULL REFERENCES dim_date, stage_key int REFERENCES dim_tournament_stage, group_name text, matchday int, leg int,
  home_team_key int REFERENCES dim_team, away_team_key int REFERENCES dim_team,
  home_team_display text NOT NULL, away_team_display text NOT NULL,
  venue_key int REFERENCES dim_venue, referee_key int REFERENCES dim_referee,
  match_status text NOT NULL CHECK (match_status IN ('completed','scheduled')), status_label text NOT NULL, fixture_detail text,
  kickoff_local text, kickoff_utc text, attendance int CHECK (attendance >= 0),
  home_score int, away_score int, score_basis text, home_score_ht int, away_score_ht int, home_score_ft90 int, away_score_ft90 int,
  home_score_et int, away_score_et int, home_pen int, away_pen int, shootout_winner_side text CHECK (shootout_winner_side IN ('home','away')), went_extra_time text, winner text, score_note text,
  man_of_the_match_raw text, primary_provider text, source_url text, retrieval_timestamp text,
  CHECK (match_status = 'completed' OR (home_score IS NULL AND away_score IS NULL)));
CREATE TABLE fact_team_match_stats (match_key int NOT NULL REFERENCES fact_matches, team_key int NOT NULL REFERENCES dim_team, provider text,
  goals int, own_goals int, assists int, shots int, shots_on_target int, passes int, passes_completed int, key_passes int, tackles int,
  interceptions int, clearances int, blocks int, fouls_committed int, fouls_won int, yellow_cards int, red_cards int, saves int,
  corners_taken int, offsides int, xg numeric, xa numeric, goals_for_incl_own_goals int, pass_accuracy numeric, possession_pct numeric, substitutions int,
  PRIMARY KEY (match_key, team_key));
CREATE TABLE fact_player_match_stats (match_key int NOT NULL REFERENCES fact_matches, team_key int NOT NULL REFERENCES dim_team,
  player_key int NOT NULL REFERENCES dim_player, provider text, jersey_number int, is_starter boolean, minutes_played numeric, sub_on boolean, sub_off boolean,
  goals int, own_goals int, assists int, shots int, shots_on_target int, passes int, passes_completed int, key_passes int, tackles int,
  interceptions int, clearances int, blocks int, fouls_committed int, fouls_won int, yellow_cards int, red_cards int, saves int,
  corners_taken int, offsides int, xg numeric, xa numeric, pass_accuracy numeric, PRIMARY KEY (match_key, team_key, player_key));
CREATE TABLE fact_player_appearances (appearance_key bigint PRIMARY KEY, match_key int NOT NULL REFERENCES fact_matches,
  team_key int REFERENCES dim_team, player_key int REFERENCES dim_player, player_name_raw text, provider text, jersey_number int,
  is_starter boolean, appeared boolean, is_captain boolean, minute_on numeric, minute_off numeric, minutes_played numeric,
  yellow_cards int, red_cards int);
CREATE TABLE fact_match_events (event_key bigint PRIMARY KEY, event_id text UNIQUE NOT NULL, match_key int NOT NULL REFERENCES fact_matches,
  provider text, event_type text, detail_type text, team_key int REFERENCES dim_team, player_key int REFERENCES dim_player,
  related_player_key int REFERENCES dim_player, player_name_raw text, related_player_name_raw text, assist_name_raw text, assist_source text,
  period int, minute numeric, minute_added numeric, second numeric, location_x numeric, location_y numeric, end_location_x numeric, end_location_y numeric,
  coordinate_system text, outcome text, card text, xg numeric, is_goal boolean, is_penalty boolean, is_own_goal boolean, is_assist boolean, is_key_pass boolean);
-- Managers: best source per team and match (statsbomb_match > wikipedia_match > wikipedia_squad_head_coach). level='tournament' = the team's head coach at that edition, not confirmed per match.
CREATE TABLE fact_match_managers (match_key int NOT NULL REFERENCES fact_matches, team_key int NOT NULL REFERENCES dim_team, side text, manager_name text NOT NULL,
  source text NOT NULL, level text NOT NULL, PRIMARY KEY (match_key, team_key));
CREATE TABLE fact_tournament_standings (season_key int NOT NULL REFERENCES dim_season, team_key int NOT NULL REFERENCES dim_team, group_name text NOT NULL,
  group_position int, played int, wins int, draws int, losses int, goals_for int, goals_against int, goal_difference int, points int,
  basis text NOT NULL, PRIMARY KEY (season_key, team_key, group_name));
-- Awards: secondary source (Wikipedia award pages). player_key/team_key are NULL when the winner could not be linked uniquely; the raw name is always kept.
CREATE TABLE fact_player_awards (award_key int PRIMARY KEY, season_key int NOT NULL REFERENCES dim_season, player_key int REFERENCES dim_player,
  team_key int REFERENCES dim_team, award_name text NOT NULL, award_category text NOT NULL, position_label text, rank int, entity_name_raw text NOT NULL,
  value_text text, link_status text, source_page text, source_revid bigint);
CREATE TABLE fact_team_awards (award_key int PRIMARY KEY, season_key int NOT NULL REFERENCES dim_season, team_key int REFERENCES dim_team,
  award_name text NOT NULL, award_category text NOT NULL, entity_name_raw text NOT NULL, source_page text, source_revid bigint);

CREATE INDEX ix_fm_season ON fact_matches(season_key);
CREATE INDEX ix_fm_date ON fact_matches(date_key);
CREATE INDEX ix_fm_home ON fact_matches(home_team_key);
CREATE INDEX ix_fm_away ON fact_matches(away_team_key);
CREATE INDEX ix_fe_match ON fact_match_events(match_key);
CREATE INDEX ix_fe_player ON fact_match_events(player_key);
CREATE INDEX ix_fe_type ON fact_match_events(event_type);
CREATE INDEX ix_fpa_match ON fact_player_appearances(match_key);
CREATE INDEX ix_fpa_player ON fact_player_appearances(player_key);
CREATE INDEX ix_fpms_player ON fact_player_match_stats(player_key);

CREATE TABLE etl_load_log (load_id serial PRIMARY KEY, loaded_at timestamptz DEFAULT now(), table_name text, rows_loaded bigint, source_rows bigint);
