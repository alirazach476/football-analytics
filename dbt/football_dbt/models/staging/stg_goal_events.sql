-- goals from event rows (is_goal flag OR event_type 'goal': OpenFootball goals carry no flag) incl. own goals (StatsBomb own_goal_against; its mirror own_goal_for is dropped to avoid double counting);
-- penalty shoot-out kicks (period 5) are excluded
select e.event_key, e.event_id, e.match_key, e.provider, e.team_key, e.player_key, e.player_name_raw,
       e.assist_name_raw, e.assist_source, e.related_player_key as assist_player_key,
       e.minute, e.minute_added, e.period, coalesce(e.is_penalty, false) as is_penalty, (coalesce(e.is_own_goal, false) or e.event_type = 'own_goal_against') as is_own_goal
from {{ source('wh', 'fact_match_events') }} e
where (e.is_goal is true or e.event_type = 'goal' or e.is_own_goal is true or e.event_type = 'own_goal_against')
  and e.event_type <> 'own_goal_for' and coalesce(e.period, 0) <> 5
