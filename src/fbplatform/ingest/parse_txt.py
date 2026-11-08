"""Parser for OpenFootball Football.TXT match files (Euro 2004-16, Copa, Champions League).

Design rules
* Nothing is guessed. If a value is not stated (or its meaning is ambiguous) it stays None and the
  verbatim score text is kept in `score_raw` / `parse_notes`.
* The `(x-y)` after an extra-time/penalty score means different things in different files
  (half-time in Euro 2016, 90-minute score in Euro 2008). It is only interpreted where the format
  makes it unambiguous: a single (x-y) after a plain 90-minute score = half-time; two values
  `(a-b, c-d)` = (90-minute score, half-time) as used in the Champions League files.
* Every match line carries its 1-based line number so the source can be re-checked.
"""
from __future__ import annotations

import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
WD = r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?|Mo|Tu|We|Th|Fr|Sa|Su)"  # 3-letter+ or 2-letter (Euro 2008)
DATE_A = re.compile(rf"^(?:(?P<wd>{WD})\s+)?(?P<mon>[A-Za-z]{{3,9}})\.?\s+(?P<day>\d{{1,2}})(?:\s+(?P<year>\d{{4}}))?(?=\s|$)")
DATE_B = re.compile(rf"^(?:(?P<wd>{WD})\s+)?(?P<day>\d{{1,2}})\s+(?P<mon>[A-Za-z]{{3,9}})\.?(?:\s+(?P<year>\d{{4}}))?(?=\s|$)")
TIME = re.compile(r"^(?P<t>\d{1,2}:\d{2})(?P<rest>(?:\s*\([^)]*\))?(?:\s*UTC(?P<tz>[+-]\d{1,2})(?::(?P<tzm>\d{2}))?)?)")
SCORE_AT = re.compile(r"\s(\d+-\d+)(?=\s|$)")
SB = re.compile(r"(\d+-\d+(?:\s+(?:pen\.?|a\.e\.t\.|\d+-\d+|\([\d\-,\s]+\)))*)(?=\s|$)")
EXTRA = re.compile(r"\((?:aet|a\.e\.t)[^)]*\)")
CC = re.compile(r"\s*\(([A-Z]{3})\)\s*$")
GROUP_LIST = re.compile(r"^(Group|Gruppe)\s+[A-L]\s*\|")


def _month(tok):
    return MONTHS.get(tok[:3].lower()) if tok[:3].lower() in MONTHS else None


def parse_date(text, year_ctx):
    """Returns (month, day, explicit_year|None, end_pos) or None."""
    for rx in (DATE_A, DATE_B):
        m = rx.match(text)
        if m and _month(m["mon"]):
            return _month(m["mon"]), int(m["day"]), (int(m["year"]) if m["year"] else None), m.end(), m["wd"]
    return None


def parse_score_block(sb: str, extra: str | None = None) -> dict:
    toks = re.findall(r"pen\.?|a\.e\.t\.|\d+-\d+|\([^)]*\)", sb)
    pair = lambda t: tuple(int(x) for x in t.split("-"))
    scores = [pair(t) for t in toks if re.fullmatch(r"\d+-\d+", t)]
    parens = [t for t in toks if t.startswith("(")]
    has_pen = any(t.startswith("pen") for t in toks)
    has_aet = "a.e.t." in toks or bool(extra and "aet" in extra.replace(".", ""))
    out = dict(score=None, ft=None, et=None, pen=None, ht=None, basis=None, went_et=None, note=None)
    inner = None
    if parens:
        vals = re.findall(r"\d+-\d+", parens[-1])
        inner = [pair(v) for v in vals]
    if extra:
        mp = re.search(r"(\d+)-(\d+)\s*pen", extra)
        if mp:
            has_pen = True
            out["pen"] = (int(mp[1]), int(mp[2]))
    if not has_pen and not has_aet:
        out.update(score=scores[0], ft=scores[0], basis="ft90", went_et=False)
        if inner and len(inner) == 1:
            out["ht"] = inner[0]
        return out
    out["went_et"] = True
    if has_pen and out["pen"] is None:
        out["pen"] = scores[0]
        rest = scores[1:]
    else:
        rest = scores
    if has_aet and rest:
        out.update(score=rest[0], et=rest[0], basis="aet")
    elif has_pen and not rest and inner and len(inner) == 1:
        out.update(score=inner[0], basis="unspecified_after_extra_time_or_90")
        out["note"] = "score taken from parenthesis of pen. form; 90/120 minute basis not stated"
        return out
    elif has_aet:
        out.update(score=scores[0], et=scores[0], basis="aet")
    if inner and len(inner) == 2:  # (90-minute score, half-time) convention
        out["ft"], out["ht"] = inner
    elif inner and len(inner) == 1:
        out["note"] = f"parenthesis {inner[0][0]}-{inner[0][1]} not interpreted (half-time vs 90-minute is ambiguous in this file)"
    return out


