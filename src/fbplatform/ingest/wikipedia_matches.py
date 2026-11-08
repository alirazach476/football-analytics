"""Wikipedia match boxes (secondary source, CC BY-SA 4.0) for the in-scope competitions:
FIFA World Cup, UEFA Euro, Copa America, UEFA Nations League.  Works from the cached raw wikitext (no scraping:
pages were fetched through the official MediaWiki API, see wikipedia.py).

Rules
  * Only tournament pages are used (group / knockout / final / league pages); qualifying, squads, statistics pages
    are excluded by title pattern.
  * A box is trusted only if date, both teams and an N-N score parse; anything else is reported.
  * National teams appear as flag codes ({{fb|GER}}); the codes are expanded to names by Wikipedia's own API.
  * Existing matches are NEVER overwritten.  Fill-null only: referee, attendance, stage, group, stadium (a martj42
    venue is only "city, country", so a Wikipedia stadium replaces it).  Score/date disagreements are reported.
  * Goals: `{{goal|minute|flag|...}}` under the CREDITED team.  A goal list becomes events only if it reproduces the
    score (complete); otherwise it is counted as partial and not emitted - never padded.
Attribution: every row keeps page title + revision URL; text is CC BY-SA 4.0 (https://en.wikipedia.org).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from urllib.parse import quote

import mwparserfromhell as mw
import pandas as pd

from ..config import DATA, RAW
from ..http import HttpClient
from .build import PROC, norm
from .wikipedia import API, _norm_name

HEAD = re.compile(r"^(={2,5})\s*(.+?)\s*\1\s*$", re.M)


# ------------------------------------------------------------------ cached pages
def cached_wikitext():
    """(title, revid, wikitext, retrieved_at) for every page already fetched (from the HTTP cache)."""
    out, seen, first = [], set(), {}
    for line in open(RAW / "manifest.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["source"] == "wikipedia" and r["status"] == 200 and not r["cached"]:
            first.setdefault(r["url"], r["retrieved_at"])
    for line in open(RAW / "manifest.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["source"] != "wikipedia" or "action=parse" not in r["url"] or r["status"] != 200 or r["url"] in seen:
            continue
        seen.add(r["url"])
        f = RAW / "wikipedia" / hashlib.sha1(r["url"].encode()).hexdigest()
        if not f.exists():
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        if "parse" in j and "wikitext" in j["parse"] and "revid" in j["parse"]:   # skips the flag-code expansion call
            out.append((j["parse"]["title"], j["parse"]["revid"], j["parse"]["wikitext"], first.get(r["url"])))
    return out


def boxes_with_heading(wikitext: str):
    heads = [(m.start(), m.group(2)) for m in HEAD.finditer(wikitext)]
    code = mw.parse(wikitext)
    res = []
    for t in code.filter_templates():
        if _norm_name(t).startswith(("footballbox", "#invoke:footballbox", "infoboxfootballmatch")):
            pos = wikitext.find(str(t)[:80])
            h = [x for p, x in heads if p <= pos]
            res.append(({str(p.name).strip(): str(p.value).strip() for p in t.params},
                        re.sub(r"\[\[|\]\]|<[^>]+>|\{\{[^}]*\}\}", "", h[-1]).strip() if h else None))
    return res


# ------------------------------------------------------------------ field parsers
def strip_markup(s: str) -> str:
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s or "", flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip(" ,; ")


MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def parse_date(v: str):
    """{{Start date|y|m|d}} or plain text ('16 July 2011' / 'July 16, 2011')."""
    m = re.search(r"\{\{\s*start date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})", v or "", re.I)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    t = strip_markup(v or "").lower()
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m and m[2] in MONTHS:
        return date(int(m[3]), MONTHS[m[2]], int(m[1]))
    m = re.search(r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})", t)
    if m and m[1] in MONTHS:
        return date(int(m[3]), MONTHS[m[1]], int(m[2]))
    return None


def score_text(v: str) -> str:
    """'{{score link|page#x|2–1}}' -> '2–1' before markup is stripped (the template would otherwise be deleted)."""
    v = re.sub(r"\{\{\s*score link\s*\|[^|}]*\|([^}]*)\}\}", r"\1", v or "", flags=re.I)
    return strip_markup(v)


FLAGT = re.compile(r"\{\{\s*(?:#invoke:)?(?:flagg?|fbaicon|fb-rt|fb|flagicon|flagdeco)\b([^{}]*)\}\}")
_SKIP = {"main", "unpre", "unpe", "fb", "fb-rt", "name", "nowrap"}


def flag_arg(v: str):
    """-> (3-letter code | None, country name | None) from {{fb|GER}}, {{fb-rt|FRA|1974}}, {{fb|Colombia}},
    {{#invoke:flag|fb-rt|CAN}}, {{#invoke:flagg|main|unpre|avar=fb|QAT}}."""
    m = FLAGT.search(v or "")
    if not m:
        return None, None
    toks = [t.strip() for t in m.group(1).split("|")[1:]
            if t.strip() and "=" not in t and t.strip().lower() not in _SKIP and not re.fullmatch(r"\d{4}", t.strip())]
    if not toks:
        return None, None
    t = toks[0]
    return (t, None) if re.fullmatch(r"[A-Z]{3}", t) else (None, t)


def parse_team(v: str):
    """-> (display name or '', link target or '', country code or country name carried as 'name:<X>')."""
    code, fname = flag_arg(v)
    link = re.search(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]", re.sub(r"\{\{[^{}]*\}\}", "", v or ""))
    plain = strip_markup(v or "")
    if link:
        return (link.group(2) or link.group(1)).strip(), link.group(1).strip(), code
    return (plain or fname or ""), (plain or fname or ""), code


PLAIN_MIN = re.compile(r"(\d{1,3})(?:\+(\d{1,2}))?\s*'?\s*(?:\((pen|o\.?g)\.?\))?")


def parse_goals_plain(v: str):
    """Fallback when a list has no {{goal}} templates: '*[[X|X]] 50', 82' (pen.)'. One entry per line."""
    out = []
    for line in re.split(r"\n\*|\n", v or ""):
        t = strip_markup(line.strip().lstrip("*"))
        m = re.match(r"([^\d]+?)\s+(\d{1,3}(?:\+\d{1,2})?\s*'.*)$", t)
        if not m:
            continue
        scorer = m.group(1).strip(" ,*")
        for mm in PLAIN_MIN.finditer(m.group(2)):
            flag = (mm.group(3) or "").lower().replace(".", "")
            out.append(dict(scorer=scorer, minute=int(mm.group(1)), added=int(mm.group(2)) if mm.group(2) else None,
                            flag="penalty" if flag == "pen" else ("own_goal" if flag == "og" else None)))
    return out


def parse_goals(v: str):
    out = []
    for line in re.split(r"\n\*|\n", v or ""):
        line = line.strip().lstrip("*").strip()
        if not re.search(r"\{\{\s*goal", line, re.I):
            continue
        tpls = [t for t in mw.parse(line).filter_templates() if str(t.name).strip().lower() == "goal"]
        name_part = line[:line.lower().find("{{goal")]
        scorer = strip_markup(re.sub(r"\{\{[^{}]*\}\}", "", name_part)).strip(" *") or None
        for t in tpls:
            p = [str(x.value).strip() for x in t.params if not x.showkey]
            i = 0
            while i < len(p):
                mm = re.match(r"(\d{1,3})(?:\+(\d{1,2}))?", p[i])
                if mm:
                    flag = (p[i + 1] if i + 1 < len(p) else "").lower().replace(" ", "")
                    out.append(dict(scorer=scorer, minute=int(mm[1]), added=int(mm[2]) if mm[2] else None,
                                    flag="penalty" if flag.startswith("pen") else ("own_goal" if flag.startswith(("o.g", "og")) else None)))
                i += 2
    return out or parse_goals_plain(v)


def parse_box(b: dict, heading):
    d = parse_date(b.get("date"))
    sc = re.search(r"(\d+)\s*[–—\-]\s*(\d+)", score_text(b.get("score", "")))
    t1, t2 = parse_team(b.get("team1")), parse_team(b.get("team2"))
    if d is None or not (t1[0] or t1[2]) or not (t2[0] or t2[2]):
        return None
    ps = re.search(r"(\d+)\s*[–—\-]\s*(\d+)", score_text(b.get("penaltyscore", "")))
    att = re.search(r"[\d,]+", strip_markup(b.get("attendance", "")))
    ref = strip_markup(b.get("referee", ""))
    refm = re.match(r"(.+?)\s*\((.+)\)$", ref)
    tm = re.search(r"(\d{1,2}):(\d{2})", b.get("time", "") or "")
    return dict(date=d, time_local=f"{int(tm[1]):02d}:{tm[2]}" if tm else None,
                home=t1[0], home_target=t1[1], home_cc=t1[2], away=t2[0], away_target=t2[1], away_cc=t2[2],
                score=(int(sc[1]), int(sc[2])) if sc else None, aet=bool(strip_markup(b.get("aet", ""))),
                pens=(int(ps[1]), int(ps[2])) if ps else None,
                goals1=parse_goals(b.get("goals1")), goals2=parse_goals(b.get("goals2")),
                stadium=strip_markup(b.get("stadium", "")) or None,
                stadium_links=[(t.strip(), (d or t).strip()) for t, d in re.findall(
                    r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]", re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", b.get("stadium", ""), flags=re.S))],
                attendance=int(att.group(0).replace(",", "")) if att and att.group(0).replace(",", "").isdigit() else None,
                referee=(refm.group(1).strip() if refm else ref) or None, referee_country=refm.group(2).strip() if refm else None,
                report_url=(b.get("report") or "").strip() or None, heading=heading)


