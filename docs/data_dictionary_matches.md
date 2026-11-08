# Data dictionary: `data/processed/matches.parquet` (+ `.csv`)

One row per match. Null means "not stated by any verified source" – never imputed.

| column | meaning |
|---|---|
| match_id | `FBM-` + sha1(season, date, normalised home, normalised away)[:12]; deterministic |
| competition_id / season_id | registry keys (`WC`, `UCL`, `EURO`, `COPA`; e.g. `WC-2022`, `UCL-2019-20`) |
| stage / stage_raw | normalised stage (Group stage, League phase, Knockout play-off, Round of 32/16, Quarter-finals, Semi-finals, Third place, Final) / label as written in source |
| group, matchday | from source headers; Champions League group files give matchday but no group letter |
| leg, leg_source | Champions League two-legged ties: `header` (play-off matchday) or `derived_from_pairing` (same two teams in same stage, ordered by date). Null for single-leg matches |
| home_team_raw / away_team_raw | team names exactly as in the source (no entity resolution yet – Phase 5). In tournaments "home" is simply the team listed first |
| home/away_team_country_code | only where the source writes `(ENG)` etc. (Champions League) |
| match_date | date as written (local date of the venue per source) |
| kickoff_time_local, tz_offset_minutes, timezone, kickoff_utc, time_note | local time as written; offset only where the source states `UTC±n`; `kickoff_utc` only computable then |
| venue_raw, referee_raw | venue text from OpenFootball; referee only from StatsBomb. Normalised venue/referee IDs come with Phase 5/9 |
| attendance, match_duration_minutes | always null: no verified source provides them |
| home_score / away_score | final on-pitch score excluding shoot-out |
| score_basis | `ft90`, `aet`, or `unspecified_after_extra_time_or_90` (source wrote `pen. (x-y)`), null for StatsBomb-only rows |
| *_score_ft90 | 90-minute score where stated (plain matches, JSON `ft`, CL two-value parentheses) |
| *_score_ht | half-time, only where unambiguous (see below) |
| *_score_et | score after extra time where stated |
| home_pen / away_pen | shoot-out result. After an unlevel second leg it decides the **tie**, not the match |
| went_extra_time | True if ET/penalties indicated; False if a 90-minute result; null if no result |
| winner | `home`/`away`/`draw` for the match: on-pitch score first, then shoot-out |
| match_status | `completed` if a score exists else `scheduled` |
| primary_provider, provider_match_ids | provider chosen for the row; JSON map of provider -> id (StatsBomb ids where linked) |
| source_url, source_line, retrieval_timestamp | provenance: file URL (+`#L<line>` for text sources), line number, UTC time of the real fetch |
| date_check | `weekday_ok` / `weekday_year_adjusted` / `weekday_mismatch` / `no_weekday` / `json_iso` |
| score_note, score_raw | parsing remarks / verbatim score text |

## Known ambiguities (deliberately left null)
* In Euro 2008–2016 and Copa files, the `(x-y)` after an `a.e.t.`/`pen.` score is sometimes half-time and sometimes the 90-minute score. It is not interpreted; half-time and 90-minute scores for those ET matches stay null (JSON-sourced seasons have them).
* Copa `pen. (x-y)` rows: the 90/120-minute basis is unknown (`score_basis` says so).
* Raw source records (full text/JSON incl. goal-scorer lines) are in `source_records.parquet`, keyed by `match_id`, for the later events phase.

# Other tables (data/processed/)

