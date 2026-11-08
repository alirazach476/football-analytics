"""Silver layer: cleaned, standardised, entity-resolved tables built ONLY from the frozen Bronze snapshot (+ the raw martj42 goalscorers file).

Rules
* Nothing is dropped: every Bronze row appears in Silver; raw values stay in `*_raw` columns next to the standardised ones.
* Upcoming fixtures are KEPT: match_status='scheduled', status_label='Coming soon', score columns stay null,
  `fixture_detail` is a readable summary of whatever is known (date, stage, group, venue/city, placeholder teams such as A1 v A2).
* Player entity resolution (documented): two player ids that share the same normalised full name AND the same non-null date of birth are
  the same person. Canonical id priority: P-SB > P-WY > P-FJ > P-SQ. All members are kept in `player_xref`; fact-like tables get
  `player_id` = canonical id and `player_id_original` = the id they arrived with.
* Assist enrichment: martj42 assist names are attached to goals that have no assist yet (same match, same minute, scorer-name match).
  They are stored as `assist_name_raw` + `assist_source='martj42'`, never overwrite an existing assist and are never linked to a player id.
* UEFA Champions League: not present in the Bronze snapshot tables (scope), asserted in the report.
"""
from __future__ import annotations

import json
import re
import unicodedata

import pandas as pd

from ..config import DATA
from ..ingest.martj42 import cn
from .bronze import latest_snapshot

SILVER = DATA / "silver"
PRIO = {"P-SB": 0, "P-WY": 1, "P-FJ": 2, "P-SQ": 3}
COMP_NAMES = {"WC": "FIFA World Cup", "EURO": "UEFA European Championship", "COPA": "Copa América", "UNL": "UEFA Nations League"}


def _tok(s) -> frozenset:
    if not isinstance(s, str):
        return frozenset()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return frozenset(t for t in re.split(r"[^a-z]+", s) if len(t) > 1)


def _name_key(s) -> str:
    return " ".join(sorted(_tok(s)))


