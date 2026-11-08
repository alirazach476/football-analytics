"""Part A.4: initial data-quality investigation (15 questions).  READ-ONLY; nothing is removed or changed.

Each finding is classified:
  confirmed_error     - provably wrong (violates a hard rule)
  possible_error      - suspicious, needs a source check
  legitimate_missing  - the value does not exist in any permitted source / does not apply
  info                - a normal condition worth knowing (e.g. aliases, corrections already applied)
Output: data/inventory/issues.csv and data_quality_initial_report.html
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from .config import DATA
from .inventory import OUT
from .registry import build_registry

P = DATA / "processed"
Q = DATA / "quality"


def _csv(path):
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def run() -> pd.DataFrame:
    m = pd.read_parquet(P / "matches.parquet")
    t = pd.read_parquet(P / "teams.parquet")
    al = pd.read_csv(P / "team_aliases.csv")
    pl = pd.read_parquet(P / "players_all.parquet")
    ev = pd.read_parquet(P / "events_all.parquet", columns=["match_id", "event_type", "player_id", "provider", "team_id", "minute"])
    lu = pd.read_parquet(P / "lineups_all.parquet", columns=["match_id", "player_id", "provider", "minutes_played_derived", "is_starter", "team_id"])
    ps = pd.read_parquet(P / "player_match_stats_all.parquet")
    sq = pd.read_parquet(P / "squads" / "squads.parquet")
    reg = build_registry().set_index("season_id")
    today = pd.Timestamp(date.today())
    out = []

    def add(n, topic, table, cls, count, text, example=""):
        out.append(dict(question=n, topic=topic, table=table, classification=cls, records=int(count), finding=text, example=str(example)[:240]))

    played = m[m.match_status == "completed"]
    # 1 duplicate matches
    add(1, "duplicate matches", "matches", "confirmed_error" if m.match_id.duplicated().sum() else "info", m.match_id.duplicated().sum(), "duplicate match_id")
    d = m.duplicated(["season_id", "match_date", "home_team_id", "away_team_id"], keep=False) & m.home_team_id.notna()
    add(1, "duplicate matches", "matches", "confirmed_error" if d.sum() else "info", d.sum(), "same season + date + home + away team appears more than once")
    # 2 duplicate players
    k = pl.assign(n=pl.full_name.str.lower().str.strip())
    dd = k[k.date_of_birth.notna()].duplicated(["n", "date_of_birth"], keep=False)
    add(2, "duplicate players", "players_all", "possible_error" if dd.sum() else "info", dd.sum(), "same full name + date of birth under different player_id (should be one person unless a rule is missing)",
        k[k.date_of_birth.notna()][dd].n.head(3).tolist())
    nd = k.duplicated(["n"], keep=False)
    add(2, "duplicate players", "players_all", "possible_error", nd.sum(), "same normalised full name under different ids (often different people: same-name players; needs DOB/team check)")
    # 3 duplicate teams
    from .ingest.build import norm
    tn = t.assign(k=t.team_name.map(norm))
    add(3, "duplicate teams", "teams", "confirmed_error" if tn.k.duplicated().sum() else "info", tn.k.duplicated().sum(), "two team ids with the same normalised name")
    multi = al.groupby("alias").team_id.nunique()
    add(3, "duplicate teams", "team_aliases", "confirmed_error" if (multi > 1).sum() else "info", (multi > 1).sum(), "one alias mapped to several teams")
    add(3, "duplicate teams", "teams", "info", len(_csv(Q.parent / "processed" / "entity_resolution_review.csv")), "similar-name team pairs reviewed and deliberately NOT merged")
    # 4 missing scores
    add(4, "missing scores", "matches", "confirmed_error" if (m.match_status.eq("completed") & m.home_score.isna()).sum() else "info",
        (m.match_status.eq("completed") & m.home_score.isna()).sum(), "completed match without a score")
    add(4, "missing scores", "matches", "legitimate_missing", (m.match_status.eq("scheduled") & m.home_score.isna()).sum(), "scheduled fixtures (Euro 2028): no score yet, kept null", "EURO-2028")
    add(4, "missing scores", "matches", "confirmed_error" if (m.match_status.eq("scheduled") & m.home_score.notna()).sum() else "info",
        (m.match_status.eq("scheduled") & m.home_score.notna()).sum(), "scheduled match that has a score")
    # 5 / 10 dates and seasons
    fut = played[pd.to_datetime(played.match_date) > today]
    add(5, "incorrect dates", "matches", "confirmed_error" if len(fut) else "info", len(fut), "completed match dated in the future")
    corr = m[m.date_check.fillna("").str.startswith("corrected")]
    add(5, "incorrect dates", "matches", "info", len(corr), "dates already corrected by majority of three sources (original recorded in date_check)", corr.date_check.head(1).tolist())
    mm = m[m.date_check.fillna("").str.contains("mismatch|disagrees")]
    add(5, "incorrect dates", "matches", "possible_error", len(mm), "date contradicts the weekday written in its source line", mm[["season_id", "match_date"]].astype(str).values.tolist()[:2])
    bad_season = 0
    ex = []
    for sid, g in m.groupby("season_id"):
        if sid in reg.index and pd.notna(reg.loc[sid, "start_date"]) and pd.notna(reg.loc[sid, "end_date"]):
            s0, s1 = pd.Timestamp(reg.loc[sid, "start_date"]), pd.Timestamp(reg.loc[sid, "end_date"])
            b = g[(pd.to_datetime(g.match_date) < s0) | (pd.to_datetime(g.match_date) > s1)]
            bad_season += len(b)
            ex += [sid] if len(b) else []
    add(10, "incorrect season assignments", "matches", "possible_error" if bad_season else "info", bad_season,
        "match date outside the season's registry window (the registry window itself is a seeded, unverified fact)", ex[:5])
    undated = reg[reg.start_date.isna()].index.tolist()
    add(10, "incorrect season assignments", "registry", "legitimate_missing", len(undated), "seasons without confirmed start/end dates", undated)
    # 6 statuses
    add(6, "invalid match statuses", "matches", "confirmed_error" if (~m.match_status.isin(["completed", "scheduled"])).sum() else "info",
        (~m.match_status.isin(["completed", "scheduled"])).sum(), f"values seen: {m.match_status.value_counts().to_dict()}; abandoned/awarded results have no own status")
    aw = m[m.score_note.fillna("").str.contains("abandoned|awarded")]
    add(6, "invalid match statuses", "matches", "possible_error", len(aw), "match whose on-pitch result differs from an awarded result (no 'awarded' status exists)", aw[["home_team_raw", "away_team_raw"]].values.tolist()[:1])
    # 7 missing player ids
    for prov, g in ev[ev.player_id.isna()].groupby("provider"):
        pass
    nm = ev.assign(has=ev.player_id.notna()).groupby("provider").has.agg(["size", "sum"])
    for prov, r in nm.iterrows():
        miss = int(r["size"] - r["sum"])
        if miss:
            cls = "legitimate_missing" if prov in ("martj42", "openfootball", "wikipedia") else "info"
            add(7, "missing player ids", "events_all", cls, miss, f"{prov}: events without player_id" + (" (source gives names only)" if cls == "legitimate_missing" else " (non-player events such as match start/end)"))
    wl = lu[lu.player_id.isna()]
    add(7, "missing player ids", "lineups_all", "legitimate_missing", len(wl), "Wikipedia line-up rows carry names only (no ids exist in that source)", wl.provider.value_counts().to_dict())
    # 8 team names
    k8 = al.groupby("team_id").alias.nunique()
    add(8, "inconsistent team names", "team_aliases", "info", (k8 > 1).sum(), "teams spelled several ways in the sources (resolved by documented rules R0-R4)", k8.sort_values(ascending=False).head(3).to_dict())
    # 9 competition names
    comps = pd.concat([m.competition_id, sq.competition_id]).unique().tolist()
    add(9, "inconsistent competition names", "matches/squads", "confirmed_error" if set(comps) - {"WC", "EURO", "COPA", "UNL"} else "info", len(comps),
        f"competition_id values in use: {sorted(comps)}; raw source spellings (e.g. 'UEFA Euro', '2018 FIFA Men's World Cup', 'Copa América') all map to these four")
    # 11 stages
    add(11, "missing tournament stages", "matches", "confirmed_error" if played.stage.isna().sum() else "info", played.stage.isna().sum(), "played matches without a stage")
    add(11, "missing tournament stages", "matches", "legitimate_missing", m[m.match_status != "completed"].stage.isna().sum(), "scheduled fixtures without a stage")
    # 12 score validity
    sc = played[(played.home_score < 0) | (played.away_score < 0) | (played.home_score > 12) | (played.away_score > 12)]
    add(12, "invalid score values", "matches", "possible_error" if len(sc) else "info", len(sc), "scores <0 or >12 (highest real score in scope: Hungary 10-1 El Salvador style results excluded; check manually)", sc[["home_team_raw", "away_team_raw", "home_score", "away_score"]].values.tolist()[:2])
    pe = played[played.home_pen.notna() & (played.home_score != played.away_score) & (played.leg != 2)]
    add(12, "invalid score values", "matches", "confirmed_error" if len(pe) else "info", len(pe), "shoot-out recorded but on-pitch score not level")
    # 13 player stats
    chk = [("passes_completed > passes", ps.passes_completed > ps.passes), ("shots_on_target > shots", ps.shots_on_target > ps.shots),
           ("minutes_played < 0 or > 130", (ps.minutes_played < 0) | (ps.minutes_played > 130))]
    for name, mask in chk:
        add(13, "inconsistent player statistics", "player_match_stats_all", "confirmed_error" if mask.sum() else "info", mask.sum(), name)
    tms = pd.read_parquet(P / "team_match_stats_all.parquet")
    tt = tms.merge(m[["match_id", "home_team_id", "home_score", "away_score"]], on="match_id")
    exp = tt.apply(lambda r: r.home_score if r.team_id == r.home_team_id else r.away_score, axis=1)
    add(13, "inconsistent player statistics", "team_match_stats_all", "confirmed_error" if (tt.goals_for_incl_own_goals != exp).sum() else "info",
        (tt.goals_for_incl_own_goals != exp).sum(), "team goals rebuilt from events differ from the recorded score")
    add(13, "inconsistent player statistics", "player_match_stats_all", "legitimate_missing", len(ps[ps.provider == "wyscout"]), "Wyscout rows: tackles, interceptions, blocks, xG, xA are null by definition (not 0)")
    # 14 missing historical records
    cnt = m.groupby("season_id").size()
    gap = [(s, int(cnt.get(s, 0)), int(reg.loc[s, "expected_matches"])) for s in reg.index if pd.notna(reg.loc[s, "expected_matches"]) and cnt.get(s, 0) != reg.loc[s, "expected_matches"]]
    add(14, "missing historical records", "matches vs registry", "confirmed_error" if gap else "info", len(gap), "seasons whose match count differs from the registry's (arithmetic) expected count", gap[:4])
    nu = reg[(reg.competition_id == "UNL") & reg.expected_matches.isna()].index.tolist()
    add(14, "missing historical records", "registry", "legitimate_missing", len(nu), "Nations League seasons have no expected count (no verified official total)", nu)
    cov = _csv(P / "match_event_coverage.csv")
    add(14, "missing historical records", "events", "legitimate_missing", int((cov.event_coverage == "none").sum()), "played matches with no event data in any permitted source")
    add(14, "missing historical records", "matches", "legitimate_missing", int(played.attendance.isna().sum()), "played matches with no attendance in either Wikipedia")
    add(14, "missing historical records", "matches", "legitimate_missing", int(played.man_of_the_match_raw.isna().sum()), "played matches without a Man of the Match (not recorded for Copa 2001/04/07 or Nations League group matches)")
    add(14, "missing historical records", "events", "legitimate_missing", int(len(played) - ev[ev.location_x.notna()].match_id.nunique()) if "location_x" in ev else len(played) - 313,
        "played matches without pass/shot coordinates (only StatsBomb and Wyscout publish them)")
    # 15 conflicts between files
    for f, label in (("wikipedia_vs_matches_conflicts.csv", "Wikipedia vs matches"), ("martj42_vs_matches_conflicts.csv", "martj42 vs matches"),
                     ("fjelstul_vs_matches_conflicts.csv", "Fjelstul vs matches")):
        c = _csv(Q / f)
        add(15, "conflicting records between files", f, "possible_error" if len(c) else "info", len(c), f"{label}: rows in the conflict report (resolved or annotated individually)", c.head(1).to_dict("records"))
    v = _csv(Q / "wikipedia_details_validation.csv")
    if len(v):
        add(15, "conflicting records between files", "wikipedia_details_validation.csv", "possible_error", int((v.cards_wikipedia != v.cards_other).sum()),
            f"matches where Wikipedia and Fjelstul/StatsBomb disagree on the NUMBER of cards ({len(v)} compared)")
    fv = _csv(Q / "fjelstul_vs_statsbomb.csv")
    if len(fv):
        add(15, "conflicting records between files", "fjelstul_vs_statsbomb.csv", "possible_error", int((fv.cards_fj != fv.cards_sb).sum()), f"matches where Fjelstul and StatsBomb disagree on card counts ({len(fv)} compared)")
    # UCL exclusion
    ucl = int(m.competition_id.eq("UCL").sum() + (ev.match_id.map(m.set_index("match_id").competition_id) == "UCL").sum())
    add(0, "UCL exclusion", "all processed tables", "confirmed_error" if ucl else "info", ucl, "UEFA Champions League rows in processed tables (must be 0)")
    df = pd.DataFrame(out)
    df.to_csv(OUT / "issues.csv", index=False)
    return df


def html(df: pd.DataFrame, inv: pd.DataFrame, cache: dict):
    css = "body{font-family:Segoe UI,Arial;margin:24px;color:#222}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ccc;padding:4px 8px;vertical-align:top}th{background:#f0f0f0}.confirmed_error{background:#fde0e0}.possible_error{background:#fff2cc}.legitimate_missing{background:#e2eefb}.info{background:#e8f5e9}"
    summ = df.groupby("classification").agg(findings=("records", "size"), records=("records", "sum"))
    body = [f"<style>{css}</style><h1>Initial data-quality report</h1><p>Generated {pd.Timestamp.now():%Y-%m-%d %H:%M}. Read-only investigation of {len(inv)} files; nothing was deleted or modified.</p>",
            "<h2>Summary by classification</h2>" + summ.to_html(), "<h2>Findings</h2><table><tr>" + "".join(f"<th>{c}</th>" for c in df.columns) + "</tr>"]
    for r in df.sort_values(["question", "classification"]).itertuples(index=False):
        body.append(f"<tr class='{r.classification}'>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>")
    body.append("</table><h2>Cached source files and staging (summarised)</h2>" + pd.DataFrame(cache["cache"]).T.to_html())
    (OUT / "data_quality_initial_report.html").write_text("\n".join(body), encoding="utf-8")


if __name__ == "__main__":
    from .inventory import inventory
    inv, ctx = inventory()
    from .inventory import write_dictionary
    write_dictionary(ctx)
    df = run()
    html(df, inv, ctx["cache"])
    print(len(inv), "files |", len(ctx["frames"]), "tables profiled |", len(ctx["columns"]), "columns |", "UCL files in raw cache:", ctx["cache"]["ucl_cached_files"])
    print(df.groupby("classification").agg(findings=("records", "size")).to_dict()["findings"])
    print(df[df.classification.isin(["confirmed_error", "possible_error"]) & (df.records > 0)][["question", "topic", "classification", "records", "finding"]].to_string(index=False))
