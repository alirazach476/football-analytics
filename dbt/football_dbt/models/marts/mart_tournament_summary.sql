-- one row per season. Scheduled fixtures are counted separately (matches_coming_soon); averages use played matches only.
with fin as (
    select season_id,
           case when home_score > away_score then home_team_name when home_score < away_score then away_team_name
                when shootout_winner_side = 'home' then home_team_name when shootout_winner_side = 'away' then away_team_name end as champion,
           case when home_score > away_score then away_team_name when home_score < away_score then home_team_name
                when shootout_winner_side = 'home' then away_team_name when shootout_winner_side = 'away' then home_team_name end as runner_up
    from {{ ref('stg_matches') }} where stage_name = 'Final' and is_played
)
select m.season_id, m.competition_id, m.competition_name, m.season_year,
       count(*) as matches_in_dataset, count(*) filter (where m.is_played) as matches_played, count(*) filter (where not m.is_played) as matches_coming_soon,
       sum(m.home_score + m.away_score) as total_goals,
       round((sum(m.home_score + m.away_score)::numeric / nullif(count(*) filter (where m.is_played), 0)), 2) as goals_per_match,
       round(100.0 * count(*) filter (where m.is_played and m.home_score = m.away_score) / nullif(count(*) filter (where m.is_played), 0), 1) as draw_pct,
       count(*) filter (where m.went_beyond_90) as matches_beyond_90, count(*) filter (where m.had_shootout) as shootouts,
       round(avg(m.attendance)::numeric, 0) as avg_attendance,
       (select count(distinct t) from (select home_team_key t from {{ ref('stg_matches') }} x where x.season_id = m.season_id and home_team_key is not null
                                       union select away_team_key from {{ ref('stg_matches') }} x where x.season_id = m.season_id and away_team_key is not null) q) as teams,
       min(m.match_date) as first_match_date, max(m.match_date) as last_match_date,
       max(f.champion) as champion, max(f.runner_up) as runner_up,
       case when count(*) filter (where not m.is_played) > 0 then 'in progress / upcoming' else 'completed' end as tournament_status
from {{ ref('stg_matches') }} m left join fin f using (season_id)
group by 1, 2, 3, 4
