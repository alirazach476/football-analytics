# Ingestion data-quality report (20261105T210022Z)

Matches: 1830  | source records: 1164

## Checks

| check_name                         | severity   | season_id   |   failing_rows | detail                                                               |
|:-----------------------------------|:-----------|:------------|---------------:|:---------------------------------------------------------------------|
| duplicate_match_id                 | error      | ALL         |              0 |                                                                      |
| duplicate_season_date_teams        | error      | ALL         |              0 |                                                                      |
| same_team_both_sides               | error      | ALL         |              0 |                                                                      |
| negative_or_implausible_score(>12) | error      | ALL         |              0 |                                                                      |
| penalties_but_level_score          | error      | ALL         |              0 | shoot-out recorded but on-pitch score not level (single-leg matches) |
| date_weekday_mismatch              | error      | ALL         |              1 | date contradicts the weekday written in the source line              |
| date_year_adjusted_by_weekday      | info       | ALL         |              0 |                                                                      |
| et_score_below_90min_score         | error      | ALL         |              0 |                                                                      |
| ht_score_above_90min_score         | error      | ALL         |              0 |                                                                      |
| completed_without_score            | error      | ALL         |              0 |                                                                      |
| missing_stage                      | warning    | ALL         |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2001   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2001   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2004   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2004   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2007   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2007   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2011   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2011   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2015   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2015   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2016   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2016   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2019   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2019   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2021   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2021   |              0 |                                                                      |
| date_outside_registry_window       | warning    | COPA-2024   |              0 |                                                                      |
| stage_chronology                   | error      | COPA-2024   |              0 |                                                                      |
| date_outside_registry_window       | warning    | EURO-2000   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2000   |              0 |                                                                      |
| date_outside_registry_window       | warning    | EURO-2004   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2004   |              0 |                                                                      |
| date_outside_registry_window       | warning    | EURO-2008   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2008   |              0 |                                                                      |
| date_outside_registry_window       | warning    | EURO-2012   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2012   |              0 |                                                                      |
| date_outside_registry_window       | warning    | EURO-2016   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2016   |              0 |                                                                      |
| date_outside_registry_window       | warning    | EURO-2020   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2020   |              0 |                                                                      |
| date_outside_registry_window       | warning    | EURO-2024   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2024   |              0 |                                                                      |
| stage_chronology                   | error      | EURO-2028   |              0 |                                                                      |
| stage_chronology                   | error      | UNL-2018-19 |              0 |                                                                      |
| stage_chronology                   | error      | UNL-2020-21 |              0 |                                                                      |
| stage_chronology                   | error      | UNL-2022-23 |              0 |                                                                      |
| stage_chronology                   | error      | UNL-2024-25 |              0 |                                                                      |
| stage_chronology                   | error      | UNL-2026-27 |              0 |                                                                      |
| date_outside_registry_window       | warning    | WC-2002     |              0 |                                                                      |
| stage_chronology                   | error      | WC-2002     |              0 |                                                                      |
| date_outside_registry_window       | warning    | WC-2006     |              0 |                                                                      |
| stage_chronology                   | error      | WC-2006     |              0 |                                                                      |
| date_outside_registry_window       | warning    | WC-2010     |              0 |                                                                      |
| stage_chronology                   | error      | WC-2010     |              0 |                                                                      |
| date_outside_registry_window       | warning    | WC-2014     |              0 |                                                                      |
| stage_chronology                   | error      | WC-2014     |              0 |                                                                      |
| date_outside_registry_window       | warning    | WC-2018     |              0 |                                                                      |
| stage_chronology                   | error      | WC-2018     |              0 |                                                                      |
| date_outside_registry_window       | warning    | WC-2022     |              0 |                                                                      |
| stage_chronology                   | error      | WC-2022     |              0 |                                                                      |
| date_outside_registry_window       | warning    | WC-2026     |              0 |                                                                      |
| stage_chronology                   | error      | WC-2026     |              0 |                                                                      |
| missing_source_url                 | error      | ALL         |              0 |                                                                      |
| missing_retrieval_timestamp        | error      | ALL         |              0 |                                                                      |
| cross_source_score_conflicts       | warning    | ALL         |              0 | OpenFootball vs StatsBomb                                            |
| matches_linked_to_statsbomb        | info       | ALL         |            262 |                                                                      |
| future_match_with_result           | error      | ALL         |              0 |                                                                      |

