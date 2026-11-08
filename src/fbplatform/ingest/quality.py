"""Data-quality checks for the match table; writes data/quality/ report for each ingestion run."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from ..config import DATA
from ..registry import build_registry
from .build import KO, PROC, norm

QDIR = DATA / "quality"
STAGE_ORDER = ["Group stage", "League phase", "Knockout play-off", "Round of 32", "Round of 16",
               "Quarter-finals", "Semi-finals", "Third place", "Final"]


def checks(m: pd.DataFrame, sr: pd.DataFrame, conflicts: pd.DataFrame, reg: pd.DataFrame) -> pd.DataFrame:
    out = []

    def add(name, sev, season, n_bad, detail=""):
        out.append(dict(check_name=name, severity=sev, season_id=season, failing_rows=int(n_bad), detail=detail))

    m = m.copy()
    m["match_date"] = pd.to_datetime(m["match_date"])
    add("duplicate_match_id", "error", "ALL", m.match_id.duplicated().sum())
    key = m.assign(k=m.season_id + m.match_date.astype(str) + m.home_team_raw.map(norm) + m.away_team_raw.map(norm))
    add("duplicate_season_date_teams", "error", "ALL", key.k.duplicated().sum())
    add("same_team_both_sides", "error", "ALL", (m.home_team_raw.map(norm) == m.away_team_raw.map(norm)).sum())
    done = m[m.match_status == "completed"]
    add("negative_or_implausible_score(>12)", "error", "ALL",
        ((done.home_score < 0) | (done.away_score < 0) | (done.home_score > 12) | (done.away_score > 12)).sum())
    pen = m[m.home_pen.notna() & (m.leg != 2)]  # after a 2nd leg the shoot-out decides the aggregate
    add("penalties_but_level_score", "error", "ALL", (pen.home_score != pen.away_score).sum(),
        "shoot-out recorded but on-pitch score not level (single-leg matches)")
    add("date_weekday_mismatch", "error", "ALL", m.date_check.fillna("").str.contains("mismatch|disagrees").sum(),
        "date contradicts the weekday written in the source line")
    add("date_year_adjusted_by_weekday", "info", "ALL", m.date_check.fillna("").str.contains("adjusted").sum())
    et = m[m.home_score_et.notna() & m.home_score_ft90.notna()]
    add("et_score_below_90min_score", "error", "ALL",
        ((et.home_score_et < et.home_score_ft90) | (et.away_score_et < et.away_score_ft90)).sum())
    ht = m[m.home_score_ht.notna() & m.home_score_ft90.notna()]
    add("ht_score_above_90min_score", "error", "ALL",
        ((ht.home_score_ht > ht.home_score_ft90) | (ht.away_score_ht > ht.away_score_ft90)).sum())
    add("completed_without_score", "error", "ALL", ((m.match_status == "completed") & m.home_score.isna()).sum())
    add("missing_stage", "warning", "ALL", m.stage.isna().sum())
    # per-season counts and dates vs registry
    r = reg.set_index("season_id")
    for sid, g in m.groupby("season_id"):
        exp = r.loc[sid, "expected_matches"]
        prim = g.primary_provider.iloc[0]
        if pd.notna(exp) and len(g) != int(exp):
            add("match_count_vs_registry", "warning", sid, abs(len(g) - int(exp)),
                f"have {len(g)}, registry seed {int(exp)}; providers={sorted(g.primary_provider.unique())}")
        s, e = r.loc[sid, "start_date"], r.loc[sid, "end_date"]
        if pd.notna(s) and pd.notna(e):
            bad = g[(g.match_date < pd.Timestamp(s)) | (g.match_date > pd.Timestamp(e))]
            add("date_outside_registry_window", "warning", sid, len(bad),
                "" if bad.empty else f"{bad.match_date.min().date()}..{bad.match_date.max().date()} vs {s}..{e}")
        # chronology: a later stage must not be played before an earlier stage's last match
        ko = g[g.stage.isin(STAGE_ORDER)]
        bad = 0
        last_end = None
        for st in STAGE_ORDER:
            sub = ko[ko.stage == st]
            if sub.empty or st == "Third place":
                continue
            if last_end is not None and sub.match_date.min() < last_end:
                bad += 1
            last_end = sub.match_date.max() if last_end is None else max(last_end, sub.match_date.max())
        add("stage_chronology", "error", sid, bad)
    # leg consistency
    legged = m[m.leg.notna()]
    if len(legged):   # two-legged ties no longer exist in scope (Champions League removed); kept for generality
        cnt = legged.groupby(["season_id", "stage", legged.apply(lambda x: frozenset((norm(x.home_team_raw), norm(x.away_team_raw))), axis=1)]).size()
        add("legs_not_paired", "warning", "ALL", (cnt != 2).sum())
    # provenance completeness
    add("missing_source_url", "error", "ALL", m.source_url.isna().sum())
    add("missing_retrieval_timestamp", "error", "ALL", m.retrieval_timestamp.isna().sum())
    add("cross_source_score_conflicts", "warning", "ALL", len(conflicts), "OpenFootball vs StatsBomb")
    cov = m.assign(has_sb=m.provider_match_ids.str.contains("statsbomb")).groupby("primary_provider").has_sb.sum()
    add("matches_linked_to_statsbomb", "info", "ALL", int(m.provider_match_ids.str.contains("statsbomb").sum()))
    # future seasons must keep results null
    fut = m[m.match_date > pd.Timestamp(datetime.now(timezone.utc).date())]
    add("future_match_with_result", "error", "ALL", fut.home_score.notna().sum())
    return pd.DataFrame(out)


def run():
    QDIR.mkdir(parents=True, exist_ok=True)
    m = pd.read_parquet(PROC / "matches.parquet")
    sr = pd.read_parquet(PROC / "source_records.parquet")
    try:
        conf = pd.read_csv(PROC / "cross_source_conflicts.csv")
    except Exception:
        conf = pd.DataFrame()
    reg = build_registry()
    res = checks(m, sr, conf, reg)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    res.insert(0, "run_id", run_id)
    res["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res.to_parquet(QDIR / "data_quality_checks.parquet", index=False)
    res.to_csv(QDIR / "data_quality_checks.csv", index=False)
    per = m.groupby(["competition_id", "season_id", "primary_provider"]).agg(
        matches=("match_id", "size"), completed=("match_status", lambda s: (s == "completed").sum()),
        with_ht=("home_score_ht", "count"), with_venue=("venue_raw", "count"),
        with_kickoff_utc=("kickoff_utc", "count"), with_referee=("referee_raw", "count")).reset_index()
    lines = [f"# Ingestion data-quality report ({run_id})", "", f"Matches: {len(m)}  | source records: {len(sr)}", "",
             "## Checks", "", res.drop(columns=["run_id", "checked_at"]).to_markdown(index=False), "",
             "## Per-season field availability (counts of non-null)", "", per.to_markdown(index=False)]
    (QDIR / "ingestion_report.md").write_text("\n".join(lines), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = run()
    print(r[r.failing_rows > 0].to_string(index=False))
