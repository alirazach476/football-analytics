"""Tournament squads (the official 23/26-man lists, incl. players who never played) for the four competitions.

Source: Wikipedia "... squads" pages through the MediaWiki API (CC BY-SA 4.0), template `nat fs g player`:
shirt number, position (GK/DF/MF/FW), name, date of birth, caps, goals, club, club country, captain flag; plus the head coach.
Cross-checks: squad size and shirt-number sets against the Fjelstul World Cup squads (WC 2002-2022), and "every
player who appeared in a match is in his team's squad" using the match line-ups of every provider.
Caps / goals / club are as of the tournament start, as written on the page (empty where Wikipedia has none).
"""
from __future__ import annotations

import re
from datetime import date

import mwparserfromhell as mw
import pandas as pd

from ..config import DATA
from .build import PROC
from .wikipedia_matches import cached_wikitext, strip_markup

HEAD = re.compile(r"^(={2,4})\s*([^=\n]+?)\s*\1\s*$", re.M)


def season_of_squad_page(title: str):
    for rx, fmt in ((r"(\d{4}) FIFA World Cup squads", "WC-{}"), (r"UEFA Euro (\d{4}) squads", "EURO-{}"),
                    (r"(\d{4}) Copa América squads", "COPA-{}")):
        m = re.fullmatch(rx, title.strip())
        if m:
            return fmt.format(m.group(1))
    if title.strip() == "Copa América Centenario squads":
        return "COPA-2016"
    return None


def _int(v):
    v = re.sub(r"[^\d]", "", strip_markup(v or ""))
    return int(v) if v else None


def _dob(age_field: str):
    """{{birth date and age2|ref_y|ref_m|ref_d|birth_y|birth_m|birth_d}} -> date"""
    age_field = re.sub(r"\|\s*df\s*=\s*\w+", "", age_field or "")          # {{birth date and age2|df=y|2006|6|9|1972|12|24}}
    m = re.search(r"birth date and age2?\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", age_field or "", re.I)
    if m:
        try:
            return date(int(m[4]), int(m[5]), int(m[6]))
        except ValueError:
            return None
    m = re.search(r"birth date(?: and age)?\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", age_field or "", re.I)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    return None


