select player_key, player_id, full_name, display_name, nationality, date_of_birth, primary_position, n_source_ids
from {{ source('wh', 'dim_player') }}
