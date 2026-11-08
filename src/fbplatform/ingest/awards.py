"""Tournament awards (Golden Ball / Boot / Glove, young player, fair play, goal of the tournament, team of the tournament ...).

Source: the English Wikipedia award roll pages ("FIFA World Cup awards", "UEFA European Championship awards", "Copa América awards")
and, for the UEFA Nations League (no roll page), the Awards section of each Finals article. Fetched through the official MediaWiki API
(CC BY-SA 4.0), cached by HttpClient. Secondary source: every row keeps page + revision + the raw name/link.
Nothing is invented: a winner is linked to a player/team id only when the match is unique, otherwise the raw name is kept with a null id.
Only editions that exist in the registry (WC 2002+, Euro 2000+, Copa 2001+, UNL) are kept. Per-match Man of the Match is NOT an award row
(it lives in matches.man_of_the_match_raw).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from ..config import DATA
from .htmltables import entities, grid, page_html, sections, txt
from .martj42 import cn_strict
from .wikipedia import client

PROC = DATA / "processed"
COLS = ["season_id", "winner_type", "award_name", "award_category", "position_label", "rank", "entity_name_raw", "entity_link_title",
        "country_code_raw", "value_text", "source_page", "revid", "retrieved_at"]
SKIP_HDR = re.compile(r"(?:ref\.?|age|position|score|scored against|opponent|minute|result|round|medium|hosts?|wins|awards|standard|rank|#|year|edition|world cup)", re.I)
VAL_HDR = re.compile(r"(goals?|clean sheets?)$", re.I)
# (page, h2 regex, h3 regex or None, award name, category, winner_type)
RULES = [
    ("wc", r"golden ball", r"official winners", "Golden Ball", "Best player", "player"),
    ("wc", r"golden boot", None, "Golden Boot", "Top scorer", "player"),
    ("wc", r"golden glove", None, "Golden Glove (Lev Yashin Award)", "Best goalkeeper", "player"),
    ("wc", r"young player", None, "Young Player Award", "Best young player", "player"),
    ("wc", r"fair play", None, "Fair Play Trophy", "Fair play", "team"),
    ("wc", r"most entertaining", None, "Most Entertaining Team", "Most entertaining team", "team"),
    ("wc", r"goal of the tournament", r"official winners", "Goal of the Tournament", "Goal of the tournament", "player"),
    ("wc", r"all-star", r"official winners", "All-Star Team", "Team of the tournament", "player"),
    ("euro", r"^player of the tournament", None, "Player of the Tournament", "Best player", "player"),
    ("euro", r"young player", None, "Young Player of the Tournament", "Best young player", "player"),
    ("euro", r"goal of the tournament", None, "Goal of the Tournament", "Goal of the tournament", "player"),
    ("euro", r"top goalscorer", "NONE", "Golden Boot", "Top scorer", "player"),
    ("euro", r"team of the tournament", r"editions", "Team of the Tournament", "Team of the tournament", "player"),
    ("copa", r"golden ball", r"official", "Golden Ball", "Best player", "player"),
    ("copa", r"golden boot", None, "Golden Boot", "Top scorer", "player"),
    ("copa", r"golden glove", None, "Golden Glove", "Best goalkeeper", "player"),
    ("copa", r"team of the tournament", None, "Team of the Tournament", "Team of the tournament", "player"),
    ("copa", r"fair play", None, "Fair Play Award", "Fair play", "team"),
    ("copa", r"best young player", None, "Best Young Player", "Best young player", "player"),
]
ROLL = {"wc": ("FIFA World Cup awards", "WC"), "euro": ("UEFA European Championship awards", "EURO"), "copa": ("Copa América awards", "COPA")}
MINYEAR = {"WC": 2002, "EURO": 2000, "COPA": 2001}


def _rank(h: str):
    if re.search(r"gold|winner$|^winner|first|top goalscorer|^lev|^fifa|^player|^best", h, re.I) and not re.search(r"silver|bronze|runner|second|third", h, re.I):
        return 1
    if re.search(r"silver|runner|second", h, re.I):
        return 2
    if re.search(r"bronze|third", h, re.I):
        return 3
    return None


def _table_rows(tb):
    """-> (header labels per column, data rows[list of cells]) with 1 or 2 stacked header rows combined."""
    g = grid(tb)
    year = re.compile(r"\b(19|20)\d\d\b")
    first_data = next((i for i, r in enumerate(g) if r and year.search(txt(r[0]))), None)
    if first_data is None or first_data == 0:
        return None, []
    heads = []
    for j in range(len(g[0])):
        parts = []
        for i in range(first_data):
            t = txt(g[i][j]) if j < len(g[i]) else ""
            if t and t not in parts:
                parts.append(t)
        heads.append(" | ".join(parts))
    return heads, g[first_data:]


def _extract_table(sid_prefix, tb, rule, page, rev, now):
    heads, rows = _table_rows(tb)
    out = []
    if not heads:
        return out
    _, h2re, h3re, name, cat, wtype = rule
    for r in rows:
        m = re.search(r"\b((?:19|20)\d\d)\b", txt(r[0]))
        if not m or int(m.group(1)) < MINYEAR[sid_prefix]:
            continue
        sid = f"{sid_prefix}-{m.group(1)}"
        group = []
        for j in range(1, len(r)):
            if j and r[j] is r[j - 1]:
                continue                                    # colspan duplicate
            h = heads[j]
            lastpart = h.split("|")[-1].strip()
            if VAL_HDR.fullmatch(lastpart):
                v = txt(r[j])
                if group and v and not re.fullmatch(r"[—–-]|n/?a|— n/a", v, re.I):
                    unit = "clean sheets" if "clean" in lastpart.lower() else "goals"
                    v = v if re.search(r"[a-z]", v) else f"{v} {unit}"
                    for k in group:                         # joint winners share the value in the next column
                        out[k]["value_text"] = v
                continue
            if SKIP_HDR.fullmatch(lastpart):
                continue
            group = []
            ents = entities(r[j])
            if wtype == "team" and not ents:
                t = txt(r[j])
                ents = [dict(link=None, display=t, country=None)] if t and not re.fullmatch(r"[—–-]|n/?a", t, re.I) else []
            for e in ents:
                out.append(dict(season_id=sid, winner_type=wtype, award_name=name, award_category=cat,
                                position_label=h if cat == "Team of the tournament" else (h if _rank(h) != 1 and heads[j] else None),
                                rank=None if cat == "Team of the tournament" else _rank(h), entity_name_raw=e["display"], entity_link_title=e["link"],
                                country_code_raw=e["country"], value_text="", source_page=page, revid=rev, retrieved_at=now))
                group.append(len(out) - 1)
    for o in out:
        o["value_text"] = o["value_text"] or None
    return out


def parse_roll(key, c, now):
    got = page_html(c, ROLL[key][0])
    if not got:
        return []
    html, rev, canon = got
    prefix = ROLL[key][1]
    out = []
    for h2, h3, tb in sections(html):
        for rule in RULES:
            if rule[0] != key or not re.search(rule[1], h2 or "", re.I):
                continue
            if rule[2] == "NONE":
                ok = h3 is None
            else:
                ok = rule[2] is None or bool(h3 and re.search(rule[2], h3, re.I))
            if ok:
                out += _extract_table(prefix, tb, rule, canon, rev, now)
                break
    return out


def parse_unl(c, now):
    """UEFA Nations League Finals pages: Awards section = bold/dt heading followed by a bullet list of winners."""
    pages = pd.read_csv(PROC / "wikipedia" / "pages.csv")
    fin = pages[pages.page.str.fullmatch(r".*UEFA Nations League Finals")]
    out = []
    for sid, title in zip(fin.season_id, fin.page):
        got = page_html(c, title)
        if not got:
            continue
        html, rev, canon = got
        soup = BeautifulSoup(html, "lxml")
        h = next((x for x in soup.find_all(["h2", "h3"]) if re.fullmatch(r"(individual )?awards", txt(x).replace("[edit]", "").strip(), re.I)), None)
        if not h:
            continue
        head = None
        for el in h.parent.find_next_siblings() if h.parent.name == "div" else h.find_next_siblings():
            if el.name in ("h2", "h3") or (el.name == "div" and el.find(["h2", "h3"])):
                if el.name == "div" and not el.find(["h2", "h3"]):
                    continue
                break
            t = txt(el)
            if el.name == "dl" or (el.name == "p" and el.find("b") and txt(el.find("b")) == t):
                head = t
            elif el.name == "ul" and head:
                for li in el.find_all("li", recursive=False):
                    ents = entities(li)
                    if ents:
                        e = ents[0]
                        val = re.search(r"(\d+ goals?[^)\]]*)", txt(li))
                        out.append(dict(season_id=sid, winner_type="player", award_name=head, award_category=_cat(head), position_label=None, rank=1,
                                        entity_name_raw=e["display"], entity_link_title=e["link"], country_code_raw=e["country"],
                                        value_text=val.group(1) if val else None, source_page=canon, revid=rev, retrieved_at=now))
    return out


def _cat(label):
    L = label.lower()
    for name, rx in [("Top scorer", r"boot|top scor"), ("Best goalkeeper", r"glove|goalkeeper"), ("Best young player", r"young"),
                     ("Best player", r"player of the|best player|golden ball|mvp"), ("Fair play", r"fair play"),
                     ("Goal of the tournament", r"goal of"), ("Team of the tournament", r"team of")]:
        if re.search(rx, L):
            return name
    return "Other"


def run() -> pd.DataFrame:
    c = client()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for k in ROLL:
        rows += parse_roll(k, c, now)
    rows += parse_unl(c, now)
    df = pd.DataFrame(rows, columns=COLS).drop_duplicates(["season_id", "award_name", "entity_name_raw", "entity_link_title", "position_label", "rank"])
    df = df[df.season_id.isin(set(pd.read_parquet(DATA / "silver" / "matches.parquet").season_id))].reset_index(drop=True)
    df = link(df)
    out = PROC / "awards"
    out.mkdir(exist_ok=True)
    df.to_parquet(out / "awards.parquet", index=False)
    return df


def _tk(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return frozenset(t for t in re.split(r"[^a-z]+", s) if len(t) > 1)


def link(df: pd.DataFrame) -> pd.DataFrame:
    teams = pd.read_parquet(PROC / "teams.parquet")
    aliases = pd.read_csv(PROC / "team_aliases.csv")
    idx = {cn_strict(r.team_name): r.team_id for r in teams.itertuples()}
    for r in aliases.itertuples():
        if str(r.team_id).startswith("T-NAT"):
            idx.setdefault(cn_strict(r.alias), r.team_id)

    def team_of(name, link_title):
        for n in (re.sub(r"\s+(men's )?national .*$", "", link_title, flags=re.I) if isinstance(link_title, str) else None, name):
            if isinstance(n, str) and cn_strict(n) in idx:
                return idx[cn_strict(n)]
        return None

    df = df.copy()
    df["team_id"] = [team_of(n, l) if w == "team" else team_of(c, None) for n, l, w, c in
                     zip(df.entity_name_raw, df.entity_link_title, df.winner_type, df.country_code_raw)]
    sq = pd.read_parquet(DATA / "silver" / "squads.parquet")[["season_id", "team_id", "player_name_raw", "player_id"]].dropna(subset=["player_id"])
    sq["tk"] = sq.player_name_raw.map(_tk)
    pid, how = [], []
    for r in df.itertuples():
        if r.winner_type != "player":
            pid.append(None)
            how.append(None)
            continue
        want = _tk(re.sub(r"\s*\(.*?\)", "", r.entity_link_title or r.entity_name_raw or ""))
        cand = sq[sq.season_id == r.season_id]
        if isinstance(r.team_id, str):
            cand = cand[cand.team_id == r.team_id]
        mask = pd.Series([bool(want) and (want <= k or k <= want or len(want & k) >= 2) for k in cand.tk], index=cand.index, dtype=bool)
        hit = cand[mask].player_id.unique()
        if len(hit) == 0 and want:                       # no squad for that edition (e.g. UNL): accept a unique name match in any season
            mask2 = pd.Series([want <= k or k <= want or len(want & k) >= 2 for k in sq.tk], index=sq.index, dtype=bool)
            h2 = sq[mask2].player_id.unique()
            if len(h2) == 1:
                pid.append(h2[0])
                how.append("squad_name_match_other_season")
                continue
        pid.append(hit[0] if len(hit) == 1 else None)
        how.append("squad_name_match" if len(hit) == 1 else ("ambiguous" if len(hit) > 1 else "not_in_season_squads"))
    df["player_id"] = pid
    df["link_status"] = how
    return df


if __name__ == "__main__":
    d = run()
    print(len(d), "rows;", d.winner_type.value_counts().to_dict())
    print(d.groupby(["season_id"]).size().to_string())
    p = d[d.winner_type == "player"]
    print("players linked:", int(p.player_id.notna().sum()), "/", len(p), p.link_status.value_counts().to_dict())
    t = d[d.winner_type == "team"]
    print("teams linked:", int(t.team_id.notna().sum()), "/", len(t))
