-- fixtures not played yet ("Coming soon"): shows whatever detail is known; scores are null by design
select match_id, competition_id, season_id, match_date, stage_name, group_name, home_team_name, away_team_name, venue_name, venue_city,
       venue_country, status_label, fixture_detail
from {{ ref('stg_matches') }} where not is_played
