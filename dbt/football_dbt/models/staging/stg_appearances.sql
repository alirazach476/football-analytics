select a.appearance_key, a.match_key, a.team_key, a.player_key, a.provider, a.is_starter, a.appeared, a.is_captain,
       a.minutes_played, coalesce(a.yellow_cards, 0) as yellow_cards, coalesce(a.red_cards, 0) as red_cards
from {{ source('wh', 'fact_player_appearances') }} a
