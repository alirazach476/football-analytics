"""Unify providers into the final event/lineup/player/stat tables (the *_all files are the ones to use).

Provider priority PER MATCH and EVENT CLASS (goals / cards+substitutions / full events); a class never has two
providers for the same match, so nothing is double counted:
  StatsBomb / Wyscout full events  >  Fjelstul (goals, cards, subs, lineups, shoot-out kicks)
  >  OpenFootball goal lines  >  martj42 goal scorers (CC0; complete or partial, never padded)
  >  Wikipedia goal lists (CC BY-SA; only lists that reproduce the score).
Wikipedia match details (line-ups, cards, substitutions; player NAMES only, no ids) are used for matches that have no
full-event provider and no Fjelstul coverage.
Lower-priority providers are kept only as validation (reports in data/quality/).

Player identity rules (cross-provider; ambiguous / non-unique cases are NOT linked):
  P1 Wyscout<->StatsBomb : equal normalised full name AND equal nationality, unique on both sides.
  P3 Fjelstul<->Wyscout  : equal date of birth AND all Fjelstul name tokens appear in the Wyscout full name.
  P4 Fjelstul<->StatsBomb: all Fjelstul name tokens appear in the StatsBomb full name AND a shared national
                           team (StatsBomb has no birth date), unique on both sides.
Linked ids are replaced by the preferred id (StatsBomb > Wyscout > Fjelstul) in `player_id`; the original
is kept in `player_id_source`.

Match statistics for Wyscout matches are computed ONLY for fields Wyscout defines unambiguously;
the rest stay null (not 0): tackles, interceptions, blocks, fouls_won, xg, xa, possession.
Goal-level providers only produce team rows with the fields they actually have.
"""
from __future__ import annotations

import json

import pandas as pd

from ..config import DATA
from .build import PROC, norm
from .stats import player_stats as sb_player_stats

QDIR = DATA / "quality"
ON_FRAME = {"gb", "gbr", "gc", "gl", "glb", "gr", "gt", "gtl", "gtr"}  # tags 1201-1209: shot placed inside the goal frame


def link_players(sb: pd.DataFrame, wy: pd.DataFrame):
    def key(df):
        return df.assign(k=df.full_name.map(norm) + "|" + df.nationality.fillna("").map(norm))
    a, b = key(sb), key(wy)
    ca, cb = a.k.value_counts(), b.k.value_counts()
    links, review = {}, []
    for k in set(a.k) & set(b.k):
        if k.endswith("|"):
            continue
        if ca[k] == 1 and cb[k] == 1:
            links[b[b.k == k].player_id.iat[0]] = a[a.k == k].player_id.iat[0]
        else:
            review.append(dict(key=k, statsbomb_rows=int(ca[k]), wyscout_rows=int(cb[k]), decision="not linked: not unique"))
    return links, pd.DataFrame(review)


def _tok(s):
    return set(norm(s).split())


def _link_by(a: pd.DataFrame, b: pd.DataFrame, ok) -> dict:
    """generic unique-both-sides linker: ok(row_a, row_b) -> bool. Returns {b_id: a_id}."""
    cand_a, cand_b = {}, {}
    for x in a.itertuples():
        for y in b.itertuples():
            if ok(x, y):
                cand_a.setdefault(x.player_id, []).append(y.player_id)
                cand_b.setdefault(y.player_id, []).append(x.player_id)
    return {y: xs[0] for y, xs in cand_b.items() if len(xs) == 1 and len(cand_a[xs[0]]) == 1}