# ------------------------------------------------------------------ page -> season / stage
def season_of_page(title: str):
    """-> (competition_id, season_id, group_letter_from_title, league_letter) or None for out-of-scope pages."""
    t = title.strip()
    m = re.fullmatch(r"(\d{4}) FIFA World Cup(?: Group ([A-L])| knockout stage| round of 32| final)?", t)
    if m:
        return "WC", f"WC-{m[1]}", m[2], None
    m = re.fullmatch(r"UEFA Euro (\d{4})(?: Group ([A-F])| knockout (?:phase|stage)| final)?", t)
    if m:
        return "EURO", f"EURO-{m[1]}", m[2], None
    m = re.fullmatch(r"Copa América Centenario(?: Group ([A-D])| knockout stage| final)?", t)
    if m:
        return "COPA", "COPA-2016", m[1], None
    m = re.fullmatch(r"(\d{4}) Copa América(?: Group ([A-D])| knockout stage| final)?", t)
    if m:
        return "COPA", f"COPA-{m[1]}", m[2], None
    m = re.fullmatch(r"(\d{4})–(\d{2}) UEFA Nations League(?: ([A-D])| play-offs)?", t)
    if m:
        return "UNL", f"UNL-{m[1]}-{m[2]}", None, m[3]
    m = re.fullmatch(r"(\d{4}) UEFA Nations League Finals", t)
    if m:
        y = int(m[1])
        return "UNL", f"UNL-{y - 1}-{y % 100:02d}", None, None
    return None


