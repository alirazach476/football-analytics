select * from {{ ref('stg_matches') }} where not is_played and (home_score is not null or away_score is not null or home_pen is not null)