def normalize_stage(h: str):
    """Header/round text -> (stage, group, matchday, leg_from_header). stage None if unrecognised."""
    t = h.strip()
    m = re.fullmatch(r"(?:Group|Gruppe)\s+([A-L])", t)
    if m:
        return "Group stage", m[1], None, None
    m = re.fullmatch(r"Group,\s*Matchday\s+(\d+)", t)
    if m:
        return "Group stage", None, int(m[1]), None
    m = re.fullmatch(r"League,\s*Matchday\s+(\d+)", t)
    if m:
        return "League phase", None, int(m[1]), None
    m = re.fullmatch(r"Playoffs,\s*Matchday\s+(\d+)", t)
    if m:
        return "Knockout play-off", None, None, int(m[1])
    t = re.sub(r"^Finals,\s*", "", t)
    low = t.lower().replace("-", "").replace(" ", "")
    for key, name in (("roundof32", "Round of 32"), ("roundof16", "Round of 16"),
                      ("quarterfinal", "Quarter-finals"), ("semifinal", "Semi-finals"),
                      ("thirdplace", "Third place"), ("matchforthirdplace", "Third place"), ("final", "Final")):
        if low.startswith(key):
            return name, None, None, None
    m = re.fullmatch(r"Matchday\s+(\d+)", t)
    if m:
        return "Group stage", None, int(m[1]), None
    return None, None, None, None


def parse_file(text: str, season_year: int, url: str, inherit_time: bool = False, split_season: bool = False) -> tuple[list[dict], list[str]]:
    """Parse one file. Returns (matches, unparsed_candidate_lines)."""
    rows, unparsed = [], []
    stage_raw = group = matchday = leg = None
    stage = None
    cur_date = cur_time = cur_tz = cur_timenote = None
    year = season_year
    date_check = None
    detail_open = False
    for ln_no, line in enumerate(text.splitlines(), 1):
        st = line.strip()
        if not st:
            detail_open = False
            continue
        if st[0] in "#=":
            continue
        if st.startswith("▪"):  # section header marker
            detail_open = False
            body = st.lstrip("▪").strip()
            if "|" in body:  # schedule summary like "Matchday 1 | Jun 10 - Jun 14"
                continue
            body = re.sub(r"\s+#.*$", "", body)
            s, g, md, lg = normalize_stage(body)
            stage_raw, stage, group, matchday, leg = body, s, g, md, lg
            continue
        if GROUP_LIST.match(st):
            continue
        if st.startswith("(") and rows and detail_open:
            rows[-1]["raw_text"] += "\n" + st
            continue
        rest = re.sub(r"\s+#.*$", "", st)
        d = parse_date(rest, year)
        if d:
            mon, day, yr, end, wd = d
            # Year: calendar tournaments use the edition year; split seasons (Jul-Jun) use the start
            # year for Jul-Dec and start+1 for Jan-Jun. Never inferred from line order (groups restart dates).
            default = (season_year if mon >= 7 else season_year + 1) if split_season else season_year
            cands = [default] + ([default - 1, default + 1] if split_season else [])
            year = default
            date_check = "no_weekday"
            if wd:
                date_check = "weekday_mismatch"
                for y in cands:
                    try:
                        if date(y, mon, day).strftime("%a").lower().startswith(wd[:2].lower()):
                            year, date_check = y, ("weekday_ok" if y == default else "weekday_year_adjusted")
                            break
                    except ValueError:
                        pass
            if yr and yr != year:
                date_check += "+explicit_year_disagrees"
            cur_date = date(year, mon, day)
            cur_time = cur_tz = cur_timenote = None
            rest = rest[end:].strip()
            if not rest:
                continue
        mt = TIME.match(rest)
        has_time = False
        if mt:
            cur_time = mt["t"].zfill(5)
            cur_tz = (int(mt["tz"]) * 60 + (int(mt["tzm"] or 0)) * (1 if int(mt["tz"]) >= 0 else -1)) if mt["tz"] else None
            cur_timenote = mt["rest"].strip() or None
            rest = rest[mt.end():].strip()
            has_time = True
        elif cur_time and not inherit_time:
            cur_time = cur_tz = cur_timenote = None
        rec = _parse_match(rest)
        if rec is None:
            if detail_open and rows:
                rows[-1]["raw_text"] += "\n" + st
            elif re.search(r"\d+-\d+|\sv\s", st):
                unparsed.append(f"{ln_no}: {st}")
            continue
        sc = rec.pop("score_info")
        rows.append({**rec, **{
            "line_no": ln_no, "source_url": f"{url}#L{ln_no}", "raw_text": line.rstrip(),
            "stage_raw": stage_raw, "stage": stage, "group": group, "matchday": matchday, "leg_header": leg,
            "date": cur_date, "date_check": date_check, "time_local": cur_time, "tz_offset_min": cur_tz, "time_note": cur_timenote,
            "score": sc["score"], "ft": sc["ft"], "et": sc["et"], "pen": sc["pen"], "ht": sc["ht"],
            "score_basis": sc["basis"], "went_extra_time": sc["went_et"], "score_note": sc["note"]}})
        detail_open = True
    return rows, unparsed


