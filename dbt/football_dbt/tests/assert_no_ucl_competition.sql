select * from {{ ref('stg_matches') }} where competition_id not in ('WC', 'EURO', 'COPA', 'UNL')