STAGE_BY_HEAD = [("round of 32", "Round of 32"), ("round of 16", "Round of 16"), ("quarter", "Quarter-finals"),
                 ("semi", "Semi-finals"), ("third", "Third place"), ("final", "Final"), ("play-off", "Play-off"),
                 ("playoff", "Play-off"), ("relegation", "Play-off")]


def stage_group(title: str, chain, grp_title, league):
    """Stage and group from the page title and the enclosing headings (nearest first).  `chain` may be a single heading
    string or a list outermost -> nearest: knockout pages put each match under its own heading ("Argentina vs Mexico")
    inside "Round of 16", and Nations League pages put "Matches" inside "Group 1"."""
    if isinstance(chain, str) or chain is None:
        chain = [chain] if chain else []
    t = title.lower()
    if grp_title:
        return "Group stage", grp_title
    for heading in reversed(chain):
        h = heading.lower()
        gm = re.match(r"group ([a-l]\d?|\d)\b", h)
        if league and gm:                                         # Nations League: "Group 1" under League A -> A1
            n = re.match(r"group (\d)", h)
            return "Group stage", f"{league}{n.group(1)}" if n else None
        if gm:
            return "Group stage", gm.group(1).upper()
        for k, v in STAGE_BY_HEAD:
            if k in h:
                return v, None
    if "promotion/relegation play-offs" in t:
        return "Promotion/relegation play-off", None
    if t.endswith(" round of 32"):                                # the page itself is the round of 32 (World Cup 2026)
        return "Round of 32", None
    if t.endswith(" final"):
        return "Final", None
    return None, None


