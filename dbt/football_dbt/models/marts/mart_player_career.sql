select p.player_key, pl.full_name, pl.nationality, pl.date_of_birth, count(distinct p.season_id) as tournaments, count(distinct p.team_key) as teams,
       min(m.season_year) as first_season_year, max(m.season_year) as last_season_year, sum(p.appearances) as appearances, sum(p.starts) as starts,
       sum(p.minutes_played) as minutes_played, sum(p.goals) as goals, sum(p.assists) as assists,
       sum(p.goals_in_minute_matches) as goals_in_minute_matches, sum(p.assists_in_minute_matches) as assists_in_minute_matches, sum(p.yellow_cards) as yellow_cards, sum(p.red_cards) as red_cards,
       count(distinct m.competition_id) as competitions
from {{ ref('int_player_seasons') }} p
join {{ ref('stg_players') }} pl using (player_key)
join (select distinct season_id, competition_id, season_year from {{ ref('stg_matches') }}) m using (season_id)
group by 1, 2, 3, 4
