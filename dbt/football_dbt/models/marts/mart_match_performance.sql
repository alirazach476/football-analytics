-- one row per match, played or scheduled. Scheduled fixtures are kept: status_label = 'Coming soon' and fixture_detail holds what is known.
with goals as (
    select match_key, count(*) as goal_events, count(*) filter (where is_own_goal) as own_goal_events
    from {{ ref('stg_goal_events') }} group by 1
), stats as (
    select match_key, sum(shots) as shots, sum(shots_on_target) as shots_on_target, sum(xg) as xg
    from {{ source('wh', 'fact_team_match_stats') }} group by 1
)
select m.match_key, m.match_id, m.competition_id, m.season_id, m.match_date, m.stage_name, m.group_name,
       m.home_team_name, m.away_team_name, m.venue_name, m.venue_city, m.venue_country, m.referee_name, m.attendance,
       m.match_status, m.status_label, m.fixture_detail,
       m.home_score, m.away_score, m.home_score + m.away_score as total_goals, abs(m.home_score - m.away_score) as goal_margin,
       case when not m.is_played then null when m.home_score > m.away_score then 'home win' when m.home_score < m.away_score then 'away win' else 'draw' end as outcome_recorded_score,
       m.went_beyond_90, m.home_pen, m.away_pen,
       g.goal_events, s.shots, s.shots_on_target, round(s.xg::numeric, 2) as xg_total,
       (g.match_key is not null) as has_goal_events, (s.match_key is not null) as has_team_stats
from {{ ref('stg_matches') }} m
left join goals g using (match_key) left join stats s using (match_key)
