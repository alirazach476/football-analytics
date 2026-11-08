select 1 where (select count(*) from {{ ref('mart_match_performance') }}) <> (select count(*) from {{ source('wh', 'fact_matches') }})
