-- season x group on played group-stage matches, plus the top team from the derived standings
with g as (
    select season_id, competition_id, group_name, count(*) as matches, sum(home_score + away_score) as goals,
           count(*) filter (where home_score = away_score) as draws
    from {{ ref('stg_matches') }} where is_played and stage_name = 'Group stage' and group_name is not null group by 1, 2, 3
), top as (
    select s.season_id, st.group_name, t.team_name as top_team, st.points as top_points, st.goal_difference as top_goal_diff
    from {{ source('wh', 'fact_tournament_standings') }} st
    join {{ source('wh', 'dim_season') }} s using (season_key) join {{ ref('stg_teams') }} t using (team_key)
    where st.group_position = 1
)
select g.*, round(g.goals::numeric / g.matches, 2) as goals_per_match, round(100.0 * g.draws / g.matches, 1) as draw_pct,
       top.top_team, top.top_points, top.top_goal_diff
from g left join top on top.season_id = g.season_id and top.group_name = g.group_name
