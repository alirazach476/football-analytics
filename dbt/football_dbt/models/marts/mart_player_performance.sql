-- player x team x season. Goals/assists come from goal-event rows that carry a linked player id (coverage caveat in docs).
select p.player_key, pl.full_name, pl.nationality, tm.team_name, s.season_id, p.appearances, p.starts, p.minutes_played, p.matches_with_minutes,
       p.goals, p.penalty_goals, p.own_goals, p.assists, p.goals + p.assists as goal_contributions, p.yellow_cards, p.red_cards,
       p.goals_in_minute_matches, p.assists_in_minute_matches,
       case when p.minutes_played >= 90 then round((p.goals_in_minute_matches * 90.0 / p.minutes_played)::numeric, 3) end as goals_per_90,
       case when p.minutes_played >= 90 then round((p.assists_in_minute_matches * 90.0 / p.minutes_played)::numeric, 3) end as assists_per_90
from {{ ref('int_player_seasons') }} p
join {{ ref('stg_players') }} pl using (player_key)
join {{ ref('stg_teams') }} tm using (team_key)
join (select distinct season_id from {{ ref('stg_matches') }}) s on s.season_id = p.season_id