def linked_season_map() -> dict:
    """title -> season_id for pages that are NOT named like a tournament page but are reached from one through a
    transclusion ({{#lst:Battle of Lusail}}) or a score hyperlink: dedicated match articles inherit the referencing
    tournament.  A page referenced from two different tournaments is ignored (ambiguous)."""
    pages = cached_wikitext()
    cached = {t for t, _, _, _ in pages}
    seen = {}
    for title, rev, text, _ in pages:
        sp = season_of_page(title)
        if sp is None:
            continue
        targets = set(re.findall(r"\{\{#lst:\s*([^|}]+)", text))
        targets |= set(re.findall(r"\{\{\s*score link\s*\|\s*([^|}#]+?)\s*(?:#[^|}]*)?\|", text, re.I))
        for t in targets:
            t = t.strip()
            if t in cached and t != title and season_of_page(t) is None and not re.search(r"qualif|statistics|squads", t, re.I):
                seen.setdefault(t, set()).add(sp[1])
    return {t: next(iter(v)) for t, v in seen.items() if len(v) == 1}


def _infobox(text: str) -> dict:
    for t in mw.parse(text).filter_templates():
        if re.sub(r"\s+", "", str(t.name).strip().lower()) == "infoboxfootballmatch":
            return {str(p.name).strip(): str(p.value).strip() for p in t.params}
    return {}


def scope_boxes():
    from . import wikipedia_details as D
    """All parsed boxes of the four competitions, de-duplicated by (season, date, team codes/targets)."""
    linked = linked_season_map()
    best = {}      # one record per match; when a match appears on several pages the MOST DETAILED copy wins
    for title, rev, text, got_at in cached_wikitext():
        sp = season_of_page(title)
        if sp is None and title in linked:
            sid_ = linked[title]
            sp = (sid_.split("-")[0], sid_, None, None)       # dedicated match article inherits the tournament that links to it
        if sp is None:
            continue
        cid, sid, grp_title, league = sp
        url = f"https://en.wikipedia.org/w/index.php?title={quote(title.replace(' ', '_'))}&oldid={rev}"
        regions = D.box_regions(text)
        info = _infobox(text) if len(regions) <= 1 else {}      # single-match pages (finals): MOTM / referee live in the infobox
        if not regions and info.get("team1") and info.get("team1score") and info.get("team2score"):
            det = info.get("details", "")
            pn = re.search(r"(\d+)\s*[\u2013\u2014-]\s*(\d+)\s+on\s+\[\[Penalty", det)
            box = {"date": info.get("date", ""), "time": info.get("time", ""),
                   "team1": info["team1"] + " " + info.get("team1association", ""), "team2": info.get("team2", "") + " " + info.get("team2association", ""),
                   "score": f"{info['team1score']}\u2013{info['team2score']}", "stadium": info.get("stadium", "") + ", " + info.get("city", ""),
                   "attendance": info.get("attendance", ""), "referee": info.get("referee", ""),
                   "aet": "yes" if "extra time" in det else "", "penaltyscore": f"{pn.group(1)}\u2013{pn.group(2)}" if pn else "",
                   "goals1": info.get("goals1", ""), "goals2": info.get("goals2", "")}
            pb = parse_box(box, None)
            if pb is not None and pb["score"] is not None:
                key = (sid, pb["date"], pb["home_cc"] or norm(pb["home_target"]), pb["away_cc"] or norm(pb["away_target"]))
                st, gr = stage_group(title, [], grp_title, league)
                detail = {"team1": {"players": [], "manager": None}, "team2": {"players": [], "manager": None},
                          "man_of_the_match": strip_markup(info.get("man_of_the_match1a", "")) or None,
                          "assistant_referees": None, "fourth_official": None, "var_officials": None}
                best.setdefault(key, {**pb, "competition_id": cid, "season_id": sid, "page": title, "revid": rev, "source_url": url,
                                      "retrieved_at": got_at, "stage": st, "group": gr, "detail": detail})
        for raw, head, region, chain in regions:
            p = parse_box(raw, head)
            if p is None or p["score"] is None:
                continue
            key = (sid, p["date"], p["home_cc"] or norm(p["home_target"]), p["away_cc"] or norm(p["away_target"]))
            stage, group = stage_group(title, chain, grp_title, league)
            rec = {**p, "competition_id": cid, "season_id": sid, "page": title, "revid": rev, "source_url": url,
                   "retrieved_at": got_at, "stage": stage, "group": group, "detail": D.parse_details(region)}
            if info and rec["detail"] is not None and not rec["detail"].get("man_of_the_match"):
                motm = strip_markup(info.get("man_of_the_match1a", ""))
                if motm:
                    rec["detail"]["man_of_the_match"] = motm
            old = best.get(key)
            if old is None:
                best[key] = rec
                continue
            richness = lambda r: (r["detail"] is not None, r["referee"] is not None, r["attendance"] is not None,
                                  len(r["goals1"]) + len(r["goals2"]))
            keep, other = (rec, old) if richness(rec) > richness(old) else (old, rec)
            for f in ("stage", "group", "attendance", "referee", "referee_country", "stadium", "time_local"):
                missing = keep[f] is None or (isinstance(keep[f], float) and keep[f] != keep[f])
                if missing and other[f] is not None:           # never lose a field found on the other copy
                    keep[f] = other[f]
            best[key] = keep
    return pd.DataFrame(list(best.values()))


