"""Wikipedia match boxes via the official MediaWiki API (secondary source, CC BY-SA 4.0).

Why Wikipedia: it is the only open source covering the seasons the other sources lack (Copa 2004-2019,
Champions League 2002-11, Nations League) and it adds referee/attendance/goals elsewhere.
Rules: API only (no HTML scraping), identified client, serial requests with delay, raw wikitext cached
with its revision id, every record keeps page title + revision id + oldid URL. Wikipedia is treated as a
SECONDARY source: wherever another source already holds the match, scores are cross-checked and conflicts
reported, never silently overwritten.
Licence: text CC BY-SA 4.0 - https://creativecommons.org/licenses/by-sa/4.0/ ; attribution = page title + revision URL
stored in every row.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

import mwparserfromhell as mw
import pandas as pd

from ..config import DATA
from ..http import HttpClient

API = "https://en.wikipedia.org/w/api.php"
GROUPS = "ABCDEFGHIJKL"
STAGING = DATA / "processed" / "wikipedia"


def client():
    return HttpClient("wikipedia", 1.0)


def candidate_titles(cid: str, sid: str) -> list[str]:
    y = sid.split("-")[1]
    out = []
    if cid == "WC":
        out += [f"{y} FIFA World Cup Group {g}" for g in GROUPS[: 12 if y == "2026" else 8]]
        out += [f"{y} FIFA World Cup knockout stage", f"{y} FIFA World Cup", f"{y} FIFA World Cup final",
                f"{y} FIFA World Cup round of 32", f"{y} FIFA World Cup squads"]
    elif cid == "EURO":
        out += [f"UEFA Euro {y} Group {g}" for g in GROUPS[:6]]
        out += [f"UEFA Euro {y} knockout phase", f"UEFA Euro {y} knockout stage", f"UEFA Euro {y}", f"UEFA Euro {y} final",
                f"UEFA Euro {y} squads"]
    elif cid == "COPA":
        out += [f"{y} Copa América", f"{y} Copa América knockout stage", f"{y} Copa América final"]
        out += [f"{y} Copa América Group {g}" for g in "ABCD"]
        out += ["Copa América Centenario", "Copa América Centenario knockout stage", "Copa América Centenario final", "Copa América Centenario squads"] if y == "2016" else [f"{y} Copa América squads"]
        out += [f"Copa América Centenario Group {g}" for g in "ABCD"] if y == "2016" else []
    elif cid == "UCL":
        a, b = y, sid.split("-")[2]
        s = f"{a}–{b}"
        out += [f"{s} UEFA Champions League group stage", f"{s} UEFA Champions League league phase",
                f"{s} UEFA Champions League knockout phase", f"{s} UEFA Champions League knockout stage",
                f"{s} UEFA Champions League second group stage", f"{s} UEFA Champions League", f"{s} UEFA Champions League final",
                f"{s} UEFA Champions League knockout phase play-offs", f"{int(a) + 1} UEFA Champions League final"]
    elif cid == "UNL":
        a, b = y, sid.split("-")[2]
        s = f"{a}–{b}"
        fy = int(a) + 1
        out += [f"{s} UEFA Nations League {x}" for x in "ABCD"]
        out += [f"{fy} UEFA Nations League Finals", f"{s} UEFA Nations League"]
        out += [f"{s} UEFA Nations League play-offs"]
    return out


def existing_titles(c: HttpClient, titles: list[str]) -> dict[str, str]:
    """title -> canonical title (after redirect) for titles that exist."""
    found = {}
    for i in range(0, len(titles), 40):
        chunk = titles[i:i + 40]
        r = c.get(f"{API}?action=query&format=json&formatversion=2&redirects=1&titles={quote('|'.join(chunk))}")
        d = json.loads(r.content)["query"]
        redir = {x["from"]: x["to"] for x in d.get("redirects", [])}
        norm_ = {x["from"]: x["to"] for x in d.get("normalized", [])}
        ok = {p["title"] for p in d["pages"] if not p.get("missing")}
        for t in chunk:
            n = norm_.get(t, t)
            n = redir.get(n, n)
            if n in ok:
                found[t] = n
    return found


def fetch(c: HttpClient, title: str):
    r = c.get(f"{API}?action=parse&format=json&formatversion=2&redirects=1&prop=wikitext%7Crevid&page={quote(title)}")
    j = json.loads(r.content)
    if "parse" not in j:  # e.g. page is a redirect to a section / API error: log and skip, never crash the run
        import logging
        logging.getLogger("fbplatform.wikipedia").warning("skipping %s: %s", title, j.get("error", {}).get("code", "no parse payload"))
        return None
    d = j["parse"]
    return d["wikitext"], d["revid"], d["title"]


def _norm_name(t):
    return re.sub(r"[\s_]+", "", str(t.name).strip().lower())


def boxes(wikitext: str):
    code = mw.parse(wikitext)
    out = []
    for t in code.filter_templates():
        if _norm_name(t).startswith(("footballbox", "#invoke:footballbox")):
            out.append({str(p.name).strip(): str(p.value).strip() for p in t.params})
    return out


def lst_titles(wikitext: str) -> list[str]:
    return sorted({m.group(1).strip() for m in re.finditer(r"\{\{#lst:\s*([^|}]+)", wikitext)})


def run(seasons=None, max_depth=1):
    import sys
    from ..registry import build_registry
    reg = build_registry()
    c = client()
    rows, pages_log = [], []
    for r in reg.itertuples():
        if seasons and r.season_id not in seasons:
            continue
        cand = candidate_titles(r.competition_id, r.season_id)
        ex = existing_titles(c, cand)
        queue = [(t, 0) for t in sorted(set(ex.values()))]
        seen = set()
        while queue:
            title, depth = queue.pop(0)
            if title in seen:
                continue
            seen.add(title)
            got = fetch(c, title)
            if got is None:
                pages_log.append(dict(season_id=r.season_id, page=title, revid=None, boxes=0))
                continue
            text, rev, canon = got
            bs = boxes(text)
            pages_log.append(dict(season_id=r.season_id, page=canon, revid=rev, boxes=len(bs)))
            for i, b in enumerate(bs):
                rows.append(dict(season_id=r.season_id, page=canon, revid=rev, box_index=i,
                                 source_url=f"https://en.wikipedia.org/w/index.php?title={quote(canon.replace(' ', '_'))}&oldid={rev}",
                                 raw=json.dumps(b, ensure_ascii=False)))
            if depth < max_depth:
                for t in lst_titles(text):
                    queue.append((t, depth + 1))
        print(r.season_id, sum(1 for p in pages_log if p["season_id"] == r.season_id), "pages", file=sys.stderr)
    df = pd.DataFrame(rows)
    if not seasons:  # a partial run must not overwrite the full snapshot
        STAGING.mkdir(parents=True, exist_ok=True)
        df.to_parquet(STAGING / "boxes_raw.parquet", index=False)
        pd.DataFrame(pages_log).to_csv(STAGING / "pages.csv", index=False)
    return df, pd.DataFrame(pages_log)


if __name__ == "__main__":
    import sys
    df, pg = run(set(sys.argv[1:]) or None)
    print(pg.groupby("season_id").boxes.sum().to_string())
