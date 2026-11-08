-- competition level comparison on played matches. NOTE formats differ (team counts, rounds, rest days) - compare with care.
select competition_id, competition_name, count(distinct season_id) as seasons, count(*) as matches_played,
       round(avg(home_score + away_score)::numeric, 3) as goals_per_match,
       round(100.0 * count(*) filter (where home_score = away_score) / count(*), 1) as draw_pct,
       round(100.0 * count(*) filter (where home_score > away_score) / count(*), 1) as home_win_pct,
       round(100.0 * count(*) filter (where went_beyond_90) / count(*), 1) as beyond_90_pct,
       round(avg(attendance)::numeric, 0) as avg_attendance,
       round(stddev_samp(home_score + away_score)::numeric, 3) as goals_stddev
from {{ ref('stg_matches') }} where is_played group by 1, 2