# ------------------------------------------------------------------ flag code -> country name (via Wikipedia's API)
def resolve_codes(codes) -> dict:
    """Expand {{fb|XXX}} with Wikipedia itself (one cached API call); returns {code: country name}."""
    codes = sorted({c for c in codes if c})
    text = "\n".join(f"@@{c}@@ {{{{fb|{c}}}}}" for c in codes)
    c = HttpClient("wikipedia", 1.0)
    r = c.get(f"{API}?action=parse&format=json&formatversion=2&contentmodel=wikitext&prop=text&disablelimitreport=1&text={quote(text)}")
    html = json.loads(r.content)["parse"]["text"]
    out = {}
    parts = re.split(r"@@([A-Za-z]{3})@@", html)
    for code, seg in zip(parts[1::2], parts[2::2]):
        names = re.findall(r"<a [^>]*>([^<]+)</a>", seg)
        if names:
            out[code.upper()] = names[-1].strip()
    return out


# ------------------------------------------------------------------ integration (after teams.run)
def _nat_index():
    from .martj42 import cn_strict
    t = pd.read_parquet(PROC / "teams.parquet")
    a = pd.read_csv(PROC / "team_aliases.csv")
    idx = {cn_strict(r.team_name): r.team_id for r in t[t.team_type == "national"].itertuples()}
    for r in a.itertuples():
        if r.team_id.startswith("T-NAT"):
            idx.setdefault(cn_strict(r.alias), r.team_id)
    return idx, cn_strict


def _winner(h, a, pens):
    if h != a:
        return "home" if h > a else "away"
    if pens:
        return "home" if pens[0] > pens[1] else "away"
    return "draw"


def add_wikipedia_only_matches():
    """Boxes whose two teams resolve but that match NO existing match (same season, date +-1 day) are real matches held by
    no other source (e.g. the March 2026 Nations League play-offs missing from martj42).  They are added with
    primary_provider='wikipedia' and a note saying single source.  Idempotent."""
    import json
    from .build import match_id
    m = pd.read_parquet(PROC / "matches.parquet")
    m = m[m.primary_provider != "wikipedia"].copy()
    df = scope_boxes()
    names = resolve_codes(set(df.home_cc.dropna()) | set(df.away_cc.dropna()))
    idx, cn = _nat_index()

    def tid(shown, target, code):
        for nm in (names.get(code), target, shown):
            if nm and cn(nm) in idx:
                return nm, idx[cn(nm)]
        return None, None

    by = {}
    for r in m.itertuples():
        by.setdefault((r.season_id, frozenset((r.home_team_id, r.away_team_id))), []).append(r)
    rows = []
    for r in df.itertuples():
        hn, h = tid(r.home, r.home_target, r.home_cc)
        an, a = tid(r.away, r.away_target, r.away_cc)
        if h is None or a is None:
            continue
        if [x for x in by.get((r.season_id, frozenset((h, a))), []) if abs((x.match_date - r.date).days) <= 1]:
            continue
        hs, as_ = r.score
        rows.append(dict(
            match_id=match_id(r.season_id, r.date, hn, an), competition_id=r.competition_id, season_id=r.season_id,
            stage=r.stage, stage_raw=r.heading, group=r.group, home_team_raw=hn, away_team_raw=an, home_team_id=h, away_team_id=a,
            match_date=r.date, kickoff_time_local=r.time_local, venue_raw=r.stadium,
            referee_raw=(f"{r.referee} ({r.referee_country})" if r.referee and r.referee_country else r.referee),
            attendance=r.attendance, home_score=hs, away_score=as_, score_basis="aet" if (r.aet or r.pens) else "ft90",
            went_extra_time=bool(r.aet or r.pens), home_pen=r.pens[0] if r.pens else None, away_pen=r.pens[1] if r.pens else None,
            score_raw=f"{hs}-{as_}", score_note="single source: Wikipedia (no other provider holds this match)",
            primary_provider="wikipedia", provider_match_ids=json.dumps({"wikipedia": r.page}), source_url=r.source_url,
            retrieval_timestamp=r.retrieved_at, date_check="wikipedia_start_date", match_status="completed",
            winner=_winner(hs, as_, r.pens)))
    new = pd.DataFrame(rows)
    if len(new):
        for c in m.columns:
            if c not in new.columns:
                new[c] = None
        new = new[m.columns]
        for c in ("home_score", "away_score", "home_pen", "away_pen", "matchday", "leg", "source_line", "attendance"):
            new[c] = pd.to_numeric(new[c]).astype("Int64")
        m = pd.concat([m, new], ignore_index=True).sort_values(["competition_id", "season_id", "match_date", "kickoff_time_local", "match_id"]).reset_index(drop=True)
    m.to_parquet(PROC / "matches.parquet", index=False)
    m.to_csv(PROC / "matches.csv", index=False)
    return len(new)


