-- one row per player x team x season: appearances from lineups, goals from goal events (own goals excluded, shoot-out excluded)
with app as (
    select a.player_key, a.team_key, m.season_id, m.competition_id,
           count(distinct a.match_key) as matches_in_squad_sheet,
           count(distinct a.match_key) filter (where a.is_starter) as starts,
           coalesce(sum(a.minutes_played), 0) as minutes_played,
           count(distinct a.match_key) filter (where a.minutes_played is not null) as matches_with_minutes,
           sum(a.yellow_cards) as yellow_cards, sum(a.red_cards) as red_cards
    from {{ ref('stg_appearances') }} a join {{ ref('stg_matches') }} m using (match_key)
    where a.player_key is not null and m.is_played and coalesce(a.appeared, true)
    group by 1, 2, 3, 4
), g as (
    select e.player_key, e.team_key, m.season_id,
           count(*) filter (where not e.is_own_goal) as goals,
           count(*) filter (where e.is_penalty and not e.is_own_goal) as penalty_goals,
           count(*) filter (where e.is_own_goal) as own_goals
    from {{ ref('stg_goal_events') }} e join {{ ref('stg_matches') }} m using (match_key)
    where e.player_key is not null group by 1, 2, 3
), asst as (
    select e.assist_player_key as player_key, e.team_key, m.season_id, count(*) as assists
    from {{ ref('stg_goal_events') }} e join {{ ref('stg_matches') }} m using (match_key)
    where e.assist_player_key is not null and not e.is_own_goal group by 1, 2, 3
), gmin as (
    -- goals/assists counted ONLY in matches where the player's minutes are known, so per-90 rates are not inflated by missing minutes
    select a.player_key, a.team_key, m.season_id,
           count(*) filter (where e.player_key = a.player_key and not e.is_own_goal) as goals_in_minute_matches,
           count(*) filter (where e.assist_player_key = a.player_key and not e.is_own_goal) as assists_in_minute_matches
    from {{ ref('stg_appearances') }} a join {{ ref('stg_matches') }} m using (match_key)
    left join {{ ref('stg_goal_events') }} e on e.match_key = a.match_key and (e.player_key = a.player_key or e.assist_player_key = a.player_key)
    where a.player_key is not null and a.minutes_played is not null and m.is_played group by 1, 2, 3
)
select coalesce(app.player_key, g.player_key) as player_key, coalesce(app.team_key, g.team_key) as team_key,
       coalesce(app.season_id, g.season_id) as season_id,
       coalesce(app.matches_in_squad_sheet, 0) as appearances, coalesce(app.starts, 0) as starts,
       app.minutes_played, app.matches_with_minutes,
       coalesce(g.goals, 0) as goals, coalesce(g.penalty_goals, 0) as penalty_goals, coalesce(g.own_goals, 0) as own_goals,
       coalesce(asst.assists, 0) as assists, coalesce(app.yellow_cards, 0) as yellow_cards, coalesce(app.red_cards, 0) as red_cards,
       coalesce(gmin.goals_in_minute_matches, 0) as goals_in_minute_matches, coalesce(gmin.assists_in_minute_matches, 0) as assists_in_minute_matches
from app
full join g on g.player_key = app.player_key and g.team_key = app.team_key and g.season_id = app.season_id
left join asst on asst.player_key = coalesce(app.player_key, g.player_key) and asst.team_key = coalesce(app.team_key, g.team_key)
              and asst.season_id = coalesce(app.season_id, g.season_id)
left join gmin on gmin.player_key = coalesce(app.player_key, g.player_key) and gmin.team_key = coalesce(app.team_key, g.team_key)
              and gmin.season_id = coalesce(app.season_id, g.season_id)
