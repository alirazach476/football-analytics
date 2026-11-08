"""Load the Silver layer into the PostgreSQL warehouse (schema `wh`). Idempotent: the schema is dropped and rebuilt from Silver.

Connection comes from environment variables (defaults match docker-compose.yml): WH_HOST, WH_PORT, WH_USER, WH_PASSWORD, WH_DB.
Surrogate keys are deterministic (sorted natural key -> 1..n), so reloads give identical keys.
"""
from __future__ import annotations

import io
import json
import os
import re

import numpy as np
import pandas as pd
import psycopg

from ..config import DATA, ROOT
from ..medallion.silver import COMP_NAMES

SILVER = DATA / "silver"
SCHEMA_SQL = ROOT / "sql" / "warehouse_schema.sql"
STAGE_ORDER = ["Group stage", "Play-off", "Promotion/relegation play-off", "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals",
               "Third place", "Final"]


def dsn() -> str:
    """Local Docker warehouse by default; a hosted Postgres (e.g. Neon) via DATABASE_URL, or via WH_* plus WH_SSLMODE=require."""
    g = os.environ.get
    if g("DATABASE_URL"):
        return g("DATABASE_URL")
    ssl = f" sslmode={g('WH_SSLMODE')}" if g("WH_SSLMODE") else ""
    return (f"host={g('WH_HOST', 'localhost')} port={g('WH_PORT', '5442')} user={g('WH_USER', 'football')} "
            f"password={g('WH_PASSWORD', 'football_local_dev')} dbname={g('WH_DB', 'football_dw')}{ssl}")


def _keys(values, name):
    u = sorted(pd.unique(pd.Series(values).dropna()))
    return pd.Series(range(1, len(u) + 1), index=u, name=name)


def _copy(cur, table: str, df: pd.DataFrame) -> int:
    df = df.copy()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='wh' AND table_name=%s", (table,))
    types = dict(cur.fetchall())
    for c in df.columns:
        if types[c] in ("integer", "bigint", "smallint"):
            df[c] = pd.to_numeric(df[c], errors="coerce").round().astype("Int64")
        if str(df[c].dtype) in ("Int64", "Int32"):
            df[c] = df[c].astype("object")
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    cols = ",".join(df.columns)
    with cur.copy(f"COPY wh.{table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
        while chunk := buf.read(1 << 20):
            cp.write(chunk)
    return len(df)


def _int(s):
    return pd.to_numeric(s, errors="coerce").round().astype("Int64")


def _bool(s):
    return s.map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA else bool(v)).astype("object")