def enrich_and_goals():
    added = add_wikipedia_only_matches()
    """Link every in-scope box to an existing match by team ids; fill nulls only; cross-check; goal events."""
    m = pd.read_parquet(PROC / "matches.parquet")
    df = scope_boxes()
    names = resolve_codes(set(df.home_cc.dropna()) | set(df.away_cc.dropna()))
    idx, cn = _nat_index()

    def tid(shown, target, code):
        for nm in (names.get(code), target, shown):
            if nm and cn(nm) in idx:
                return idx[cn(nm)]
        return None

    by = {}
    for r in m.itertuples():
        by.setdefault((r.season_id, frozenset((r.home_team_id, r.away_team_id))), []).append(r)
    from . import martj42 as _mj
    mcn = _mj.cn
    mj_res = _mj.load()[0]
    mj_idx = {(r_.date, frozenset((mcn(r_.home_team), mcn(r_.away_team)))) for r_ in mj_res.itertuples()}
    date_fix = {}
    lineup_rows, detail_events, manager_rows, sub_mismatch = [], [], [], []
    conflicts, unresolved, upd, ev = [], [], {}, []
    n_complete = n_partial = n_linked = 0
    for r in df.itertuples():
        h, a = tid(r.home, r.home_target, r.home_cc), tid(r.away, r.away_target, r.away_cc)
        if h is None or a is None:
            unresolved.append(dict(season_id=r.season_id, date=r.date, home=f"{r.home_target}|{r.home_cc}", away=f"{r.away_target}|{r.away_cc}"))
            continue
        cands = [x for x in by.get((r.season_id, frozenset((h, a))), []) if abs((x.match_date - r.date).days) <= 1]
        if len(cands) != 1:
            conflicts.append(dict(season_id=r.season_id, kind="no_unique_match", date=r.date, match=f"{r.home_target or r.home_cc} v {r.away_target or r.away_cc}",
                                  ours=f"{len(cands)} candidates", wikipedia=str(r.score)))
            continue
        x = cands[0]
        n_linked += 1
        same_side = x.home_team_id == h
        sc = r.score if same_side else (r.score[1], r.score[0])
        u = {}
        if pd.notna(x.home_score) and ((int(x.home_score), int(x.away_score)) != sc or x.match_date != r.date):
            same_score = (int(x.home_score), int(x.away_score)) == sc
            wn = (names.get(r.home_cc) or r.home_target or r.home, names.get(r.away_cc) or r.away_target or r.away)
            mj_agrees = (r.date, frozenset((mcn(wn[0]), mcn(wn[1])))) in mj_idx
            if same_score and x.match_date != r.date and mj_agrees and x.primary_provider != "martj42":
                # three sources: the primary disagrees, martj42 and Wikipedia agree -> majority date (original recorded)
                date_fix[x.match_id] = (r.date, f"corrected {x.match_date} -> {r.date}: martj42 and Wikipedia agree against {x.primary_provider}")
            else:
                conflicts.append(dict(season_id=r.season_id, kind="score_or_date", date=r.date, match=f"{r.home_target or r.home_cc} v {r.away_target or r.away_cc}",
                                      ours=f"{x.match_date} {x.home_score}-{x.away_score} [{x.primary_provider}]", wikipedia=f"{r.date} {sc[0]}-{sc[1]}"))
                if not same_score:   # never overwrite; attach the other source's score as a note (e.g. abandoned / awarded results)
                    u["score_note"] = f"Wikipedia lists {sc[0]}-{sc[1]} (on-pitch score kept; the match may have been abandoned or the result awarded)"
        if pd.isna(x.referee_raw) and r.referee:
            u["referee_raw"] = f"{r.referee} ({r.referee_country})" if r.referee_country else r.referee
        if pd.isna(x.attendance) and pd.notna(r.attendance):      # 0 is a real value: match played behind closed doors
            u["attendance"] = r.attendance
        if r.stadium and (x.venue_raw is None or pd.isna(x.venue_raw) or x.primary_provider == "martj42"):
            u["venue_raw"] = r.stadium            # martj42 only has "city, country"; the stadium is more specific
        if r.stadium_links:
            cur = x.venue_wikipedia_title if "venue_wikipedia_title" in m.columns else None
            if cur is None or pd.isna(cur):
                u["venue_wikipedia_title"] = r.stadium_links[0][0]
                if len(r.stadium_links) > 1:
                    u["venue_city_raw"] = r.stadium_links[1][1]
        if r.stage and (x.stage is None or pd.isna(x.stage)):
            u["stage"] = r.stage
            u["stage_raw"] = r.heading
        if r.group and (x.group is None or pd.isna(x.group)):
            u["group"] = r.group
        if u:
            upd[x.match_id] = u
        d = r.detail
        if d:
            t1_id, t2_id = (x.home_team_id, x.away_team_id) if same_side else (x.away_team_id, x.home_team_id)
            for side_id, tm in ((t1_id, d["team1"]), (t2_id, d["team2"])):
                offs, ons = {}, {}
                for pl in tm["players"]:
                    lineup_rows.append(dict(match_id=x.match_id, team_id=side_id, player_id=None, player_name_raw=pl["name"],
                                            jersey_number=pl["number"], is_starter=pl["starter"],
                                            appeared=bool(pl["starter"] or pl["on"]), is_captain=pl["captain"],
                                            positions=json.dumps([{"position": pl["position"]}]), cards=json.dumps(pl["cards"]),
                                            minute_on=pl["on"][0] if pl["on"] else None, minute_off=pl["off"][0] if pl["off"] else None,
                                            minutes_played_derived=None, source_player_id=None, provider="wikipedia"))
                    for c in pl["cards"]:
                        detail_events.append(dict(event_id=f"WP-{x.match_id}-c{len(detail_events)}", match_id=x.match_id,
                                                  event_type="card", detail_type=c["card"], player_id=None,
                                                  player_name_raw=pl["name"], team_id=side_id, minute=c["minute"],
                                                  minute_added=c["added"], card=c["card"], outcome=None, provider="wikipedia",
                                                  source_id=f"{r.page}#{r.date}:{pl['name']}:{c['card']}:{c['minute']}", source_url=r.source_url))
                    if pl["off"]:
                        offs.setdefault(pl["off"], []).append(pl["name"])
                    if pl["on"]:
                        ons.setdefault(pl["on"], []).append(pl["name"])
                for key in sorted(set(offs) | set(ons), key=lambda k: (k[0], k[1] or 0)):           # pair the n-th player off with the n-th player on at that minute
                    o, n_ = offs.get(key, []), ons.get(key, [])
                    if len(o) != len(n_):
                        sub_mismatch.append(dict(match_id=x.match_id, minute=key[0], off=len(o), on=len(n_)))
                    for po, pn in zip(o, n_):
                        detail_events.append(dict(event_id=f"WP-{x.match_id}-s{len(detail_events)}", match_id=x.match_id,
                                                  event_type="substitution", detail_type=None, player_id=None, player_name_raw=po,
                                                  related_player_name_raw=pn, team_id=side_id, minute=key[0], minute_added=key[1],
                                                  card=None, outcome=None, provider="wikipedia",
                                                  source_id=f"{r.page}#{r.date}:{po}>{pn}:{key[0]}", source_url=r.source_url))
                if tm["manager"]:
                    manager_rows.append(dict(match_id=x.match_id, team_id=side_id, manager_raw=tm["manager"], provider="wikipedia"))
            for col, val in (("man_of_the_match_raw", d["man_of_the_match"]), ("assistant_referees_raw", d["assistant_referees"]),
                             ("fourth_official_raw", d["fourth_official"]), ("var_officials_raw", d["var_officials"])):
                if val:
                    upd.setdefault(x.match_id, {})[col] = val
        g1, g2 = (r.goals1, r.goals2) if same_side else (r.goals2, r.goals1)
        if (len(g1), len(g2)) == sc and sum(sc) > 0:
            n_complete += 1
            k = 0
            for team, lst in ((x.home_team_id, g1), (x.away_team_id, g2)):
                for gl in lst:
                    k += 1
                    ev.append(dict(event_id=f"WP-{x.match_id}-g{k}", match_id=x.match_id, event_type="goal", detail_type=gl["flag"],
                                   player_id=None, player_name_raw=gl["scorer"], team_id=team, minute=gl["minute"], minute_added=gl["added"],
                                   second=None, period=None, timestamp=None, location_x=None, location_y=None, end_location_x=None,
                                   end_location_y=None, outcome="Goal", related_player_id=None, card=None, xg=None, is_goal=True,
                                   is_penalty=True if gl["flag"] == "penalty" else None, is_own_goal=True if gl["flag"] == "own_goal" else None,
                                   source_id=f"{r.page}#{r.date}", provider="wikipedia", coordinate_system=None, tags="[]", source_url=r.source_url))
        elif sum(sc) > 0:
            n_partial += 1
    mi = m.set_index("match_id")
    for col in ("man_of_the_match_raw", "assistant_referees_raw", "fourth_official_raw", "var_officials_raw",
                "venue_wikipedia_title", "venue_city_raw"):
        if col not in mi.columns:
            mi[col] = None
    for mid, u in upd.items():
        for c, v in u.items():
            if c.endswith("_raw") and c in ("man_of_the_match_raw", "assistant_referees_raw", "fourth_official_raw", "var_officials_raw"):
                if pd.notna(mi.at[mid, c]):
                    continue                                   # fill-null only
            mi.at[mid, c] = v
    for mid, (d, why) in date_fix.items():          # match_id keeps the as-ingested date, so ids stay stable across runs
        mi.at[mid, "match_date"] = d
        mi.at[mid, "date_check"] = why
    out = mi.reset_index()
    out["attendance"] = pd.to_numeric(out["attendance"]).astype("Int64")
    out.to_parquet(PROC / "matches.parquet", index=False)
    out.to_csv(PROC / "matches.csv", index=False)
    (PROC / "wikipedia").mkdir(exist_ok=True)
    pd.DataFrame(ev).to_parquet(PROC / "wikipedia" / "goal_events_wikipedia.parquet", index=False)
    pd.DataFrame(lineup_rows).to_parquet(PROC / "wikipedia" / "lineups_wikipedia.parquet", index=False)
    pd.DataFrame(detail_events).to_parquet(PROC / "wikipedia" / "detail_events_wikipedia.parquet", index=False)
    pd.DataFrame(manager_rows).to_parquet(PROC / "wikipedia" / "managers_wikipedia.parquet", index=False)
    pd.DataFrame(sub_mismatch, columns=["match_id", "minute", "off", "on"]).to_csv(DATA / "quality" / "wikipedia_sub_pairing_mismatches.csv", index=False)
    q = DATA / "quality"
    q.mkdir(exist_ok=True)
    pd.DataFrame(conflicts, columns=["season_id", "kind", "date", "match", "ours", "wikipedia"]).to_csv(q / "wikipedia_vs_matches_conflicts.csv", index=False)
    pd.DataFrame(unresolved, columns=["season_id", "date", "home", "away"]).to_csv(q / "wikipedia_unresolved_teams.csv", index=False)
    return dict(wikipedia_only_matches_added=added, boxes=len(df), linked=n_linked, updated_matches=len(upd), conflicts=len(conflicts), unresolved=len(unresolved),
                goal_lists_complete=n_complete, goal_lists_partial=n_partial, goal_events=len(ev), dates_corrected=len(date_fix),
                lineup_rows=len(lineup_rows), card_and_sub_events=len(detail_events), managers=len(manager_rows), sub_pairing_mismatches=len(sub_mismatch))


if __name__ == "__main__":
    df = scope_boxes()
    c = df.groupby(["competition_id", "season_id"]).agg(boxes=("date", "size"), with_referee=("referee", "count"),
                                                         with_attendance=("attendance", "count"))
    print(len(df), "boxes parsed\n", c.to_string())
