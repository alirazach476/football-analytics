"""Match-detail sections of Wikipedia tournament pages (the part a match's score links to):
line-ups with shirt numbers/positions/captain, yellow & red cards with minutes, substitutions, managers,
Man of the Match and officials.  Parsed from the wikitext already fetched through the MediaWiki API (CC BY-SA 4.0).

What it can give: player NAMES (raw text, no player ids), shirt numbers, positions, minutes of cards / substitutions.
What it cannot: coordinates, passes, shots, xG - Wikipedia does not hold them.
Every figure is validated against an independent provider where one exists (see wikipedia_details_validation.csv).
"""
from __future__ import annotations

import re

from .wikipedia_matches import strip_markup

TABLE = re.compile(r'\{\|[^\n]*font-size[^\n]*\n(.*?)\n\|\}', re.S)
LINEUP = re.compile(r"\|\s*GK\s*\|\|")
SENT_OFF = re.compile(r"\{\{\s*sent\s?off\s*\|\s*(\d)\s*\|\s*(\d{1,3})(?:\s*\+\s*(\d{1,2}))?(?:\s*\|\s*(\d{1,3})(?:\s*\+\s*(\d{1,2}))?)?\s*\}\}", re.I)
ROW_SPLIT = re.compile(r"\n\|-[ \t]*")
TPL = re.compile(r"\{\{\s*(yel|red|suboff|subon)\s*\|\s*(\d{1,3})(?:\s*\+\s*(\d{1,2}))?\s*(?:\|[^{}]*)?\}\}", re.I)
CAPTAIN = re.compile(r"\(\s*\[\[Captain[^\]]*\]\]\s*\)|\(\s*c\s*\)", re.I)


def _name(cell: str) -> str:
    cell = CAPTAIN.sub("", cell)
    cell = re.sub(r"\{\{[^{}]*\}\}", "", cell)
    return strip_markup(cell).strip(" '")


def parse_team_table(body: str) -> dict:
    players, mode, manager, expect_manager = [], "starters", None, False
    for row in ROW_SPLIT.split(body):
        row = row.strip()
        if not row or row.startswith("!"):
            continue
        low = row.lower()
        if "'''substitut" in low:
            mode = "subs"
            continue
        if "'''manager" in low or "'''coach" in low or "'''head coach" in low:
            expect_manager = True
            continue
        if expect_manager:
            manager = _name(re.sub(r"^colspan\s*=\s*\"?\d\"?\s*\|", "", row)) or None
            expect_manager = False
            continue
        cells = row.lstrip("|").split("||")
        if len(cells) < 3:
            continue
        pos, num = cells[0].strip(), re.sub(r"\D", "", cells[1])
        if not re.fullmatch(r"[A-Z]{2,3}", pos):
            continue
        rest = " || ".join(cells[3:])
        ev = [(m.group(1).lower(), int(m.group(2)), int(m.group(3)) if m.group(3) else None) for m in TPL.finditer(rest)]
        cards = []
        for k, a, b in ev:
            if k == "yel":
                cards.append(dict(card="Yellow Card", minute=a, added=b))
            elif k == "red":
                cards.append(dict(card="Red Card", minute=a, added=b))
        for m in SENT_OFF.finditer(rest):
            n, m1, a1, m2, a2 = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4), m.group(5)
            if n == 0:                                            # straight red at m1
                cards.append(dict(card="Red Card", minute=m1, added=int(a1) if a1 else None))
            elif n == 1 and m2:                                   # a yellow at m1, then a straight red at m2
                cards.append(dict(card="Yellow Card", minute=m1, added=int(a1) if a1 else None))
                cards.append(dict(card="Red Card", minute=int(m2), added=int(a2) if a2 else None))
            elif n == 2 and m2:                                   # a yellow at m1, second yellow (dismissal) at m2
                cards.append(dict(card="Yellow Card", minute=m1, added=int(a1) if a1 else None))
                cards.append(dict(card="Second Yellow", minute=int(m2), added=int(a2) if a2 else None))
            else:
                cards.append(dict(card="Red Card", minute=m1, added=int(a1) if a1 else None))
        seen_c, uniq = set(), []
        for c in sorted(cards, key=lambda c: (c["minute"], c["added"] or 0)):
            key = (c["card"], c["minute"], c["added"])
            if key not in seen_c:
                seen_c.add(key)
                uniq.append(c)
        cards = uniq
        on = next(((a, b) for k, a, b in ev if k == "subon"), None)
        off = next(((a, b) for k, a, b in ev if k == "suboff"), None)
        players.append(dict(position=pos, number=int(num) if num else None, name=_name(cells[2]),
                            captain=bool(CAPTAIN.search(cells[2])), starter=(mode == "starters"),
                            on=on, off=off, cards=cards))
    return dict(players=players, manager=manager)


