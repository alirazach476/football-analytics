-- every pair of teams that met; team_a_key < team_b_key. Results use the recorded score (shoot-outs shown separately).
select ta.team_name as team_a, tb.team_name as team_b, t.team_key as team_a_key, t.opponent_key as team_b_key,
       count(*) as matches, count(*) filter (where result = 'W') as team_a_wins, count(*) filter (where result = 'D') as draws,
       count(*) filter (where result = 'L') as team_b_wins, sum(goals_for) as team_a_goals, sum(goals_against) as team_b_goals,
       count(*) filter (where shootout_result = 'W') as team_a_shootout_wins, count(*) filter (where shootout_result = 'L') as team_b_shootout_wins,
       min(match_date) as first_meeting, max(match_date) as last_meeting
from {{ ref('int_team_matches') }} t
join {{ ref('stg_teams') }} ta on ta.team_key = t.team_key
join {{ ref('stg_teams') }} tb on tb.team_key = t.opponent_key
where t.team_key < t.opponent_key group by 1, 2, 3, 4
