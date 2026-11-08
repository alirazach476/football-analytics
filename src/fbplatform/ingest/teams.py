"""Phase 5a: canonical team registry + entity resolution.

Matching rules (applied in this order, documented in docs/entity_resolution.md):
  R0  placeholder names ("A1", "Winner Group A", "3rd Group A/B/C", "Winner Match 37") never
      become teams; the match keeps a null team id.
  R1  curated alias table (CLUB_ALIASES / NATIONAL_ALIASES below) - explicit human decisions.
  R2  exact equality after normalisation (case, accents, punctuation, country-code suffix).
  R3  equality after stripping generic legal/club-form tokens (fc, cf, ac, afc, sc, ...), ONLY when
      the country code agrees. Never fuzzy: two different clubs with similar names
      (Sporting CP vs Sporting Braga) must not merge.
  R4  a club name with no country code (StatsBomb-only) joins an existing club iff the stripped names
      are equal AND exactly one such club exists; otherwise it stays separate.
Everything that is similar but NOT merged is written to entity_resolution_review.csv.
Teams are identified by canonical name (clubs: T-CLU-<slug>; national: T-NAT-<slug>); the club country
is the code most often written by the source (conflicting codes are kept in `country_codes_seen`).
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

import pandas as pd

from .build import PROC, norm

PLACEHOLDER = re.compile(r"^([A-L][1-4]|[WL]\d+|(winner|loser|runner-up|3rd)\b.*)$", re.I)
GENERIC = {"fc", "cf", "ac", "afc", "sc", "fk", "sk", "as", "ss", "ssc", "rc", "cd", "ud", "sv", "vfb", "vfl",
           "bsc", "bc", "ks", "pfc", "asc", "fcsb", "club", "de", "futbol", "fotbal", "calcio", "1909", "1893", "04", "05", "96", "29"}

# canonical name -> variants (normalised later). Each pair below is a documented identity decision.
CLUB_ALIASES = {
    "Atlético Madrid": ["Club Atlético de Madrid", "Atletico Madrid"],
    "Inter Milan": ["Inter", "FC Internazionale Milano", "Internazionale"],
    "Lazio": ["Lazio Roma", "SS Lazio"],
    "Olympique de Marseille": ["Olympique Marseille", "Marseille"],
    "Sporting CP": ["Sporting Clube de Portugal"],
    "Sporting Braga": ["Sporting Clube de Braga", "SC Braga", "S.C. Braga"],
    "Benfica": ["SL Benfica", "Sport Lisboa e Benfica"],
    "Bayern Munich": ["Bayern München", "FC Bayern München"],
    "Bayer Leverkusen": ["Bayer 04 Leverkusen"],
    "Borussia Mönchengladbach": ["Bor. Mönchengladbach"],
    "Real Sociedad": ["Real Sociedad de Fútbol"],
    "Napoli": ["SSC Napoli"],
    "Stade Rennais": ["Stade Rennais FC"],
    "Hoffenheim": ["1899 Hoffenheim", "TSG 1899 Hoffenheim"],
    "Dinamo Zagreb": ["GNK Dinamo Zagreb"],
    "Red Star Belgrade": ["FK Crvena Zvezda", "Crvena Zvezda"],
    "Shakhtar Donetsk": ["FK Shakhtar Donetsk"],
    "AS Monaco": ["AS Monaco FC"],  # source writes the country code as FRA in some seasons and MCO in others
    "Feyenoord": ["Feyenoord Rotterdam"],
    "CSKA Moscow": ["CSKA Moskva", "PFC CSKA Moscow", "PFC CSKA Moskva"],
    # --- Wikipedia vs OpenFootball spelling variants of the SAME club (each reviewed by hand) ---
    "Olympiacos": ["Olympiacos F.C.", "Olympiakos Piraeus", "Olympiacos Piraeus", "PAE Olympiakos SFP"],
    "Zenit Saint Petersburg": ["FC Zenit Saint Petersburg", "Zenit St. Petersburg", "Zenit St Petersburg"],
    "Dynamo Kyiv": ["FC Dynamo Kyiv", "Dynamo Kiev", "Dinamo Kiev"],
    "Copenhagen": ["F.C. Copenhagen", "FC Copenhagen", "FC København"],
    "Red Bull Salzburg": ["FC Red Bull Salzburg", "RB Salzburg", "FC Salzburg"],
    "APOEL": ["APOEL FC", "APOEL Nikosia", "APOEL Nicosia"],
    "Olympique Lyonnais": ["Lyon", "Olympique Lyon"],
    "Anderlecht": ["R.S.C. Anderlecht", "RSC Anderlecht"],
    "Lokomotiv Moscow": ["FC Lokomotiv Moscow", "Lokomotiv Moskva"],
    "Club Brugge": ["Club Brugge KV"],
    "PSV Eindhoven": ["PSV"],
    "Spartak Moscow": ["FC Spartak Moscow", "Spartak Moskva"],
    "Athletic Bilbao": ["Athletic Club"],
    "Slavia Prague": ["SK Slavia Prague", "Slavia Praha", "SK Slavia Praha"],
    "FCSB": ["FC Steaua Bucureşti", "Steaua București", "Steaua Bucharest"],   # same continuous club (renamed 2017)
    "Lille": ["Lille OSC"],
    "Gent": ["KAA Gent"],
    "Legia Warsaw": ["Legia Warszawa"],
    "AEK Athens": ["AEK Athens F.C.", "AEK Athen"],   # "AEK Athen" is an OpenFootball typo
    "Sheriff Tiraspol": ["FC Sheriff Tiraspol", "FC Sheriff"],
    "Brest": ["Stade Brestois 29"],
    "Pafos": ["Pafos FC", "Paphos FC"],
    "Kairat": ["FC Kairat", "FK Kairat", "Kairat Almaty"],
    "Fiorentina": ["ACF Fiorentina"],
    "AC Sparta Praha": ["AC Sparta Prague"],
    "Bordeaux": ["FC Girondins de Bordeaux", "Girondins de Bordeaux"],
    "Lens": ["RC Lens", "Racing Club de Lens"],
    "Qarabağ": ["Qarabag FK", "Qarabag Agdam FK", "Qarabağ FK", "Qarabağ Agdam FK"],
}
NATIONAL_ALIASES = {
    "United States": ["USA", "United States of America"],
    "Ivory Coast": ["Côte d'Ivoire", "Cote d'Ivoire"],
    "Bosnia and Herzegovina": ["Bosnia & Herzegovina", "Bosnia-Herzegovina", "Bosnia Herzegovina"],
    "Czech Republic": ["Czechia"],
    "DR Congo": ["Congo DR"],
    "South Korea": ["Korea Republic"],
    "North Korea": ["Korea DPR"],
    "China": ["China PR"],
    "Iran": ["IR Iran"],
    "Turkey": ["Türkiye", "Turkiye"],
    "Yugoslavia": ["FR Yugoslavia", "Federal Republic of Yugoslavia"],   # Euro 2000; distinct from Serbia and Montenegro (2003-06)
    "Republic of Ireland": ["Ireland"],  # "Ireland" in these competitions is the FAI team; Northern Ireland is separate
}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")


def _stripped(name):
    toks = [t for t in norm(name).split() if t not in GENERIC]
    # single letters are club initials ('F.C.' -> 'f c'); drop them unless the name is nothing else
    return " ".join(t for t in toks if len(t) > 1 or len(toks) == 1)


def _alias_map(table):
    out = {}
    for canon, vs in table.items():
        out[norm(canon)] = canon
        for v in vs:
            out[norm(v)] = canon
    return out


def build_teams(matches: pd.DataFrame, statsbomb_ids: dict):
    """Returns (teams, aliases, review, matches_with_ids)."""
    club_al, nat_al = _alias_map(CLUB_ALIASES), _alias_map(NATIONAL_ALIASES)
    obs = []  # (competition, season, raw name, cc, side)
    for side in ("home", "away"):
        obs.append(pd.DataFrame({"comp": matches.competition_id, "season": matches.season_id,
                                 "raw": matches[f"{side}_team_raw"], "cc": matches[f"{side}_team_country_code"]}))
    obs = pd.concat(obs, ignore_index=True)
    obs["is_club"] = obs.comp == "UCL"
    obs["placeholder"] = obs.raw.map(lambda s: bool(PLACEHOLDER.match(s.strip())))

    # country code for a club: from any row where the source wrote it, by normalised name
    cc_by_norm = (obs[obs.cc.notna()].assign(n=lambda d: d.raw.map(norm)).groupby("n").cc.agg(lambda s: s.mode().iat[0]))
    # canonical club cc via alias too
    resolved = {}  # (is_club, normalised raw, cc) -> (team_id, canonical, rule)
    teams = {}
    rule_hits = []

    def ensure(is_club, canon, cc):
        tid = f"T-CLU-{_slug(canon)}" if is_club else f"T-NAT-{_slug(canon)}"
        teams.setdefault(tid, dict(team_id=tid, team_name=canon, team_type="club" if is_club else "national",
                                   classification="club" if is_club else "national team",
                                   country=(cc if is_club else canon), country_code_iso3_source=cc if is_club else None))
        return tid

    # R1/R2 pass
    stripped_index = {}  # (cc, stripped) -> team_id for R3
    rows = obs[~obs.placeholder].drop_duplicates(["is_club", "raw", "cc"])
    # curated aliases first (so their canonical club exists before R2/R3 look for it), then coded names, then the rest
    rows = rows.assign(_nocc=rows.cc.isna(), _noalias=~rows.raw.map(lambda s: norm(s) in club_al or norm(s) in nat_al))
    rows = rows.sort_values(["is_club", "_noalias", "_nocc", "raw"])
    for r in rows.itertuples():
        n = norm(r.raw)
        cc = r.cc if isinstance(r.cc, str) else cc_by_norm.get(n)
        if r.is_club:
            canon = club_al.get(n)
            rule = "R1_alias" if canon else None
            if not canon:
                canon, rule = r.raw, "R2_exact"
            key = (cc, _stripped(canon))
            if rule == "R2_exact" and cc and key in stripped_index:
                tid, rule = stripped_index[key], "R3_stripped_same_country"
            elif rule == "R2_exact" and cc is None:
                same = {t for (c2, st), t in stripped_index.items() if st == key[1]}
                if len(same) == 1:
                    tid, rule = same.pop(), "R4_no_code_unique_stripped_match"
                else:
                    tid = ensure(True, canon, None)
            else:
                tid = ensure(True, canon, cc)
            stripped_index.setdefault(key, tid)
        else:
            canon = nat_al.get(n)
            rule = "R1_alias" if canon else None
            if not canon:
                canon, rule = r.raw, "R2_exact"
            tid = ensure(False, canon, None)
        resolved[(bool(r.is_club), r.raw, r.cc if isinstance(r.cc, str) else None)] = (tid, rule)
        rule_hits.append((r.raw, tid, rule))

    # alias table with seasons seen
    al = []
    for (is_club, raw, cc), (tid, rule) in resolved.items():
        seasons = sorted(obs[(obs.raw == raw) & (obs.is_club == is_club)].season.unique())
        al.append(dict(alias=raw, team_id=tid, rule=rule, seasons_seen=";".join(seasons)))
    aliases = pd.DataFrame(al, columns=["alias", "team_id", "rule", "seasons_seen"]).sort_values(["team_id", "alias"]).reset_index(drop=True)
    hist = aliases.groupby("team_id").alias.agg(lambda s: sorted(set(s)))
    ccs = {}
    for (is_club, raw, cc), (tid_, rule) in resolved.items():
        if is_club:
            n_obs = int(((obs.raw == raw) & obs.cc.notna() & (obs.cc == cc)).sum()) if isinstance(cc, str) else 0
            if isinstance(cc, str):
                ccs.setdefault(tid_, {}).update({cc: ccs.get(tid_, {}).get(cc, 0) + n_obs})
    for tid_, d in ccs.items():
        teams[tid_]["country"] = max(d, key=d.get)
        teams[tid_]["country_code_iso3_source"] = max(d, key=d.get)
        teams[tid_]["country_codes_seen"] = ";".join(sorted(d))
    teams_df = pd.DataFrame(list(teams.values()), columns=["team_id", "team_name", "team_type", "classification", "country",
                                                           "country_code_iso3_source", "country_codes_seen"])
    teams_df["historical_names"] = teams_df.team_id.map(lambda t: json.dumps([a for a in hist.get(t, []) if a != teams[t]["team_name"]], ensure_ascii=False))
    teams_df["confederation"] = None      # not verified for any team yet
    teams_df["logo_ref"] = None           # no licensed crest/flag source selected yet
    teams_df["source_identifiers"] = teams_df.team_id.map(lambda t: json.dumps(statsbomb_ids.get(t, {})))

    # review: same-type teams that look alike but were NOT merged
    review = []
    tl = teams_df.to_dict("records")
    for i, a in enumerate(tl):
        for b in tl[i + 1:]:
            if a["team_type"] != b["team_type"]:
                continue
            ra = SequenceMatcher(None, norm(a["team_name"]), norm(b["team_name"])).ratio()
            if ra >= 0.75 or _stripped(a["team_name"]) in _stripped(b["team_name"]) and len(_stripped(a["team_name"])) > 3:
                review.append(dict(team_a=a["team_id"], team_b=b["team_id"], similarity=round(ra, 2),
                                   decision="NOT merged (distinct unless an alias is added)"))
    review = pd.DataFrame(review)

    # attach ids to matches
    def tid(is_club_series, raw_series, cc_series):
        out = []
        for ic, raw, cc in zip(is_club_series, raw_series, cc_series):
            out.append(resolved.get((bool(ic), raw, cc if isinstance(cc, str) else None), (None, None))[0])
        return out

    ic = matches.competition_id == "UCL"
    m = matches.copy()
    m["home_team_id"] = tid(ic, m.home_team_raw, m.home_team_country_code)
    m["away_team_id"] = tid(ic, m.away_team_raw, m.away_team_country_code)
    return teams_df, aliases, review, m


def statsbomb_team_ids(sr: pd.DataFrame, matches: pd.DataFrame) -> dict:
    """provider ids for teams, read from StatsBomb raw match records (verified field values)."""
    out = {}
    for r in sr[sr.provider == "statsbomb"].itertuples():
        raw = json.loads(r.raw)
        mm = matches.loc[matches.match_id == r.match_id]
        if mm.empty:
            continue
        mm = mm.iloc[0]
        for side in ("home", "away"):
            t = raw[f"{side}_team"]
            out.setdefault((mm.competition_id == "UCL", mm[f"{side}_team_raw"], mm[f"{side}_team_country_code"]), set()).add(
                (t[f"{side}_team_id"], t[f"{side}_team_name"]))
    return out


def run():
    m = pd.read_parquet(PROC / "matches.parquet")
    sr = pd.read_parquet(PROC / "source_records.parquet")
    sbraw = statsbomb_team_ids(sr, m)
    # first pass to know ids, second pass to embed provider ids
    t, a, rv, m2 = build_teams(m, {})
    ids = {}
    for (is_club, raw, cc), vals in sbraw.items():
        tid_ = m2.loc[(m2.home_team_raw == raw), "home_team_id"].dropna()
        tid_ = tid_.iat[0] if len(tid_) else None
        if tid_ is None:
            tid_ = m2.loc[(m2.away_team_raw == raw), "away_team_id"].dropna().iat[0]
        for sid, sname in vals:
            ids.setdefault(tid_, {})["statsbomb_team_id"] = sid
            ids[tid_]["statsbomb_team_name"] = sname
    t, a, rv, m2 = build_teams(m, ids)
    t.to_parquet(PROC / "teams.parquet", index=False)
    t.to_csv(PROC / "teams.csv", index=False)
    a.to_csv(PROC / "team_aliases.csv", index=False)
    rv.to_csv(PROC / "entity_resolution_review.csv", index=False)
    m2.to_parquet(PROC / "matches.parquet", index=False)
    m2.to_csv(PROC / "matches.csv", index=False)
    return t, a, rv, m2


if __name__ == "__main__":
    t, a, rv, m2 = run()
    print(len(t), "teams;", t.team_type.value_counts().to_dict(), "| aliases", len(a), "| review pairs", len(rv))
    print("matches with unresolved team id:", int(m2.home_team_id.isna().sum() + m2.away_team_id.isna().sum()))
    print(a.rule.value_counts().to_dict())
    print(rv.to_string(index=False))
