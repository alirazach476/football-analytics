-- two rows per PLAYED match (one per team). Result uses the recorded score (incl. extra time, excl. shoot-out); 3-1-0 points.
with base as (
    select match_key, season_id, competition_id, match_date, stage_name, stage_order, is_knockout, group_name,
           home_team_key as team_key, away_team_key as opponent_key, true as is_home,
           home_score as goals_for, away_score as goals_against, home_pen as pens_for, away_pen as pens_against, attendance, went_beyond_90,
           case when shootout_winner_side = 'home' then 'W' when shootout_winner_side = 'away' then 'L' end as shootout_result
    from {{ ref('stg_matches') }} where is_played and home_team_key is not null and away_team_key is not null
    union all
    select match_key, season_id, competition_id, match_date, stage_name, stage_order, is_knockout, group_name,
           away_team_key, home_team_key, false, away_score, home_score, away_pen, home_pen, attendance, went_beyond_90,
           case when shootout_winner_side = 'away' then 'W' when shootout_winner_side = 'home' then 'L' end
    from {{ ref('stg_matches') }} where is_played and home_team_key is not null and away_team_key is not null
)
select *,
       goals_for - goals_against as goal_diff,
       case when goals_for > goals_against then 'W' when goals_for = goals_against then 'D' else 'L' end as result,
       case when goals_for > goals_against then 3 when goals_for = goals_against then 1 else 0 end as points,
       (goals_against = 0) as clean_sheet
from base
