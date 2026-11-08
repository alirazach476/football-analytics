"""Venue registry (the `venues` table) and `matches.venue_id`.

Identity: the stadium's Wikipedia article (the hyperlink in every match box), after resolving redirects through the official
MediaWiki API; the Wikidata item of that article gives the id (`V-Q123`), else `V-<slug>`.  Two spellings that redirect to the same
article are one venue; two different stadiums are never merged by name.
Attributes and where they come from
  name / wikidata_id / latitude / longitude : MediaWiki API (coordinates + pageprops) - null where the article has none
  capacity                                  : the article's infobox (first number >= 1,000); as written there, null if absent
  city                                      : the city link in the match boxes (most frequent); country: martj42 `country` of the
                                              matches played there (most frequent; every other value kept in country_values_seen)
  name_variants / n_matches / first_match / last_match : computed from our matches
Checks written to data/quality/venues_checks.csv: every match has a venue, one country per venue, attendance vs capacity.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import quote

import pandas as pd

from ..config import DATA
from ..http import HttpClient
from .build import PROC, norm
from .martj42 import cn, load
from .wikipedia import API
from .wikipedia_matches import strip_markup

BATCH = 25


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")


def _capacity(wikitext: str):
    m = re.search(r"\|\s*capacity\s*=\s*(.+)", wikitext)
    if not m:
        return None
    line = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", m.group(1), flags=re.S)
    line = re.sub(r"\{\{\s*(?:nowrap|small|nobr)\s*\|([^{}]*)\}\}", r"\1", line, flags=re.I)
    for n in re.findall(r"\d{1,3}(?:,\d{3})+|\d{4,}", line):
        v = int(n.replace(",", ""))
        if v >= 1000:
            return v
    return None


def _coord_from_text(text: str):
    for m in re.finditer(r"\{\{\s*coord\s*\|([^{}]*)\}\}", text, re.I):
        parts = [x.strip() for x in m.group(1).split("|") if x.strip() and "=" not in x and ":" not in x]
        try:
            dms = any(x in ("N", "S", "E", "W") for x in parts)                    # degrees|minutes|seconds|N|... carries a hemisphere letter
            if not dms and len(parts) >= 2 and re.fullmatch(r"-?\d+(\.\d+)?", parts[0]) and re.fullmatch(r"-?\d+(\.\d+)?", parts[1]):
                return float(parts[0]), float(parts[1])
            lat, i = [], 0
            while parts[i] not in ("N", "S"):
                lat.append(float(parts[i]))
                i += 1
            ns, i, lon = parts[i], i + 1, []
            while parts[i] not in ("E", "W"):
                lon.append(float(parts[i]))
                i += 1
            conv = lambda xs: sum(x / 60 ** k for k, x in enumerate(xs))
            return conv(lat) * (1 if ns == "N" else -1), conv(lon) * (1 if parts[i] == "E" else -1)
        except (ValueError, IndexError):
            continue
    return None, None


def fetch_articles(titles: list[str]) -> dict:
    """title -> dict(canonical, lat, lon, wikidata, capacity, revid) for every title (redirects resolved)."""
    c = HttpClient("wikipedia", 1.0)
    out, redir = {}, {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        url = (f"{API}?action=query&format=json&formatversion=2&redirects=1&prop=coordinates%7Cpageprops%7Crevisions"
               f"&rvprop=content%7Cids&rvslots=main&colimit=max&coprimary=primary&ppprop=wikibase_item%7Cdisambiguation&titles={quote('|'.join(chunk))}")
        q = json.loads(c.get(url).content)["query"]
        norm_ = {x["from"]: x["to"] for x in q.get("normalized", [])}
        redir.update({x["from"]: x["to"] for x in q.get("redirects", [])})
        for p in q["pages"]:
            co = (p.get("coordinates") or [{}])[0]
            rev = (p.get("revisions") or [{}])[0]
            text = ((rev.get("slots") or {}).get("main") or {}).get("content") or ""
            lat, lon = co.get("lat"), co.get("lon")
            if lat is None:
                lat, lon = _coord_from_text(text)
            out[p["title"]] = dict(canonical=p["title"], missing=bool(p.get("missing")), lat=lat, lon=lon,
                                   disambiguation="disambiguation" in (p.get("pageprops") or {}),
                                   wikidata=(p.get("pageprops") or {}).get("wikibase_item"), capacity=_capacity(text),
                                   revid=rev.get("revid"))
        for t in chunk:
            n = norm_.get(t, t)
            n = redir.get(n, n)
            out.setdefault(t, out.get(n))
            out[t] = out.get(n, out.get(t))
    return out


def build():
    m = pd.read_parquet(PROC / "matches.parquet")
    if "venue_wikipedia_title" not in m.columns:
        raise RuntimeError("run wikipedia_matches.enrich_and_goals first (it records the stadium hyperlink per match)")
    titles = sorted(m.venue_wikipedia_title.dropna().unique())
    # Fixtures without a match box (scheduled, e.g. Euro 2028) only name a CITY in the fixture list.  The tournament page's own
    # host-venue map lists city -> stadium link; a fixture takes the stadium of its city (for "London (Tottenham)" the London
    # stadium whose name contains "Tottenham").  Ambiguous or missing cities stay without a venue.
    m.loc[m.match_status != "completed", "venue_wikipedia_title"] = None      # scheduled fixtures are always recomputed from the host-venue map
    m["venue_link_rule"] = m.venue_wikipedia_title.map(lambda t: "match_box_hyperlink" if isinstance(t, str) else None)
    hostmap = {}
    from .wikipedia_matches import cached_wikitext
    for title, _, text, _ in cached_wikitext():
        if re.fullmatch(r"UEFA Euro \d{4}|\d{4} FIFA World Cup|\d{4} Copa Am\u00e9rica", title):
            for n, city in re.findall(r"label(\d+)\s*=\s*\'*\[\[([^\]|]+)", text):
                d = re.search(rf"mark-description{n}\s*=\s*\[\[([^\]|]+)", text)
                if d:
                    hostmap.setdefault((title, city.strip()), []).append(d.group(1).strip())
    for r in m[m.venue_wikipedia_title.isna() & m.venue_raw.notna() & (m.match_status != "completed")].itertuples():
        base = re.split(r"\(", r.venue_raw)[0].strip()
        hint = re.search(r"\(([^)]*)\)", r.venue_raw)
        cands = [st for (pg, city), sts in hostmap.items() if pg.endswith(r.season_id.split("-")[1]) and city.lower() == base.lower() for st in sts]
        if hint:
            cands = [c for c in cands if hint.group(1).lower() in c.lower()]      # "London (Tottenham)" needs a Tottenham stadium in the map
        if len(set(cands)) == 1:
            m.loc[m.match_id == r.match_id, "venue_wikipedia_title"] = cands[0]
            m.loc[m.match_id == r.match_id, "venue_city_raw"] = base
            m.loc[m.match_id == r.match_id, "venue_link_rule"] = "tournament_host_venue_map"
    titles = sorted(m.venue_wikipedia_title.dropna().unique())
    art = fetch_articles(titles)

    # country of every match from martj42 (date +-1 day, same two teams)
    res = load()[0]
    ctry = {}
    for r in res.itertuples():
        ctry[(r.date, frozenset((cn(r.home_team), cn(r.away_team))))] = (r.country, r.city)
    from datetime import timedelta
    def country_of(r):
        for dd in (0, -1, 1):
            k = (r.match_date + timedelta(days=dd), frozenset((cn(r.home_team_raw), cn(r.away_team_raw))))
            if k in ctry:
                return ctry[k]
        return (None, None)
    m["_canon"] = m.venue_wikipedia_title.map(lambda t: (art.get(t) or {}).get("canonical") if isinstance(t, str) else None)
    cc = m.apply(country_of, axis=1, result_type="expand")
    m["_country"], m["_city_m"] = cc[0], cc[1]

    rows = []
    for canon, g in m[m._canon.notna()].groupby("_canon"):
        a = next(v for v in art.values() if v and v["canonical"] == canon)
        names = Counter(g.venue_raw.dropna()) + Counter(g.venue_wikipedia_title.dropna())
        cities = Counter(g.venue_city_raw.dropna())
        countries = Counter(g._country.dropna())
        vid = f"V-{a['wikidata']}" if a["wikidata"] else f"V-{_slug(canon)}"
        rows.append(dict(venue_id=vid, venue_name=re.sub(r"\s*\([^)]*\)\s*$", "", canon), wikipedia_title=canon, wikidata_id=a["wikidata"],
                         city=cities.most_common(1)[0][0] if cities else (g._city_m.dropna().mode().iat[0] if g._city_m.notna().any() else None),
                         country=countries.most_common(1)[0][0] if countries else None,
                         country_values_seen=json.dumps(dict(countries), ensure_ascii=False),
                         latitude=a["lat"], longitude=a["lon"], capacity=a["capacity"],
                         name_variants=json.dumps(sorted(set(names) - {canon}), ensure_ascii=False),
                         n_matches=len(g), first_match=str(g.match_date.min()), last_match=str(g.match_date.max()),
                         source="en.wikipedia article (MediaWiki API); capacity from its infobox; country from martj42", revid=a["revid"]))
    v = pd.DataFrame(rows).sort_values(["country", "city", "venue_name"]).reset_index(drop=True)
    assert v.venue_id.is_unique, v[v.venue_id.duplicated(keep=False)]
    canon_to_id = dict(zip(v.wikipedia_title, v.venue_id))
    m["venue_id"] = m._canon.map(canon_to_id)
    name_of = dict(zip(v.venue_id, v.venue_name)); city_of = dict(zip(v.venue_id, v.city)); country_of_v = dict(zip(v.venue_id, v.country))
    m["venue_name"] = m.venue_id.map(name_of); m["venue_city"] = m.venue_id.map(city_of); m["venue_country"] = m.venue_id.map(country_of_v)
    m = m.drop(columns=["_canon", "_country", "_city_m"])
    m.to_parquet(PROC / "matches.parquet", index=False)
    m.to_csv(PROC / "matches.csv", index=False)
    v.to_parquet(PROC / "venues.parquet", index=False)
    v.to_csv(PROC / "venues.csv", index=False, encoding="utf-8-sig")

    # ---- checks
    q = []
    played = m[m.match_status == "completed"]
    q.append(dict(check="matches_without_venue_id", failing=int(m.venue_id.isna().sum()), detail=""))
    q.append(dict(check="venues_with_more_than_one_country", failing=int((v.country_values_seen.map(lambda s: len(json.loads(s))) > 1).sum()),
                  detail=";".join(v[v.country_values_seen.map(lambda s: len(json.loads(s))) > 1].venue_name.head(8))))
    x = played.merge(v[["venue_id", "capacity"]], on="venue_id")
    x = x[x.attendance.notna() & x.capacity.notna() & (x.attendance > x.capacity * 1.2)]
    q.append(dict(check="attendance_over_120pct_of_capacity", failing=len(x),
                  detail=";".join(f"{r.venue_name}:{int(r.attendance)}>{int(r.capacity)}" for r in x.merge(v[["venue_id", "venue_name"]], on="venue_id", suffixes=("_m", "")).head(6).itertuples())))
    q.append(dict(check="venues_without_coordinates", failing=int(v.latitude.isna().sum()), detail=""))
    q.append(dict(check="venues_without_capacity", failing=int(v.capacity.isna().sum()), detail=""))
    q.append(dict(check="venues_without_country", failing=int(v.country.isna().sum()), detail=""))
    (DATA / "quality").mkdir(exist_ok=True)
    pd.DataFrame(q).to_csv(DATA / "quality" / "venues_checks.csv", index=False)
    return v, m, pd.DataFrame(q)


if __name__ == "__main__":
    v, m, q = build()
    print(len(v), "venues |", int(m.venue_id.notna().sum()), "of", len(m), "matches linked")
    print(q.to_string(index=False))
    print(v[["venue_id", "venue_name", "city", "country", "capacity", "latitude", "n_matches"]].head(8).to_string(index=False))