def _after(label: str, text: str) -> str | None:
    m = re.search(label + r"[^\n]*?'''\s*:?\s*(?:<br\s*/?>)?\s*(.+?)(?=<ref|\n\n|<br\s*/?>\s*'''|$)", text, re.S | re.I)
    return strip_markup(m.group(1)) if m else None


def parse_details(region: str) -> dict | None:
    """region = wikitext from one football box up to the next one. Returns None if no two line-up tables."""
    tables = [t for t in TABLE.findall(region) if LINEUP.search(t)]
    if len(tables) < 2:
        return None
    t1, t2 = parse_team_table(tables[0]), parse_team_table(tables[1])
    motm = _after(r"'''Man of the Match", region)
    after_tables = region
    def officials(label, nxt):
        m = re.search(label + r".*?(?=" + nxt + r"|$)", after_tables, re.S | re.I)
        if not m:
            return None
        names = [strip_markup(x) for x in re.findall(r"<br\s*/?>\s*([^<\n]+)", m.group(0)) if not x.strip().startswith("'''")]
        names = [n for n in names if n and not n.lower().startswith(("fourth", "assistant", "video"))]
        return "; ".join(names) or None
    return dict(team1=t1, team2=t2, man_of_the_match=motm,
                assistant_referees=officials(r"Assistant referees", r"'''\[\[Assistant referee \(association football\)#Fourth|Fourth official|Video assistant|Match rules"),
                fourth_official=officials(r"Fourth official", r"Video assistant|Match rules|Reserve"),
                var_officials=officials(r"Video assistant referee", r"Match rules|Reserve|Fourth"))


def box_regions(wikitext: str):
    """[(params dict, nearest heading, region_text, heading_chain)] - region runs from a box to the next box.
    heading_chain lists the enclosing headings outermost -> nearest (e.g. ['Round of 16', 'Argentina vs Mexico'])."""
    import mwparserfromhell as mw
    from .wikipedia import _norm_name
    from .wikipedia_matches import HEAD
    heads = [(m.start(), len(m.group(1)), m.group(2)) for m in HEAD.finditer(wikitext)]
    clean = lambda h: re.sub(r"\[\[|\]\]|<[^>]+>|\{\{[^}]*\}\}", "", h).strip()
    found, cursor = [], 0
    for t in mw.parse(wikitext).filter_templates():
        if _norm_name(t).startswith(("footballbox", "#invoke:footballbox")):
            pos = wikitext.find(str(t), cursor)         # search forward: two boxes can share the same first 80 characters
            if pos < 0:
                pos = wikitext.find(str(t)[:80], cursor)
            cursor = pos + 1
            stack = []
            for hp, lvl, text in heads:
                if hp > pos:
                    break
                while stack and stack[-1][0] >= lvl:
                    stack.pop()
                stack.append((lvl, clean(text)))
            chain = [h for _, h in stack]
            found.append((pos, {str(p.name).strip(): str(p.value).strip() for p in t.params}, chain[-1] if chain else None, chain))
    found.sort(key=lambda x: x[0])
    out = []
    for i, (pos, params, head, chain) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(wikitext)
        out.append((params, head, wikitext[pos:end], chain))
    return out


if __name__ == "__main__":
    import collections
    from .wikipedia_matches import cached_wikitext, season_of_page
    stat = collections.defaultdict(lambda: collections.Counter())
    for title, rev, text, _ in cached_wikitext():
        sp = season_of_page(title)
        if not sp:
            continue
        for params, head, region, chain in box_regions(text):
            d = parse_details(region)
            s = stat[sp[1]]
            s["boxes"] += 1
            if d:
                s["with_tables"] += 1
                s["both_11_starters"] += int(sum(p["starter"] for p in d["team1"]["players"]) == 11 and sum(p["starter"] for p in d["team2"]["players"]) == 11)
                s["motm"] += bool(d["man_of_the_match"])
                s["assistants"] += bool(d["assistant_referees"])
    for k in sorted(stat):
        print(k, dict(stat[k]))