def _split_cc(name: str):
    name = name.strip()
    m = CC.search(name)
    return (name[:m.start()].strip(), m[1]) if m else (name, None)


def _parse_match(rest: str):
    """Parse the part of a line after date/time. Returns None if it is not a match line."""
    if " v " in rest:  # Champions League style: "Team (CC) v Team (CC)  1-0 (0-0)"
        left, right = rest.split(" v ", 1)
        padded = " " + right
        ms = SCORE_AT.search(padded)
        if ms:
            t2 = padded[:ms.start()].strip()
            sbm = SB.match(padded[ms.start():].strip())
            sb = sbm.group(1)
            sc = parse_score_block(sb)
        else:
            t2, sb, sc = right.strip(), None, _empty()
        if not left.strip() or not t2:
            return None
        h, hc = _split_cc(left)
        a, ac = _split_cc(t2)
        return dict(home_raw=h, away_raw=a, home_cc=hc, away_cc=ac, venue_raw=None, score_info=sc, score_raw=sb)
    # Euro 2000 style: "@ Liege   Germany   1-1 Romania" - the venue comes BEFORE the teams (two or more spaces end it)
    lead_venue = None
    mv = re.match(r"^@\s*(.+?)\s{2,}(\S.*)$", rest)
    if mv:
        lead_venue, rest = mv.group(1).strip(), mv.group(2)
    padded = " " + rest
    ms = SCORE_AT.search(padded)
    if not ms:
        return None
    t1 = padded[:ms.start()].strip()
    tail = padded[ms.start():].strip()
    sbm = SB.match(tail)
    if not t1 or not sbm:
        return None
    sb = sbm.group(1)
    after = tail[sbm.end():].strip()
    venue = lead_venue
    if "@" in after:
        after, venue = after.split("@", 1)
        venue = venue.strip() or None
    extra = EXTRA.search(after)
    ex = extra.group(0) if extra else None
    t2 = EXTRA.sub("", after).strip()
    if not t2:
        return None
    sc = parse_score_block(sb, ex)
    return dict(home_raw=t1, away_raw=t2, home_cc=None, away_cc=None, venue_raw=venue, score_info=sc,
                score_raw=sb + (f" {ex}" if ex else ""))


def _empty():
    return dict(score=None, ft=None, et=None, pen=None, ht=None, basis=None, went_et=None, note=None)
