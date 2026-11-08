-- every goal scored is conceded by someone: league-wide goals_for must equal goals_against
select 1 where (select sum(goals_for) from {{ ref('mart_team_performance') }}) <> (select sum(goals_against) from {{ ref('mart_team_performance') }})