def parse_squads_page(title: str, rev: int, text: str, got_at):
    sid = season_of_squad_page(title)
    heads = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in HEAD.finditer(text)]
    url = f"https://en.wikipedia.org/w/index.php?title={title.replace(' ', '_')}&oldid={rev}"
    rows, coaches = [], {}
    cursor = 0
    for t in mw.parse(text).filter_templates():
        if str(t.name).strip().lower() not in ("nat fs g player", "nat fs player", "national football squad player"):   # newer pages use the "g" variant
            continue
        pos = text.find(str(t), cursor)
        cursor = pos + 1
        team = [h for p, lvl, h in heads if p <= pos and lvl >= 3]
        team = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", team[-1]) if team else None
        g = lambda k: str(t.get(k).value).strip() if t.has(k) else ""
        name_raw = g("name")
        name_raw = re.sub(r"\{\{\s*sortname\s*\|\s*([^|}]*)\|\s*([^|}]*)(?:\|[^}]*)?\}\}", r"\1 \2", name_raw, flags=re.I)   # Euro 2004
        name_raw = re.sub(r"\{\{\s*sort\s*\|[^|}]*\|(.*?)\}\}", r"\1", name_raw, flags=re.I)   # {{sort|key|[[Name]]}} (Euro 2016)
        name_raw = re.sub(r"\{\{\s*nowrap\s*\|([^{}]*)\}\}", r"\1", name_raw, flags=re.I)
        rows.append(dict(season_id=sid, team_heading=team, shirt_number=_int(g("no")), position=strip_markup(g("pos")) or None,
                         player_name_raw=re.sub(r"\(\s*c\s*\)|\(\s*captain\s*\)", "", strip_markup(re.sub(r"\(\s*\[\[Captain[^\]]*\]\]\s*\)", "(c)", name_raw))).strip(),
                         is_captain=bool(re.search(r"(?<!vice-)(?<!vice )(?<!vice)captain|\(c\)", strip_markup(name_raw) + " " + strip_markup(g("other")), re.I)), date_of_birth=_dob(g("age")),
                         caps=_int(g("caps")), goals=_int(g("goals")), club_raw=strip_markup(g("club")) or None,
                         club_country_raw=strip_markup(g("clubnat")) or None, page=title, revid=rev, source_url=url, retrieved_at=got_at))
    # head coach: "Head coach: [[Name]]" (or "Coach:", "Manager:") right under the team heading
    for (p, lvl, h), nxt in zip(heads, heads[1:] + [(len(text), 0, "")]):
        if lvl < 3:
            continue
        m = re.search(r"(?:Head coach|Coach|Manager)s?\s*:\s*(.+)", text[p:nxt[0]])
        if m:
            coaches[re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", h)] = strip_markup(m.group(1).split("\n")[0])
    return sid, rows, coaches


def run():
    from .martj42 import cn_strict
    t = pd.read_parquet(PROC / "teams.parquet")
    a = pd.read_csv(PROC / "team_aliases.csv")
    idx = {cn_strict(r.team_name): r.team_id for r in t[t.team_type == "national"].itertuples()}
    for r in a.itertuples():
        if r.team_id.startswith("T-NAT"):
            idx.setdefault(cn_strict(r.alias), r.team_id)
    allrows, coach_rows = [], []
    for title, rev, text, got_at in cached_wikitext():
        if season_of_squad_page(title) is None:
            continue
        sid, rows, coaches = parse_squads_page(title, rev, text, got_at)
        allrows += rows
        for team, name in coaches.items():
            coach_rows.append(dict(season_id=sid, team_heading=team, head_coach_raw=name))
    df = pd.DataFrame(allrows)
    df["competition_id"] = df.season_id.str.split("-").str[0]
    df["team_id"] = df.team_heading.map(lambda h: idx.get(cn_strict(h)) if h else None)
    unresolved = df[df.team_id.isna()].team_heading.value_counts()
    coaches = pd.DataFrame(coach_rows)
    coaches["team_id"] = coaches.team_heading.map(lambda h: idx.get(cn_strict(h)))
    df = df.drop(columns="team_heading")
    (PROC / "squads").mkdir(exist_ok=True)
    df.to_parquet(PROC / "squads" / "squads.parquet", index=False)
    df.to_csv(PROC / "squads" / "squads.csv", index=False, encoding="utf-8-sig")
    coaches.to_parquet(PROC / "squads" / "head_coaches.parquet", index=False)
    return df, coaches, unresolved


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """squad size + shirt numbers vs Fjelstul (WC 2002-2022); line-up appearances vs squad membership (all providers)."""
    rows = []
    fj = pd.read_csv(DATA / "raw" / "fjelstul" / "squads.csv")
    from .martj42 import cn_strict
    t = pd.read_parquet(PROC / "teams.parquet")
    a = pd.read_csv(PROC / "team_aliases.csv")
    idx = {cn_strict(r.team_name): r.team_id for r in t[t.team_type == "national"].itertuples()}
    for r in a.itertuples():
        if r.team_id.startswith("T-NAT"):
            idx.setdefault(cn_strict(r.alias), r.team_id)
    fj["team_id_ours"] = fj.team_name.map(lambda n: idx.get(cn_strict(n)))
    for (sid, tid), g in df.groupby(["season_id", "team_id"]):
        row = dict(season_id=sid, team_id=tid, squad_size_wikipedia=len(g))
        if sid.startswith("WC") and 2002 <= int(sid.split("-")[1]) <= 2022:
            f = fj[(fj.tournament_id == sid) & (fj.team_id_ours == tid)]
            row.update(squad_size_fjelstul=len(f), numbers_equal=set(g.shirt_number.dropna().astype(int)) == set(f.shirt_number.dropna().astype(int)))
        rows.append(row)
    v = pd.DataFrame(rows)
    # appearances: every shirt number that appeared for a team in a season must be in that team's squad
    m = pd.read_parquet(PROC / "matches.parquet", columns=["match_id", "season_id"]).set_index("match_id").season_id
    lu = pd.read_parquet(PROC / "lineups_all.parquet", columns=["match_id", "team_id", "jersey_number", "appeared"])
    lu = lu[lu.appeared.fillna(True) & lu.jersey_number.notna()].assign(season_id=lambda d: d.match_id.map(m))
    sq = df.dropna(subset=["shirt_number"]).groupby(["season_id", "team_id"]).shirt_number.agg(lambda s: set(s.astype(int))).to_dict()
    miss = []
    for (sid, tid), g in lu.groupby(["season_id", "team_id"]):
        have = sq.get((sid, tid))
        if have is None:
            continue
        absent = set(g.jersey_number.astype(int)) - have
        if absent:
            miss.append(dict(season_id=sid, team_id=tid, appeared_numbers_not_in_squad=sorted(absent)))
    (DATA / "quality").mkdir(exist_ok=True)
    v.to_csv(DATA / "quality" / "squads_validation.csv", index=False)
    pd.DataFrame(miss, columns=["season_id", "team_id", "appeared_numbers_not_in_squad"]).to_csv(DATA / "quality" / "squads_appearance_check.csv", index=False)
    return v, pd.DataFrame(miss)


def _tok(name: str) -> set:
    from .build import norm
    return set(norm(name).split())


def link_and_register():
    """Attach a canonical player_id to every squad row (run AFTER unify) and register squad-only players.
    S1  same tournament + team + shirt number as the Fjelstul squad row (WC 2002-2022) AND >=1 shared name token
    S2  same date of birth AND one name's tokens contained in the other's, unique on both sides (players_all)
    S3  otherwise: players sharing (team, date of birth) across tournaments share one new id `P-SQ-<hash>`; two squad rows of
        the same team-tournament with the same birth date are kept apart by name.  Nothing is merged on name alone."""
    import hashlib
    import json
    sq = pd.read_parquet(PROC / "squads" / "squads.parquet")
    pl = pd.read_parquet(PROC / "players_all.parquet")
    pl = pl[~pl.player_id.str.startswith("P-SQ-")]
    links = pd.read_csv(PROC / "player_links.csv")
    canon = dict(zip(links.source_id, links.canonical_id))
    from .martj42 import cn_strict
    t = pd.read_parquet(PROC / "teams.parquet")
    a = pd.read_csv(PROC / "team_aliases.csv")
    idx = {cn_strict(r.team_name): r.team_id for r in t[t.team_type == "national"].itertuples()}
    for r in a.itertuples():
        if r.team_id.startswith("T-NAT"):
            idx.setdefault(cn_strict(r.alias), r.team_id)
    fj = pd.read_csv(DATA / "raw" / "fjelstul" / "squads.csv")
    fj["team_id_ours"] = fj.team_name.map(lambda n: idx.get(cn_strict(n)))
    fj["full"] = fj.given_name.fillna("").replace("not applicable", "") + " " + fj.family_name.fillna("")
    fjk = {(r.tournament_id, r.team_id_ours, int(r.shirt_number)): ("P-FJ-" + r.player_id[2:], r.full) for r in fj.dropna(subset=["shirt_number", "team_id_ours"]).itertuples()}

    sq = sq.copy()
    mt = pd.read_parquet(PROC / "matches.parquet", columns=["season_id", "home_team_id", "away_team_id"])
    played = set(zip(mt.season_id, mt.home_team_id)) | set(zip(mt.season_id, mt.away_team_id))
    sq["team_played"] = [(a, b) in played for a, b in zip(sq.season_id, sq.team_id)]   # False: squad named, team withdrew (Copa 2001: Argentina, Canada)
    sq["player_id"], sq["link_rule"] = None, None
    for i, r in sq.iterrows():                                              # S1
        if pd.isna(r.shirt_number):
            continue
        hit = fjk.get((r.season_id, r.team_id, int(r.shirt_number)))
        if hit and (_tok(hit[1]) & _tok(r.player_name_raw)):
            sq.at[i, "player_id"] = canon.get(hit[0], hit[0])
            sq.at[i, "link_rule"] = "S1_fjelstul_shirt_number"
    known = pl[pl.date_of_birth.notna()].assign(dob=lambda d: pd.to_datetime(d.date_of_birth, errors="coerce").dt.date)
    by_dob = {}
    for r in known.itertuples():
        by_dob.setdefault(r.dob, []).append((r.player_id, _tok(r.full_name) | _tok(r.display_name)))
    cand_sq, cand_pl = {}, {}
    todo = sq[sq.player_id.isna() & sq.date_of_birth.notna()]
    for i, r in todo.iterrows():                                            # S2
        nt = _tok(r.player_name_raw)
        for pid, pt in by_dob.get(r.date_of_birth, []):
            if nt and pt and (nt <= pt or pt <= nt or len(nt & pt) >= 2):
                cand_sq.setdefault(i, []).append(pid)
                cand_pl.setdefault(pid, []).append(i)
    for i, c in cand_sq.items():
        if len(c) == 1 and len(cand_pl[c[0]]) <= 1 or (len(set(c)) == 1 and all(sq.at[j, "season_id"] != sq.at[i, "season_id"] for j in cand_pl[c[0]] if j != i)):
            sq.at[i, "player_id"], sq.at[i, "link_rule"] = c[0], "S2_dob_and_name"
    rest = sq[sq.player_id.isna() & sq.date_of_birth.notna()]               # S3
    dup = rest.groupby(["season_id", "team_id", "date_of_birth"]).size()
    twins = {(tm, dob) for (_, tm, dob), n in dup.items() if n > 1}          # same team + birth date seen twice in a squad
    new_players = {}
    for i, r in rest.iterrows():
        key = f"{r.team_id}|{r.date_of_birth}"
        if (r.team_id, r.date_of_birth) in twins:
            key += "|" + " ".join(sorted(_tok(r.player_name_raw))) if _tok(r.player_name_raw) else f"|no-name-{r.shirt_number}"
        pid = "P-SQ-" + hashlib.sha1(key.encode()).hexdigest()[:12]
        sq.at[i, "player_id"], sq.at[i, "link_rule"] = pid, "S3_team_dob"
        new_players.setdefault(pid, []).append(i)
    reg = []
    for pid, ids in new_players.items():
        g = sq.loc[ids]
        names = g.player_name_raw.value_counts()
        reg.append(dict(player_id=pid, full_name=max(g.player_name_raw, key=len), display_name=names.index[0], name_variants=json.dumps(sorted(set(g.player_name_raw) - {names.index[0]}), ensure_ascii=False),
                        nationality=None, date_of_birth=g.date_of_birth.iloc[0].isoformat(), height_cm=None, preferred_foot=None,
                        primary_position={"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Forward"}.get(g.position.mode().iat[0] if g.position.notna().any() else None),
                        team_ids=json.dumps(sorted(set(g.team_id.dropna()))), source_identifiers=json.dumps({"source": "wikipedia_squads"})))
    # squad players linked (S1) to a Fjelstul id that never appeared in a match (unused squad members) are not in
    # players_all yet: register them from Fjelstul's player file, so every squad row points at a real registry row
    missing = sorted(set(sq.player_id) - set(pl.player_id) - {r["player_id"] for r in reg})
    fjp = pd.read_csv(DATA / "raw" / "fjelstul" / "players.csv")
    fjp["pid"] = "P-FJ-" + fjp.player_id.str[2:]
    fjp = fjp.set_index("pid")
    for pid in missing:
        if pid not in fjp.index:
            raise ValueError(f"squad player_id {pid} not found in any registry source")
        r = fjp.loc[pid]
        given = "" if r.given_name == "not applicable" else r.given_name
        reg.append(dict(player_id=pid, full_name=f"{given} {r.family_name}".strip(), display_name=r.family_name, name_variants="[]",
                        nationality=None, date_of_birth=None if r.birth_date == "not available" else r.birth_date, height_cm=None,
                        preferred_foot=None,
                        primary_position="Goalkeeper" if r.goal_keeper else "Defender" if r.defender else "Midfielder" if r.midfielder else "Forward" if r.forward else None,
                        team_ids="[]", source_identifiers=json.dumps({"fjelstul_player_id": r.player_id})))
    allp = pd.concat([pl, pd.DataFrame(reg)], ignore_index=True)
    allp.to_parquet(PROC / "players_all.parquet", index=False)
    allp.to_csv(PROC / "players_all.csv", index=False)
    sq.to_parquet(PROC / "squads" / "squads.parquet", index=False)
    sq.to_csv(PROC / "squads" / "squads.csv", index=False, encoding="utf-8-sig")
    return sq, len(reg)


def stage():
    """Pipeline stage: parse -> validate -> link to the player registry (must run after unify)."""
    df, coaches, unresolved = run()
    if len(unresolved):
        raise ValueError(f"unresolved team headings: {dict(unresolved)}")
    validate(df)
    return link_and_register()


if __name__ == "__main__":
    df, coaches, unres = run()
    print(len(df), "squad players |", df.groupby("season_id").team_id.nunique().to_dict())
    print("unresolved team headings:", dict(unres))
    print(df.groupby("competition_id").size().to_dict(), "| with DOB:", int(df.date_of_birth.notna().sum()), "| with club:", int(df.club_raw.notna().sum()),
          "| with caps:", int(df.caps.notna().sum()), "| head coaches:", len(coaches))
    v, miss = validate(df)
    w = v.dropna(subset=["squad_size_fjelstul"])
    print("vs Fjelstul:", len(w), "team-squads | size equal", int((w.squad_size_wikipedia == w.squad_size_fjelstul).sum()),
          "| shirt numbers equal", int(w.numbers_equal.sum()))
    print("team-seasons where an appeared shirt number is NOT in the squad:", len(miss))
    sq, n_new = link_and_register()
    print("linked:", sq.link_rule.value_counts(dropna=False).to_dict(), "| new squad-only players registered:", n_new)
