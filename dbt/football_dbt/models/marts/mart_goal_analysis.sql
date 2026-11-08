-- one row per goal event (shoot-out kicks excluded); minute bands for timing analysis
select e.event_key, m.match_key, m.season_id, m.competition_id, m.stage_name, m.match_date, e.provider,
       e.team_key, t.team_name as event_team_name, e.player_key, e.player_name_raw, e.assist_name_raw, e.assist_source,
       e.minute, e.minute_added, e.period, e.is_penalty, e.is_own_goal,
       case when e.minute is null then 'unknown' when e.minute <= 15 then '00-15' when e.minute <= 30 then '16-30' when e.minute <= 45 then '31-45'
            when e.minute <= 60 then '46-60' when e.minute <= 75 then '61-75' when e.minute <= 90 then '76-90' else '90+ (extra time)' end as minute_band,
       case when e.is_own_goal then 'own goal' when e.is_penalty then 'penalty' else 'open play / other' end as goal_type
from {{ ref('stg_goal_events') }} e
join {{ ref('stg_matches') }} m using (match_key)
left join {{ ref('stg_teams') }} t on t.team_key = e.team_key