def wyscout_stats(ev: pd.DataFrame, lu: pd.DataFrame) -> pd.DataFrame:
    e = ev[(ev.period <= 4) & ev.player_id.notna() & (ev.event_type != "substitution")].copy()
    tags = e.tags.map(json.loads)
    e["on_frame"] = tags.map(lambda t: bool(ON_FRAME & set(t)))
    shot = e.event_type.eq("shot") | (e.event_type.eq("free_kick") & e.detail_type.isin(["Free kick shot", "Penalty"]))
    pas = e.event_type.eq("pass")
    keys = ["match_id", "player_id", "team_id"]

    def cnt(mask):
        return e[mask].groupby(keys).size()

    st = pd.DataFrame({
        "goals": cnt(e.is_goal.eq(True)), "own_goals": cnt(e.is_own_goal.eq(True)), "assists": cnt(e.is_assist.eq(True)),
        "shots": cnt(shot), "shots_on_target": cnt(shot & (e.on_frame | e.is_goal.eq(True))),
        "passes": cnt(pas), "passes_completed": cnt(pas & e.outcome.eq("Accurate")),
        "key_passes": cnt(e.is_key_pass.eq(True)), "clearances": cnt(e.detail_type.eq("Clearance")),
        "fouls_committed": cnt(e.event_type.eq("foul")),
        "yellow_cards": cnt(e.card.isin(["Yellow Card", "Second Yellow"])), "red_cards": cnt(e.card.isin(["Red Card", "Second Yellow"])),
        "saves": cnt(e.event_type.eq("save_attempt") & e.outcome.ne("Goal conceded")),
        "corners_taken": cnt(e.is_corner.eq(True)), "offsides": cnt(e.event_type.eq("offside"))}).fillna(0).astype(int)
    st = st.reset_index()
    st["pass_accuracy"] = (st.passes_completed / st.passes).where(st.passes > 0)
    subs = ev[ev.event_type == "substitution"]
    l = lu.copy()
    l["sub_on"] = l.player_id.isin(subs.related_player_id) & ~l.is_starter
    l["sub_off"] = l.player_id.isin(subs.player_id)
    out = l[["match_id", "team_id", "player_id", "jersey_number", "is_starter", "minutes_played_derived", "sub_on", "sub_off"]] \
        .merge(st, on=keys, how="outer")
    counts = [c for c in st.columns if c not in keys + ["pass_accuracy"]]
    out[counts] = out[counts].fillna(0).astype(int)
    for c in ("tackles", "interceptions", "blocks", "fouls_won", "xg", "xa"):
        out[c] = None  # not defined unambiguously in Wyscout -> null, never 0
    return out.rename(columns={"minutes_played_derived": "minutes_played"})


def goal_level_team_stats(ev: pd.DataFrame, m: pd.DataFrame, full: set, detail_ids: set) -> pd.DataFrame:
    """One row per (match, team) for matches without full events, built from ALL providers' events for that match
    (goals may come from one provider, cards/substitutions from another). Cards/substitutions are only counted where a
    provider with card + substitution coverage exists (Fjelstul / Wikipedia details); otherwise they stay null."""
    e = ev[~ev.match_id.isin(full)]
    if e.empty:
        return pd.DataFrame()
    prov = e.groupby("match_id").provider.agg(lambda x: "+".join(sorted(set(x))))
    rows = []
    for (mid, tid), g in e.groupby(["match_id", "team_id"]):
        has = mid in detail_ids
        rows.append(dict(match_id=mid, team_id=tid, provider=prov[mid],
                         goals_for_incl_own_goals=int((g.event_type == "goal").sum()),
                         own_goals=int(((g.event_type == "goal") & g.is_own_goal.eq(True)).sum()),
                         yellow_cards=int(g.card.isin(["Yellow Card", "Second Yellow"]).sum()) if has else None,
                         red_cards=int(g.card.isin(["Red Card", "Second Yellow"]).sum()) if has else None,
                         substitutions=int((g.event_type == "substitution").sum()) if has else None))
    out = pd.DataFrame(rows)
    have = set(zip(out.match_id, out.team_id))
    extra = []
    for r in m[m.match_id.isin(set(e.match_id))].itertuples():
        for tid in (r.home_team_id, r.away_team_id):
            if (r.match_id, tid) not in have:
                has = r.match_id in detail_ids
                extra.append(dict(match_id=r.match_id, team_id=tid, provider=prov[r.match_id], goals_for_incl_own_goals=0, own_goals=0,
                                  yellow_cards=0 if has else None, red_cards=0 if has else None, substitutions=0 if has else None))
    return pd.concat([out, pd.DataFrame(extra)], ignore_index=True)