## Per-season field availability (counts of non-null)

| competition_id   | season_id   | primary_provider   |   matches |   completed |   with_ht |   with_venue |   with_kickoff_utc |   with_referee |
|:-----------------|:------------|:-------------------|----------:|------------:|----------:|-------------:|-------------------:|---------------:|
| COPA             | COPA-2001   | martj42            |        26 |          26 |         0 |           26 |                  0 |             26 |
| COPA             | COPA-2004   | martj42            |        26 |          26 |         0 |           26 |                  0 |             26 |
| COPA             | COPA-2007   | martj42            |        26 |          26 |         0 |           26 |                  0 |             26 |
| COPA             | COPA-2011   | openfootball       |        26 |          26 |         0 |           26 |                  0 |             26 |
| COPA             | COPA-2015   | martj42            |        26 |          26 |         0 |           26 |                  0 |             26 |
| COPA             | COPA-2016   | martj42            |        32 |          32 |         0 |           32 |                  0 |             32 |
| COPA             | COPA-2019   | martj42            |        26 |          26 |         0 |           26 |                  0 |             26 |
| COPA             | COPA-2021   | openfootball       |        28 |          28 |         0 |           28 |                 28 |             28 |
| COPA             | COPA-2024   | openfootball       |        32 |          32 |         0 |           32 |                 32 |             32 |
| EURO             | EURO-2000   | openfootball       |        31 |          31 |         0 |           31 |                  0 |             31 |
| EURO             | EURO-2004   | openfootball       |        31 |          31 |         0 |           31 |                  0 |             31 |
| EURO             | EURO-2008   | openfootball       |        31 |          31 |         0 |           31 |                  0 |             31 |
| EURO             | EURO-2012   | openfootball       |        31 |          31 |         0 |           31 |                  0 |             31 |
| EURO             | EURO-2016   | openfootball       |        51 |          51 |         0 |           51 |                  0 |             51 |
| EURO             | EURO-2020   | openfootball       |        51 |          51 |        51 |           51 |                  0 |             51 |
| EURO             | EURO-2024   | openfootball       |        51 |          51 |        45 |           51 |                  0 |             51 |
| EURO             | EURO-2028   | openfootball       |        51 |           0 |         0 |           51 |                  0 |              0 |
| UNL              | UNL-2018-19 | martj42            |       142 |         142 |         0 |          142 |                  0 |            142 |
| UNL              | UNL-2020-21 | martj42            |       170 |         170 |         0 |          170 |                  0 |            170 |
| UNL              | UNL-2022-23 | martj42            |       162 |         162 |         0 |          162 |                  0 |            162 |
| UNL              | UNL-2024-25 | martj42            |       184 |         184 |         0 |          184 |                  0 |            184 |
| UNL              | UNL-2024-25 | wikipedia          |         4 |           4 |         0 |            4 |                  0 |              4 |
| UNL              | UNL-2026-27 | martj42            |       104 |         104 |         0 |          104 |                  0 |            104 |
| WC               | WC-2002     | openfootball       |        64 |          64 |         0 |           64 |                  0 |             64 |
| WC               | WC-2006     | openfootball       |        64 |          64 |        56 |           64 |                  0 |             64 |
| WC               | WC-2010     | openfootball       |        64 |          64 |         0 |           64 |                  0 |             64 |
| WC               | WC-2014     | openfootball       |        64 |          64 |        20 |           64 |                 64 |             64 |
| WC               | WC-2018     | openfootball       |        64 |          64 |        64 |           64 |                 64 |             64 |
| WC               | WC-2022     | openfootball       |        64 |          64 |        57 |           64 |                  0 |             64 |
| WC               | WC-2026     | openfootball       |       104 |         104 |       104 |          104 |                104 |            104 |