# Data quality

_Generated 2026-11-06._

**Automated checks:** 14 of 14 passed in the latest run (Pandera on Silver, dbt on Gold) = 100%. This is rule compliance, **not** completeness: see coverage below.

## What is checked, and where

| layer | tool | examples |
|---|---|---|
| Bronze | file register | SHA-256 + size + version per source file; unchanged re-run registers nothing; UEFA Champions League files flagged `excluded_ucl` |
| Silver | Pandera (critical: stop the run; warning: recorded) | unique ids, allowed competitions (WC/EURO/COPA/UNL only), scheduled fixtures have null scores + a 'Coming soon' detail, completed matches have both scores, plausible dates/minutes/coordinates/attendance |
| Warehouse | PostgreSQL constraints | PK/FK, CHECKs, scheduled ⇒ NULL score |
| Gold | dbt tests (115) | unique/not_null/relationships/accepted_values, W+D+L and points arithmetic, goals scored = goals conceded, Gold row counts reconcile to the warehouse, no upcoming fixture dropped |
| Cross-source | collection phase | goals rebuilt from events = recorded score; Fjelstul vs StatsBomb vs Wikipedia agreement rates (see README history) |

## Latest check results

| layer | table | check | severity | status | failed rows |
|---|---|---|---|---|---|
| gold | dbt_project | dbt build (models + tests) | critical | pass | 0 |
| silver | awards | pandera_warning_schema | warning | pass | 0 |
| silver | lineups | pandera_warning_schema | warning | pass | 0 |
| silver | events | pandera_warning_schema | warning | pass | 0 |
| silver | players | pandera_warning_schema | warning | pass | 0 |
| silver | matches | pandera_warning_schema | warning | pass | 0 |
| silver | teams | pandera_critical_schema | critical | pass | 0 |
| silver | venues | pandera_critical_schema | critical | pass | 0 |
| silver | awards | pandera_critical_schema | critical | pass | 0 |
| silver | lineups | pandera_critical_schema | critical | pass | 0 |
| silver | events | pandera_critical_schema | critical | pass | 0 |
| silver | player_xref | pandera_critical_schema | critical | pass | 0 |
| silver | players | pandera_critical_schema | critical | pass | 0 |
| silver | matches | pandera_critical_schema | critical | pass | 0 |

## Duplicates and entity resolution

| check | found |
|---|---|
| duplicate match ids | 0 |
| players with the same name and date of birth still separate | 39 |
| player ids merged into another canonical id (entity resolution) | 1568 |
| duplicate (match, team, player) line-up rows | 0 |
| duplicate event ids | 0 |

## Coverage by edition (latest run)

Expected matches are format arithmetic, not official records. Percentages are of *played* matches.

| edition | expected | in dataset | played | coming soon | lineups % | events % | goals with event % | man of match % | attendance % | flag |
|---|---|---|---|---|---|---|---|---|---|---|
| COPA-2001 | 26 | 26 | 26 | 0 | 100 | 100 | 100 | 0 | 100 | complete vs expectation |
| COPA-2004 | 26 | 26 | 26 | 0 | 100 | 100 | 100 | 0 | 100 | complete vs expectation |
| COPA-2007 | 26 | 26 | 26 | 0 | 100 | 100 | 100 | 0 | 100 | complete vs expectation |
| COPA-2011 | 26 | 26 | 26 | 0 | 100 | 100 | 100 | 100 | 77 | complete vs expectation |
| COPA-2015 | 26 | 26 | 26 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| COPA-2016 | 32 | 32 | 32 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| COPA-2019 | 26 | 26 | 26 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| COPA-2021 | 28 | 28 | 28 | 0 | 100 | 100 | 100 | 93 | 100 | complete vs expectation |
| COPA-2024 | 32 | 32 | 32 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2000 | 31 | 31 | 31 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2004 | 31 | 31 | 31 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2008 | 31 | 31 | 31 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2012 | 31 | 31 | 31 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2016 | 51 | 51 | 51 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2020 | 51 | 51 | 51 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2024 | 51 | 51 | 51 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| EURO-2028 | 51 | 51 | 0 | 51 |  |  |  |  |  | upcoming - not played yet |
| UNL-2018-19 |  | 142 | 142 | 0 | 3 | 90 | 100 | 3 | 100 | no expectation defined |
| UNL-2020-21 |  | 170 | 170 | 0 | 2 | 86 | 98 | 2 | 99 | goal events cover 98.5% of recorded goals |
| UNL-2022-23 |  | 162 | 162 | 0 | 2 | 96 | 100 | 2 | 100 | no expectation defined |
| UNL-2024-25 |  | 188 | 188 | 0 | 2 | 91 | 100 | 2 | 100 | no expectation defined |
| UNL-2026-27 |  | 104 | 104 | 0 | 0 | 86 | 100 | 0 | 100 | no expectation defined |
| WC-2002 | 64 | 64 | 64 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| WC-2006 | 64 | 64 | 64 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| WC-2010 | 64 | 64 | 64 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| WC-2014 | 64 | 64 | 64 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| WC-2018 | 64 | 64 | 64 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| WC-2022 | 64 | 64 | 64 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |
| WC-2026 | 104 | 104 | 104 | 0 | 100 | 100 | 100 | 100 | 100 | complete vs expectation |

## Known limitations (all real, none hidden)

* **Nations League group matches:** no line-ups, cards or substitutions (the public pages we are allowed to use have none; UEFA's terms prohibit scraping). Goals exist for all of them; goal scorers are *names only* (no squad data to link them).
* **Man of the match** is not published for Copa 2001/2004/2007 or Nations League group matches.
* **Possession, VAR decisions and (outside StatsBomb) xG** are not available and are NULL, never estimated.
* **Coordinates/passes/shots** exist only for the 313 StatsBomb/Wyscout matches.
* **Half-time scores** exist for WC and Euro only; **extra time is not recorded for the Nations League**, so extra-time statistics undercount it there.
* **Shoot-outs:** winners are known for all (martj42), kick-by-kick scores only for some.
* **Minutes** for Wikipedia-based editions are derived from substitution and card times with a nominal 90/120-minute end (stoppage ignored): accurate to a few minutes.
* **Standings** are derived from matches (3-1-0, tiebreak points/GD/GF only), not official tables.
* **Awards** come from Wikipedia (secondary source); unlinked winners keep their raw name.
* **8 attendances** are recorded nowhere; 12 Copa 2011 values are rounded estimates from the Spanish Wikipedia (labelled).
* **Romania–Kosovo 2024** was abandoned at 0-0 and awarded 3-0; the on-pitch score is kept with a note.

## Bugs the checks found and that were fixed

Champions League date roll-over (before it left scope); Euro 2008 two-letter weekday headers; Euro 2000 venue-before-teams layout creating bogus teams; overlapping StatsBomb position intervals; duplicated Wyscout goal tags; best-copy-wins merge of duplicate Wikipedia boxes; attendance 0 treated as missing; own goals missing from goal events (StatsBomb `own_goal_against`); OpenFootball goals without an `is_goal` flag (all of Euro 2000/2004 and WC 2026 showed zero goal events until the coverage report exposed it); literal `\uXXXX` escapes in 399 Wyscout names; Wikipedia line-ups without player ids and minutes; goals-per-90 inflated by missing minutes; the pipeline ignoring Silver code changes.