def run():
    from . import martj42
    m = pd.read_parquet(PROC / "matches.parquet")
    sbe = pd.read_parquet(PROC / "events.parquet").assign(provider="statsbomb", coordinate_system="statsbomb_120x80",
                                                         is_own_goal=None, tags=None)
    wye = pd.read_parquet(PROC / "wyscout" / "events_wyscout.parquet")
    fje = pd.read_parquet(PROC / "fjelstul" / "events_fjelstul.parquet")
    gl = pd.read_parquet(PROC / "goal_events_openfootball.parquet").assign(coordinate_system=None)
    sbl = pd.read_parquet(PROC / "lineups.parquet").assign(provider="statsbomb")
    wyl = pd.read_parquet(PROC / "wyscout" / "lineups_wyscout.parquet")
    fjl = pd.read_parquet(PROC / "fjelstul" / "lineups_fjelstul.parquet")
    sbp = pd.read_parquet(PROC / "players.parquet")
    wyp = pd.read_parquet(PROC / "wyscout" / "players_wyscout.parquet")
    fjp = pd.read_parquet(PROC / "fjelstul" / "players_fjelstul.parquet")
    wpl_f, wpd_f = PROC / "wikipedia" / "lineups_wikipedia.parquet", PROC / "wikipedia" / "detail_events_wikipedia.parquet"
    wpl = pd.read_parquet(wpl_f) if wpl_f.exists() else pd.DataFrame()
    wpd = pd.read_parquet(wpd_f) if wpd_f.exists() else pd.DataFrame()

    # ---------------- player identity
    links_wy, review = link_players(sbp, wyp)                       # P1: Wyscout id -> StatsBomb id
    p3 = _link_by(wyp[wyp.date_of_birth.notna()], fjp[fjp.date_of_birth.notna()],
                  lambda x, y: x.date_of_birth == y.date_of_birth and _tok(y.full_name) <= _tok(x.full_name))  # {fj: wy}
    fj_teams = pd.concat([fje[["player_id", "team_id"]], fjl[["player_id", "team_id"]]]).dropna().groupby("player_id").team_id.agg(set).to_dict()
    sb_teams = {r.player_id: set(json.loads(r.team_ids)) for r in sbp.itertuples()}
    p4 = _link_by(sbp, fjp, lambda x, y: _tok(y.full_name) <= _tok(x.full_name)
                  and bool(sb_teams.get(x.player_id, set()) & fj_teams.get(y.player_id, set())))               # {fj: sb}
    canon = dict(links_wy)
    for fj, wy in p3.items():
        canon[fj] = links_wy.get(wy, wy)
    for fj, sb in p4.items():
        canon[fj] = sb                        # StatsBomb id preferred when both exist
    for df in (wye, wyl, fje, fjl):
        df["player_id_source"] = df.player_id
        df["player_id"] = df.player_id.map(canon).fillna(df.player_id)
        if "related_player_id" in df:
            df["related_player_id"] = df.related_player_id.map(canon).fillna(df.related_player_id)
    sbe["player_id_source"] = sbe.player_id

    # ---------------- provider priority per match
    full = set(sbe.match_id) | set(wye.match_id)
    fj_ids = (set(fje.match_id) | set(fjl.match_id)) - full
    fje = fje[fje.match_id.isin(fj_ids)]
    fjl = fjl[fjl.match_id.isin(fj_ids)]
    gl = gl[~gl.match_id.isin(full | fj_ids)]
    of_ids = set(gl.match_id)
    mj = martj42.goal_events(m)
    mj = mj[~mj.match_id.isin(full | fj_ids | of_ids)]
    done = m[m.match_status == "completed"].set_index("match_id")
    mj_status, keep = {}, []
    for mid, g in mj.groupby("match_id"):
        r = done.loc[mid]
        h, a = int(g._credited_home.sum()), int((~g._credited_home).sum())
        st = "complete" if (h, a) == (int(r.home_score), int(r.away_score)) else (
            "partial" if h <= r.home_score and a <= r.away_score else "inconsistent")
        mj_status[mid] = st
        if st != "inconsistent":
            keep.append(g)       # inconsistent lists (more goals than the score) are dropped, partial ones kept + labelled
    mj = pd.concat(keep, ignore_index=True) if keep else mj.iloc[0:0]
    mj = mj.drop(columns="_credited_home")
    wpf = PROC / "wikipedia" / "goal_events_wikipedia.parquet"
    wp = pd.read_parquet(wpf) if wpf.exists() else mj.iloc[0:0]
    wp = wp[~wp.match_id.isin(full | fj_ids | of_ids | set(mj.match_id))]

    # Wikipedia match details (cards, substitutions, line-ups): only for matches without a richer provider.
    # Per event CLASS one provider: goals from the best goal source above, cards/substitutions/line-ups from Wikipedia.
    wp_detail_ids = (set(wpd.match_id) | set(wpl.match_id)) - full - fj_ids if len(wpd) or len(wpl) else set()
    wpd = wpd[wpd.match_id.isin(wp_detail_ids)] if len(wpd) else wpd
    wpl = wpl[wpl.match_id.isin(wp_detail_ids)] if len(wpl) else wpl
    events = pd.concat([sbe, wye, fje, gl, mj, wp, wpd], ignore_index=True)
    if "assist_name_raw" not in events:
        events["assist_name_raw"] = None
    lineups = pd.concat([sbl, wyl, fjl, wpl], ignore_index=True)
    lineups["source_player_id"] = lineups.source_player_id.astype("string")   # ints (StatsBomb/Wyscout), 'P-123' (Fjelstul), none (Wikipedia)

    # ---------------- players table (linked pairs collapse onto the preferred id, nulls filled from the other)
    wy_idx, fj_idx = wyp.set_index("player_id"), fjp.set_index("player_id")
    rev_wy = {v: k for k, v in links_wy.items()}
    rev_fj = {}
    for fj, c in canon.items():
        if fj in fj_idx.index:
            rev_fj.setdefault(c, []).append(fj)
    sbp = sbp.copy()
    for i, r in sbp.iterrows():
        ids = json.loads(r.source_identifiers)
        srcs = ([(wy_idx, rev_wy[r.player_id])] if r.player_id in rev_wy else []) + [(fj_idx, x) for x in rev_fj.get(r.player_id, [])]
        for idx, sid in srcs:
            w = idx.loc[sid]
            for c in ("date_of_birth", "height_cm", "preferred_foot"):
                if pd.isna(sbp.at[i, c]):
                    sbp.at[i, c] = w[c]
            ids.update(json.loads(w.source_identifiers))
        sbp.at[i, "source_identifiers"] = json.dumps(ids)
    wyp2 = wyp[~wyp.player_id.isin(links_wy)].copy()
    for i, r in wyp2.iterrows():
        ids = json.loads(r.source_identifiers)
        for sid in rev_fj.get(r.player_id, []):
            w = fj_idx.loc[sid]
            ids.update(json.loads(w.source_identifiers))
            if pd.isna(wyp2.at[i, "date_of_birth"]):
                wyp2.at[i, "date_of_birth"] = w["date_of_birth"]
        wyp2.at[i, "source_identifiers"] = json.dumps(ids)
    fjp2 = fjp[~fjp.player_id.isin(canon)]
    players = pd.concat([sbp, wyp2, fjp2], ignore_index=True)

    # ---------------- stats
    sb_ps = sb_player_stats(sbe[sbe.provider == "statsbomb"], sbl).assign(provider="statsbomb")
    wy_ps = wyscout_stats(wye, wyl).assign(provider="wyscout")
    ps = pd.concat([sb_ps, wy_ps], ignore_index=True)
    opp = {}
    for r in m.itertuples():
        opp[(r.match_id, r.home_team_id)] = r.away_team_id
        opp[(r.match_id, r.away_team_id)] = r.home_team_id
    cols = [c for c in ps.columns if c not in ("match_id", "team_id", "player_id", "jersey_number", "is_starter", "pass_accuracy",
                                               "provider", "minutes_played", "sub_on", "sub_off")]
    ts = ps.groupby(["match_id", "team_id", "provider"])[cols].sum(min_count=1).reset_index()
    og = ts.set_index(["match_id", "team_id"]).own_goals
    ts["goals_for_incl_own_goals"] = [g + og.get((mm, opp.get((mm, t))), 0) for mm, t, g in zip(ts.match_id, ts.team_id, ts.goals)]
    ts["pass_accuracy"] = (ts.passes_completed / ts.passes).where(ts.passes > 0)
    ts["possession_pct"] = None
    ts["substitutions"] = ps.groupby(["match_id", "team_id"]).sub_on.sum().reindex(pd.MultiIndex.from_frame(ts[["match_id", "team_id"]])).values
    extra = goal_level_team_stats(events, m, full, fj_ids | wp_detail_ids)
    ts = pd.concat([ts, extra], ignore_index=True)

    # ---------------- coverage, recomputed from the final tables (per event class)
    comp = m[m.match_status == "completed"][["match_id", "season_id", "competition_id", "home_score", "away_score"]].copy()
    goal_prov = events[events.event_type == "goal"].groupby("match_id").provider.first()

    def status(r):
        mid = r.match_id
        if mid in set(sbe.match_id):
            return "statsbomb_full_events"
        if mid in set(wye.match_id):
            return "wyscout_full_events"
        if mid in fj_ids:
            return "fjelstul_goals_cards_subs_lineups"
        if mid in wp_detail_ids:
            return "wikipedia_goals_cards_subs_lineups" if (mid in goal_prov.index or int(r.home_score) + int(r.away_score) == 0) else "wikipedia_cards_subs_lineups"
        p = goal_prov.get(mid)
        if p == "openfootball":
            return "goals_only_openfootball"
        if p == "wikipedia":
            return "goals_only_wikipedia"
        if p == "martj42":
            return "goals_only_martj42" if mj_status.get(mid) == "complete" else "goals_partial_martj42"
        return "scoreless_0-0" if int(r.home_score) + int(r.away_score) == 0 else "none"

    cov = comp.assign(event_coverage=[status(r) for r in comp.itertuples()])
    cards_prov = events[events.card.notna() | (events.event_type == "substitution")].groupby("match_id").provider.first()
    cov = cov.assign(goals_provider=cov.match_id.map(goal_prov), cards_subs_provider=cov.match_id.map(cards_prov),
                     has_lineups=cov.match_id.isin(set(lineups.match_id)),
                     has_coordinates=cov.match_id.isin(set(events[events.location_x.notna()].match_id)),
                     has_xg=cov.match_id.isin(set(events[events.xg.notna()].match_id)))[
        ["match_id", "season_id", "event_coverage", "goals_provider", "cards_subs_provider", "has_lineups", "has_coordinates", "has_xg"]]

    events.to_parquet(PROC / "events_all.parquet", index=False)
    lineups.to_parquet(PROC / "lineups_all.parquet", index=False)
    players.to_parquet(PROC / "players_all.parquet", index=False)
    players.to_csv(PROC / "players_all.csv", index=False)
    ps.to_parquet(PROC / "player_match_stats_all.parquet", index=False)
    ts.to_parquet(PROC / "team_match_stats_all.parquet", index=False)
    cov.to_csv(PROC / "match_event_coverage.csv", index=False)
    pd.DataFrame([dict(source_id=k, canonical_id=v, rule="P1" if k in links_wy else "P3/P4") for k, v in canon.items()]) \
        .to_csv(PROC / "player_links.csv", index=False)
    QDIR.mkdir(exist_ok=True)
    review.reindex(columns=["key", "statsbomb_rows", "wyscout_rows", "decision"]).to_csv(QDIR / "player_link_review.csv", index=False)
    return events, lineups, players, ps, ts, cov, canon


if __name__ == "__main__":
    ev, lu, pl, ps, ts, cov, links = run()
    print(len(ev), "events |", len(lu), "lineup rows |", len(pl), "players |", len(ps), "player-match rows |",
          len(links), "cross-provider player links")
    print(cov.event_coverage.value_counts().to_string())
    print(ev.provider.value_counts().to_dict())
