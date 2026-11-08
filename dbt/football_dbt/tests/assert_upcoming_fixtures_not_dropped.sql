-- reconciliation: every scheduled fixture in the warehouse must appear in the Gold fixtures mart (the user asked for them to stay visible)
select s.match_id from {{ ref('stg_matches') }} s left join {{ ref('mart_upcoming_fixtures') }} u using (match_id)
where not s.is_played and u.match_id is null
