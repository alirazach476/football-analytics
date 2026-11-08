select 'player' as winner_type, a.season_key, a.player_key, a.team_key, a.award_name, a.award_category, a.rank,
       a.entity_name_raw, a.value_text, a.link_status, a.source_page
from {{ source('wh', 'fact_player_awards') }} a
union all
select 'team', t.season_key, null::int, t.team_key, t.award_name, t.award_category, null::int, t.entity_name_raw, null, null, t.source_page
from {{ source('wh', 'fact_team_awards') }} t