| table | grain | notes |
|---|---|---|
| teams.parquet | one per canonical team | team_id, team_name, team_type, classification, country, historical_names (JSON, all spellings seen), country_codes_seen, source_identifiers (StatsBomb team id), confederation=null, logo_ref=null |
| team_aliases.csv | one per raw spelling | alias, team_id, rule (R1-R4), seasons_seen |
| players.parquet | one per StatsBomb player | full_name, display_name, name_variants, nationality (lineup `country`), primary_position (most frequent), team_ids; DOB/height/foot null |
| lineups.parquet | player x match | is_starter, appeared, positions (JSON incl. from/to/reasons), jersey_number, cards (JSON), minutes_played_derived = first entry to last exit (0 if never appeared; match end = last event minute of periods 1-4) |
| events.parquet | one per StatsBomb event (995,873) | event_id `SB-<uuid>`, event_type (StatsBomb type, snake_case), detail_type (pass/shot/duel/goalkeeper type), player_id, team_id, timestamp, minute, second, period (5 = shoot-out), location_x/y (120x80 pitch), end_location_x/y, outcome, related_player_id (pass recipient / substitute / shot's key passer), source_id (StatsBomb uuid), xg, card, flags is_goal/is_penalty/is_key_pass/is_assist/is_corner (null unless true) |
| player_match_stats.parquet, team_match_stats.parquet | player/team x match | derived from events + lineups; definitions in `ingest/stats.py` docstring. Shoot-out excluded. possession_pct is null (not computed). xa = xG of shots from the player's key pass |

Brief's event categories -> storage: goals = `shot` with outcome Goal (is_goal); assists = `pass` with is_assist; penalties = `shot` detail Penalty; tackles = `duel` detail Tackle; cards = `card` column on foul_committed/bad_behaviour; corners = `pass` is_corner; saves = `goal_keeper` events; **VAR decisions: not provided by StatsBomb open data, zero rows**.

# Final tables to use (data/processed/) - provider-unified

| table | content |
|---|---|
| events_all.parquet | 1,074,945 rows: StatsBomb (995,873 full events), Wyscout (78,433 events, Euro 2016), OpenFootball (639 goal-only events). Extra columns: `provider`, `coordinate_system` (`statsbomb_120x80` / `wyscout_pct_0_100`, never rescaled), `tags` (Wyscout labels), `is_own_goal`, `player_name_raw` (goal-only events: scorer name, no player id), `minute_added` (stoppage, goal-only events), `player_id_source`. A match has events from exactly one provider. |
| lineups_all.parquet | StatsBomb + Wyscout lineups (Wyscout: starters/bench from match formation; substitutions as `substitution` events; minutes derived like StatsBomb's) |
| players_all.parquet | 3,248 players. StatsBomb rows enriched with Wyscout DOB/height/foot where rule P1 links them (375 people); other Wyscout players (Euro 2016/WC 2018 squads) kept as `P-WY-` rows. DOB/height/foot null for the rest |
| player_links.csv | the 375 P1 links (exact normalised name + nationality, unique on both sides) |
| player_match_stats_all / team_match_stats_all | StatsBomb stats (full set) + Wyscout stats (only fields Wyscout defines; tackles, interceptions, blocks, fouls_won, xg, xa, possession are NULL for Wyscout, not 0). Shoot-out excluded. |
| match_event_coverage.csv | per completed match: what event data exists (see docs/event_coverage.md) |

Wyscout flags: `is_goal` only on the scoring event (Wyscout also tags the goalkeeper's mirrored "Save attempt" - that one has outcome `Goal conceded`). Shots on target for Wyscout = shot tagged with a goal-frame placement (tags 1201-1209) or scored. Saves = goalkeeper `save_attempt` events not conceding.

## Attribution (licences)
* Wyscout events/players: CC BY 4.0 - Pappalardo et al., "A public data set of spatio-temporal match events in soccer competitions", Scientific Data 6:236 (2019), doi:10.1038/s41597-019-0247-7.
* StatsBomb Open Data: attribution to StatsBomb required (user agreement in their repo).
* OpenFootball: CC0.


# Squads and match details (added 2026-11-05)

| table | grain | notes |
|---|---|---|
| squads/squads.parquet | squad member x tournament | season_id, team_id, shirt_number, position (GK/DF/MF/FW), player_name_raw, is_captain, date_of_birth, caps, goals, club_raw, club_country_raw, player_id + link_rule (S1/S2/S3), source_url (page revision), retrieved_at |
| squads/head_coaches.parquet | team x tournament | head_coach_raw as written under each team heading |
| lineups_all (Wikipedia rows) | player x match | player_id empty (names only): player_name_raw, jersey_number, position, is_starter, is_captain, minute_on, minute_off |
| events_all (Wikipedia rows) | card / substitution / goal | player_name_raw, related_player_name_raw (player coming on), minute + minute_added (stoppage); no coordinates |
| matches (new columns) | match | man_of_the_match_raw, assistant_referees_raw, fourth_official_raw, var_officials_raw (the VAR *officials*; VAR decisions are not available) |
| match_event_coverage | match | event_coverage, goals_provider, cards_subs_provider, has_lineups, has_coordinates, has_xg |

Card minutes: Wikipedia shows the minute being played (51'), StatsBomb the elapsed minute (50): comparisons use a 1-2 minute tolerance.


# Venues and attendance provenance (added 2026-11-06)

| table / column | meaning |
|---|---|
| venues.parquet | venue_id (`V-Q123` Wikidata id, else `V-<slug>`), venue_name, wikipedia_title, wikidata_id, city, country, country_values_seen, latitude, longitude, capacity (infobox, as written there; null if absent), name_variants, n_matches, first_match, last_match, source, revid |
| matches.venue_id / venue_name / venue_city / venue_country | the venue of the match (null only for 4 unplayed Euro 2028 fixtures) |
| matches.venue_wikipedia_title, venue_city_raw, venue_link_rule | the stadium hyperlink found in the match box; rule = `match_box_hyperlink` or `tournament_host_venue_map` (fixtures with no box yet) |
| matches.venue_raw | the raw venue text of the primary source, unchanged |
| matches.attendance_source | `en.wikipedia`, or `es.wikipedia (often a rounded estimate)`; 0 is a real value (closed doors); null = recorded nowhere |
