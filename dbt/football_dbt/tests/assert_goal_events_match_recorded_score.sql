{{ config(severity='warn') }}
-- WARN only: matches whose goal events (excl. shoot-out) differ from the recorded score. Event coverage from secondary sources can be partial.
select m.match_id, m.home_score + m.away_score as recorded, g.n as from_events
from {{ ref('stg_matches') }} m join (select match_key, count(*) as n from {{ ref('stg_goal_events') }} group by 1) g using (match_key)
where m.is_played and m.home_score + m.away_score <> g.n
