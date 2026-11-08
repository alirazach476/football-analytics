"""Managers per match, from every source that records them (no guessing):

1. StatsBomb match files  (home_team.managers / away_team.managers)      -> level 'match'
2. Wikipedia match boxes  (manager row of the line-up tables)            -> level 'match'
3. Wikipedia squad pages  (head coach of the team at that tournament)     -> level 'tournament' (fallback only)

Priority per (match, team): 1 > 2 > 3. The source and level are kept so the UI can say where a name comes from.
Output: data/processed/match_managers.parquet  (match_id, team_id, side, manager_name, source, level)
Run:    PYTHONPATH=src python -m fbplatform.ingest.managers
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from ..config import ROOT

PROC = ROOT / "data" / "processed"
RAW_SB = ROOT / "data" / "raw" / "statsbomb"
PRIORITY = {"statsbomb_match": 0, "wikipedia_match": 1, "wikipedia_squad_head_coach": 2}


def clean_name(raw) -> str | None:
    """Wikipedia table rows leave markup behind ('|colspan=3| Name', '[[Link|Name]]', footnotes)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw)
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>|<[^>]+>", "", s)
    s = re.sub(r"^\s*(\|?\s*(colspan|rowspan|style|align)\s*=\s*\"?[^|]*\"?\s*\|)+", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\{\{[^}]*\}\}|''+|\(.*?\)|\[\d+\]", "", s)
    s = s.strip(" |*-–: \t")
    s = re.sub(r"\s+", " ", s)
    return s if len(s) > 2 and re.search(r"[A-Za-zÀ-ÿ]", s) else None


def statsbomb_managers(matches: pd.DataFrame, source_records: pd.DataFrame) -> pd.DataFrame:
    link = source_records[source_records.provider == "statsbomb"].drop_duplicates("provider_match_id").set_index("provider_match_id").match_id.to_dict()
    side_team = matches.set_index("match_id")[["home_team_id", "away_team_id"]].to_dict("index")
    rows = []
    for f in RAW_SB.glob("*"):
        try:
            txt = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if '"managers"' not in txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for m in data:
            mid = link.get(str(m.get("match_id"))) or link.get(m.get("match_id"))
            if mid is None or mid not in side_team:
                continue
            for side in ("home", "away"):
                for mg in (m.get(f"{side}_team") or {}).get("managers") or []:
                    name = mg.get("nickname") and mg.get("name") or mg.get("name")
                    rows.append(dict(match_id=mid, team_id=side_team[mid][f"{side}_team_id"], side=side, manager_name=name, source="statsbomb_match", level="match"))
    return pd.DataFrame(rows)


def build() -> pd.DataFrame:
    matches = pd.read_parquet(PROC / "matches.parquet", columns=["match_id", "season_id", "home_team_id", "away_team_id"])
    sr = pd.read_parquet(PROC / "source_records.parquet")
    parts = [statsbomb_managers(matches, sr)]
    w = pd.read_parquet(PROC / "wikipedia" / "managers_wikipedia.parquet")
    w = w.assign(manager_name=w.manager_raw.map(clean_name)).dropna(subset=["manager_name"]).merge(matches, on="match_id")
    w["side"] = (w.team_id == w.home_team_id).map({True: "home", False: "away"})
    parts.append(w.assign(source="wikipedia_match", level="match")[["match_id", "team_id", "side", "manager_name", "source", "level"]])
    hc = pd.read_parquet(PROC / "squads" / "head_coaches.parquet").assign(manager_name=lambda d: d.head_coach_raw.map(clean_name)).dropna(subset=["manager_name"])
    long = pd.concat([matches.assign(team_id=matches.home_team_id, side="home"), matches.assign(team_id=matches.away_team_id, side="away")])
    f = long.merge(hc[["season_id", "team_id", "manager_name"]].drop_duplicates(["season_id", "team_id"]), on=["season_id", "team_id"])
    parts.append(f.assign(source="wikipedia_squad_head_coach", level="tournament")[["match_id", "team_id", "side", "manager_name", "source", "level"]])
    allm = pd.concat([p for p in parts if len(p)], ignore_index=True).dropna(subset=["team_id"])
    allm["rank"] = allm.source.map(PRIORITY)
    best = allm.sort_values("rank").drop_duplicates(["match_id", "team_id"], keep="first")        # best source per team and match
    return best.drop(columns="rank").sort_values(["match_id", "side"]).reset_index(drop=True)


def load_into_warehouse() -> int:
    """Create/refresh wh.fact_match_managers in the running warehouse without reloading everything else."""
    import psycopg

    from ..warehouse.load import dsn

    df = pd.read_parquet(PROC / "match_managers.parquet")
    with psycopg.connect(dsn()) as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS wh.fact_match_managers (match_key int NOT NULL REFERENCES wh.fact_matches, team_key int NOT NULL REFERENCES wh.dim_team, side text,
                       manager_name text NOT NULL, source text NOT NULL, level text NOT NULL, PRIMARY KEY (match_key, team_key))""")
        cur.execute("TRUNCATE wh.fact_match_managers")
        cur.execute("select match_id, match_key from wh.fact_matches")
        mk = dict(cur.fetchall())
        cur.execute("select team_id, team_key from wh.dim_team")
        tk = dict(cur.fetchall())
        rows = [(mk[r.match_id], tk[r.team_id], r.side, r.manager_name, r.source, r.level) for r in df.itertuples() if r.match_id in mk and r.team_id in tk]
        cur.executemany("INSERT INTO wh.fact_match_managers VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows)
        conn.commit()
    return len(rows)


def main():
    df = build()
    df.to_parquet(PROC / "match_managers.parquet", index=False)
    m = pd.read_parquet(PROC / "matches.parquet", columns=["match_id", "match_status"])
    played = set(m[m.match_status == "completed"].match_id)
    cover = df[df.match_id.isin(played)].groupby("match_id").size()
    print(f"manager rows: {len(df):,} | by source: {df.source.value_counts().to_dict()}")
    print(f"played matches with both managers: {(cover == 2).sum():,} of {len(played):,}; with one: {(cover == 1).sum():,}; none: {len(played) - len(cover):,}")


if __name__ == "__main__":
    main()
    print("loaded into warehouse:", load_into_warehouse())
