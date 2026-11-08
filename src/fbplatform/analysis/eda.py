"""Comprehensive EDA (sections A-E of the project spec) on all four competitions.
Outputs: reports/eda/tables/*.csv, reports/eda/figures/*.html, reports/eda/eda_report.html, reports/eda/eda_summary.json.
Rules: per-match rates only (never raw totals across editions of different size); played matches only; scheduled fixtures are listed
separately as 'Coming soon'; career totals are NOT used - every player number is limited to the collected competitions."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import statsmodels.api as sm

from ..config import ROOT
from . import data as D

OUT = ROOT / "reports" / "eda"
POS_GROUP = [("Goalkeeper", r"goalkeeper"), ("Defender", r"back|defen|centre-back|center back|sweeper"), ("Midfielder", r"midfield|wing|pivot"),
             ("Forward", r"forward|striker|attack|winger|centre-forward|second striker")]
LAYOUT = dict(template="plotly_white", font=dict(family="Inter, Segoe UI, sans-serif", size=13), margin=dict(l=60, r=20, t=60, b=50), legend=dict(orientation="h", y=-0.2))


def _pos_group(p):
    if not isinstance(p, str):
        return None
    pl = p.lower()
    if "goalkeeper" in pl:
        return "Goalkeeper"
    for name, rx in POS_GROUP[1:]:
        if re.search(rx, pl):
            return name
    return "Other"


def _slope(x, y):
    X = sm.add_constant(np.asarray(x, float))
    r = sm.OLS(np.asarray(y, float), X).fit()
    lo, hi = r.conf_int()[1]
    return dict(slope_per_year=r.params[1], ci_low=lo, ci_high=hi, p_value=r.pvalues[1], r2=r.rsquared, n=int(r.nobs))


def build() -> dict:
    m_all, m = D.matches(played_only=False), D.matches()
    tm, g, tr = D.team_matches(), D.goals(), D.tournaments()
    ps, pc, aw = D.player_seasons(), D.players(), D.awards()
    T, F = {}, {}                                       # tables, figures

    # ------------------------------------------------------------------ A. competition level
    tr_played = tr[tr.matches_played > 0].copy()
    T["A1_competition_summary"] = D.q("select * from gold.mart_competition_comparison").set_index("competition_id").loc[D.COMP_ORDER].reset_index() \
        .merge(tr_played.groupby("competition_id").agg(avg_teams=("teams", "mean"), total_goals=("total_goals", "sum")).reset_index(), on="competition_id")
    T["A2_edition_table"] = tr[["season_id", "competition_id", "teams", "matches_played", "matches_coming_soon", "total_goals", "goals_per_match", "draw_pct",
                                "matches_beyond_90", "shootouts", "avg_attendance", "champion", "runner_up", "tournament_status"]]
    ranked = tr_played.sort_values("goals_per_match", ascending=False)
    T["A3_highest_scoring_editions"] = ranked.head(8)[["season_id", "goals_per_match", "matches_played"]]
    T["A4_lowest_scoring_editions"] = ranked.tail(8)[["season_id", "goals_per_match", "matches_played"]].iloc[::-1]
    o = m.groupby(["competition_id", "outcome"]).size().unstack(fill_value=0).loc[D.COMP_ORDER]
    T["A5_outcome_distribution_pct"] = (100 * o.div(o.sum(axis=1), axis=0)).round(1).reset_index()
    T["A6_knockout_vs_group"] = m.groupby(["competition_id", "phase"]).agg(
        matches=("match_key", "size"), goals_per_match_recorded=("goals_total", "mean"), goals90_per_match=("goals90", "mean"), n_goals90=("goals90", "count"),
        draw_pct=("outcome", lambda s: 100 * (s == "draw").mean())).round(3).reset_index()
    T["A7_home_vs_away_note"] = m.groupby("competition_id").agg(home_win=("outcome", lambda s: (s == "home win").mean()), away_win=("outcome", lambda s: (s == "away win").mean())).round(3).reset_index() \
        .assign(note="'home' = team listed first; most tournament matches are at neutral venues, so this is NOT a home-advantage measure except for hosts")
    host_note = m.groupby("competition_id").size().rename("matches").reset_index()
    fig = px.line(tr_played, x="season_year", y="goals_per_match", color="competition_id", markers=True, color_discrete_map=D.COMP_COLOR,
                  labels={"goals_per_match": "Goals per match", "season_year": "Edition year", "competition_id": "Competition"},
                  title="Goals per match by edition (per-match rate, formats differ)")
    F["A_goals_per_match_by_edition"] = fig.update_layout(**LAYOUT)
    po = T["A5_outcome_distribution_pct"].melt("competition_id", var_name="outcome", value_name="pct")
    F["A_outcome_distribution"] = px.bar(po, x="competition_id", y="pct", color="outcome", barmode="stack", title="Match outcome distribution (recorded score)",
                                         color_discrete_map={"home win": "#0072B2", "draw": "#999999", "away win": "#D55E00"}).update_layout(**LAYOUT)

    # ------------------------------------------------------------------ B. team level
    ts = tm.groupby("team_name").agg(matches=("match_key", "size"), wins=("result", lambda s: (s == "W").sum()), draws=("result", lambda s: (s == "D").sum()),
                                     losses=("result", lambda s: (s == "L").sum()), goals_for=("goals_for", "sum"), goals_against=("goals_against", "sum"),
                                     clean_sheets=("clean_sheet", "sum"), points=("points", "sum"), editions=("season_id", "nunique")).reset_index()
    ts["win_pct"] = 100 * ts.wins / ts.matches
    ts["points_per_match"] = ts.points / ts.matches
    ts["goals_for_pm"] = ts.goals_for / ts.matches
    ts["goals_against_pm"] = ts.goals_against / ts.matches
    ts["clean_sheet_pct"] = 100 * ts.clean_sheets / ts.matches
    T["B0_team_summary_all_matches"] = ts.sort_values("matches", ascending=False).round(3)
    elig = ts[ts.matches >= 15]
    titles = tr.champion.value_counts().rename("titles").rename_axis("team_name").reset_index()
    T["B1_most_successful_by_ppm_min15"] = elig.merge(titles, how="left", on="team_name").fillna({"titles": 0}).sort_values("points_per_match", ascending=False).head(20).round(3)
    T["B2_most_goals_scored"] = ts.sort_values("goals_for", ascending=False).head(15)[["team_name", "matches", "goals_for", "goals_for_pm"]].round(3)
    T["B3_best_defences_min15_by_ga_pm"] = elig.sort_values("goals_against_pm").head(15)[["team_name", "matches", "goals_against", "goals_against_pm", "clean_sheet_pct"]].round(3)
    T["B4_best_attacks_min15_by_gf_pm"] = elig.sort_values("goals_for_pm", ascending=False).head(15)[["team_name", "matches", "goals_for", "goals_for_pm"]].round(3)
    T["B5_win_draw_loss_distribution"] = elig.sort_values("win_pct", ascending=False).head(20)[["team_name", "matches", "wins", "draws", "losses", "win_pct"]].round(1)
    T["B6_performance_by_edition"] = D.q("select team_name, season_id, played, wins, draws, losses, goals_for, goals_against, points, furthest_stage_played from gold.mart_team_performance order by season_id, points desc, goals_for desc")
    T["B7_performance_by_stage"] = tm.groupby(["team_name", "stage_name"]).agg(matches=("match_key", "size"), ppm=("points", "mean"), gf_pm=("goals_for", "mean"), ga_pm=("goals_against", "mean")).round(3).reset_index()
    ed = tm.groupby(["team_name", "season_id"]).points.mean().rename("ppm").reset_index()
    cons = ed.groupby("team_name").agg(editions=("ppm", "size"), mean_ppm=("ppm", "mean"), sd_ppm=("ppm", "std")).reset_index()
    T["B8_consistency_over_editions_min4"] = cons[cons.editions >= 4].assign(cv=lambda d: d.sd_ppm / d.mean_ppm).sort_values("sd_ppm").round(3)
    F["B_team_attack_vs_defence"] = px.scatter(elig, x="goals_for_pm", y="goals_against_pm", size="matches", hover_name="team_name", text="team_name",
                                               title="Teams with 15+ matches: attack vs defence (goals per match)", labels={"goals_for_pm": "Goals scored / match", "goals_against_pm": "Goals conceded / match"}) \
        .update_traces(textposition="top center", textfont_size=9).update_yaxes(autorange="reversed").update_layout(**LAYOUT)

    top12 = elig.sort_values("matches", ascending=False).head(12).team_name
    hm = ed[ed.team_name.isin(top12)].pivot(index="team_name", columns="season_id", values="ppm")
    F["B_points_per_match_by_edition_top_teams"] = px.imshow(hm.round(2), aspect="auto", color_continuous_scale="Blues", labels=dict(color="Points / match"),
                                                             title="Points per match by edition: the 12 teams with most matches (blank = did not play)").update_layout(**LAYOUT)

    # ------------------------------------------------------------------ C. player level (collected competitions only)
    pcs = pc.copy()
    pcs["goals_per_90"] = np.where(pcs.minutes_played >= 270, 90 * pcs.goals_in_minute_matches / pcs.minutes_played, np.nan)
    pcs["assists_per_90"] = np.where(pcs.minutes_played >= 270, 90 * pcs.assists_in_minute_matches / pcs.minutes_played, np.nan)
    pcs = pcs.merge(D.q("select player_key, primary_position from wh.dim_player"), on="player_key", how="left")
    T["C1_top_scorers"] = pcs.sort_values(["goals", "appearances"], ascending=[False, True]).head(25)[["full_name", "nationality", "goals", "appearances", "tournaments", "first_season_year", "last_season_year"]]
    T["C2_top_assists_PARTIAL"] = pcs.sort_values("assists", ascending=False).head(15)[["full_name", "nationality", "assists", "appearances", "tournaments"]] \
        .assign(note="assists exist only for StatsBomb-covered matches plus martj42 names; treat as lower bounds")
    T["C3_most_appearances"] = pcs.sort_values("appearances", ascending=False).head(20)[["full_name", "nationality", "appearances", "starts", "tournaments"]]
    T["C4_most_minutes_known"] = pcs.sort_values("minutes_played", ascending=False).head(20)[["full_name", "nationality", "minutes_played", "appearances"]]
    T["C5_goals_per_90_min270"] = pcs[pcs.goals >= 3].sort_values("goals_per_90", ascending=False).head(20)[["full_name", "nationality", "goals", "goals_in_minute_matches", "minutes_played", "goals_per_90"]].round(3)
    T["C6_assists_per_90_min270_PARTIAL"] = pcs[pcs.assists >= 2].sort_values("assists_per_90", ascending=False).head(15)[["full_name", "nationality", "assists", "minutes_played", "assists_per_90"]].round(3)
    multi = ps.groupby("player_key").agg(tournaments=("season_id", "nunique"), goals=("goals", "sum"), sd_goals=("goals", "std")).reset_index()
    multi = multi[(multi.tournaments >= 3) & (multi.goals > 0)].merge(pc[["player_key", "full_name"]], on="player_key")
    multi["scoring_tournaments"] = ps[ps.goals > 0].groupby("player_key").season_id.nunique().reindex(multi.player_key).values
    multi["share_of_tournaments_scored_in"] = multi.scoring_tournaments / multi.tournaments
    T["C7_scoring_consistency_3plus_tournaments"] = multi.sort_values(["share_of_tournaments_scored_in", "goals"], ascending=False).head(20).round(3)
    T["C8_top_scorer_by_edition"] = ps.sort_values(["season_id", "goals"], ascending=[True, False]).groupby("season_id").head(1)[["season_id", "full_name", "team_name", "goals", "appearances"]]
    a = ps[(ps.age.between(15, 45)) & (ps.minutes_played >= 90)].copy()
    a["age_band"] = pd.cut(a.age, [15, 21, 24, 27, 30, 33, 45], labels=["<=21", "22-24", "25-27", "28-30", "31-33", "34+"])
    ab = a.groupby("age_band", observed=True).agg(player_seasons=("player_key", "size"), minutes=("minutes_played", "sum"), goals=("goals_in_minute_matches", "sum")).reset_index()
    ab["goals_per_90"] = 90 * ab.goals / ab.minutes
    T["C9_age_vs_goals_per_90"] = ab.round(3).assign(note=f"age known for {int(a.shape[0])} player-seasons with minutes; association only")
    ps2 = ps.copy()
    ps2["pos"] = ps2.primary_position.map(_pos_group)
    pg = ps2[ps2.pos.notna() & (ps2.minutes_played > 0)].groupby("pos").agg(player_seasons=("player_key", "size"), minutes=("minutes_played", "sum"), goals=("goals_in_minute_matches", "sum"), assists=("assists_in_minute_matches", "sum")).reset_index()
    pg["goals_per_90"], pg["assists_per_90"] = 90 * pg.goals / pg.minutes, 90 * pg.assists / pg.minutes
    T["C10_position_performance"] = pg.round(3).assign(note="position known only for players from StatsBomb/Wyscout/Fjelstul sources")
    pw = aw[aw.winner_type == "player"].copy()
    pw["name"] = pw.full_name.fillna(pw.entity_name_raw)
    T["C11_award_winners_most_awards"] = pw[pw.award_category.isin(["Best player", "Top scorer", "Best goalkeeper", "Best young player"])].groupby("name").size().sort_values(ascending=False).head(15).rename("individual_awards").reset_index()
    cov = D.q("""select competition_id, count(*) goals, count(*) filter (where player_key is not null and not is_own_goal) with_player
                 from gold.mart_goal_analysis group by 1""")
    cov["pct_goals_attributed_to_a_player"] = (100 * cov.with_player / cov.goals).round(1)
    T["C12_coverage_caveat_player_goals"] = cov.assign(note="player tables count only goals linked to a player id; the Nations League has no squad data to link names")
    topn = T["C1_top_scorers"].head(15).iloc[::-1]
    F["C_top_scorers"] = px.bar(topn, x="goals", y="full_name", orientation="h", title="Top scorers in the collected competitions (linked goals only)", labels={"full_name": ""}).update_layout(**LAYOUT)

    # ------------------------------------------------------------------ D. match level
    sc = m.assign(score=lambda d: d[["home_score", "away_score"]].max(axis=1).astype(int).astype(str) + "-" + d[["home_score", "away_score"]].min(axis=1).astype(int).astype(str))
    T["D1_common_scorelines"] = sc.score.value_counts().rename_axis("scoreline_winner_first").rename("matches").reset_index().head(15).assign(pct=lambda d: (100 * d.matches / len(m)).round(1))
    cols = ["season_id", "stage_name", "match_date", "home_team_name", "away_team_name", "home_score", "away_score"]
    T["D2_highest_scoring_matches"] = m.sort_values(["goals_total", "match_date"], ascending=[False, True]).head(15)[cols]
    T["D3_largest_margins"] = m.sort_values(["margin", "goals_total"], ascending=[False, False]).head(15)[cols]
    ht = m[m.home_score_ht.notna() & m.away_score_ht.notna()].copy()
    lead_ht = np.sign(ht.home_score_ht - ht.away_score_ht)
    res = np.sign(ht.home_score - ht.away_score)
    ht["comeback"] = (lead_ht != 0) & (res == -lead_ht)
    ht["draw_from_behind"] = (lead_ht != 0) & (res == 0)
    T["D4_comebacks_halftime_definition"] = pd.DataFrame([dict(
        matches_with_ht_score=len(ht), led_at_ht=int((lead_ht != 0).sum()), comebacks_win=int(ht.comeback.sum()), draws_from_behind=int(ht.draw_from_behind.sum()),
        comeback_pct_of_matches_led_at_ht=round(100 * ht.comeback.sum() / max((lead_ht != 0).sum(), 1), 2),
        note="a comeback = trailing at half-time and winning on the recorded score; half-time scores exist for WC/Euro only (Copa/UNL none)")])
    T["D4b_comeback_matches"] = ht[ht.comeback].assign(ht_score=lambda d: d.home_score_ht.astype(int).astype(str) + "-" + d.away_score_ht.astype(int).astype(str))[cols + ["ht_score"]].sort_values("match_date")
    et = m.groupby(["competition_id", "stage_name"]).agg(matches=("match_key", "size"), beyond_90=("went_beyond_90", "sum"), shootouts=("had_shootout", "sum")).reset_index()
    et["beyond_90_pct"] = (100 * et.beyond_90 / et.matches).round(1)
    T["D5_extra_time_and_shootouts"] = et[et.stage_name != "Group stage"]
    T["D5b_shootouts_by_edition"] = m[m.had_shootout].groupby("season_id").size().rename("shootouts").reset_index()
    gg = g[g.minute.notna()].copy()
    band = gg.groupby("minute_band").size().reindex(["00-15", "16-30", "31-45", "46-60", "61-75", "76-90", "90+ (extra time)"]).rename("goals").reset_index()
    band["pct"] = (100 * band.goals / band.goals.sum()).round(1)
    band["goals_per_minute"] = band.goals / [15, 15, 15, 15, 15, 15, 30]
    T["D6_goals_by_minute_band"] = band.assign(note="minute 45 and 90 absorb stoppage-time goals; the last band mixes extra time (30 min) and is not comparable per minute to regulation bands without that caveat")
    T["D7_group_vs_knockout_outcomes_pct"] = (100 * m.groupby(["phase", "outcome"]).size().unstack(fill_value=0).pipe(lambda d: d.div(d.sum(axis=1), axis=0))).round(1).reset_index()
    T["D8_empirical_outcome_probabilities"] = (m.groupby("competition_id").outcome.value_counts(normalize=True).unstack().round(3).loc[D.COMP_ORDER].reset_index()
                                                 .assign(note="empirical frequencies of the listed team's recorded-score result; not a prediction"))
    sm_ = pd.crosstab(np.minimum(m.home_score, m.away_score).clip(upper=4), np.maximum(m.home_score, m.away_score).clip(upper=6))
    F["D_scoreline_heatmap"] = px.imshow(sm_.values, x=[str(c) for c in sm_.columns], y=[str(i) for i in sm_.index], text_auto=True, color_continuous_scale="Blues",
                                         labels=dict(x="Winner's goals (6 = 6+)", y="Loser's goals (4 = 4+)", color="Matches"), title="Scoreline frequency (winner vs loser goals)").update_layout(**LAYOUT)
    kb = T["D5_extra_time_and_shootouts"].groupby("competition_id")[["matches", "beyond_90", "shootouts"]].sum().reset_index()
    kb["beyond_90_pct"] = 100 * kb.beyond_90 / kb.matches
    kb["shootout_pct"] = 100 * kb.shootouts / kb.matches
    F["D_extra_time_and_shootouts"] = px.bar(kb.melt("competition_id", ["beyond_90_pct", "shootout_pct"], var_name="measure", value_name="pct"), x="competition_id", y="pct", color="measure",
                                             barmode="group", title="Knockout matches: share beyond 90 minutes and decided by shoot-out (Nations League extra time is not recorded)").update_layout(**LAYOUT)
    F["D_goals_by_minute_band"] = px.bar(band, x="minute_band", y="goals", title="Goals by minute band (goal events with a known minute)", labels={"minute_band": "Minute band"}).update_layout(**LAYOUT)

    # ------------------------------------------------------------------ E. historical trends
    rows = []
    for c, gdf in tr_played.groupby("competition_id"):
        if len(gdf) >= 4:
            rows.append(dict(competition_id=c, **_slope(gdf.season_year, gdf.goals_per_match)))
    wc_cur = tr_played[tr_played.competition_id.isin(["WC", "EURO", "COPA"])]
    T["E1_goals_per_match_trend_ols_by_competition"] = pd.DataFrame(rows).round(4).assign(note="OLS on edition means (small n); the formal per-match test with overdispersion check is in the statistics report (Q1)")
    ccomp = tm.groupby(["season_id", "team_key"]).points.sum().reset_index().merge(tr[["season_id", "competition_id", "season_year"]], on="season_id")
    comp = ccomp.groupby(["season_id", "competition_id", "season_year"]).points.agg(sd_points="std", teams="size").reset_index()
    T["E2_team_competitiveness_sd_of_points_per_edition"] = comp.round(3).assign(note="SD of team points within an edition; depends on matches played per team, so compare within one competition/format")
    cs = tm.groupby("season_id").agg(clean_sheet_pct=("clean_sheet", lambda s: 100 * s.mean()), gf_pm=("goals_for", "mean")).round(3).reset_index()
    T["E3_attack_defence_evolution"] = cs.merge(tr[["season_id", "competition_id", "season_year", "draw_pct"]], on="season_id").sort_values(["competition_id", "season_year"])
    T["E4_format_table"] = tr_played[["season_id", "competition_id", "teams", "matches_played", "goals_per_match"]].assign(
        note="format = number of teams and match count; compare within competition")
    T["E5_upcoming_fixtures_coming_soon"] = m_all[~m_all.is_played][["season_id", "match_date", "stage_name", "group_name", "home_team_name", "away_team_name", "venue_name", "venue_city", "status_label", "fixture_detail"]] \
        if "is_played" in m_all else pd.DataFrame()
    F["E_clean_sheet_trend"] = px.line(T["E3_attack_defence_evolution"], x="season_year", y="clean_sheet_pct", color="competition_id", markers=True, color_discrete_map=D.COMP_COLOR,
                                       title="Clean-sheet share of team-matches by edition").update_layout(**LAYOUT)
    return dict(tables=T, figures=F)


def write(res: dict) -> dict:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    for k, df in res["tables"].items():
        df.to_csv(OUT / "tables" / f"{k}.csv", index=False)
    first = True
    parts = []
    for k, fig in res["figures"].items():
        fig.write_html(OUT / "figures" / f"{k}.html", include_plotlyjs="cdn")
        parts.append((k, fig.to_html(full_html=False, include_plotlyjs=True if first else False)))
        first = False
    toc = "".join(f"<li><a href='#{k}'>{k}</a></li>" for k in res["tables"])
    tabs = "".join(f"<h3 id='{k}'>{k}</h3>{df.head(25).to_html(index=False, border=0, classes='t', na_rep='')}" for k, df in res["tables"].items())
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>Football EDA report</title><style>body{font-family:Segoe UI,Arial;margin:24px;max-width:1200px}"
            "table.t{border-collapse:collapse;font-size:12px}table.t td,table.t th{border-bottom:1px solid #ddd;padding:3px 8px}h3{margin-top:28px}</style></head><body>"
            "<h1>EDA: FIFA World Cup, UEFA Euro, Copa América, UEFA Nations League</h1>"
            "<p>Played matches only; scheduled fixtures are listed in E5 as <b>Coming soon</b>. Rates are per match; raw totals are never compared across formats. "
            "Player numbers cover the collected competitions only (not careers) and linked goals only.</p>"
            f"<h2>Figures</h2>{''.join(h for _, h in parts)}<h2>Tables</h2><ul>{toc}</ul>{tabs}</body></html>")
    (OUT / "eda_report.html").write_text(html, encoding="utf-8")
    summary = {k: len(v) for k, v in res["tables"].items()}
    (OUT / "eda_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


if __name__ == "__main__":
    s = write(build())
    print(len(s), "tables;", "report:", OUT / "eda_report.html")
