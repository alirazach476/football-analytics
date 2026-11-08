select * from {{ source('wh', 'fact_tournament_standings') }} where points <> 3 * wins + draws or played <> wins + draws + losses
