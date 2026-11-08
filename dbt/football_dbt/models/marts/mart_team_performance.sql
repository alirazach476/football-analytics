-- team x season record from played matches (recorded score incl. extra time, excl. shoot-out; 3-1-0 points)
select t.team_key, tm.team_name, ms.season_id, ms.competition_id,
       count(*) as played, count(*) filter (where result = 'W') as wins, count(*) filter (where result = 'D') as draws,
       count(*) filter (where result = 'L') as losses, sum(goals_for) as goals_for, sum(goals_against) as goals_against,
       sum(goal_diff) as goal_diff, sum(points) as points, round(100.0 * count(*) filter (where result = 'W') / count(*), 1) as win_pct,
       round(avg(goals_for)::numeric, 2) as goals_for_per_match, count(*) filter (where clean_sheet) as clean_sheets,
       count(*) filter (where shootout_result = 'W') as shootouts_won, count(*) filter (where shootout_result = 'L') as shootouts_lost,
       max(t.stage_order) as furthest_stage_order,
       (array_agg(t.stage_name order by t.stage_order desc))[1] as furthest_stage_played
from {{ ref('int_team_matches') }} t
join {{ ref('stg_teams') }} tm using (team_key)
join (select distinct season_id, competition_id, match_key from {{ ref('stg_matches') }}) ms using (match_key)
group by 1, 2, 3, 4
