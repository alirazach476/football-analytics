"""Spanish Wikipedia (CC BY-SA 4.0, official MediaWiki API) as a SECOND route to attendance where the English page leaves it empty.

Pages with `{{Partidos|local|resultado|visita|fecha|estadio|ciudad|refe|asistencia}}` entries:
  * Copa America 2011 (the 18 group matches have no attendance on en.wikipedia)
  * Nations League 2020-21 League A-D annex pages (two matches without attendance)
Rules: fill-null only; a match is linked by season + date (+-1 day) + both teams; "Sin datos" (no data) stays null;
the value is recorded in `attendance_source` ('es.wikipedia') because Spanish figures are often rounded estimates ("35 000").
"""
from __future__ import annotations

import json
import re
from datetime import date
from urllib.parse import quote

import mwparserfromhell as mw
import pandas as pd

from ..config import DATA
from ..http import HttpClient
from .build import PROC
from .wikipedia_matches import _nat_index, resolve_codes

API = "https://es.wikipedia.org/w/api.php"
PAGES = {  # page title -> season
    "Copa América 2011": "COPA-2011",
    "Anexo:Liga A de la Liga de Naciones de la UEFA 2020-21": "UNL-2020-21",
    "Anexo:Liga B de la Liga de Naciones de la UEFA 2020-21": "UNL-2020-21",
    "Anexo:Liga C de la Liga de Naciones de la UEFA 2020-21": "UNL-2020-21",
    "Anexo:Liga D de la Liga de Naciones de la UEFA 2020-21": "UNL-2020-21",
}
MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
          "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def fetch(c: HttpClient, title: str):
    j = json.loads(c.get(f"{API}?action=parse&format=json&formatversion=2&redirects=1&prop=wikitext%7Crevid&page={quote(title)}").content)
    return (j["parse"]["wikitext"], j["parse"]["revid"]) if "parse" in j else (None, None)


def _team(v: str):
    """-> (3-letter code | None, country name | None) from {{self-d|BRA}}, {{selb|VEN}}, {{bandera|Bolivia}} ..."""
    for t in mw.parse(v or "").filter_templates():
        p = [str(x.value).strip() for x in t.params if not x.showkey]
        if p:
            return (p[0], None) if re.fullmatch(r"[A-Z]{3}", p[0]) else (None, p[0])
    return None, None


def _date(v: str):
    t = (v or "").lower()
    m = re.search(r"\{\{\s*fecha\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*\|\s*(\d{4})", t)          # {{fecha|7|9|2020}}
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r"(\d{1,2})\s+de\s+([a-z\u00e1\u00e9\u00ed\u00f3\u00fa]+)\s+de\s+(\d{4})", t)
    if m and m.group(2) in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    return None


def _att(v: str):
    t = re.sub(r"<ref.*?(</ref>|/>)", "", v or "", flags=re.S)
    t = re.sub(r"&nbsp;|\s", "", t)
    m = re.match(r"^(\d{1,3}(?:[.,]\d{3})+|\d+)", t)
    return int(re.sub(r"[.,]", "", m.group(1))) if m else None


def parse_page(text: str):
    text = text.replace("'''", "")        # stray bold markers inside `resultado = '''1:1''' (1:0)` break the template parser
    out = []
    for t in mw.parse(text).filter_templates():
        if str(t.name).strip().lower() not in ("partidos", "partido"):
            continue
        g = lambda k: str(t.get(k).value).strip() if t.has(k) else ""
        res = re.search(r"(\d+)\s*[:\u2013-]\s*(\d+)", g("resultado"))
        d = _date(g("fecha"))
        if not res or d is None:
            continue
        hc, ac = g("pa\u00edslocal"), g("pa\u00edsvisita")           # explicit 3-letter codes when present
        home = (hc, None) if re.fullmatch(r"[A-Z]{3}", hc) else _team(g("local"))
        away = (ac, None) if re.fullmatch(r"[A-Z]{3}", ac) else _team(g("visita"))
        out.append(dict(date=d, home=home, away=away, score=(int(res.group(1)), int(res.group(2))), attendance=_att(g("asistencia"))))
    return out


def run():
    c = HttpClient("wikipedia_es", 1.0)
    m = pd.read_parquet(PROC / "matches.parquet")
    if "attendance_source" not in m.columns:
        m["attendance_source"] = None
    m.loc[m.attendance.notna() & m.attendance_source.isna(), "attendance_source"] = "en.wikipedia"
    rows = []
    for title, sid in PAGES.items():
        text, rev = fetch(c, title)
        if text:
            rows += [{**r, "season_id": sid, "page": title, "revid": rev} for r in parse_page(text)]
    names = resolve_codes({code for r in rows for code in (r["home"][0], r["away"][0]) if code})
    idx, cn = _nat_index()

    def tid(code, name):
        for nm in (names.get(code), name):
            if nm and cn(nm) in idx:
                return idx[cn(nm)]
        return None

    by = {}
    for r in m.itertuples():
        by.setdefault((r.season_id, frozenset((r.home_team_id, r.away_team_id))), []).append(r)
    filled, no_data, unlinked = 0, 0, 0
    for r in rows:
        h, a = tid(*r["home"]), tid(*r["away"])
        cands = [x for x in by.get((r["season_id"], frozenset((h, a))), []) if abs((x.match_date - r["date"]).days) <= 1] if h and a else []
        if len(cands) != 1:
            unlinked += 1
            continue
        x = cands[0]
        if pd.isna(x.attendance):
            if r["attendance"] is None:
                no_data += 1
            else:
                m.loc[m.match_id == x.match_id, ["attendance", "attendance_source"]] = [r["attendance"], "es.wikipedia (often a rounded estimate)"]
                filled += 1
    m["attendance"] = pd.to_numeric(m["attendance"]).astype("Int64")
    m.to_parquet(PROC / "matches.parquet", index=False)
    m.to_csv(PROC / "matches.csv", index=False)
    return dict(es_entries=len(rows), attendance_filled=filled, es_has_no_data=no_data, unlinked=unlinked)


if __name__ == "__main__":
    print(run())