def build_tables() -> dict[str, pd.DataFrame]:
    rd = lambda n: pd.read_parquet(SILVER / f"{n}.parquet")
    m, teams, players, xref, venues = rd("matches"), rd("teams"), rd("players"), rd("player_xref"), rd("venues")
    reg = pd.read_csv(DATA / "registry" / "competition_seasons.csv")
    T = {}
    # --- competitions / seasons
    ck = _keys(list(COMP_NAMES), "competition_key")
    T["dim_competition"] = pd.DataFrame({"competition_key": ck.values, "competition_id": ck.index, "competition_name": [COMP_NAMES[c] for c in ck.index]})
    sk = _keys(m.season_id, "season_key")
    cnt = m.groupby("season_id").agg(n=("match_id", "size"), played=("is_played", "sum"))
    exp = reg.drop_duplicates("season_id").set_index("season_id").expected_matches
    T["dim_season"] = pd.DataFrame({
        "season_key": sk.values, "season_id": sk.index, "competition_key": [ck[s.split("-")[0]] for s in sk.index],
        "season_year": [int(s.split("-")[1]) for s in sk.index], "expected_matches": _int(pd.Series(sk.index).map(exp)),
        "matches_in_dataset": cnt.n.reindex(sk.index).values, "matches_played": cnt.played.reindex(sk.index).astype(int).values})
    T["dim_season"]["matches_scheduled"] = T["dim_season"].matches_in_dataset - T["dim_season"].matches_played
    # --- teams (+ name history; validity dates unknown -> NULL)
    tk = _keys(teams.team_id, "team_key")
    t = teams.copy()
    T["dim_team"] = pd.DataFrame({"team_key": t.team_id.map(tk), "team_id": t.team_id, "team_name": t.team_name, "team_type": t.team_type,
                                  "country": t.country, "country_code": t.country_code_iso3_source, "confederation": t.confederation,
                                  "is_current": True}).sort_values("team_key")
    rows = [(tk[r.team_id], r.team_name, "current") for r in t.itertuples()]
    for r in t.itertuples():
        for n in json.loads(r.historical_names or "[]"):
            if n != r.team_name:
                rows.append((tk[r.team_id], n, "alias_or_former_name"))
    T["dim_team_name_history"] = pd.DataFrame(rows, columns=["team_key", "name", "name_type"]).drop_duplicates(["team_key", "name"])
    T["dim_team_name_history"]["valid_from"] = None
    T["dim_team_name_history"]["valid_to"] = None
    # --- players
    pk = _keys(players.player_id, "player_key")
    p = players.copy()
    p["date_of_birth"] = pd.to_datetime(p.date_of_birth, errors="coerce").dt.date
    T["dim_player"] = pd.DataFrame({"player_key": p.player_id.map(pk), "player_id": p.player_id, "full_name": p.full_name, "display_name": p.display_name,
                                    "nationality": p.nationality, "date_of_birth": p.date_of_birth, "height_cm": p.height_cm, "preferred_foot": p.preferred_foot,
                                    "primary_position": p.primary_position, "merged_player_ids": p.merged_player_ids, "n_source_ids": p.n_source_ids}).sort_values("player_key")
    T["dim_player_xref"] = pd.DataFrame({"player_id_original": xref.player_id_original, "player_key": xref.canonical_player_id.map(pk),
                                         "resolution_rule": xref.resolution_rule})
    # --- venues
    vk = _keys(venues.venue_id, "venue_key")
    T["dim_venue"] = pd.DataFrame({"venue_key": venues.venue_id.map(vk), "venue_id": venues.venue_id, "venue_name": venues.venue_name, "city": venues.city,
                                   "country": venues.country, "latitude": venues.latitude, "longitude": venues.longitude, "capacity": _int(venues.capacity),
                                   "wikidata_id": venues.wikidata_id}).sort_values("venue_key")
    # --- referees ("Name (Country)")
    ref = m.referee_raw.dropna().str.strip()
    parsed = ref.str.extract(r"^(?P<n>.*?)(?:\s*\((?P<c>[^)]*)\))?$")
    rk_src = pd.DataFrame({"referee_name": parsed.n.str.strip(), "referee_country": parsed.c.fillna("").str.strip()}).drop_duplicates() \
        .sort_values(["referee_name", "referee_country"]).reset_index(drop=True)
    rk_src.insert(0, "referee_key", range(1, len(rk_src) + 1))
    T["dim_referee"] = rk_src
    rmap = {(r.referee_name, r.referee_country): r.referee_key for r in rk_src.itertuples()}
    # --- dates
    d = pd.date_range(m.match_date.min().normalize(), m.match_date.max().normalize())
    T["dim_date"] = pd.DataFrame({"date_key": d.strftime("%Y%m%d").astype(int), "full_date": d.date, "year": d.year, "quarter": d.quarter, "month": d.month,
                                  "month_name": d.strftime("%B"), "day": d.day, "day_of_week": d.dayofweek + 1, "day_name": d.strftime("%A"),
                                  "is_weekend": d.dayofweek >= 5})
    # --- stages
    stages = [s for s in STAGE_ORDER if s in set(m.stage)] + sorted(set(m.stage.dropna()) - set(STAGE_ORDER))
    T["dim_tournament_stage"] = pd.DataFrame({"stage_key": range(1, len(stages) + 1), "stage_name": stages,
                                              "stage_order": range(1, len(stages) + 1), "is_knockout": [s not in ("Group stage",) for s in stages]})
    stk = dict(zip(stages, range(1, len(stages) + 1)))
    # --- fact_matches
    mk = _keys(m.match_id, "match_key")
    fm = pd.DataFrame({"match_key": m.match_id.map(mk), "match_id": m.match_id, "competition_key": m.competition_id.map(ck), "season_key": m.season_id.map(sk),
                       "date_key": m.match_date.dt.strftime("%Y%m%d").astype(int), "stage_key": _int(m.stage.map(stk)), "group_name": m.group,
                       "matchday": m.matchday, "leg": m.leg, "home_team_key": _int(m.home_team_id.map(tk)), "away_team_key": _int(m.away_team_id.map(tk)),
                       "home_team_display": m.home_team_display, "away_team_display": m.away_team_display, "venue_key": _int(m.venue_id.map(vk)),
                       "match_status": m.match_status, "status_label": m.status_label, "fixture_detail": m.fixture_detail,
                       "kickoff_local": m.kickoff_time_local, "kickoff_utc": m.kickoff_utc, "attendance": m.attendance})
    keyed = [rmap.get((a, b)) for a, b in zip(parsed.n.str.strip().reindex(m.index), parsed.c.fillna("").str.strip().reindex(m.index))]
    fm["referee_key"] = _int(pd.Series([k if isinstance(r, str) else None for k, r in zip(keyed, m.referee_raw)], index=m.index))
    for c in ["home_score", "away_score", "score_basis", "home_score_ht", "away_score_ht", "home_score_ft90", "away_score_ft90", "home_score_et",
              "away_score_et", "home_pen", "away_pen", "shootout_winner_side", "went_extra_time", "winner", "score_note", "man_of_the_match_raw", "primary_provider",
              "source_url", "retrieval_timestamp"]:
        fm[c] = m[c]
    T["fact_matches"] = fm.sort_values("match_key")
    # --- team match stats
    ts = rd("team_match_stats")
    f = ts.copy()
    f["match_key"] = f.match_id.map(mk)
    f["team_key"] = f.team_id.map(tk)
    T["fact_team_match_stats"] = f.drop(columns=["match_id", "team_id"])
    # --- player match stats
    ps = rd("player_match_stats")
    f = ps.copy()
    f["match_key"], f["team_key"], f["player_key"] = f.match_id.map(mk), f.team_id.map(tk), f.player_id.map(pk)
    f = f.drop(columns=["match_id", "team_id", "player_id", "player_id_original"])
    f = f[f.player_key.notna() & f.team_key.notna()]
    f = f.groupby(["match_key", "team_key", "player_key"], as_index=False).first()        # one row per player/match (providers merged)
    for c in ["is_starter", "sub_on", "sub_off"]:
        f[c] = _bool(f[c])
    T["fact_player_match_stats"] = f
    # --- appearances
    lu = rd("lineups")
    cards = lu.cards.map(lambda s: json.loads(s) if isinstance(s, str) else (list(s) if s is not None else []))
    a = pd.DataFrame({"match_key": lu.match_id.map(mk), "team_key": _int(lu.team_id.map(tk)), "player_key": _int(lu.player_id.map(pk)),
                      "player_name_raw": lu.player_name_raw, "provider": lu.provider, "jersey_number": _int(lu.jersey_number),
                      "is_starter": _bool(lu.is_starter), "appeared": _bool(lu.appeared), "is_captain": _bool(lu.is_captain),
                      "minute_on": lu.minute_on, "minute_off": lu.minute_off, "minutes_played": lu.minutes_played_derived,
                      "yellow_cards": _int(lu.yellow_cards_source), "red_cards": _int(lu.red_cards_source)})
    a.insert(0, "appearance_key", range(1, len(a) + 1))
    T["fact_player_appearances"] = a
    # --- managers (ingest/managers.py)
    mf = DATA / "processed" / "match_managers.parquet"
    if mf.exists():
        mm = pd.read_parquet(mf)
        mgr = pd.DataFrame({"match_key": mm.match_id.map(mk), "team_key": _int(mm.team_id.map(tk)), "side": mm.side, "manager_name": mm.manager_name, "source": mm.source, "level": mm.level})
        T["fact_match_managers"] = mgr[mgr.match_key.notna() & mgr.team_key.notna()].drop_duplicates(["match_key", "team_key"])
    else:
        T["fact_match_managers"] = pd.DataFrame(columns=["match_key", "team_key", "side", "manager_name", "source", "level"])
    # --- events
    ev = rd("events")
    e = pd.DataFrame({"event_key": range(1, len(ev) + 1), "event_id": ev.event_id, "match_key": ev.match_id.map(mk), "provider": ev.provider,
                      "event_type": ev.event_type, "detail_type": ev.detail_type, "team_key": _int(ev.team_id.map(tk)),
                      "player_key": _int(ev.player_id.map(pk)), "related_player_key": _int(ev.related_player_id.map(pk)),
                      "player_name_raw": ev.player_name_raw, "related_player_name_raw": ev.related_player_name_raw, "assist_name_raw": ev.assist_name_raw, "assist_source": ev.assist_source,
                      "period": _int(ev.period), "minute": ev.minute, "minute_added": ev.minute_added, "second": ev.second,
                      "location_x": ev.location_x, "location_y": ev.location_y, "end_location_x": ev.end_location_x, "end_location_y": ev.end_location_y,
                      "coordinate_system": ev.coordinate_system, "outcome": ev.outcome, "card": ev.card, "xg": ev.xg})
    for c in ["is_goal", "is_penalty", "is_own_goal", "is_assist", "is_key_pass"]:
        e[c] = _bool(ev[c])
    T["fact_match_events"] = e
    # --- standings derived from played group-stage matches (basis recorded)
    g = m[m.is_played & m.stage.eq("Group stage") & m.group.notna() & m.home_team_id.notna()]
    rows = []
    for r in g.itertuples():
        hs, as_ = int(r.home_score_ft90 if pd.notna(r.home_score_ft90) else r.home_score), int(r.away_score_ft90 if pd.notna(r.away_score_ft90) else r.away_score)
        for tid, gf, ga in ((r.home_team_id, hs, as_), (r.away_team_id, as_, hs)):
            rows.append(dict(season_id=r.season_id, group_name=str(r.group), team_id=tid, played=1, wins=int(gf > ga), draws=int(gf == ga),
                             losses=int(gf < ga), goals_for=gf, goals_against=ga))
    st = pd.DataFrame(rows).groupby(["season_id", "group_name", "team_id"], as_index=False).sum()
    st["goal_difference"] = st.goals_for - st.goals_against
    st["points"] = 3 * st.wins + st.draws          # 3-1-0 applied uniformly: historical points rules differ only before 1994
    st = st.sort_values(["season_id", "group_name", "points", "goal_difference", "goals_for"], ascending=[True, True, False, False, False])
    st["group_position"] = st.groupby(["season_id", "group_name"]).cumcount() + 1     # tie-breaks beyond GD/GF (head-to-head, fair play) NOT applied
    st["season_key"], st["team_key"] = st.season_id.map(sk), st.team_id.map(tk)
    st["basis"] = "derived_from_matches(90min,3-1-0; tiebreak=points,GD,GF only)"
    T["fact_tournament_standings"] = st.drop(columns=["season_id", "team_id"])
    aw = rd("awards")
    aw["season_key"] = aw.season_id.map(sk)
    pa = aw[aw.winner_type == "player"].reset_index(drop=True)
    T["fact_player_awards"] = pd.DataFrame({
        "award_key": range(1, len(pa) + 1), "season_key": pa.season_key, "player_key": _int(pa.player_id.map(pk)), "team_key": _int(pa.team_id.map(tk)),
        "award_name": pa.award_name, "award_category": pa.award_category, "position_label": pa.position_label, "rank": _int(pa["rank"]),
        "entity_name_raw": pa.entity_name_raw, "value_text": pa.value_text, "link_status": pa.link_status, "source_page": pa.source_page,
        "source_revid": _int(pa.revid)})
    ta = aw[aw.winner_type == "team"].reset_index(drop=True)
    T["fact_team_awards"] = pd.DataFrame({
        "award_key": range(1, len(ta) + 1), "season_key": ta.season_key, "team_key": _int(ta.team_id.map(tk)), "award_name": ta.award_name,
        "award_category": ta.award_category, "entity_name_raw": ta.entity_name_raw, "source_page": ta.source_page, "source_revid": _int(ta.revid)})
    return T


ORDER = ["dim_competition", "dim_season", "dim_team", "dim_team_name_history", "dim_player", "dim_player_xref", "dim_venue", "dim_referee",
         "dim_date", "dim_tournament_stage", "fact_matches", "fact_team_match_stats", "fact_player_match_stats", "fact_player_appearances",
         "fact_match_events", "fact_match_managers", "fact_tournament_standings", "fact_player_awards", "fact_team_awards"]


def load() -> dict:
    T = build_tables()
    out = {}
    with psycopg.connect(dsn(), autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
            for t in ORDER:
                df = T[t]
                n = _copy(cur, t, df) if len(df) else 0
                cur.execute("INSERT INTO wh.etl_load_log(table_name, rows_loaded, source_rows) VALUES (%s,%s,%s)", (t, n, len(df)))
                out[t] = n
        conn.commit()
    return out


if __name__ == "__main__":
    for k, v in load().items():
        print(f"{k:28s}{v:>10,}")
