select season_id, competition_id, stage_name, count(*) as matches, sum(home_score + away_score) as goals,
       round(avg(home_score + away_score)::numeric, 2) as goals_per_match,
       count(*) filter (where went_beyond_90) as matches_beyond_90, count(*) filter (where had_shootout) as shootouts,
       count(*) filter (where abs(home_score - away_score) = 1) as one_goal_margin, count(*) filter (where home_score = away_score) as drawn_after_et_or_90
from {{ ref('stg_matches') }} where is_played and is_knockout group by 1, 2, 3
