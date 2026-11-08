select team_key, team_id, team_name, team_type, country, confederation from {{ source('wh', 'dim_team') }}
