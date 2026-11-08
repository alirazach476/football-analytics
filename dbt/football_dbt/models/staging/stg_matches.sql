-- one row per match (played AND scheduled); scheduled fixtures keep their placeholders/venue detail and null scores
select
    m.match_key, m.match_id, c.competition_id, c.competition_name, s.season_id, s.season_year,
    d.full_date as match_date, st.stage_name, st.stage_order, st.is_knockout, m.group_name, m.matchday, m.leg,
    m.home_team_key, m.away_team_key, m.home_team_display, m.away_team_display,
    coalesce(ht.team_name, m.home_team_display) as home_team_name,
    coalesce(at.team_name, m.away_team_display) as away_team_name,
    v.venue_key, v.venue_name, v.city as venue_city, v.country as venue_country, r.referee_name,
    m.match_status, m.status_label, m.fixture_detail, (m.match_status = 'completed') as is_played,
    m.attendance, m.home_score, m.away_score, m.score_basis, m.home_score_ht, m.away_score_ht,
    m.home_score_ft90, m.away_score_ft90, m.home_score_et, m.away_score_et, m.home_pen, m.away_pen,
    (coalesce(m.went_extra_time, 'False') = 'True' or m.home_pen is not null or m.shootout_winner_side is not null or m.score_basis = 'aet') as went_beyond_90,
    coalesce(m.shootout_winner_side,
             case when m.home_pen > m.away_pen then 'home' when m.home_pen < m.away_pen then 'away' end) as shootout_winner_side,
    (m.home_pen is not null or m.shootout_winner_side is not null) as had_shootout,
    m.winner, m.man_of_the_match_raw, m.primary_provider, m.source_url
from {{ source('wh', 'fact_matches') }} m
join {{ source('wh', 'dim_competition') }} c using (competition_key)
join {{ source('wh', 'dim_season') }} s using (season_key)
join {{ source('wh', 'dim_date') }} d using (date_key)
left join {{ source('wh', 'dim_tournament_stage') }} st using (stage_key)
left join {{ source('wh', 'dim_team') }} ht on ht.team_key = m.home_team_key
left join {{ source('wh', 'dim_team') }} at on at.team_key = m.away_team_key
left join {{ source('wh', 'dim_venue') }} v on v.venue_key = m.venue_key
left join {{ source('wh', 'dim_referee') }} r on r.referee_key = m.referee_key
