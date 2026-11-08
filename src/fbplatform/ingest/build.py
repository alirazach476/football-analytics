"""Build the canonical matches table (Phase 4) from every verified source.

Primary source per season is chosen by the coverage audit (OpenFootball JSON > OpenFootball TXT >
StatsBomb). StatsBomb is attached as a second provider on matches it also covers, and used as the
primary only where nothing else exists (single Champions League finals). Conflicts between
providers are reported, never silently resolved.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher

import pandas as pd

from ..config import DATA, RAW
from ..http import HttpClient
from ..registry import build_registry
from ..sources import openfootball as of
from ..sources import statsbomb as sbsrc
from .parse_txt import normalize_stage, parse_file

log = logging.getLogger("fbplatform.ingest")
PROC = DATA / "processed"

ALIASES = {"united states": "usa", "korea republic": "south korea", "republic of korea": "south korea",
           "ir iran": "iran", "czechia": "czech republic", "turkiye": "turkey", "turkey": "turkey",
           "cote divoire": "ivory coast", "cote d ivoire": "ivory coast", "bosnia and herzegovina": "bosnia herzegovina",
           "china pr": "china", "dr congo": "congo dr", "netherlands": "netherlands", "holland": "netherlands",
           "ireland": "republic of ireland", "korea dpr": "north korea", "north macedonia": "macedonia"}
KO = {"Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Third place", "Final", "Knockout play-off"}


def norm(name: str | None) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([a-z]{3}\)", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return ALIASES.get(s, s)


def match_id(season_id, d, home, away) -> str:
    return "FBM-" + hashlib.sha1(f"{season_id}|{d}|{norm(home)}|{norm(away)}".encode()).hexdigest()[:12]


def _retrieved(url_prefix_map: dict) -> dict:
    """url -> first real (non-cached) retrieval timestamp from the fetch manifest."""
    out = {}
    for line in open(RAW / "manifest.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["status"] == 200 and not r["cached"] and r["url"] not in out:
            out[r["url"]] = r["retrieved_at"]
    return out


# ---------------------------------------------------------------- OpenFootball JSON
def _pair(v):
    return tuple(v) if isinstance(v, (list, tuple)) and len(v) == 2 else None


def parse_json(text: str, url: str) -> list[dict]:
    rows = []
    for i, m in enumerate(json.loads(text)["matches"]):
        s = m.get("score")
        ft = et = pen = ht = None
        if isinstance(s, dict):
            ft, et, pen, ht = _pair(s.get("ft")), _pair(s.get("et")), _pair(s.get("p")), _pair(s.get("ht"))
        elif isinstance(s, list):
            ft = _pair(s)
        final = et or ft
        t = m.get("time")
        time_local = tz = None
        if t:
            mt = re.match(r"(\d{1,2}:\d{2})(?:\s*UTC([+-]\d{1,2})(?::(\d{2}))?)?", t)
            if mt:
                time_local = mt[1].zfill(5)
                tz = (int(mt[2]) * 60 + int(mt[3] or 0) * (1 if int(mt[2]) >= 0 else -1)) if mt[2] else None
        stage, grp, md, _ = normalize_stage(m["round"])
        if m.get("group") and (stage is None or stage == "Group stage"):
            grp = m["group"].replace("Group ", "")
            stage = stage or "Group stage"
        rows.append(dict(
            home_raw=m["team1"], away_raw=m["team2"], home_cc=None, away_cc=None, venue_raw=m.get("ground"),
            line_no=None, source_url=url, raw_text=json.dumps(m, ensure_ascii=False), stage_raw=m["round"],
            stage=stage, group=grp, matchday=md, leg_header=None, date=date.fromisoformat(m["date"]), date_check="json_iso",
            time_local=time_local, tz_offset_min=tz, time_note=None, score=final, ft=ft, et=et, pen=pen, ht=ht,
            score_basis=(None if final is None else ("aet" if et else ("ft90" if isinstance(s, dict) or isinstance(s, list) else None))),
            went_extra_time=(None if final is None else bool(et or pen)), score_note=None,
            score_raw=json.dumps(s) if s is not None else None))
    return rows


# ---------------------------------------------------------------- StatsBomb
def load_statsbomb(client, registry_ids: set) -> list[dict]:
    comps = json.loads(client.get(f"{sbsrc.RAW}/competitions.json").content)
    rows = []
    for c in comps:
        cid = sbsrc.NAMES.get(c["competition_name"])
        if not cid or c.get("competition_gender", "male") != "male":
            continue
        sid = sbsrc.season_id(cid, c["season_name"])
        if sid not in registry_ids:
            continue
        url = f"{sbsrc.RAW}/matches/{c['competition_id']}/{c['season_id']}.json"
        for m in json.loads(client.get(url).content):
            rows.append(dict(season_id=sid, provider_match_id=str(m["match_id"]), source_url=url, raw=m))
    return rows


def sb_to_row(r):
    m = r["raw"]
    st = (m.get("competition_stage") or {}).get("name")
    stage = {"Group Stage": "Group stage", "Round of 16": "Round of 16", "Quarter-finals": "Quarter-finals",
             "Semi-finals": "Semi-finals", "Final": "Final", "3rd Place Final": "Third place",
             "Round of 32": "Round of 32"}.get(st) or normalize_stage(st or "")[0]
    hs, as_ = m.get("home_score"), m.get("away_score")
    return dict(home_raw=m["home_team"]["home_team_name"], away_raw=m["away_team"]["away_team_name"],
                home_cc=None, away_cc=None, venue_raw=(m.get("stadium") or {}).get("name"), line_no=None,
                source_url=r["source_url"], raw_text=json.dumps(m, ensure_ascii=False), stage_raw=st, stage=stage,
                group=None, matchday=m.get("match_week"), leg_header=None, date=date.fromisoformat(m["match_date"]),
                time_local=(m.get("kick_off") or "")[:5] or None, tz_offset_min=None, time_note=None,
                score=(hs, as_) if hs is not None else None, ft=None, et=None, pen=None, ht=None,
                score_basis=None, went_extra_time=None, score_note="StatsBomb matches.json does not state 90/120/penalty basis",
                score_raw=f"{hs}-{as_}",
                referee_raw=(m.get("referee") or {}).get("name"), stadium_country=(m.get("stadium") or {}).get("country", {}).get("name"))


# ---------------------------------------------------------------- orchestration
def _similar(a, b):
    a, b = norm(a), norm(b)
    return 1.0 if a == b else (0.9 if (a and b and (a in b or b in a)) else SequenceMatcher(None, a, b).ratio())


def _winner(r):
    if r["score"] is None:
        return None
    h, a = r["score"]  # winner of the MATCH (on-pitch score); a shoot-out only decides a level match
    if h != a:         # (a shoot-out after an unlevel second leg decides the TIE, not the match)
        return "home" if h > a else "away"
    if r["pen"]:
        return "home" if r["pen"][0] > r["pen"][1] else "away"
    return "draw"


def _kickoff(r):
    if not r["time_local"] or pd.isna(r["tz_offset_min"]) or pd.isna(r["date"]):
        return None, None
    local = datetime.combine(r["date"], datetime.strptime(r["time_local"], "%H:%M").time())
    return (local - timedelta(minutes=r["tz_offset_min"])).replace(tzinfo=timezone.utc).isoformat(), \
        f"UTC{r['tz_offset_min'] / 60:+g}"


def _derive_legs(df: pd.DataFrame) -> pd.Series:
    leg = df["leg_header"].copy()
    ko = df[df.stage.isin(KO - {"Final", "Third place"}) & df.competition_id.eq("UCL")]
    for (_, _), g in ko.groupby(["season_id", "stage"]):
        pairs = {}
        for idx, r in g.iterrows():
            pairs.setdefault(frozenset((norm(r.home_team_raw), norm(r.away_team_raw))), []).append((r.match_date, idx))
        for lst in pairs.values():
            if len(lst) == 2:
                for n, (_, idx) in enumerate(sorted(lst), 1):
                    leg.loc[idx] = n
    return leg


def run(write: bool = True):
    PROC.mkdir(parents=True, exist_ok=True)
    reg = build_registry()
    rids = set(reg.season_id)
    gh = HttpClient("openfootball", 0.3)
    sbc = HttpClient("statsbomb", 0.05)
    disc = of.discover(gh)
    files = {k: set(v["files"]) for k, v in disc.items()}
    retrieved = _retrieved({})
    prim, unparsed_all, src_records = [], {}, []

    for _, rg in reg.iterrows():
        cid, sid = rg.competition_id, rg.season_id
        hit = of.locate(cid, sid, files)
        if not hit:
            continue
        repo, path, kind = hit
        url = f"{of.RAW}/{repo}/master/{path}"
        blob_url = f"{of.GH}/{repo}/blob/master/{path}"
        body = gh.get(url).content.decode("utf-8")
        if kind == "json":
            rows, un = parse_json(body, blob_url), []
        else:
            paths = [path]
            if cid == "WC":  # not used: WC always has JSON
                pass
            rows, un = parse_file(body, int(sid.split("-")[1]) if cid != "UCL" else int(sid.split("-")[1]),
                                  blob_url, inherit_time=(cid == "UCL"), split_season=(cid == "UCL"))
        for r in rows:
            r.update(season_id=sid, competition_id=cid, provider="openfootball", provider_match_id=None,
                     retrieved_at=retrieved.get(url))
        prim += rows
        unparsed_all[sid] = un
        log.info("%s: %d matches from %s (%d unparsed candidate lines)", sid, len(rows), path, len(un))

    of_df = pd.DataFrame(prim)
    sb_rows = load_statsbomb(sbc, rids)
    sb_prim = []
    used_sb = set()
    # attach StatsBomb to OpenFootball matches
    link = {}  # of row idx -> sb row
    conflicts = []
    by_season = {}
    for r in sb_rows:
        by_season.setdefault(r["season_id"], []).append(r)
    for idx, r in of_df.iterrows():
        cands = []
        for sbr in by_season.get(r.season_id, []):
            if id(sbr) in used_sb:
                continue
            x = sb_to_row(sbr)
            if abs((x["date"] - r.date).days) > 1:
                continue
            fwd = _similar(r.home_raw, x["home_raw"]) + _similar(r.away_raw, x["away_raw"])
            rev = _similar(r.home_raw, x["away_raw"]) + _similar(r.away_raw, x["home_raw"])
            cands.append((max(fwd, rev), rev > fwd, sbr, x))
        if cands:
            best = max(cands, key=lambda c: c[0])
            if best[0] >= 1.4:
                used_sb.add(id(best[2]))
                link[idx] = best
    # StatsBomb matches with no OpenFootball counterpart
    sb_only = []
    for r in sb_rows:
        if id(r) in used_sb:
            continue
        x = sb_to_row(r)
        x.update(season_id=r["season_id"], competition_id=r["season_id"].split("-")[0], provider="statsbomb",
                 provider_match_id=r["provider_match_id"], retrieved_at=retrieved.get(r["source_url"]))
        sb_only.append(x)

    all_rows = prim + sb_only
    df = pd.DataFrame(all_rows)
    df["provider_ids"] = [{} for _ in range(len(df))]
    for i in range(len(df)):
        if df.at[i, "provider_match_id"]:
            df.at[i, "provider_ids"] = {df.at[i, "provider"]: df.at[i, "provider_match_id"]}
    for idx, (score, swapped, sbr, x) in link.items():
        df.at[idx, "provider_ids"] = {"statsbomb": sbr["provider_match_id"]}
        df.at[idx, "referee_raw"] = x["referee_raw"]
        df.at[idx, "stadium_country"] = x["stadium_country"]
        a, b = df.at[idx, "score"], x["score"]
        if a is not None and b is not None:
            b_cmp = (b[1], b[0]) if swapped else b
            if tuple(a) != tuple(b_cmp):
                conflicts.append(dict(season_id=sbr["season_id"], date=str(df.at[idx, "date"]),
                                      match=f"{df.at[idx,'home_raw']} v {df.at[idx,'away_raw']}",
                                      openfootball=tuple(a), statsbomb=tuple(b_cmp)))
        src_records.append(dict(provider="statsbomb", provider_match_id=sbr["provider_match_id"],
                                season_id=sbr["season_id"], source_url=sbr["source_url"],
                                retrieved_at=retrieved.get(sbr["source_url"]), raw=x["raw_text"], matched_row=idx))
    for i, r in df.iterrows():
        if r.provider == "statsbomb":
            src_records.append(dict(provider="statsbomb", provider_match_id=r.provider_match_id,
                                    season_id=r.season_id, source_url=r.source_url, retrieved_at=r.retrieved_at,
                                    raw=r.raw_text, matched_row=i))
        else:
            src_records.append(dict(provider="openfootball", provider_match_id=None, season_id=r.season_id,
                                    source_url=r.source_url, retrieved_at=r.retrieved_at, raw=r.raw_text, matched_row=i))

    # canonical columns
    out = pd.DataFrame({
        "match_id": [match_id(r.season_id, r.date, r.home_raw, r.away_raw) for r in df.itertuples()],
        "competition_id": df.competition_id, "season_id": df.season_id, "stage": df.stage, "stage_raw": df.stage_raw,
        "group": df.group, "matchday": df.matchday, "leg_header": df.leg_header,
        "home_team_raw": df.home_raw, "away_team_raw": df.away_raw,
        "home_team_country_code": df.home_cc, "away_team_country_code": df.away_cc,
        "match_date": df.date, "kickoff_time_local": df.time_local, "tz_offset_minutes": df.tz_offset_min,
        "time_note": df.time_note,
        "venue_raw": df.venue_raw, "referee_raw": df.get("referee_raw"), "attendance": None,
        "home_score": [r[0] if r is not None else None for r in df.score],
        "away_score": [r[1] if r is not None else None for r in df.score],
        "score_basis": df.score_basis,
        "home_score_ft90": [r[0] if r is not None else None for r in df.ft],
        "away_score_ft90": [r[1] if r is not None else None for r in df.ft],
        "home_score_ht": [r[0] if r is not None else None for r in df.ht],
        "away_score_ht": [r[1] if r is not None else None for r in df.ht],
        "home_score_et": [r[0] if r is not None else None for r in df.et],
        "away_score_et": [r[1] if r is not None else None for r in df.et],
        "home_pen": [r[0] if r is not None else None for r in df.pen],
        "away_pen": [r[1] if r is not None else None for r in df.pen],
        "went_extra_time": df.went_extra_time, "date_check": df.date_check, "score_note": df.score_note, "score_raw": df.score_raw,
        "match_duration_minutes": None,
        "primary_provider": df.provider, "provider_match_ids": df.provider_ids.map(json.dumps),
        "source_url": df.source_url, "source_line": df.line_no, "retrieval_timestamp": df.retrieved_at,
    })
    out["match_status"] = ["completed" if pd.notna(h) else "scheduled" for h in out.home_score]
    out["winner"] = [_winner(r) for r in df.to_dict("records")]
    for c in ("home_score", "away_score", "home_score_ft90", "away_score_ft90", "home_score_ht", "away_score_ht",
              "home_score_et", "away_score_et", "home_pen", "away_pen", "matchday", "leg_header", "source_line"):
        out[c] = out[c].astype("Int64")
    out = out.rename(columns={"leg_header": "leg"})
    # derive legs (Champions League two-legged ties)
    d2 = out.copy()
    d2["leg_header"] = d2["leg"].astype("float")
    d2["match_date"] = pd.to_datetime(d2["match_date"])
    out["leg"] = _derive_legs(d2).astype("Int64")
    out["leg_source"] = ["header" if pd.notna(a) else None for a in d2["leg_header"]]
    out.loc[out.leg.notna() & out.leg_source.isna(), "leg_source"] = "derived_from_pairing"
    ks = _kickoff_cols(df)
    out["kickoff_utc"], out["timezone"] = ks
    out = out.sort_values(["competition_id", "season_id", "match_date", "kickoff_time_local", "match_id"]).reset_index(drop=True)
    sr = pd.DataFrame(src_records)
    sr["match_id"] = [out_idmap(df, out, i) for i in sr.matched_row]
    sr = sr.drop(columns="matched_row")
    if write:
        out.to_parquet(PROC / "matches.parquet", index=False)
        out.to_csv(PROC / "matches.csv", index=False)
        sr.to_parquet(PROC / "source_records.parquet", index=False)
        pd.DataFrame(conflicts, columns=["season_id", "date", "match", "openfootball", "statsbomb"]).to_csv(PROC / "cross_source_conflicts.csv", index=False)
        pd.Series({k: v for k, v in unparsed_all.items() if v}).to_json(PROC / "unparsed_lines.json", indent=1)
    return out, sr, conflicts, unparsed_all


def _kickoff_cols(df):
    ko, tz = [], []
    for r in df.to_dict("records"):
        a, b = _kickoff(r)
        ko.append(a)
        tz.append(b)
    return ko, tz


def out_idmap(df, out, i):
    r = df.iloc[i]
    return match_id(r.season_id, r.date, r.home_raw, r.away_raw)


if __name__ == "__main__":
    (DATA / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(DATA / "logs" / "pipeline.log", encoding="utf-8")])
    o, s, c, u = run()
    print(len(o), "matches;", len(s), "source records;", len(c), "cross-source conflicts")