def silver_matches(m: pd.DataFrame, venues: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    m["match_date"] = pd.to_datetime(m.match_date)
    m["competition_name"] = m.competition_id.map(COMP_NAMES)
    m["season_year"] = m.season_id.str.extract(r"-(\d{4})")[0].astype(int)
    m["is_played"] = m.match_status.eq("completed")
    m["status_label"] = m.match_status.map({"completed": "Full time", "scheduled": "Coming soon"}).fillna("Unknown")
    sched = ~m.is_played
    assert m.loc[sched, ["home_score", "away_score"]].isna().all().all(), "scheduled fixtures must have null scores"

    def detail(r):
        bits = [f"{r.match_date:%d %b %Y}", r.stage if isinstance(r.stage, str) else None,
                f"Group {r.group}" if isinstance(r.group, str) else None]
        place = ", ".join(x for x in (r.venue_name if isinstance(r.venue_name, str) else None,
                                      r.venue_city if isinstance(r.venue_city, str) else (r.venue_city_raw if isinstance(r.venue_city_raw, str) else None)) if x)
        bits.append(place or "venue to be confirmed")
        return f"{r.home_team_raw} v {r.away_team_raw}: " + " · ".join(b for b in bits if b)

    m["fixture_detail"] = None
    m.loc[sched, "fixture_detail"] = [detail(r) for r in m[sched].itertuples()]
    m["home_team_display"] = m.home_team_raw
    m["away_team_display"] = m.away_team_raw
    m["teams_known"] = m.home_team_id.notna() & m.away_team_id.notna()
    m["stage_standard"] = m.stage
    m["silver_built_from"] = "bronze_collected_snapshot"
    return m


BS = chr(92)                                        # a literal backslash
_ESC = re.compile(re.escape(BS) + r"u([0-9a-fA-F]{4})")


def fix_escapes(v):
    """Wyscout names arrive double-escaped (backslash-u00f3 instead of the accented letter). Decode those literal sequences; anything else is unchanged."""
    if not isinstance(v, str) or BS + "u" not in v:
        return v
    out = _ESC.sub(lambda m: chr(int(m.group(1), 16)), v)
    try:
        out = out.encode("utf-16", "surrogatepass").decode("utf-16")      # rejoin surrogate pairs
    except UnicodeError:
        pass
    return out


def player_resolution(players: pd.DataFrame, lineups: pd.DataFrame | None = None):
    """Entity resolution for players.
    D1  same normalised full name AND same non-null date of birth.
    D2  the shorter name (>= 2 tokens) is contained in the longer one (e.g. "Lionel Messi" / "Lionel Andres Messi Cuccittini"), they share a
        national team, their dates of birth do not conflict (equal or one missing) and they NEVER appear in the same match line-up of one team.
    Canonical id priority: P-SB > P-WY > P-FJ > P-SQ. All members stay in player_xref with the rule that merged them."""
    p = players.copy()
    for c in ("full_name", "display_name"):
        p[c + "_raw"] = p[c]
        p[c] = p[c].map(fix_escapes)
    p["prefix"] = p.player_id.str[:4]
    p["name_key"] = p.full_name.map(_name_key)
    p["dob"] = pd.to_datetime(p.date_of_birth, errors="coerce")
    p["rank"] = p.prefix.map(PRIO)
    p["canonical_player_id"] = p.player_id
    p["resolution_rule"] = "singleton"
    ok = p[p.dob.notna() & p.name_key.ne("")]
    for _, g in ok.groupby(["name_key", "dob"]):
        if len(g) > 1:
            best = g.sort_values(["rank", "player_id"]).iloc[0].player_id
            for pid in g.player_id:
                p.loc[p.player_id == pid, "canonical_player_id"] = best
                p.loc[p.player_id == pid, "resolution_rule"] = "D1_same_name_and_dob"
    # ---- D2
    d1 = dict(zip(p.player_id, p.canonical_player_id))
    teams = {r.player_id: set(json.loads(r.team_ids)) if isinstance(r.team_ids, str) else set() for r in p.itertuples()}
    seen = {}
    if lineups is not None:
        lu = lineups.dropna(subset=["player_id"])
        for pid, mid, tid in zip(lu.player_id.map(lambda x: d1.get(x, x)), lu.match_id, lu.team_id):
            seen.setdefault(pid, set()).add((mid, tid))
    c1 = p.drop_duplicates("canonical_player_id").set_index("canonical_player_id")
    c1 = c1.assign(tk=c1.full_name.map(_tok))
    team_of = {}                                                                 # canonical -> union of teams of all members
    for pid, cid in d1.items():
        team_of.setdefault(cid, set()).update(teams.get(pid, set()))
    by_team = {}
    for cid in c1.index:
        for t in team_of.get(cid, ()):
            if t.startswith("T-NAT"):
                by_team.setdefault(t, []).append(cid)
    merged = {}
    for t, ids in by_team.items():
        for a_i in range(len(ids)):
            for b_i in range(a_i + 1, len(ids)):
                a, b = ids[a_i], ids[b_i]
                ta, tb = c1.at[a, "tk"], c1.at[b, "tk"]
                short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
                if len(short) < 2 or not short <= long_ or ta == tb:
                    continue
                da, db_ = c1.at[a, "dob"], c1.at[b, "dob"]
                if pd.notna(da) and pd.notna(db_) and da != db_:
                    continue
                if seen.get(a, set()) & seen.get(b, set()):
                    continue                                                       # two players in one line-up are two people
                keep = a if (c1.at[a, "rank"], a) <= (c1.at[b, "rank"], b) else b
                merged[b if keep == a else a] = keep

    def root(x):
        while x in merged:
            x = merged[x]
        return x

    p["canonical_player_id"] = p.canonical_player_id.map(root)
    changed = p.canonical_player_id != p.player_id
    d2 = changed & (p.canonical_player_id.map(root).ne(p.player_id.map(d1)))
    p.loc[d2, "resolution_rule"] = "D2_name_subset_same_national_team"
    canon = {pid: cid for pid, cid in zip(p.player_id, p.canonical_player_id) if pid != cid}
    grp = p.groupby("canonical_player_id").player_id.transform("size")
    p.loc[(p.player_id == p.canonical_player_id) & (grp > 1), "resolution_rule"] = "canonical"
    xref = p[["player_id", "canonical_player_id", "resolution_rule", "full_name", "date_of_birth"]].rename(columns={"player_id": "player_id_original"})
    rows = []
    for cid, g in p.groupby("canonical_player_id"):
        g = g.sort_values(["rank", "player_id"])
        base = g.iloc[0].to_dict()
        for c in ["nationality", "date_of_birth", "height_cm", "preferred_foot", "primary_position"]:
            if pd.isna(base[c]):
                v = g[c].dropna()
                base[c] = v.iloc[0] if len(v) else base[c]
        nat = set().union(*[set(json.loads(x)) if isinstance(x, str) else set() for x in g.team_ids])
        nat = {t for t in nat if t.startswith("T-NAT")}
        base["nationality_basis"] = "source" if pd.notna(base["nationality"]) else None
        if pd.isna(base["nationality"]) and len(nat) == 1:                    # only when the player has exactly one national team in our data
            base["nationality"] = next(iter(nat)).replace("T-NAT-", "").replace("-", " ").title()
            base["nationality_basis"] = "single_national_team_played_for"
        base["merged_player_ids"] = json.dumps(sorted(g.player_id.tolist()))
        base["n_source_ids"] = len(g)
        rows.append(base)
    cp = pd.DataFrame(rows).drop(columns=["prefix", "name_key", "dob", "rank", "canonical_player_id", "resolution_rule"])
    return cp, xref, canon


def attach_assists(ev: pd.DataFrame, matches: pd.DataFrame, players: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    raw = DATA / "raw" / "martj42" / "goalscorers.csv"
    gs = pd.read_csv(raw)
    gs = gs[gs.assist.notna() & gs.assist.ne("NA")].copy()
    gs["date"] = pd.to_datetime(gs.date)
    idx = {}
    for r in matches.itertuples():
        idx.setdefault(frozenset((cn(r.home_team_raw), cn(r.away_team_raw))), []).append(r)
    pname = players.set_index("player_id").full_name.to_dict()
    ev = ev.copy()
    ev["assist_source"] = None
    goals = ev[(ev.is_goal == True) & ev.related_player_id.isna() & ev.assist_name_raw.isna()]
    by_match = {k: g for k, g in goals.groupby("match_id")}
    done, unmatched_match, unmatched_goal = 0, 0, 0
    for r in gs.itertuples():
        cands = [c for c in idx.get(frozenset((cn(r.home_team), cn(r.away_team))), []) if abs((c.match_date - r.date).days) <= 1]
        if len(cands) != 1:
            unmatched_match += 1
            continue
        g = by_match.get(cands[0].match_id)
        if g is None:
            unmatched_goal += 1
            continue
        st = _tok(r.scorer)
        hit = []
        for i, e in g.iterrows():
            if pd.notna(e.minute) and pd.notna(r.minute) and int(e.minute) == int(r.minute):
                nm = e.player_name_raw if isinstance(e.player_name_raw, str) else pname.get(e.player_id)
                if st & _tok(nm) and ev.at[i, "assist_name_raw"] is None:
                    hit.append(i)
        if len(hit) == 1:
            ev.at[hit[0], "assist_name_raw"] = r.assist
            ev.at[hit[0], "assist_source"] = "martj42"
            done += 1
        else:
            unmatched_goal += 1
    return ev, dict(martj42_assist_rows=len(gs), attached=done, no_unique_match=unmatched_match, no_unique_goal=unmatched_goal)


def _beyond90(m: pd.DataFrame) -> pd.Series:
    return (m.went_extra_time.astype(str).eq("True") | m.home_pen.notna() | m.shootout_winner_side.notna() | m.score_basis.eq("aet"))


def link_lineups(lu: pd.DataFrame, matches: pd.DataFrame, squads: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Wikipedia line-ups carry names only. A row gets a player_id when exactly one squad player of that edition and team fits
    (name tokens equal first, then contained). Provenance: player_id_source='squad_name_match'. No squad (Nations League) -> stays unlinked."""
    lu = lu.copy()
    season = matches.set_index("match_id").season_id
    sq = squads.dropna(subset=["player_id"]).copy()
    sq["tk"] = sq.player_name_raw.map(_tok)
    by = {k: g for k, g in sq.groupby(["season_id", "team_id"])}
    todo = lu[lu.player_id.isna() & lu.player_name_raw.notna()]
    linked = ambiguous = nosquad = 0
    for i, r in todo.iterrows():
        cand = by.get((season.get(r.match_id), r.team_id))
        if cand is None:
            nosquad += 1
            continue
        want = _tok(r.player_name_raw)
        if not want:
            continue
        hit = cand[[want == k for k in cand.tk]].player_id.unique()
        if len(hit) == 0:
            hit = cand[[want <= k or k <= want for k in cand.tk]].player_id.unique()
        if len(hit) == 1:
            lu.at[i, "player_id"] = hit[0]
            lu.at[i, "player_id_source"] = "squad_name_match"
            linked += 1
        elif len(hit) > 1:
            ambiguous += 1
    return lu, dict(rows_considered=len(todo), linked=linked, ambiguous=ambiguous, no_squad_for_edition=nosquad)


def derive_minutes(lu: pd.DataFrame, matches: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Minutes for lineup rows that have none (Wikipedia): start = minute_on (0 for starters); end = minute_off, else the red-card minute,
    else the nominal end of the match (90, or 120 when the match went beyond 90). Whole minutes, stoppage time ignored -> an approximation,
    flagged in minutes_basis. Rows from other providers keep their own (event-derived) minutes."""
    lu = lu.copy()
    lu["minutes_basis"] = lu.minutes_played_derived.notna().map({True: "provider_event_derived", False: None})
    end90 = matches.set_index("match_id").pipe(lambda m: _beyond90(m).map({True: 120, False: 90}))
    n = 0
    for i, r in lu[lu.minutes_played_derived.isna() & (lu.provider == "wikipedia") & lu.appeared.fillna(False).astype(bool)].iterrows():
        start = r.minute_on if pd.notna(r.minute_on) else (0 if r.is_starter else None)
        if start is None:
            continue
        end = r.minute_off if pd.notna(r.minute_off) else None
        if end is None:
            try:
                reds = [c["minute"] for c in json.loads(r.cards or "[]") if c.get("card") in ("Red Card", "Second Yellow") and c.get("minute") is not None]
            except Exception:
                reds = []
            end = min(reds) if reds else end90.get(r.match_id, 90)
        if end >= start:
            lu.at[i, "minutes_played_derived"] = float(end - start)
            lu.at[i, "minutes_basis"] = "wikipedia_sub_card_minutes_nominal_end"
            n += 1
    return lu, dict(minutes_derived_rows=n)


def link_scorers(ev: pd.DataFrame, matches: pd.DataFrame, squads: pd.DataFrame, lineups: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Give goal events that only carry a scorer NAME a player_id when exactly one player fits: name tokens must be contained in the
    player's squad name for that edition and team; if several fit, only players in that match's lineup count. Otherwise stays unlinked.
    Provenance: player_id_source = 'squad_name_match'. Editions without squad data (Nations League) stay unlinked by design."""
    ev = ev.copy()
    season = matches.set_index("match_id").season_id
    sq = squads.dropna(subset=["player_id"]).copy()
    sq["tk"] = sq.player_name_raw.map(_tok)
    by = {k: g for k, g in sq.groupby(["season_id", "team_id"])}
    lu = lineups.dropna(subset=["player_id"])
    lu_by = {k: set(g.player_id) for k, g in lu.groupby(["match_id", "team_id"])}
    lu_names = {k: [_tok(n) for n in g.player_name_raw.dropna()] for k, g in lineups.groupby(["match_id", "team_id"])}
    goal = ev.event_type.isin(["goal", "shot", "free_kick"]) & ((ev.is_goal == True) | (ev.event_type == "goal"))
    todo = ev[goal & ev.player_id.isna() & ev.player_name_raw.notna() & ev.team_id.notna()]
    linked = ambiguous = nosquad = 0
    for i, r in todo.iterrows():
        cand = by.get((season.get(r.match_id), r.team_id))
        if cand is None:
            nosquad += 1
            continue
        want = _tok(r.player_name_raw)
        if not want:
            continue
        hit = cand[[want <= k for k in cand.tk]].player_id.unique()
        if len(hit) > 1:
            names = lu_names.get((r.match_id, r.team_id), [])
            inm = lu_by.get((r.match_id, r.team_id), set())
            hit2 = cand[[want <= k and (pid in inm or any(n and (n <= k or k <= n) for n in names)) for k, pid in zip(cand.tk, cand.player_id)]].player_id.unique()
            hit = hit2 if len(hit2) == 1 else hit
        if len(hit) == 1:
            ev.at[i, "player_id"] = hit[0]
            ev.at[i, "player_id_source"] = "squad_name_match"
            linked += 1
        elif len(hit) > 1:
            ambiguous += 1
    return ev, dict(goal_events_considered=len(todo), linked=linked, ambiguous=ambiguous, no_squad_for_edition=nosquad)


def attach_shootouts(m: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """martj42 shootouts.csv gives the WINNER of each shoot-out (no kick scores). Attach it as home/away side; never overwrites the pen scores."""
    so = pd.read_csv(DATA / "raw" / "martj42" / "shootouts.csv")
    so["date"] = pd.to_datetime(so.date)
    idx = {}
    for r in m.itertuples():
        idx.setdefault(frozenset((cn(r.home_team_raw), cn(r.away_team_raw))), []).append(r)
    m = m.copy()
    m["shootout_winner_side"] = None
    m["shootout_winner_source"] = None
    attached = conflict = 0
    for r in so.itertuples():
        c = [x for x in idx.get(frozenset((cn(r.home_team), cn(r.away_team))), []) if abs((x.match_date - r.date).days) <= 1 and x.is_played]
        if len(c) != 1:
            continue
        x = c[0]
        side = "home" if cn(r.winner) == cn(x.home_team_raw) else ("away" if cn(r.winner) == cn(x.away_team_raw) else None)
        if side is None:
            continue
        i = m.index[m.match_id == x.match_id][0]
        if pd.notna(x.home_pen) and pd.notna(x.away_pen) and x.home_pen != x.away_pen and (("home" if x.home_pen > x.away_pen else "away") != side):
            conflict += 1                                            # pen scores win; conflict is reported
            continue
        m.at[i, "shootout_winner_side"], m.at[i, "shootout_winner_source"] = side, "martj42_shootouts"
        attached += 1
    return m, dict(shootouts_attached=attached, shootout_conflicts_with_pen_scores=conflict)


def build() -> dict:
    snap = latest_snapshot()
    SILVER.mkdir(parents=True, exist_ok=True)
    rd = lambda n: pd.read_parquet(snap / n)
    matches = silver_matches(rd("matches.parquet"), rd("venues.parquet"))
    matches, shoot_stats = attach_shootouts(matches)
    cp, xref, canon = player_resolution(rd("players_all.parquet"), rd("lineups_all.parquet"))
    remap = lambda s: s.map(canon).fillna(s)
    ev = rd("events_all.parquet")
    ev["player_id_original"] = ev.player_id
    ev["player_id"] = remap(ev.player_id)
    ev["related_player_id"] = remap(ev.related_player_id)
    ev, assist_stats = attach_assists(ev, matches, cp)
    lu = rd("lineups_all.parquet")
    lu["player_id_original"] = lu.player_id
    lu["player_id"] = remap(lu.player_id)
    ps = rd("player_match_stats_all.parquet")
    ps["player_id_original"] = ps.player_id
    ps["player_id"] = remap(ps.player_id)
    sq = rd("squads.parquet")
    sq["player_id_original"] = sq.player_id
    sq["player_id"] = remap(sq.player_id)
    aw = rd("awards.parquet")
    aw["player_id_original"] = aw.player_id
    aw["player_id"] = remap(aw.player_id)
    lu, lineup_link_stats = link_lineups(lu, matches, sq)
    lu, minutes_stats = derive_minutes(lu, matches)
    ev, scorer_stats = link_scorers(ev, matches, sq, lu)
    out = dict(awards=aw, matches=matches, players=cp, player_xref=xref, events=ev, lineups=lu, player_match_stats=ps, squads=sq,
               teams=rd("teams.parquet"), venues=rd("venues.parquet"), team_match_stats=rd("team_match_stats_all.parquet"))
    for k, v in out.items():
        v.to_parquet(SILVER / f"{k}.parquet", index=False)
    rep = dict(
        matches=len(matches), scheduled_kept=int((~matches.is_played).sum()), scheduled_seasons=sorted(matches[~matches.is_played].season_id.unique()),
        players_bronze=len(rd("players_all.parquet")), players_silver=len(cp), player_ids_merged=int((xref.player_id_original != xref.canonical_player_id).sum()),
        merge_groups=int((xref.resolution_rule == "canonical").sum()), merged_by_rule=xref[xref.player_id_original != xref.canonical_player_id].resolution_rule.value_counts().to_dict(), assists=assist_stats,
        events=len(ev), lineups=len(lu), squads=len(sq), awards=len(aw), shootouts=shoot_stats, scorer_links=scorer_stats, lineup_links=lineup_link_stats, minutes=minutes_stats,
        ucl_rows=int(matches.competition_id.str.contains("UCL|CL", regex=True).sum()))
    (SILVER / "silver_report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return rep


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=str))
