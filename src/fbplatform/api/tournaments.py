"""Tournament catalogue and per-edition data for the React tournament pages."""
from __future__ import annotations

from ..analysis.data import q
from . import store
from .serialize import records, scalar, table

COMP_NAME = {"WC": "FIFA World Cup", "EURO": "UEFA European Championship", "COPA": "Copa América", "UNL": "UEFA Nations League"}


def theme_key(season_id: str) -> str:
    return "unl" if season_id.startswith("UNL") else season_id.lower()


def catalogue() -> list[dict]:
    reg = store.registry()
    tr = store.tournaments().set_index("season_id")
    out = []
    for r in reg.itertuples():
        sid = r.season_id
        t = tr.loc[sid] if sid in tr.index else None
        played = int(t.matches_played) if t is not None else 0
        soon = int(t.matches_coming_soon) if t is not None else 0
        status = "upcoming" if (t is not None and played == 0 and soon > 0) else "in_data" if played > 0 else "announced"
        out.append({"seasonId": sid, "slug": sid.lower(), "themeKey": theme_key(sid), "competition": r.competition_id, "competitionName": COMP_NAME[r.competition_id], "edition": r.tournament_edition,
                    "year": int(sid.split("-")[1]), "host": scalar(r.host_country), "start": scalar(r.start_date), "end": scalar(r.end_date), "teams": scalar(r.participating_teams_count),
                    "format": scalar(r.competition_format), "verification": scalar(r.verification_status), "status": status, "matchesPlayed": played, "matchesComingSoon": soon,
                    "champion": scalar(t.champion) if t is not None else None, "runnerUp": scalar(t.runner_up) if t is not None else None})
    return out


def edition(season_id: str) -> dict:
    cat = {c["seasonId"]: c for c in catalogue()}
    if season_id not in cat:
        raise KeyError(season_id)
    meta = cat[season_id]
    tr = store.tournaments()
    summ = tr[tr.season_id == season_id]
    summary = records(summ)[0] if len(summ) else None
    awards = q("""select a.award_name, a.award_category, a.rank, a.entity_name_raw, a.value_text, a.link_status, a.player_key, a.position_label, a.team_key, t.team_name
                  from wh.fact_player_awards a join wh.dim_season s using (season_key) left join wh.dim_team t using (team_key) where s.season_id = %s
                  order by a.award_category, a.rank nulls last, a.entity_name_raw""", (season_id,))
    team_awards = q("""select a.award_name, a.award_category, a.entity_name_raw, t.team_name from wh.fact_team_awards a join wh.dim_season s using (season_key)
                       left join wh.dim_team t using (team_key) where s.season_id = %s""", (season_id,))
    scorers = q("""select player_key, full_name, max(team_name) team_name, sum(goals) goals, sum(assists) assists, sum(appearances) appearances, sum(minutes_played) minutes
                   from gold.mart_player_performance where season_id = %s group by 1, 2 having sum(goals) > 0 order by goals desc, appearances limit 25""", (season_id,))
    matches = q("""select match_key, match_id, match_date, stage_name, group_name, home_team_name, away_team_name, home_score, away_score, home_pen, away_pen, shootout_winner_side, went_beyond_90,
                          status_label, fixture_detail, venue_name, venue_city, attendance, referee_name, man_of_the_match_raw as motm, is_played
                   from staging.stg_matches where season_id = %s order by match_date, match_key""", (season_id,))
    teams = q("""select team_name, played, wins, draws, losses, goals_for, goals_against, goal_diff, points, furthest_stage_played from gold.mart_team_performance
                 where season_id = %s order by points desc, goal_diff desc""", (season_id,))
    motm = q("""select man_of_the_match_raw as player, count(*) awards from staging.stg_matches where season_id = %s and man_of_the_match_raw is not null group by 1 order by 2 desc, 1 limit 15""", (season_id,))
    cols = "stage_name, match_date, home_team_name, away_team_name, home_score, away_score, total_goals, goal_margin"
    hi = q(f"select {cols} from gold.mart_match_performance where season_id = %s and match_status='completed' order by total_goals desc, match_date limit 5", (season_id,))
    mg = q(f"select {cols} from gold.mart_match_performance where season_id = %s and match_status='completed' order by goal_margin desc, total_goals desc limit 5", (season_id,))
    played = matches[matches.is_played == True] if len(matches) else matches
    n_played, motm_n = int(len(played)), int(played.motm.notna().sum()) if len(played) else 0
    note = None
    if n_played and motm_n == 0:
        note = "Player of the match is not published for this edition's matches (verified absent from the sources we may use)."
    elif n_played and motm_n < n_played:
        note = "Player of the match exists only for some matches of this edition (for the Nations League, the Finals matches)."
    return {"meta": meta, "summary": summary, "awards": table(awards), "teamAwards": table(team_awards), "topScorers": table(scorers), "matches": table(matches, 2000), "teams": table(teams),
            "motmLeaders": table(motm), "highestScoring": table(hi), "biggestMargins": table(mg), "coverage": {"matchesPlayed": n_played, "withPlayerOfTheMatch": motm_n, "playerOfTheMatchNote": note}}
